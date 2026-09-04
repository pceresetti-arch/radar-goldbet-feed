#!/usr/bin/env python3
import json, pathlib, re, unicodedata
from collections import defaultdict
from datetime import datetime, timezone

ROOT=pathlib.Path('feed')
NOW=datetime.now(timezone.utc)

PRIMARY_SOURCE_MARKERS={
    'OFFICIAL_CLUB','CLUB_OFFICIAL','OFFICIAL_LEAGUE','LEAGUE_OFFICIAL',
    'OFFICIAL_FEDERATION','FEDERATION_OFFICIAL'
}


def load(name, default):
    p=ROOT/name
    try:
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:
        return default


def dt(s):
    if not s:return None
    try:return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None


def age_minutes(s):
    d=dt(s)
    return None if not d else round((NOW-d).total_seconds()/60,1)


def norm(s):
    s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().lower()
    s=re.sub(r'\b(fc|cf|sc|ac|afc|cd|fk|bk|calcio|club|deportivo|sporting|united|city|pr|sp|rj|mg)\b',' ',s)
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def by_id_and_name(rows):
    by_id={}; by_name={}
    for x in rows or []:
        if not isinstance(x,dict):continue
        if x.get('match_market_id') not in (None,''):
            by_id[str(x.get('match_market_id'))]=x
        n=norm(x.get('match'))
        if n:by_name[n]=x
    return by_id,by_name


def find_link(m, by_id, by_name):
    mmid=str(m.get('match_market_id') or '')
    return by_id.get(mmid) or by_name.get(norm(m.get('match'))) or {}


def upper(v):
    return str(v or '').strip().upper()


def xi_source_confidence(match):
    """Never promote a single provider to OFFICIAL without explicit primary metadata."""
    status=upper(match.get('status') or match.get('confirmation_status'))
    source_class=upper(match.get('source_class') or match.get('source_type'))
    source_meta=match.get('source_meta') if isinstance(match.get('source_meta'),dict) else {}
    explicit_primary=(
        source_class in PRIMARY_SOURCE_MARKERS or
        bool(match.get('official_primary_source')) or
        upper(source_meta.get('class')) in PRIMARY_SOURCE_MARKERS or
        bool(source_meta.get('official_primary_source'))
    )
    if status=='CROSS_CONFIRMED':
        return 'CERTIFIED_CROSSCHECK'
    if status=='SOURCE_CONFIRMED' and explicit_primary:
        return 'CERTIFIED_PRIMARY'
    if status=='SOURCE_CONFIRMED':
        return 'PROVIDER_ONLY'
    if status in {'PREDICTED','PROBABLE'}:
        return 'PREDICTED'
    return 'MISSING'


def market_completeness(current_standard_ready, player_discovery_ready):
    if not current_standard_ready:
        return 'MISSING'
    if player_discovery_ready:
        return 'COMPLETE'
    return 'PARTIAL'


def movement_certification(current_standard_ready, fixture_record):
    """Only explicit BetFlag metadata may upgrade CURRENT_ONLY to an OPEN certificate."""
    if not current_standard_ready:
        return 'MISSING'
    explicit=upper(
        fixture_record.get('movement_certification') or
        fixture_record.get('movement_status')
    )
    allowed={
        'TRUE_OPEN_CURRENT_T30','TRUE_OPEN_CURRENT',
        'OPEN_RADAR_CURRENT_T30','OPEN_RADAR_CURRENT',
        'FIRST_SEEN_CURRENT','CURRENT_ONLY'
    }
    return explicit if explicit in allowed else 'CURRENT_ONLY'


def mark(ok, label, detail=''):
    suffix=f' {detail}' if detail else ''
    return f'{label} {"OK" if ok else "WARN"}{suffix}'


lineups=load('lineups-current.json',{'matches':[]})
tactical=load('lineups-tactical-current.json',{'matches':[]})
context=load('player-matchup-context-current.json',{'matches':[]})
betflag=load('betflag-fixtures-index.json',{'fixtures':[]})

