#!/usr/bin/env python3
import json, pathlib, re, unicodedata
from collections import defaultdict
from datetime import datetime, timezone

ROOT=pathlib.Path('feed')
NOW=datetime.now(timezone.utc)


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

    official_standard=(
        m.get('status') in ('SOURCE_CONFIRMED','CROSS_CONFIRMED') and
        bool(line.get('confirmed')) and
        str(line.get('lineup_type') or '').lower()=='standard' and
        not bool(line.get('historical_reference'))
    )
    lineup_ready=official_standard and lineup_feed_fresh

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

    current_fp=line.get('xi_fingerprint')
    context_fp=c.get('xi_fingerprint')
    context_available=c.get('context_status')=='AVAILABLE'
    context_matches_current_xi=bool(current_fp and context_fp and current_fp==context_fp)
    player_context_ready=context_available and context_feed_fresh and context_matches_current_xi

    # Current price discovery and analytical readiness are BetFlag-only.
    # An exact player quote is still certified on demand at FINAL GATE.
    standard_ready=lineup_ready and tactical_ready and current_standard_ready
    player_lane_ready=standard_ready and player_discovery_ready and player_context_ready
    player_market_bet_ready=player_lane_ready

    # TRUE OPEN is intentionally non-blocking. If not independently certified,
    # the Radar must state movement is incomplete instead of inventing an open.
    true_open_status='TRUE OPEN BETFLAG NON CERTIFICATA — MOVIMENTO INCOMPLETO'

    reasons=[]; warnings=[]
    if not official_standard:reasons.append('WAIT_OFFICIAL_STANDARD_XI')
    elif not lineup_feed_fresh:reasons.append('STALE_LINEUP_FEED')
    if official_standard and not tactical_available:reasons.append('WAIT_TACTICAL')
    elif tactical_available and not tactical_feed_fresh:reasons.append('STALE_TACTICAL_FEED')
    elif tactical_available and not tactical_synced:reasons.append('WAIT_TACTICAL_SYNC_TO_CURRENT_XI')
    if not betflag_fixture_mapped:reasons.append('WAIT_BETFLAG_FIXTURE_MAPPING')
    elif not betflag_standard_fresh:reasons.append('STALE_BETFLAG_STANDARD_CURRENT')
    elif standard_count<=0:reasons.append('BETFLAG_STANDARD_MARKETS_EMPTY')

    if not player_discovery_ready:
        if not betflag_fixture_mapped:warnings.append('PLAYER_PROPS_ACQUISITION_WAIT_FIXTURE_MAPPING')
        elif not betflag_player_fresh:warnings.append('PLAYER_PROPS_BETFLAG_STALE')
        elif player_count<=0 or player_quote_count<=0:warnings.append('PLAYER_PROPS_NOT_QUOTED_OR_NOT_AVAILABLE_ON_BETFLAG')
    if player_discovery_ready and not player_context_ready:
        warnings.append('PLAYER_MARKETS_WAIT_MINUTES_POSITION_CONCESSION_CONTEXT')
    if m.get('xi_changed_after_confirmation'):
        warnings.append('XI_CHANGED_AFTER_FIRST_CONFIRMATION')
    warnings.append(true_open_status)

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

    out.append({
        'match_market_id':str(m.get('match_market_id') or ''),
        'match_event_id':m.get('match_event_id'),
        'match':m.get('match'),'league':m.get('league'),'start_time':m.get('start_time'),'start_utc':m.get('start_utc'),'minutes_to_start':m.get('minutes_to_start'),
        'readiness':state,'analysis_scope':analysis_scope,'blocking_reasons':reasons,'warnings':warnings,
        'lineup_status':m.get('status'),'lineup_type':line.get('lineup_type'),'official_standard_xi':official_standard,'lineup_ready':lineup_ready,'xi_fingerprint':current_fp,'xi_changed_after_confirmation':bool(m.get('xi_changed_after_confirmation')),
        'tactical_status':tactical_status,'tactical_confidence':t.get('positioning_confidence'),'tactical_feed_fresh':tactical_feed_fresh,'tactical_synced_to_current_lineup':tactical_synced,'tactical_ready':tactical_ready,
        'betflag_source_class':'BETFLAG_AAMS_DIRECT','betflag_fixture_mapped':betflag_fixture_mapped,'betflag_fixture_file':fixture_file,
        'betflag_standard_count':standard_count,'betflag_standard_current_fresh':betflag_standard_fresh,'betflag_standard_ready':current_standard_ready,
        'player_count':player_count,'player_quote_count':player_quote_count,'player_props_available':player_count>0 and player_quote_count>0,'player_props_ready':player_discovery_ready,
        'player_context_available':context_available,'player_context_fresh':context_feed_fresh,'player_context_matches_current_xi':context_matches_current_xi,'player_market_bet_ready':player_market_bet_ready,'player_lane_ready':player_lane_ready,
        'player_price_source_class':'BETFLAG_AAMS_DIRECT','player_exact_price_endpoint':'https://radar-betflag-v7.p-ceresetti.workers.dev/live/player-price','player_exact_price_required_at_decision_time':True,
        'true_open_status':true_open_status,'true_open_blocks_current_analysis':False,
        'strong_drop_count':0,'strong_drops':[]
    })

