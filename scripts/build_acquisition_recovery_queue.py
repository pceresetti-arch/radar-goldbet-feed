#!/usr/bin/env python3
import json, pathlib, unicodedata, re
from datetime import datetime, timezone

FEED=pathlib.Path('feed')
OUT=FEED/'acquisition-recovery-queue.json'


def load(name, default):
    p=FEED/name
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:return default


def norm(v):
    s=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def key(row):
    mm=row.get('match_market_id')
    if mm not in (None,''): return ('id',str(mm))
    return ('name',norm(row.get('match')))

lineups=load('lineups-current.json',{'matches':[]})
readiness=load('deep-analysis-readiness.json',{'matches':[]})
bf=load('betflag-residential-fixtures-index.json',{'fixtures':[]})

bf_map={key(x):x for x in bf.get('fixtures') or [] if key(x)[1]}
queue=[]
for m in readiness.get('matches') or []:
    b=bf_map.get(key(m),{})
    reasons=list(m.get('blocking_reasons') or [])
    warnings=list(m.get('warnings') or [])
    actions=[]
    xi=m.get('xi_source_confidence')
    if xi in {'MISSING','PREDICTED','PROVIDER_ONLY'}:
        actions.append({
            'type':'XI_RECOVERY',
            'priority':'CRITICAL' if xi=='PROVIDER_ONLY' else 'HIGH',
            'instruction':'Seek official club/league source first; otherwise require a second independent live provider before certification.',
            'current_confidence':xi,
        })
    if not m.get('betflag_fixture_mapped'):
        actions.append({'type':'BETFLAG_FIXTURE_REMAP','priority':'CRITICAL','instruction':'Re-resolve exact fixture in fresh betflag-live index; do not infer absence from aggregate feed.'})
    elif not m.get('betflag_standard_ready'):
        actions.append({'type':'BETFLAG_STANDARD_RETRY','priority':'CRITICAL','instruction':'Retry standard lane exact fixture acquisition and refresh source timestamp.'})
    if b and not b.get('player_price_gate_fixture_eligible', bool((b.get('player_props_count') or 0)>0)):
        actions.append({'type':'BETFLAG_PLAYER_RETRY','priority':'HIGH','instruction':'Retry full player matrix; standard CURRENT may remain usable independently.'})
    if m.get('movement_certification') in {None,'MISSING','CURRENT_ONLY','FIRST_SEEN_CURRENT'}:
        actions.append({'type':'MOVEMENT_RECOVERY','priority':'MEDIUM','instruction':'Recover same-book exact identity snapshots; never substitute cross-book movement.'})
    if 'WAIT_POST_XI_DELTA_RECOMPUTE' in reasons or not m.get('post_xi_delta_ready',True):
        actions.append({'type':'POST_XI_DELTA_REBUILD','priority':'CRITICAL','instruction':'Recompute roles, minutes, matchup, player allocation, 1H model, fair/gate and post-XI movement.'})
    if actions:
        queue.append({
            'match':m.get('match'),'match_market_id':m.get('match_market_id'),'start_time':m.get('start_time'),
            'readiness':m.get('readiness'),'blocking_reasons':reasons,'warnings':warnings,
            'actions':actions,
        })

priority_rank={'CRITICAL':0,'HIGH':1,'MEDIUM':2,'LOW':3}
queue.sort(key=lambda x:(min(priority_rank.get(a.get('priority'),9) for a in x['actions']), x.get('start_time') or ''))
payload={
    'schema_version':'radar-acquisition-recovery-queue-v1',
    'generated_at':datetime.now(timezone.utc).isoformat(),
    'purpose':'Machine-readable recovery queue for missing XI, exact BetFlag lanes, movement and POST-XI recomputation. Data gaps remain explicit until recovered.',
    'count':len(queue),'matches':queue,
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'recovery_items':len(queue)},ensure_ascii=False))
