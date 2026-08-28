#!/usr/bin/env python3
import difflib, hashlib, json, pathlib, re, time, unicodedata, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

NOW=datetime.now(timezone.utc); NOW_ISO=NOW.isoformat(); ROME=ZoneInfo('Europe/Rome')
REQ=pathlib.Path('radar-movement-request.json')
STATE=pathlib.Path('feed/goldbet-diretta-movement-state.json')
OUT=pathlib.Path('feed/radar-movement-diretta-current.json')
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/139.0.0.0 Safari/537.36'


def load(p,d):
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
    except Exception:return d

def parse_dt(s):
    if not s:return None
    try:return datetime.fromisoformat(str(s).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:
        try:return datetime.strptime(str(s),'%d-%m-%Y %H:%M').replace(tzinfo=ROME).astimezone(timezone.utc)
        except Exception:return None

def norm(s):
    s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().lower()
    aliases={'al-nassr':'al nassr','al taawon':'al taawoun','al-taawoun':'al taawoun','al-khaleej':'al khaleej','al-hilal':'al hilal','neom sc':'neom'}
    for a,b in aliases.items():s=s.replace(a,b)
    toks=re.findall(r'[a-z0-9]+',s); stop={'fc','cf','sc','ac','afc','club','football','calcio'}
    return ' '.join(t for t in toks if t not in stop)
def split_event(s):
    s=str(s or '')
    for sep in (' - ',' – ',' vs ',' v '):
        if sep in s:return tuple(x.strip() for x in s.split(sep,1))
    return s,''
def score(a,b):
    a,b=norm(a),norm(b)
    if not a or not b:return 0
    seq=difflib.SequenceMatcher(None,a,b).ratio();A=set(a.split());B=set(b.split());jac=len(A&B)/max(1,len(A|B))
    return max(seq,.70*seq+.30*jac)
def fnum(x):
    try:return float(x)
    except:return None
def same_line(a,b):
    if a is None and b is None:return True
    aa,bb=fnum(a),fnum(b)
    return abs(aa-bb)<1e-9 if aa is not None and bb is not None else str(a)==str(b)
def key(parts):return hashlib.sha1('|'.join('' if x is None else str(x) for x in parts).encode()).hexdigest()[:24]

def http(url,headers=None,cap=8000000,retries=3):
    h={'User-Agent':UA,'Accept':'*/*','Accept-Language':'it-IT,it;q=0.9,en;q=0.8','Referer':'https://www.diretta.it/','x-fsign':'SW9D1eZo'}
    if headers:h.update(headers)
    last=(None,'')
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=30) as r:return r.status,r.read(cap).decode('utf-8','replace')
        except urllib.error.HTTPError as e:
            last=(e.code,e.read(100000).decode('utf-8','replace'))
            if e.code==429:time.sleep(2*(attempt+1));continue
            return last
        except Exception:
            time.sleep(1+attempt)
    return last

def fields(sec):
    d={}
    for p in sec.split(chr(0xAC)):
        if chr(0xF7) in p:
            k,_,v=p.partition(chr(0xF7));d[k]=v
    return d

req=load(REQ,{})
queries=req.get('queries') if isinstance(req,dict) else []
if not isinstance(queries,list):queries=[]

# Discover requested fixtures from current Flashscore/Diretta football schedule.
feed_urls=['https://www.flashscore.com/x/feed/f_1_0_3_en_1','https://www.flashscore.com/x/feed/f_1_0_3_it_1','https://local-global.flashscore.ninja/2/x/feed/f_1_0_3_it_1']
feed='';feed_url=None;feed_statuses=[]
for u in feed_urls:
    st,body=http(u);feed_statuses.append({'url':u,'status':st,'bytes':len(body)})
    if st==200 and 'AA÷' in body:feed=body;feed_url=u;break
fixtures=[];tourn=''
if feed:
    for sec in feed.split('~'):
        f=fields(sec)
        if 'ZA' in f:tourn=f.get('ZA','')
        if 'AA' in f and ('AE' in f or 'AF' in f):
            try:ts=int(f.get('AD') or 0)
            except:ts=0
            if ts:fixtures.append({'id':f.get('AA'),'home':f.get('AE'),'away':f.get('AF'),'start':datetime.fromtimestamp(ts,timezone.utc),'tournament':tourn})

matched=[];unmatched=[]
for qi,q in enumerate(queries[:40]):
    if not isinstance(q,dict):continue
    th,ta=split_event(q.get('event')); qstart=parse_dt(q.get('start_time'))
    best=None
    for f in fixtures:
        hs,as_=score(th,f['home']),score(ta,f['away'])
        if min(hs,as_)<.44:continue
        name_score=(hs+as_)/2
        dm=abs((f['start']-qstart).total_seconds())/60 if qstart else None
        if qstart and dm>180:continue
        time_score=1 if dm is None else max(0,1-dm/180)
        total=.88*name_score+.12*time_score
        cand=(total,-(dm or 0),f,hs,as_,dm)
        if best is None or cand[:2]>best[:2]:best=cand
    if best and best[0]>=.58:
        _,_,f,hs,as_,dm=best
        matched.append({'query_index':qi,'query':q,'flashscore_event_id':f['id'],'event':f"{f['home']} - {f['away']}",
                        'home':f['home'],'away':f['away'],'tournament':f['tournament'],'start_time':f['start'].isoformat(),
                        'match_score':round(best[0],4),'home_score':round(hs,4),'away_score':round(as_,4),'time_diff_min':None if dm is None else round(dm,1)})
    else:unmatched.append({'query_index':qi,'query':q,'reason':'fixture_not_matched'})

