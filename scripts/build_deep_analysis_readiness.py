#!/usr/bin/env python3
import json, pathlib, re, unicodedata
from collections import defaultdict
from datetime import datetime, timezone

ROOT=pathlib.Path('feed')
NOW=datetime.now(timezone.utc)


def load(name, default):
    p=ROOT/name
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:return default

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
def is_ft(rec):
    return str(rec.get('period') or '').lower() in ('','full_time','fulltime','match','ft')
def is_main_1x2(rec):
    return rec.get('source')=='GOLDBET_DIRECT_STANDARD' and is_ft(rec) and str(rec.get('market') or '').lower()=='1x2'
def is_main_over(rec):
    if rec.get('source')!='GOLDBET_DIRECT_STANDARD' or not is_ft(rec):return False
    m=str(rec.get('market') or '').lower(); scope=str(rec.get('scope') or '').lower(); sel=str(rec.get('selection') or '').upper()
    if sel!='OVER' or scope in ('home_team','away_team') or 'team' in m:return False
    return ('total' in m or 'over' in m or 'under' in m)
def current_drop(rec):
    try:
        if rec.get('true_open_status')!='TRUE_OPEN_CERTIFIED':return None
        return round(float(rec['true_open_price'])-float(rec['current_price']),3)
    except Exception:return None

lineups=load('lineups-current.json',{'matches':[]})
tactical=load('lineups-tactical-current.json',{'matches':[]})
movement=load('odds-movement-state.json',{'records':{}})
props=load('player-props-current.json',{'rows':[]})
context=load('player-matchup-context-current.json',{'matches':[]})
proxy_policy=load('shared-goldbet-proxy-policy.json',{})

TAC={str(m.get('match_market_id')):m for m in tactical.get('matches') or []}
CTX={str(m.get('match_market_id')):m for m in context.get('matches') or []}
PROP_BY_MM=defaultdict(list); PROP_BY_EID=defaultdict(list)
for r in props.get('rows') or []:
    if not isinstance(r,dict):continue
    if r.get('match_market_id') is not None:PROP_BY_MM[str(r.get('match_market_id'))].append(r)
    if r.get('match_event_id') is not None:PROP_BY_EID[str(r.get('match_event_id'))].append(r)
MOV=list((movement.get('records') or {}).values())
MOV_BY_EID=defaultdict(list); MOV_BY_NAME=defaultdict(list)
for r in MOV:
    if not isinstance(r,dict):continue
    if r.get('event_id') is not None:MOV_BY_EID[str(r.get('event_id'))].append(r)
    MOV_BY_NAME[norm(r.get('event'))].append(r)

props_age=age_minutes(props.get('generated_at')); movement_age=age_minutes(movement.get('generated_at'))
lineup_age=age_minutes(lineups.get('generated_at')); tactical_age=age_minutes(tactical.get('generated_at')); context_age=age_minutes(context.get('generated_at'))
proxy_policy_age=age_minutes(proxy_policy.get('generated_at'))
lineup_feed_fresh=lineup_age is not None and lineup_age<=15
tactical_feed_fresh=tactical_age is not None and tactical_age<=20
movement_feed_fresh=movement_age is not None and movement_age<=15
props_feed_fresh=props_age is not None and props_age<=20
context_feed_fresh=context_age is not None and context_age<=30
proxy_policy_fresh=proxy_policy_age is not None and proxy_policy_age<=float(proxy_policy.get('stale_after_minutes') or 45)
proxy_verdict=str(proxy_policy.get('verdict') or '')
proxy_player_gate_allowed=bool(proxy_policy.get('proxy_player_gate_allowed')) and proxy_verdict in ('STRONG_EXACT_MATCH','STRONG_NEAR_MATCH') and proxy_policy_fresh
lineup_generated=dt(lineups.get('generated_at')); tactical_source_lineup=dt(tactical.get('source_lineup_generated_at'))
tactical_synced=bool(lineup_generated and tactical_source_lineup and tactical_source_lineup>=lineup_generated)

