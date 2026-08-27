import json, pathlib, re, unicodedata, urllib.request
from datetime import datetime, timezone

BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001
URL=f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0'
HEADERS={
    'Accept':'application/json,text/plain,*/*','x-api-version':'1.0','X-Auth-Token':'',
    'X-Brand':'3','X-IdCanale':'0','Origin':'https://www.betflag.it','Referer':'https://www.betflag.it/',
    'User-Agent':'Mozilla/5.0 RadarBetFlagStandardOpen/1.0'
}
FEED=pathlib.Path('feed')
STATE=FEED/'betflag-standard-movement.json'
LATEST=FEED/'betflag-standard-current.json'


def norm(v):
    s=unicodedata.normalize('NFD',str(v or ''))
    s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower().replace('°','')
    return ' '.join(s.split()).strip()


def get_json(url):
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.status,json.loads(r.read().decode('utf-8','replace'))


def market_rows(event):
    out=[]
    mm=event.get('mmkW')
    markets=mm.values() if isinstance(mm,dict) else (mm if isinstance(mm,list) else [])
    for market in markets:
        if not isinstance(market,dict): continue
        mn=str(market.get('mn') or '')
        spd=market.get('spd')
        spreads=spd.items() if isinstance(spd,dict) else enumerate(spd or []) if isinstance(spd,list) else []
        for spread_key,spread in spreads:
            if not isinstance(spread,dict): continue
            line=spread.get('sl')
            if line in (None,'',0,'0',0.0,'0.0') and str(spread_key) not in ('0','0.0'):
                line=spread_key
            sels=[]
            for q in spread.get('asl') or []:
                if not isinstance(q,dict) or q.get('ov') is None: continue
                sels.append(str(q.get('sn') or ''))
                out.append({
                    'market':mn,'line':line,'selection':q.get('sn'),'odd':q.get('ov'),
                    'selection_id':q.get('si'),'selection_type':q.get('sti'),'market_type':q.get('mti'),
                    'market_id':q.get('mi'),'odds_id':q.get('oi')
                })
    return out


def family(row):
    m=norm(row.get('market')); s=norm(row.get('selection'))
    if '1x2' in m or 'esito finale' in m or s in ('1','x','2'):
        return '1X2'
    if any(x in m for x in ('under/over','over/under','totale gol','totale goal','goal totali','gol totali')) or s.startswith('over') or s.startswith('under'):
        return 'TOTAL'
    return None


def walk_events(x, out):
    if isinstance(x,dict):
        if x.get('ei') is not None and x.get('en') and x.get('mmkW') is not None:
            n=norm(x.get('en')); sn=norm(x.get('sn'))
            if not n.startswith('(') and not sn.startswith('giocatori'):
                rows=[]
                for r in market_rows(x):
                    f=family(r)
                    if f:
                        r['family']=f; rows.append(r)
                if rows:
                    out.append({
                        'event_id':x.get('ei'),'event':x.get('en'),'start_time':x.get('ed'),'league':x.get('td'),
                        'match_market_id':x.get('mi'),'tournament_id':x.get('ti'),'sport_id':x.get('si'),
                        'rows':rows
                    })
        for v in x.values(): walk_events(v,out)
    elif isinstance(x,list):
        for v in x: walk_events(v,out)


def qkey(event,row):
    return '|'.join(str(v or '') for v in (
        event.get('match_market_id'),row.get('family'),row.get('market_id'),row.get('market_type'),
        row.get('line'),row.get('selection_id'),row.get('selection')
    ))


def load_state():
    if not STATE.exists():
        return {'schema_version':'betflag-standard-movement-v1','source_class':'BETFLAG_AAMS_DIRECT_STANDARD','events':{},'last_success_at':None,'last_seen_keys':[]}
    return json.loads(STATE.read_text(encoding='utf-8'))


def main():
    FEED.mkdir(exist_ok=True)
    now=datetime.now(timezone.utc).isoformat()
    status,data=get_json(URL)
    events=[]; walk_events(data,events)
    state=load_state(); prev_keys=set(state.get('last_seen_keys') or [])
    prev_success=state.get('last_success_at')
    current=[]; seen_keys=set()
    for ev in events:
        eid=str(ev.get('match_market_id') or ev.get('event_id'))
        estate=state['events'].setdefault(eid,{
            'event_id':ev.get('event_id'),'match_market_id':ev.get('match_market_id'),'event':ev.get('event'),
            'league':ev.get('league'),'start_time':ev.get('start_time'),'markets':{}
        })
        estate.update({k:ev.get(k) for k in ('event_id','match_market_id','event','league','start_time')})
        for row in ev['rows']:
            key=qkey(ev,row); seen_keys.add(key)
            first_after_absence=bool(prev_success and key not in prev_keys)
            ms=estate['markets'].setdefault(key,{
                'family':row['family'],'market':row.get('market'),'line':row.get('line'),'selection':row.get('selection'),
                'selection_id':row.get('selection_id'),'market_id':row.get('market_id'),'market_type':row.get('market_type'),
                'odds_id':row.get('odds_id'),'first_seen_at':now,'first_seen_odd':row.get('odd'),
                'open_capture_status':'TRUE_OPEN_CERTIFIED_WITHIN_SCAN_INTERVAL' if first_after_absence else 'FIRST_SEEN_ONLY',
                'history':[],'min_odd':row.get('odd'),'max_odd':row.get('odd'),'changes':0
            })
            if first_after_absence and ms.get('open_capture_status')=='FIRST_SEEN_ONLY' and not ms.get('history'):
                ms['open_capture_status']='TRUE_OPEN_CERTIFIED_WITHIN_SCAN_INTERVAL'
            hist=ms.setdefault('history',[])
            odd=row.get('odd')
            if not hist or hist[-1].get('odd')!=odd:
                hist.append({'at':now,'odd':odd})
                if len(hist)>1: ms['changes']=int(ms.get('changes') or 0)+1
                ms['last_change_at']=now
            ms['current_odd']=odd; ms['current_at']=now
            try:
                ms['min_odd']=min(float(ms.get('min_odd',odd)),float(odd)); ms['max_odd']=max(float(ms.get('max_odd',odd)),float(odd))
            except Exception: pass
            current.append({**{k:ev.get(k) for k in ('event_id','event','league','start_time','match_market_id')},**row,'fetched_at':now,'open_capture_status':ms['open_capture_status'],'first_seen_at':ms['first_seen_at'],'first_seen_odd':ms['first_seen_odd']})
    state.update({'generated_at':now,'last_success_at':now,'source_status':status,'source_url':URL,'source_class':'BETFLAG_AAMS_DIRECT_STANDARD','last_seen_keys':sorted(seen_keys)})
    STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    LATEST.write_text(json.dumps({'generated_at':now,'source_status':status,'source_class':'BETFLAG_AAMS_DIRECT_STANDARD','row_count':len(current),'rows':current},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'generated_at':now,'status':status,'events':len(events),'rows':len(current),'true_open_within_scan':sum(1 for r in current if r['open_capture_status'].startswith('TRUE_OPEN'))},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
