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
    p=str(rec.get('period') or '').lower()
    return p in ('','full_time','fulltime','match','ft')

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

TAC={str(m.get('match_market_id')):m for m in tactical.get('matches') or []}
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

props_age=age_minutes(props.get('generated_at'))
movement_age=age_minutes(movement.get('generated_at'))
lineup_age=age_minutes(lineups.get('generated_at'))
tactical_age=age_minutes(tactical.get('generated_at'))

out=[]
for m in lineups.get('matches') or []:
    mmid=str(m.get('match_market_id') or '')
    eid=str(m.get('match_event_id') or '')
    t=TAC.get(mmid) or {}
    recs=MOV_BY_EID.get(eid) or MOV_BY_NAME.get(norm(m.get('match'))) or []
    pr=PROP_BY_MM.get(mmid) or PROP_BY_EID.get(eid) or []

    lineup_ready=m.get('status') in ('SOURCE_CONFIRMED','CROSS_CONFIRMED')
    tactical_status=t.get('positioning_status')
    tactical_ready=tactical_status in ('PROVIDER_TACTICAL_CONFIRMED','PROVIDER_TACTICAL_AVAILABLE')
    odds_1x2=[r for r in recs if is_main_1x2(r)]
    odds_over=[r for r in recs if is_main_over(r)]
    odds_ready=len(odds_1x2)>=3 and len(odds_over)>=1 and movement_age is not None and movement_age<=15
    true_1x2=[r for r in odds_1x2 if r.get('true_open_status')=='TRUE_OPEN_CERTIFIED' and r.get('true_open_price') is not None]
    true_over=[r for r in odds_over if r.get('true_open_status')=='TRUE_OPEN_CERTIFIED' and r.get('true_open_price') is not None]
    true_open_ready=len(true_1x2)>=3 and len(true_over)>=1
    props_ready=bool(pr) and props_age is not None and props_age<=20

    reasons=[]
    if not lineup_ready:reasons.append('WAIT_LINEUP')
    if lineup_ready and not tactical_ready:reasons.append('WAIT_TACTICAL')
    if not odds_ready:reasons.append('WAIT_GOLDBET_ODDS')
    if odds_ready and not true_open_ready:reasons.append('WAIT_TRUE_OPEN_1X2_OVER')
    if not props_ready:reasons.append('WAIT_PLAYER_PROPS')

    if not reasons:state='READY_DEEP_ANALYSIS'
    elif lineup_ready and tactical_ready and odds_ready and true_open_ready:state='READY_STANDARD_ONLY'
    else:state=reasons[0]

    drops=[]
    for r in odds_1x2+odds_over:
        d=current_drop(r)
        if d is not None and d>=0.20:
            drops.append({'market':r.get('market'),'line':r.get('line'),'selection':r.get('selection'),'true_open':r.get('true_open_price'),'current':r.get('current_price'),'drop':d,'T-40':(r.get('checkpoints') or {}).get('T-40'),'T-30':(r.get('checkpoints') or {}).get('T-30')})
    drops.sort(key=lambda x:x['drop'],reverse=True)

    out.append({
        'match_market_id':mmid,'match_event_id':m.get('match_event_id'),'match':m.get('match'),'league':m.get('league'),
        'start_time':m.get('start_time'),'start_utc':m.get('start_utc'),'minutes_to_start':m.get('minutes_to_start'),
        'readiness':state,'blocking_reasons':reasons,
        'lineup_status':m.get('status'),'lineup_ready':lineup_ready,
        'tactical_status':tactical_status,'tactical_confidence':t.get('positioning_confidence'),'tactical_ready':tactical_ready,
        'goldbet_1x2_selection_count':len(odds_1x2),'goldbet_over_selection_count':len(odds_over),'goldbet_odds_ready':odds_ready,
        'true_open_1x2_count':len(true_1x2),'true_open_over_count':len(true_over),'true_open_ready':true_open_ready,
        'player_prop_rows':len(pr),'player_props_ready':props_ready,
        'strong_drop_count':len(drops),'strong_drops':drops[:20]
    })

out.sort(key=lambda x:(x.get('minutes_to_start') is None, x.get('minutes_to_start') or 9999))
counts=defaultdict(int)
for x in out:counts[x['readiness']]+=1
ready=[x for x in out if x['readiness']=='READY_DEEP_ANALYSIS']
payload={
    'generated_at':NOW.isoformat(),'contract':'Notify/analyze when READY_DEEP_ANALYSIS; do not promote incomplete data to final BET.',
    'input_freshness_minutes':{'lineups':lineup_age,'tactical':tactical_age,'odds_movement':movement_age,'player_props':props_age},
    'match_count':len(out),'readiness_counts':dict(counts),'ready_count':len(ready),'ready_matches':ready,'matches':out
}
ROOT.mkdir(exist_ok=True)
(ROOT/'deep-analysis-readiness.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
summary={k:v for k,v in payload.items() if k!='matches'}
summary['ready_matches']=[{k:m.get(k) for k in ('match_market_id','match','league','start_time','minutes_to_start','readiness','strong_drop_count')} for m in ready]
(ROOT/'deep-analysis-readiness-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
