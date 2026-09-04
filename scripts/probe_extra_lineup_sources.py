#!/usr/bin/env python3
import json, pathlib, re, unicodedata, difflib
from datetime import datetime, timezone
from curl_cffi import requests

NOW = datetime.now(timezone.utc)
LINEUPS = pathlib.Path('feed/lineups-current.json')
OUT = pathlib.Path('feed/extra-lineup-source-probe.json')
HEADERS = {
    'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36',
    'Accept':'*/*',
    'Accept-Language':'it-IT,it;q=0.9,en;q=0.8',
}

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().lower()
    s=re.sub(r'\b(fc|cf|sc|ac|afc|cd|fk|bk|calcio|club|deportivo|sporting|united|city)\b',' ',s)
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())

def score(a,b):
    a,b=norm(a),norm(b)
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None,a,b).ratio()

def split_match(s):
    for sep in (' - ',' vs ',' v '):
        if sep in str(s): return tuple(x.strip() for x in str(s).split(sep,1))
    return str(s),''

def get_text(url, referer=None, extra=None):
    h=dict(HEADERS)
    if referer: h['Referer']=referer
    if extra: h.update(extra)
    r=requests.get(url,headers=h,impersonate='chrome',timeout=20)
    return r.status_code,r.text

def get_json(url, referer=None):
    st,txt=get_text(url,referer)
    if st!=200: return st,None
    return st,json.loads(txt)

def flashscore_matches(day=0):
    # Flashscore/Diretta internal public feed. Discovery only: never certifies XI by itself.
    urls=[
        f'https://local-global.flashscore.ninja/2/x/feed/f_1_{day}_3_en_1',
        f'https://local-global.flashscore.ninja/2/x/feed/f_1_{day}_3_it_1',
    ]
    hdr={'x-fsign':'SW9D1eZo','Origin':'https://www.flashscore.com'}
    for u in urls:
        try:
            st,txt=get_text(u,'https://www.flashscore.com/',hdr)
            if st!=200 or 'AA÷' not in txt: continue
            events=[]
            blocks=txt.split('~AA÷')
            for b in blocks[1:]:
                eid=b.split('¬',1)[0]
                fields={}
                for part in b.split('¬'):
                    if '÷' in part:
                        k,v=part.split('÷',1); fields[k]=v
                home=fields.get('AE'); away=fields.get('AF')
                if eid and home and away:
                    events.append({'id':eid,'home':home,'away':away,'raw_start':fields.get('AD')})
            return events,{'status':st,'url':u,'event_count':len(events)}
        except Exception as e:
            last={'error':type(e).__name__+': '+str(e)[:180],'url':u}
    return [], locals().get('last',{'error':'FLASH_DISCOVERY_FAILED'})

def best_event(match, events):
    h,a=split_match(match)
    best=None
    for e in events:
        s=(score(h,e.get('home'))+score(a,e.get('away')))/2
        if best is None or s>best[0]: best=(s,e)
    return best[1] if best and best[0]>=0.72 else None

def flashscore_probe(match, events):
    ev=best_event(match,events)
    if not ev: return {'provider':'Diretta/Flashscore','matched':False}
    eid=ev['id']; hdr={'x-fsign':'SW9D1eZo','Origin':'https://www.flashscore.com'}
    candidates=[
        f'https://local-global.flashscore.ninja/2/x/feed/df_sui_1_{eid}',
        f'https://local-global.flashscore.ninja/2/x/feed/dc_1_{eid}',
        f'https://local-global.flashscore.ninja/2/x/feed/df_li_1_{eid}',
        f'https://local-global.flashscore.ninja/2/x/feed/df_lu_1_{eid}',
        f'https://local-global.flashscore.ninja/2/x/feed/df_lineup_1_{eid}',
    ]
    attempts=[]
    for u in candidates:
        try:
            st,txt=get_text(u,'https://www.flashscore.com/',hdr)
            low=txt.lower()
            attempts.append({'url':u,'status':st,'bytes':len(txt),'has_lineup_marker':('starting lineups' in low or 'lineup' in low),'playerish':bool(re.search(r'\b(IA|IB|IF|player|formation)\b',txt,re.I))})
        except Exception as e:
            attempts.append({'url':u,'error':type(e).__name__+': '+str(e)[:160]})
    return {'provider':'Diretta/Flashscore','matched':True,'event':ev,'attempts':attempts}