TAC_ID,TAC_NAME=by_id_and_name(tactical.get('matches'))
CTX_ID,CTX_NAME=by_id_and_name(context.get('matches'))
BF_ID,BF_NAME=by_id_and_name(betflag.get('fixtures'))

lineup_age=age_minutes(lineups.get('generated_at'))
tactical_age=age_minutes(tactical.get('generated_at'))
context_age=age_minutes(context.get('generated_at'))
betflag_age=age_minutes(betflag.get('generated_at'))
standard_source_age=age_minutes(betflag.get('standard_source_generated_at'))
player_source_age=age_minutes(betflag.get('player_source_generated_at'))

lineup_feed_fresh=lineup_age is not None and lineup_age<=15
tactical_feed_fresh=tactical_age is not None and tactical_age<=20
context_feed_fresh=context_age is not None and context_age<=30
betflag_feed_fresh=bool(betflag.get('source_healthy')) and betflag_age is not None and betflag_age<=12
betflag_standard_fresh=betflag_feed_fresh and standard_source_age is not None and standard_source_age<=12
betflag_player_fresh=betflag_feed_fresh and player_source_age is not None and player_source_age<=12

lineup_generated=dt(lineups.get('generated_at'))
tactical_source_lineup=dt(tactical.get('source_lineup_generated_at'))
tactical_synced=bool(lineup_generated and tactical_source_lineup and tactical_source_lineup>=lineup_generated)