out=[]
for m in lineups.get('matches') or []:
    mmid=str(m.get('match_market_id') or ''); eid=str(m.get('match_event_id') or '')
    line=m.get('lineup') or {}; t=TAC.get(mmid) or {}; c=CTX.get(mmid) or {}
    recs=MOV_BY_EID.get(eid) or MOV_BY_NAME.get(norm(m.get('match'))) or []
    pr=PROP_BY_MM.get(mmid) or PROP_BY_EID.get(eid) or []

    official_standard=(m.get('status') in ('SOURCE_CONFIRMED','CROSS_CONFIRMED') and bool(line.get('confirmed')) and str(line.get('lineup_type') or '').lower()=='standard' and not bool(line.get('historical_reference')))
    lineup_ready=official_standard and lineup_feed_fresh
    tactical_status=t.get('positioning_status')
    tactical_available=tactical_status in ('PROVIDER_TACTICAL_CONFIRMED','PROVIDER_TACTICAL_AVAILABLE')
    tactical_ready=tactical_available and tactical_feed_fresh and tactical_synced

    odds_1x2=[r for r in recs if is_main_1x2(r)]; odds_over=[r for r in recs if is_main_over(r)]
    odds_ready=len(odds_1x2)>=3 and len(odds_over)>=1 and movement_feed_fresh
    true_1x2=[r for r in odds_1x2 if r.get('true_open_status')=='TRUE_OPEN_CERTIFIED' and r.get('true_open_price') is not None]
    true_over=[r for r in odds_over if r.get('true_open_status')=='TRUE_OPEN_CERTIFIED' and r.get('true_open_price') is not None]
    true_open_ready=len(true_1x2)>=3 and len(true_over)>=1
    props_available=bool(pr); props_ready=props_available and props_feed_fresh

    current_fp=line.get('xi_fingerprint'); context_fp=c.get('xi_fingerprint')
    context_available=c.get('context_status')=='AVAILABLE'
    context_matches_current_xi=bool(current_fp and context_fp and current_fp==context_fp)
    player_context_ready=context_available and context_feed_fresh and context_matches_current_xi
    player_market_bet_ready=props_ready and player_context_ready
    player_proxy_price_ready=props_ready and proxy_player_gate_allowed
    player_operational_proxy_ready=player_market_bet_ready and player_proxy_price_ready
    standard_ready=lineup_ready and tactical_ready and odds_ready and true_open_ready

    reasons=[]; warnings=[]
    if not official_standard:reasons.append('WAIT_OFFICIAL_STANDARD_XI')
    elif not lineup_feed_fresh:reasons.append('STALE_LINEUP_FEED')
    if official_standard and not tactical_available:reasons.append('WAIT_TACTICAL')
    elif tactical_available and not tactical_feed_fresh:reasons.append('STALE_TACTICAL_FEED')
    elif tactical_available and not tactical_synced:reasons.append('WAIT_TACTICAL_SYNC_TO_CURRENT_XI')
    if not odds_ready:reasons.append('WAIT_GOLDBET_ODDS')
    if odds_ready and not true_open_ready:reasons.append('WAIT_TRUE_OPEN_1X2_OVER')
    if m.get('xi_changed_after_confirmation'):warnings.append('XI_CHANGED_AFTER_FIRST_CONFIRMATION')
    if not props_available:warnings.append('PLAYER_PROPS_NOT_OFFERED_OR_NOT_MAPPED')
    elif not props_feed_fresh:warnings.append('PLAYER_PROPS_STALE')
    if props_ready and not player_context_ready:warnings.append('PLAYER_MARKETS_WAIT_MINUTES_POSITION_CONCESSION_CONTEXT')
    if props_ready and not proxy_player_gate_allowed:warnings.append('PLAYER_PROXY_PRICE_NOT_CERTIFIED_OR_STALE')

    if standard_ready:
        state='READY_DEEP_ANALYSIS'; reasons=[]
        if player_operational_proxy_ready:analysis_scope='FULL_WITH_PLAYER_CONTEXT_AND_CERTIFIED_PROXY_PRICE_PATH'
        elif player_market_bet_ready:analysis_scope='FULL_WITH_PLAYER_CONTEXT_DIRECT_PRICE_OR_PROXY_PENDING'
        elif props_ready:analysis_scope='STANDARD_READY_PLAYER_PROPS_CONTEXT_PENDING'
        else:analysis_scope='STANDARD_COMPLETE_PLAYER_PROPS_OPTIONAL_MISSING'
    else:
        state=reasons[0] if reasons else 'WAIT_DATA'; analysis_scope='NOT_READY'

    drops=[]
    for r in odds_1x2+odds_over:
        d=current_drop(r)
        if d is not None and d>=0.20:
            drops.append({'market':r.get('market'),'line':r.get('line'),'selection':r.get('selection'),'true_open':r.get('true_open_price'),'current':r.get('current_price'),'drop':d,'T-40':(r.get('checkpoints') or {}).get('T-40'),'T-30':(r.get('checkpoints') or {}).get('T-30')})
    drops.sort(key=lambda x:x['drop'],reverse=True)

    out.append({
        'match_market_id':mmid,'match_event_id':m.get('match_event_id'),'match':m.get('match'),'league':m.get('league'),'start_time':m.get('start_time'),'start_utc':m.get('start_utc'),'minutes_to_start':m.get('minutes_to_start'),
        'readiness':state,'analysis_scope':analysis_scope,'blocking_reasons':reasons,'warnings':warnings,
        'lineup_status':m.get('status'),'lineup_type':line.get('lineup_type'),'official_standard_xi':official_standard,'lineup_ready':lineup_ready,'xi_fingerprint':current_fp,'xi_changed_after_confirmation':bool(m.get('xi_changed_after_confirmation')),
        'tactical_status':tactical_status,'tactical_confidence':t.get('positioning_confidence'),'tactical_feed_fresh':tactical_feed_fresh,'tactical_synced_to_current_lineup':tactical_synced,'tactical_ready':tactical_ready,
        'goldbet_1x2_selection_count':len(odds_1x2),'goldbet_over_selection_count':len(odds_over),'goldbet_odds_ready':odds_ready,'true_open_1x2_count':len(true_1x2),'true_open_over_count':len(true_over),'true_open_ready':true_open_ready,
        'player_prop_rows':len(pr),'player_props_available':props_available,'player_props_ready':props_ready,'player_context_available':context_available,'player_context_fresh':context_feed_fresh,'player_context_matches_current_xi':context_matches_current_xi,'player_market_bet_ready':player_market_bet_ready,
        'player_proxy_policy_verdict':proxy_verdict,'player_proxy_policy_age_minutes':proxy_policy_age,'player_proxy_price_ready':player_proxy_price_ready,'player_operational_proxy_ready':player_operational_proxy_ready,'player_proxy_gate_formula':proxy_policy.get('strong_proxy_gate_formula'),
        'strong_drop_count':len(drops),'strong_drops':drops[:20]
    })