base='https://global.ds.lsapp.eu/odds/pq_graphql'
H={'User-Agent':UA,'Accept':'*/*','Accept-Language':'it-IT,it;q=0.9,en;q=0.8','Referer':'https://www.diretta.it/','Origin':'https://www.diretta.it'}
def api(params):
    st,body=http(base+'?'+urllib.parse.urlencode(params),H,3500000)
    try:return st,json.loads(body) if st==200 else None
    except:return st,None

def flatten(bt,payload):
    rows=[]
    def add(sel,item,line=None):
        if not isinstance(item,dict):return
        try:op=float(item.get('opening')) if item.get('opening') not in (None,'') else None
        except:op=None
        try:cur=float(item.get('value')) if item.get('value') not in (None,'') else None
        except:cur=None
        if op is None and cur is None:return
        rows.append({'market':bt,'period':'full_time','line':line,'selection':sel,'opening':op,'current':cur,'change_flag':item.get('change')})
    if bt=='HOME_DRAW_AWAY':
        add('HOME',payload.get('home'));add('DRAW',payload.get('draw'));add('AWAY',payload.get('away'))
    elif bt=='OVER_UNDER':
        for x in payload.get('opportunities') or []:
            if not isinstance(x,dict):continue
            h=x.get('handicap') or {};line=h.get('value')
            try:line=float(line)
            except:pass
            add('OVER',x.get('over'),line);add('UNDER',x.get('under'),line)
    elif bt=='BOTH_TEAMS_TO_SCORE':
        add('YES',payload.get('yes'));add('NO',payload.get('no'))
    elif bt=='DOUBLE_CHANCE':
        for k,sel in [('homeDraw','HOME_DRAW'),('homeAway','HOME_AWAY'),('drawAway','DRAW_AWAY')]:add(sel,payload.get(k))
    return rows