out.sort(key=lambda x:(x.get('minutes_to_start') is None,x.get('minutes_to_start') or 9999))
counts=defaultdict(int)
for x in out:counts[x['readiness']]+=1
ready=[x for x in out if x['readiness']=='READY_DEEP_ANALYSIS']
player_ready=[x for x in out if x.get('player_lane_ready')]

payload={
    'generated_at':NOW.isoformat(),
    'contract':'READY requires fresh official XI + tactical layer synchronized to that XI + fresh CURRENT BetFlag/AAMS direct standard prices for the same fixture. TRUE OPEN is movement metadata and never blocks CURRENT analysis when unavailable. Player lane additionally requires fresh BetFlag player discovery and context matched to the current XI; a unique fresh exact BetFlag/AAMS price certificate is mandatory only at FINAL GATE decision time.',
    'operational_bookmaker':'BETFLAG_ONLY',
    'input_freshness_minutes':{
        'lineups':lineup_age,'tactical':tactical_age,'betflag_fixture_feed':betflag_age,
        'betflag_standard_source':standard_source_age,'betflag_player_source':player_source_age,'player_context':context_age
    },
    'freshness_limits_minutes':{
        'lineups':15,'tactical':20,'betflag_fixture_feed':12,'betflag_standard_current':12,'betflag_player_discovery':12,'player_context':30,'betflag_exact_price_seconds':45
    },
    'betflag_feed_path':{
        'index':'feed/betflag-fixtures-index.json','fixture_dir':'feed/betflag-fixtures','source_class':'BETFLAG_AAMS_DIRECT','worker':'https://radar-betflag-v7.p-ceresetti.workers.dev'
    },
    'player_price_path':{
        'source_class':'BETFLAG_AAMS_DIRECT','certified_class':'BETFLAG_AAMS_DIRECT_CERTIFIED','worker':'https://radar-betflag-v7.p-ceresetti.workers.dev','endpoint':'/live/player-price','exact_proof_required_at_decision_time':True
    },
    'true_open_policy':'TRUE OPEN BETFLAG NON CERTIFICATA — MOVIMENTO INCOMPLETO when no direct certified open exists; never substitute GoldBet/other books and never block CURRENT price analysis solely for missing open.',
    'match_count':len(out),'readiness_counts':dict(counts),'ready_count':len(ready),'ready_matches':ready,
    'player_lane_ready_count':len(player_ready),'player_lane_ready_matches':player_ready,'matches':out
}

ROOT.mkdir(exist_ok=True)
(ROOT/'deep-analysis-readiness.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
summary={k:v for k,v in payload.items() if k!='matches'}
summary['ready_matches']=[{k:m.get(k) for k in ('match_market_id','match','league','start_time','minutes_to_start','readiness','analysis_scope','betflag_standard_count','player_count','player_quote_count','player_lane_ready','true_open_status')} for m in ready]
summary['player_lane_ready_matches']=[{k:m.get(k) for k in ('match_market_id','match','league','start_time','minutes_to_start','player_lane_ready','player_market_bet_ready','player_count','player_quote_count','player_price_source_class','player_exact_price_required_at_decision_time')} for m in player_ready]
(ROOT/'deep-analysis-readiness-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
