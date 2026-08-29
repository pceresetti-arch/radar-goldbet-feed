import json, pathlib, urllib.request
from datetime import datetime, timezone

BASE='https://radar-betflag-v7.p-ceresetti.workers.dev'
URL=f'{BASE}/live/standard-odds?limit=5000'
HEADERS={'Accept':'application/json','User-Agent':'RadarBetFlagTrueOpenTracker/3.0','Cache-Control':'no-cache, no-store, max-age=0','Pragma':'no-cache'}
FEED=pathlib.Path('feed')
STATE=FEED/'betflag-standard-movement.json'
LATEST=FEED/'betflag-standard-current.json'

# TRUE_OPEN = real BetFlag opening price only.
# FIRST_OBSERVED = first price the Radar captured. Never promote FIRST_OBSERVED to TRUE_OPEN
# unless BetFlag itself exposes an explicit opening-price field.


def get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=45) as r:
        return r.status,json.loads(r.read().decode('utf-8','replace'))


def qkey(row):
    return '|'.join(str(v or '') for v in (
        row.get('match_market_id'),row.get('family'),row.get('market_id'),row.get('market_type'),
        row.get('line'),row.get('selection_id'),row.get('selection')
    ))


def load_state():
    if not STATE.exists():
        return {'schema_version':'betflag-standard-movement-v3','source_class':'BETFLAG_AAMS_DIRECT_STANDARD','events':{},'last_success_at':None}
    s=json.loads(STATE.read_text(encoding='utf-8'))
    s['schema_version']='betflag-standard-movement-v3'
    return s


def repair_false_true_open(state):
    repaired=0
    for ev in (state.get('events') or {}).values():
        for ms in (ev.get('markets') or {}).values():
            if str(ms.get('open_capture_status') or '').startswith('TRUE_OPEN') and not ms.get('betflag_opening_odd'):
                ms['open_capture_status']='FIRST_OBSERVED_ONLY'
                ms['open_certification_basis']=None
                ms['true_open_odd']=None
                ms['true_open_at']=None
                repaired+=1
    return repaired


def main():
    FEED.mkdir(exist_ok=True)
    now=datetime.now(timezone.utc).isoformat()
    status,data=get_json(URL)
    if status!=200 or not data.get('source_healthy'):
        raise SystemExit(f'BetFlag v7 standard source unhealthy: HTTP {status}')
    rows=data.get('rows') or []
    state=load_state(); repaired=repair_false_true_open(state)
    current=[]

    for row in rows:
        eid=str(row.get('match_market_id') or row.get('event_id') or '')
        estate=state['events'].setdefault(eid,{
            'event_id':row.get('event_id'),'match_market_id':row.get('match_market_id'),'event':row.get('event'),
            'league':row.get('league'),'start_time':row.get('start_time'),'markets':{}
        })
        estate.update({k:row.get(k) for k in ('event_id','match_market_id','event','league','start_time')})
        key=qkey(row)
        source_open=row.get('betflag_opening_odd')
        source_open_at=row.get('betflag_source_open_at')
        source_certified=source_open not in (None,'')
        ms=estate['markets'].setdefault(key,{
            'family':row.get('family'),'market':row.get('market'),'line':row.get('line'),'selection':row.get('selection'),
            'selection_id':row.get('selection_id'),'market_id':row.get('market_id'),'market_type':row.get('market_type'),
            'odds_id':row.get('odds_id'),'first_seen_at':now,'first_seen_odd':row.get('odd'),
            'open_capture_status':'TRUE_OPEN_BETFLAG_SOURCE_CERTIFIED' if source_certified else 'FIRST_OBSERVED_ONLY',
            'open_certification_basis':'explicit_betflag_opening_field' if source_certified else None,
            'true_open_odd':source_open if source_certified else None,
            'true_open_at':source_open_at if source_certified else None,
            'history':[],'changes':0
        })

        if source_certified:
            ms['betflag_opening_odd']=source_open
            ms['betflag_opening_odd_field']=row.get('betflag_opening_odd_field')
            ms['betflag_source_open_at']=source_open_at
            ms['betflag_source_time_field']=row.get('betflag_source_time_field')
            ms['true_open_odd']=source_open
            ms['true_open_at']=source_open_at
            ms['open_capture_status']='TRUE_OPEN_BETFLAG_SOURCE_CERTIFIED'
            ms['open_certification_basis']='explicit_betflag_opening_field'
        elif str(ms.get('open_capture_status') or '').startswith('TRUE_OPEN') and not ms.get('betflag_opening_odd'):
            ms['open_capture_status']='FIRST_OBSERVED_ONLY'
            ms['open_certification_basis']=None
            ms['true_open_odd']=None
            ms['true_open_at']=None

        odd=row.get('odd'); hist=ms.setdefault('history',[])
        if not hist or hist[-1].get('odd')!=odd:
            hist.append({'at':now,'odd':odd,'source':'BETFLAG_AAMS_DIRECT'})
            if len(hist)>1: ms['changes']=int(ms.get('changes') or 0)+1
            ms['last_change_at']=now
        ms['current_odd']=odd; ms['current_at']=now

        current.append({**row,
            'fetched_at':now,
            'open_capture_status':ms.get('open_capture_status'),
            'open_certification_basis':ms.get('open_certification_basis'),
            'true_open_odd':ms.get('true_open_odd'),
            'true_open_at':ms.get('true_open_at'),
            'first_seen_at':ms.get('first_seen_at'),
            'first_seen_odd':ms.get('first_seen_odd')
        })

    state.update({
        'generated_at':now,'last_success_at':now,'source_status':status,'source_url':URL,
        'source_class':'BETFLAG_AAMS_DIRECT_STANDARD','true_open_definition':'REAL_BETFLAG_OPENING_PRICE_ONLY',
        'false_true_open_labels_repaired':repaired
    })
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    certified=sum(1 for r in current if r.get('open_capture_status')=='TRUE_OPEN_BETFLAG_SOURCE_CERTIFIED')
    fam_counts={f:sum(1 for r in current if r.get('family')==f) for f in ('1X2','TOTAL','OTHER')}
    LATEST.write_text(json.dumps({
        'generated_at':now,'source_status':status,'source_class':'BETFLAG_AAMS_DIRECT_STANDARD',
        'true_open_definition':'REAL_BETFLAG_OPENING_PRICE_ONLY','row_count':len(current),
        'family_counts':fam_counts,'true_open_source_certified_count':certified,'rows':current
    },ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'generated_at':now,'status':status,'rows':len(current),'family_counts':fam_counts,
                      'true_open_source_certified':certified,'old_false_labels_repaired':repaired},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