out=[]
for m in lineups.get('matches') or []:
    line=m.get('lineup') or {}
    t=find_link(m,TAC_ID,TAC_NAME)
    c=find_link(m,CTX_ID,CTX_NAME)
    bf=find_link(m,BF_ID,BF_NAME)

    xi_confidence=xi_source_confidence(m)
    xi_certified=xi_confidence in {'CERTIFIED_PRIMARY','CERTIFIED_CROSSCHECK'}
    standard_lineup=(
        bool(line.get('confirmed')) and
        str(line.get('lineup_type') or '').lower()=='standard' and
        not bool(line.get('historical_reference'))
    )
    lineup_ready=xi_certified and standard_lineup and lineup_feed_fresh

    tactical_status=t.get('positioning_status')
    tactical_available=tactical_status in ('PROVIDER_TACTICAL_CONFIRMED','PROVIDER_TACTICAL_AVAILABLE')
    tactical_ready=tactical_available and tactical_feed_fresh and tactical_synced

    standard_count=int(bf.get('standard_count') or 0)
    player_count=int(bf.get('player_count') or 0)
    player_quote_count=int(bf.get('player_quote_count') or 0)
    fixture_file=bf.get('file')
    betflag_fixture_mapped=bool(bf)
    current_standard_ready=betflag_fixture_mapped and betflag_standard_fresh and standard_count>0
    player_discovery_ready=betflag_fixture_mapped and betflag_player_fresh and player_count>0 and player_quote_count>0
    market_status=market_completeness(current_standard_ready,player_discovery_ready)
    movement_status=movement_certification(current_standard_ready,bf)
    movement_claims_allowed=movement_status in {
        'TRUE_OPEN_CURRENT_T30','TRUE_OPEN_CURRENT','OPEN_RADAR_CURRENT_T30','OPEN_RADAR_CURRENT'
    }
    price_only_decision_allowed=movement_status in {'CURRENT_ONLY','FIRST_SEEN_CURRENT'} and current_standard_ready

    current_fp=line.get('xi_fingerprint')
    context_fp=c.get('xi_fingerprint')
    context_available=c.get('context_status')=='AVAILABLE'
    context_matches_current_xi=bool(current_fp and context_fp and current_fp==context_fp)
    player_context_ready=context_available and context_feed_fresh and context_matches_current_xi

    xi_changed=bool(m.get('xi_changed_after_confirmation'))
    post_xi_delta_ready=(not xi_changed) or (tactical_ready and player_context_ready)

    # FULL readiness is intentionally strict: a single-provider XI cannot be called official.
    standard_ready=lineup_ready and tactical_ready and current_standard_ready and post_xi_delta_ready
    player_lane_ready=standard_ready and player_discovery_ready and player_context_ready
    player_market_bet_ready=player_lane_ready

    reasons=[]; warnings=[]
    if xi_confidence=='MISSING':
        reasons.append('WAIT_XI')
    elif xi_confidence=='PREDICTED':
        reasons.append('WAIT_CERTIFIED_XI')
    elif xi_confidence=='PROVIDER_ONLY':
        reasons.append('WAIT_PRIMARY_OR_CROSSCHECK_XI')
        warnings.append('XI_PROVIDER_ONLY_NOT_OFFICIAL')
    elif not standard_lineup:
        reasons.append('WAIT_STANDARD_11V11_XI')
    elif not lineup_feed_fresh:
        reasons.append('STALE_LINEUP_FEED')

    if xi_certified and not tactical_available:
        reasons.append('WAIT_TACTICAL')
    elif tactical_available and not tactical_feed_fresh:
        reasons.append('STALE_TACTICAL_FEED')
    elif tactical_available and not tactical_synced:
        reasons.append('WAIT_TACTICAL_SYNC_TO_CURRENT_XI')

    if not betflag_fixture_mapped:
        reasons.append('WAIT_BETFLAG_FIXTURE_MAPPING')
    elif not betflag_standard_fresh:
        reasons.append('STALE_BETFLAG_STANDARD_CURRENT')
    elif standard_count<=0:
        reasons.append('BETFLAG_STANDARD_MARKETS_EMPTY')

    if not player_discovery_ready:
        if not betflag_fixture_mapped:warnings.append('PLAYER_PROPS_ACQUISITION_WAIT_FIXTURE_MAPPING')
        elif not betflag_player_fresh:warnings.append('PLAYER_PROPS_BETFLAG_STALE')
        elif player_count<=0 or player_quote_count<=0:warnings.append('PLAYER_PROPS_NOT_QUOTED_OR_NOT_AVAILABLE_ON_BETFLAG')
    if player_discovery_ready and not player_context_ready:
        warnings.append('PLAYER_MARKETS_WAIT_MINUTES_POSITION_CONCESSION_CONTEXT')
    if xi_changed:
        warnings.append('XI_CHANGED_AFTER_FIRST_CONFIRMATION')
        if not post_xi_delta_ready:reasons.append('WAIT_POST_XI_DELTA_RECOMPUTE')

    if movement_status=='CURRENT_ONLY':
        warnings.append('MOVEMENT_CURRENT_ONLY_NO_OPEN_CLAIM')
    elif movement_status=='FIRST_SEEN_CURRENT':
        warnings.append('MOVEMENT_FIRST_SEEN_DIAGNOSTIC_ONLY')
    elif movement_status=='MISSING':
        warnings.append('MOVEMENT_AUDIT_MISSING')

    if market_status=='PARTIAL':
        warnings.append('BETFLAG_MARKET_MATRIX_PARTIAL')

    if standard_ready:
        state='READY_DEEP_ANALYSIS'
        reasons=[]
        if player_lane_ready:
            analysis_scope='FULL_WITH_PLAYER_CONTEXT_EXACT_BETFLAG_PRICE_REQUIRED'
        elif player_discovery_ready:
            analysis_scope='STANDARD_READY_PLAYER_CONTEXT_PENDING'
        else:
            analysis_scope='STANDARD_READY_PLAYER_PROPS_UNAVAILABLE_OR_PENDING'
    else:
        state=reasons[0] if reasons else 'WAIT_DATA'
        analysis_scope='NOT_READY'

    analysis_total_ready=bool(standard_ready)
    price_only_mode=bool(analysis_total_ready and price_only_decision_allowed and not movement_claims_allowed)
    decision_mode=('BET_PRICE_ONLY_ELIGIBLE' if price_only_mode else ('FULL_ELIGIBLE' if analysis_total_ready else 'ATTESA_DATA_GAP'))

    readiness_strip=' | '.join([
        f'Fixture {"OK" if betflag_fixture_mapped else "BLOCK"}',
        f'XI {"OK" if lineup_ready else "BLOCK"} {xi_confidence}',
        f'BetFlag CURRENT {"OK" if current_standard_ready else "BLOCK"}',
        f'Props {"OK" if player_discovery_ready else "WARN"} {market_status}',
        f'Movement {"OK" if movement_claims_allowed else "WARN"} {movement_status}',
        f'Tactical {"OK" if tactical_ready else "BLOCK"}',
        f'Player context {"OK" if player_context_ready else "WARN"}',
        '1H model REQUIRED_AT_ANALYSIS',
        'Price gate REQUIRED_AT_FINAL_GATE'
    ])

    out.append({
        'match_market_id':str(m.get('match_market_id') or ''),
        'match_event_id':m.get('match_event_id'),
        'match':m.get('match'),'league':m.get('league'),'start_time':m.get('start_time'),'start_utc':m.get('start_utc'),'minutes_to_start':m.get('minutes_to_start'),
        'readiness':state,'analysis_scope':analysis_scope,'analysis_total_ready':analysis_total_ready,'decision_mode':decision_mode,'blocking_reasons':reasons,'warnings':warnings,'readiness_strip':readiness_strip,
        'lineup_status':m.get('status'),'lineup_type':line.get('lineup_type'),'xi_source_confidence':xi_confidence,'official_standard_xi':xi_certified and standard_lineup,'lineup_ready':lineup_ready,'xi_fingerprint':current_fp,'xi_changed_after_confirmation':xi_changed,'post_xi_delta_ready':post_xi_delta_ready,
        'tactical_status':tactical_status,'tactical_confidence':t.get('positioning_confidence'),'tactical_feed_fresh':tactical_feed_fresh,'tactical_synced_to_current_lineup':tactical_synced,'tactical_ready':tactical_ready,
        'betflag_source_class':'BETFLAG_AAMS_DIRECT','betflag_fixture_mapped':betflag_fixture_mapped,'betflag_fixture_file':fixture_file,
        'betflag_standard_count':standard_count,'betflag_standard_current_fresh':betflag_standard_fresh,'betflag_standard_ready':current_standard_ready,'betflag_market_completeness':market_status,
        'player_count':player_count,'player_quote_count':player_quote_count,'player_props_available':player_count>0 and player_quote_count>0,'player_props_ready':player_discovery_ready,
        'player_context_available':context_available,'player_context_fresh':context_feed_fresh,'player_context_matches_current_xi':context_matches_current_xi,'player_market_bet_ready':player_market_bet_ready,'player_lane_ready':player_lane_ready,
        'player_price_source_class':'BETFLAG_AAMS_DIRECT','player_exact_price_endpoint':'https://radar-betflag-v7.p-ceresetti.workers.dev/live/player-price','player_exact_price_required_at_decision_time':True,
        'movement_certification':movement_status,'movement_based_claims_allowed':movement_claims_allowed,'price_only_decision_allowed':price_only_decision_allowed,
        'true_open_status':('BETFLAG OPEN CERTIFIED' if movement_claims_allowed else 'TRUE OPEN BETFLAG NON CERTIFICATA / MOVIMENTO INCOMPLETO'),
        'true_open_blocks_current_analysis':False,
        'model_1h_required_at_analysis':True,'price_gate_required_at_final_gate':True,
        'strong_drop_count':0,'strong_drops':[]
    })