old=load(STATE,{})
records=old.get('records') if isinstance(old,dict) else {}
if not isinstance(records,dict):records={}
results=[];errors=[];checkpoints=(120,75,60,40,30,15)
for m in matched:
    fid=m['flashscore_event_id']
    st,md=api({'_hash':'pobtm','eventId':fid,'projectId':'400','geoIpCode':'IT','geoIpSubdivisionCode':'IT21'})
    menu=((md or {}).get('data') or {}).get('getPrematchOddsBettingTypeMenu') or {} if isinstance(md,dict) else {}
    books=[]
    for be in ((menu.get('settings') or {}).get('bookmakers') or []):
        inn=(be or {}).get('bookmaker') or {}
        if inn.get('id') is not None and inn.get('name'):books.append({'id':inn['id'],'name':inn['name']})
    gb=next((b for b in books if str(b['name']).lower()=='goldbet'),None) or next((b for b in books if 'gold' in str(b['name']).lower()),None)
    if not gb:
        unmatched.append({'query_index':m['query_index'],'query':m['query'],'reason':'goldbet_not_in_bookmaker_menu','matched_event':m['event']});continue
    rows=[];seen=set();gbid=str(gb['id'])
    for it in menu.get('items') or []:
        if not isinstance(it,dict):continue
        bt,bs=it.get('bettingType'),it.get('bettingScope');ids=[str(x) for x in (it.get('bookmakerIds') or [])]
        if not bt or bs!='FULL_TIME' or bt not in ('HOME_DRAW_AWAY','OVER_UNDER','BOTH_TEAMS_TO_SCORE','DOUBLE_CHANCE') or (bt,bs) in seen:continue
        if ids and gbid not in ids:continue
        seen.add((bt,bs))
        st2,dd=api({'_hash':'ope2','eventId':fid,'bookmakerId':gbid,'betType':bt,'betScope':bs})
        payload=((dd or {}).get('data') or {}).get('findPrematchOddsForBookmaker') if isinstance(dd,dict) else None
        if isinstance(payload,dict):rows.extend(flatten(bt,payload))
        elif st2!=200:errors.append({'event':m['event'],'market':bt,'status':st2})
    start=parse_dt(m['start_time']);mt=None if not start else round((start-NOW).total_seconds()/60,2)
    outrows=[]
    for r in rows:
        k=key([fid,'GoldBet',r.get('market'),r.get('period'),r.get('line'),r.get('selection')]);rec=records.get(k)
        if not isinstance(rec,dict):
            rec={'key':k,'flashscore_event_id':fid,'event':m['event'],'tournament':m['tournament'],'start_time':m['start_time'],
                 'bookmaker':'GoldBet','bookmaker_id':gb.get('id'),'source':'GOLDBET_SAME_BOOKMAKER_VIA_DIRETTA',
                 'market':r.get('market'),'period':r.get('period'),'line':r.get('line'),'selection':r.get('selection'),
                 'true_open_price':r.get('opening'),'true_open_status':'TRUE_OPEN_CERTIFIED' if r.get('opening') is not None else 'TRUE_OPEN_NOT_AVAILABLE',
                 'first_captured_at':NOW_ISO,'current_price':r.get('current'),'last_captured_at':NOW_ISO,'checkpoints':{},'snapshots':[]}
            records[k]=rec
        if r.get('opening') is not None:
            rec['true_open_price']=r.get('opening');rec['true_open_status']='TRUE_OPEN_CERTIFIED'
        rec['current_price']=r.get('current');rec['last_captured_at']=NOW_ISO;rec['last_change_flag']=r.get('change_flag')
        snaps=rec.setdefault('snapshots',[])
        if not snaps or snaps[-1].get('price')!=r.get('current') or (parse_dt(snaps[-1].get('captured_at')) and (NOW-parse_dt(snaps[-1].get('captured_at'))).total_seconds()>240):
            snaps.append({'price':r.get('current'),'captured_at':NOW_ISO,'minutes_to_start':mt,'capture_reason':'REQUEST_OR_SCHEDULE'})
        rec['snapshots']=snaps[-80:]
        if mt is not None and r.get('current') is not None:
            cps=rec.setdefault('checkpoints',{})
            for cp in checkpoints:
                dist=abs(mt-cp)
                if dist<=7.5:
                    oldcp=cps.get(f'T-{cp}');oldd=fnum((oldcp or {}).get('distance_from_target_min')) if isinstance(oldcp,dict) else None
                    if oldd is None or dist<oldd:
                        quality='EXACT_NEAR' if dist<=1.5 else ('GOOD' if dist<=3 else ('ACCEPTABLE' if dist<=5 else 'FALLBACK'))
                        cps[f'T-{cp}']={'price':r.get('current'),'captured_at':NOW_ISO,'minutes_to_start':mt,'target_minutes':cp,'distance_from_target_min':round(dist,2),'quality':quality}
        try:
            delta=round(float(r['current'])-float(r['opening']),3) if r.get('current') is not None and r.get('opening') is not None else None
            pp=round((1/float(r['current'])-1/float(r['opening']))*100,3) if r.get('current') and r.get('opening') else None
        except:delta=pp=None
        cps=rec.get('checkpoints') or {}
        outrows.append({'market':r.get('market'),'period':'full_time','line':r.get('line'),'selection':r.get('selection'),
                        'true_open':rec.get('true_open_price'),'open_status':rec.get('true_open_status'),'T-40':cps.get('T-40'),'T-30':cps.get('T-30'),
                        'request_current':r.get('current'),'request_captured_at':NOW_ISO,'price_delta_open_to_request':delta,
                        'implied_probability_delta_pp':pp,'movement_complete':bool(rec.get('true_open_status')=='TRUE_OPEN_CERTIFIED' and cps.get('T-40') and r.get('current') is not None)})
    results.append({'query_index':m['query_index'],'request_query':m['query'],'event':m['event'],'tournament':m['tournament'],'start_time':m['start_time'],
                    'minutes_to_start':mt,'flashscore_event_id':fid,'match_score':m['match_score'],'bookmaker':'GoldBet','bookmaker_id':gb.get('id'),
                    'source':'GOLDBET_SAME_BOOKMAKER_VIA_DIRETTA','same_bookmaker':True,'rows':outrows})

# retain 14 days for audit
records={k:r for k,r in records.items() if not (parse_dt(r.get('start_time')) and parse_dt(r.get('start_time'))<NOW-timedelta(days=14))}
state={'schema_version':'goldbet-diretta-movement-v1.0','generated_at':NOW_ISO,'source':'Diretta/Flashscore odds service','bookmaker':'GoldBet',
       'same_bookmaker':True,'records':records}
STATE.parent.mkdir(exist_ok=True);STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
out={'schema_version':'radar-movement-diretta-query-v1.0','request_id':req.get('request_id'),'requested_at':req.get('requested_at'),'generated_at':NOW_ISO,
     'rome_time':datetime.now(ROME).isoformat(),'feed_url':feed_url,'feed_statuses':feed_statuses,'fixture_feed_healthy':bool(feed),
     'source':'GOLDBET_SAME_BOOKMAKER_VIA_DIRETTA','bookmaker':'GoldBet','same_bookmaker':True,'cross_book':False,
     'matched_count':len(matched),'result_count':len(results),'unmatched':unmatched,'errors':errors,'results':results,
     'contract':{'opening_field':'GoldBet opening from Diretta/Flashscore bookmaker-specific odds payload','request_current':'GoldBet value from same bookmaker-specific payload',
                 'T-40_policy':'closest captured same-bookmaker snapshot within 7.5m; distance/quality exposed','true_open_never_fabricated':True}}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'generated_at':NOW_ISO,'feed_healthy':bool(feed),'matched':len(matched),'results':len(results),'unmatched':len(unmatched),'errors':len(errors)},ensure_ascii=False,indent=2))