out.sort(key=lambda x:(x.get('minutes_to_start') is None,x.get('minutes_to_start') or 9999))
counts=defaultdict(int)
for x in out:counts[x['readiness']]+=1
ready=[x for x in out if x['readiness']=='READY_DEEP_ANALYSIS']
payload={
    'generated_at':NOW.isoformat(),
    'contract':'READY standard requires fresh official FotMob standard XI + tactical layer synchronized to that XI + current GoldBet 1X2/Over + certified TRUE OPEN. Player BET additionally requires fresh player context matched to XI. If direct GoldBet player price is absent, a fresh strong GOLDBET_ALIGNED_PROXY policy may provide the operational price path subject to PROXY_GATE.',
    'input_freshness_minutes':{'lineups':lineup_age,'tactical':tactical_age,'odds_movement':movement_age,'player_props':props_age,'player_context':context_age,'shared_goldbet_proxy_policy':proxy_policy_age},
    'freshness_limits_minutes':{'lineups':15,'tactical':20,'odds_movement':15,'player_props':20,'player_context':30,'shared_goldbet_proxy_policy':float(proxy_policy.get('stale_after_minutes') or 45)},
    'proxy_policy':{'verdict':proxy_verdict,'fresh':proxy_policy_fresh,'proxy_player_gate_allowed':proxy_player_gate_allowed,'formula':proxy_policy.get('strong_proxy_gate_formula'),'source_class':proxy_policy.get('source_class')},
    'match_count':len(out),'readiness_counts':dict(counts),'ready_count':len(ready),'ready_matches':ready,'matches':out
}
ROOT.mkdir(exist_ok=True)
(ROOT/'deep-analysis-readiness.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
summary={k:v for k,v in payload.items() if k!='matches'}
summary['ready_matches']=[{k:m.get(k) for k in ('match_market_id','match','league','start_time','minutes_to_start','readiness','analysis_scope','player_market_bet_ready','player_proxy_price_ready','player_operational_proxy_ready','strong_drop_count')} for m in ready]
(ROOT/'deep-analysis-readiness-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