out.sort(key=lambda x:(x.get('minutes_to_start') is None,x.get('minutes_to_start') or 9999))
counts=defaultdict(int)
for x in out:counts[x['readiness']]+=1
ready=[x for x in out if x['readiness']=='READY_DEEP_ANALYSIS']
player_ready=[x for x in out if x.get('player_lane_ready')]

payload={
    'generated_at':NOW.isoformat(),
    'contract':'RADAR_FULL_ANALYSIS_GATE_V2: FULL requires certified primary/crosschecked XI, synchronized tactical layer, fresh exact CURRENT BetFlag/AAMS standard prices, explicit market/movement status, and POST-XI delta when required. Single-provider SOURCE_CONFIRMED is PROVIDER_ONLY and cannot be called official. Missing TRUE OPEN never permits a movement claim; CURRENT_ONLY may support PRICE-ONLY value analysis with exact FINAL GATE price.',
    'contract_file':'RADAR_FULL_ANALYSIS_GATE_V2.md',
    'operational_bookmaker':'BETFLAG_ONLY',
    'input_freshness_minutes':{
        'lineups':lineup_age,'tactical':tactical_age,'betflag_fixture_feed':betflag_age,
        'betflag_standard_source':standard_source_age,'betflag_player_source':player_source_age,'player_context':context_age
    },
    'freshness_limits_minutes':{
        'lineups':15,'tactical':20,'betflag_fixture_feed':12,'betflag_standard_current':12,'betflag_player_discovery':12,'player_context':30,'betflag_exact_price_seconds':45
    },
    'betflag_feed_path':{
        'runtime_branch':'betflag-live','live_status':'feed/betflag-live-status.json','live_index':'feed/betflag-residential-fixtures-index.json',
        'builder_index':'feed/betflag-fixtures-index.json','fixture_dir':'feed/betflag-fixtures','source_class':'BETFLAG_AAMS_DIRECT','worker':'https://radar-betflag-v7.p-ceresetti.workers.dev'
    },
    'player_price_path':{
        'source_class':'BETFLAG_AAMS_DIRECT','certified_class':'BETFLAG_AAMS_DIRECT_CERTIFIED','worker':'https://radar-betflag-v7.p-ceresetti.workers.dev','endpoint':'/live/player-price','exact_proof_required_at_decision_time':True
    },
    'xi_policy':'SOURCE_CONFIRMED from one provider => PROVIDER_ONLY unless explicit official-primary metadata; CROSS_CONFIRMED => CERTIFIED_CROSSCHECK.',
    'movement_policy':'Only explicit BetFlag evidence can be TRUE_OPEN/OPEN_RADAR. FIRST_SEEN is diagnostic. CURRENT_ONLY permits no movement claim and cross-book movement never substitutes BetFlag.',
    'mandatory_output_status':['XI_SOURCE_CONFIDENCE','BETFLAG_MARKET_COMPLETENESS','MOVEMENT_CERTIFICATION','readiness_strip'],
    'match_count':len(out),'readiness_counts':dict(counts),'ready_count':len(ready),'ready_matches':ready,
    'player_lane_ready_count':len(player_ready),'player_lane_ready_matches':player_ready,'matches':out
}

ROOT.mkdir(exist_ok=True)
(ROOT/'deep-analysis-readiness.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
summary={k:v for k,v in payload.items() if k!='matches'}
summary['ready_matches']=[{k:m.get(k) for k in ('match_market_id','match','league','start_time','minutes_to_start','readiness','analysis_scope','decision_mode','xi_source_confidence','betflag_standard_count','betflag_market_completeness','movement_certification','player_count','player_quote_count','player_lane_ready','readiness_strip')} for m in ready]
summary['player_lane_ready_matches']=[{k:m.get(k) for k in ('match_market_id','match','league','start_time','minutes_to_start','player_lane_ready','player_market_bet_ready','player_count','player_quote_count','player_price_source_class','player_exact_price_required_at_decision_time','xi_source_confidence','movement_certification')} for m in player_ready]
(ROOT/'deep-analysis-readiness-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