def livescore_events(date_yyyymmdd):
    urls=[
        f'https://prod-public-api.livescore.com/v1/api/app/date/soccer/{date_yyyymmdd}/0?MD=1&countryCode=IT',
        f'https://prod-public-api.livescore.com/v1/api/react/date/soccer/{date_yyyymmdd}/0.00?MD=1',
    ]
    for u in urls:
        try:
            st,data=get_json(u,'https://www.livescore.com/')
            if st!=200 or not isinstance(data,dict): continue
            events=[]
            for stage in data.get('Stages') or []:
                for e in stage.get('Events') or []:
                    try:
                        home=(e.get('T1') or [{}])[0].get('Nm'); away=(e.get('T2') or [{}])[0].get('Nm')
                    except Exception:
                        home=away=None
                    if e.get('Eid') and home and away:
                        events.append({'id':e.get('Eid'),'home':home,'away':away,'raw':e})
            return events,{'status':st,'url':u,'event_count':len(events)}
        except Exception as e:
            last={'error':type(e).__name__+': '+str(e)[:180],'url':u}
    return [],locals().get('last',{'error':'LIVESCORE_DISCOVERY_FAILED'})

def livescore_probe(match, events):
    ev=best_event(match,events)
    if not ev: return {'provider':'LiveScore','matched':False}
    eid=ev['id']
    # Candidate event-detail routes are probed conservatively; only successful structured responses are reported.
    candidates=[
        f'https://prod-public-api.livescore.com/v1/api/app/event/soccer/{eid}',
        f'https://prod-public-api.livescore.com/v1/api/app/event/soccer/{eid}/lineups',
        f'https://prod-public-api.livescore.com/v1/api/app/match/soccer/{eid}',
    ]
    attempts=[]
    for u in candidates:
        try:
            st,txt=get_text(u,'https://www.livescore.com/')
            low=txt.lower()
            attempts.append({'url':u,'status':st,'bytes':len(txt),'json_like':txt.lstrip().startswith(('{','[')),'has_lineup_marker':('lineup' in low or 'formation' in low or 'starting' in low)})
        except Exception as e:
            attempts.append({'url':u,'error':type(e).__name__+': '+str(e)[:160]})
    return {'provider':'LiveScore','matched':True,'event':{'id':eid,'home':ev['home'],'away':ev['away']},'attempts':attempts}

def main():
    payload={'schema':'radar-extra-lineup-source-probe-v1','generated_at':NOW.isoformat(),'source_policy':'Discovery only. Diretta/Flashscore and LiveScore are not promoted to official XI until a complete 11v11 parser is validated and cross-checked.','targets':[]}
    src=json.loads(LINEUPS.read_text(encoding='utf-8')) if LINEUPS.exists() else {'matches':[]}
    targets=[]
    for m in src.get('matches') or []:
        try: mins=float(m.get('minutes_to_start'))
        except Exception: mins=None
        if mins is not None and 0 < mins <= 120: targets.append(m)
    flash,flash_meta=flashscore_matches(0)
    if not flash: flash,flash_meta=flashscore_matches(1)
    dates=sorted({str((m.get('start_utc') or '')[:10]).replace('-','') for m in targets if m.get('start_utc')})
    ls_by_date={}; ls_meta={}
    for d in dates:
        ls_by_date[d],ls_meta[d]=livescore_events(d)
    for m in targets[:30]:
        d=str((m.get('start_utc') or '')[:10]).replace('-','')
        payload['targets'].append({'match':m.get('match'),'minutes_to_start':m.get('minutes_to_start'),'flashscore':flashscore_probe(m.get('match'),flash),'livescore':livescore_probe(m.get('match'),ls_by_date.get(d,[]))})
    payload['flashscore_schedule_meta']=flash_meta
    payload['livescore_schedule_meta']=ls_meta
    payload['target_count']=len(payload['targets'])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'target_count':payload['target_count'],'flashscore_schedule_meta':flash_meta,'livescore_schedule_meta':ls_meta},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
