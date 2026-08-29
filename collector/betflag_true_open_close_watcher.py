import argparse, hashlib, json, os, pathlib, re, time, unicodedata
from datetime import datetime, timezone, timedelta
from betflag_session_transport import BetFlagTransport
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001
CORE={'1X2':13617,'OVER_UNDER':13618,'GOAL_NO_GOAL':13619,'DOUBLE_CHANCE':13620,'HANDICAP':13156}
TAB_ID=2454

def norm(v):
    s=unicodedata.normalize('NFD',str(v or '')); s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower()
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())

def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values(): yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)

def family(name, fallback=None):
    n=norm(name)
    if n=='1x2': return '1X2'
    if n in ('u o','under over','over under','totale gol') or n.startswith('u o '): return 'OVER_UNDER'
    if n in ('gg ng','goal no goal','gol no gol','btts'): return 'GOAL_NO_GOAL'
    if n in ('dc','doppia chance'): return 'DOUBLE_CHANCE'
    if 'handicap' in n: return 'HANDICAP'
    return fallback

def qkey(r):
    raw='|'.join(str(r.get(k) or '') for k in ('match_market_id','event_id','family','market','line','selection','selection_id','market_id'))
    return hashlib.sha1(raw.encode()).hexdigest()[:24]

def parse_start(v):
    if v is None: return None
    if isinstance(v,(int,float)):
        x=float(v); x=x/1000 if x>10_000_000_000 else x
        try: return datetime.fromtimestamp(x,tz=timezone.utc)
        except Exception: return None
    s=str(v).strip()
    if not s: return None
    try:
        d=datetime.fromisoformat(s.replace('Z','+00:00'))
        if d.tzinfo is None:
            tz=ZoneInfo('Europe/Rome') if ZoneInfo else timezone(timedelta(hours=2))
            d=d.replace(tzinfo=tz)
        return d.astimezone(timezone.utc)
    except Exception:
        return None

def collect():
    rows=[]; event_ids=set(); errors=[]
    client=BetFlagTransport(timeout=30)
    try:
        for fam,slot in CORE.items():
            try:
                st,data=client.get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/{TAB_ID}/{slot}/0?channelId=0')
                if st!=200: continue
                for ev in walk(data):
                    if not isinstance(ev,dict) or ev.get('mi') is None or not ev.get('en') or str(ev.get('en')).startswith('('): continue
                    event_ids.add(str(ev.get('ei') or ev.get('mi')))
                    mm=ev.get('mmkW') or {}; mks=mm.values() if isinstance(mm,dict) else (mm if isinstance(mm,list) else [])
                    for mk in mks:
                        if not isinstance(mk,dict): continue
                        mn=mk.get('mn') or fam; rfam=family(mn,fam)
                        if rfam!=fam: continue
                        spd=mk.get('spd') or {}; spreads=spd.items() if isinstance(spd,dict) else enumerate(spd if isinstance(spd,list) else [])
                        for line,spr in spreads:
                            if not isinstance(spr,dict): continue
                            real_line=spr.get('sl') if spr.get('sl') not in (None,'','0','0.0',0,0.0) else line
                            if str(real_line) in ('0','0.0'): real_line=None
                            for q in spr.get('asl') or []:
                                odd=q.get('ov')
                                if not isinstance(odd,(int,float)): continue
                                r={'event_id':ev.get('ei'),'match_market_id':ev.get('mi'),'match':ev.get('en'),'match_start':ev.get('ed') or ev.get('eventDateTime'),'family':fam,'market':mn,'line':real_line,'selection':q.get('sn'),'odd':odd,'selection_id':q.get('si'),'market_id':q.get('mi'),'odds_id':q.get('oi')}
                                r['quote_id']=qkey(r); rows.append(r)
            except Exception as e:
                errors.append({'family':fam,'error':repr(e)})
        transport=client.diagnostics()
    finally:
        client.close()
    return rows,event_ids,errors,transport

def default_state_dir():
    env=os.getenv('BETFLAG_WATCHER_STATE_DIR')
    if env: return pathlib.Path(env)
    if os.name=='nt': return pathlib.Path(r'C:\BetFlagRadar\state')
    return pathlib.Path('feed/local-watcher-state')

def one_scan(state):
    now_dt=datetime.now(timezone.utc); now=now_dt.isoformat()
    rows,event_ids,errors,transport=collect(); current={r['quote_id']:r for r in rows}; current_keys=set(current)
    hist=state.setdefault('recent_scans',[]); quotes=state.setdefault('quotes',{})
    continuous=False; prior_key_sets=[]; prior_event_sets=[]
    if len(hist)>=2:
        a,b=hist[-2],hist[-1]
        try:
            da=datetime.fromisoformat(a['at']); db=datetime.fromisoformat(b['at'])
            continuous=(now_dt-db).total_seconds()<=90 and (db-da).total_seconds()<=90 and bool(a.get('source_healthy')) and bool(b.get('source_healthy'))
        except Exception: continuous=False
        prior_key_sets=[set(a.get('keys',[])),set(b.get('keys',[]))]
        prior_event_sets=[set(a.get('events',[])),set(b.get('events',[]))]
    scan_healthy=len(rows)>0 and len(errors)==0
    new_count=0; certified_open=0; changes=0
    for k,r in current.items():
        odd=float(r['odd']); q=quotes.get(k)
        if q is None:
            eid=str(r.get('event_id') or r.get('match_market_id'))
            proven_absent=scan_healthy and continuous and all(k not in s for s in prior_key_sets) and all(eid in es for es in prior_event_sets)
            status='OPEN_RADAR_CERTIFICATA_CONTINUOUS_WATCH' if proven_absent else 'FIRST_SEEN_ONLY'
            q={'quote_id':k,'identity':{x:r.get(x) for x in ('event_id','match_market_id','match','match_start','family','market','line','selection','selection_id','market_id','odds_id')},'open_status':status,'open_at':now,'open_odd':odd,'true_open_betflag_official':False,'true_open_radar_certified':bool(proven_absent),'current_at':now,'current_odd':odd,'last_pre_kickoff_at':None,'last_pre_kickoff_odd':None,'close_status':None,'close_at':None,'close_odd':None,'changes':[]}
            quotes[k]=q; new_count+=1; certified_open+=int(proven_absent)
        else:
            q.setdefault('changes',[])
            if q.get('current_odd') is not None and float(q['current_odd'])!=odd:
                q['changes'].append({'at':now,'from':q['current_odd'],'to':odd,'delta':round(odd-float(q['current_odd']),4)}); changes+=1
            q['current_at']=now; q['current_odd']=odd
        start=parse_start(r.get('match_start'))
        if start and now_dt < start:
            q['last_pre_kickoff_at']=now; q['last_pre_kickoff_odd']=odd
    closed=0
    for q in quotes.values():
        if q.get('close_status'): continue
        start=parse_start((q.get('identity') or {}).get('match_start'))
        if not start or now_dt < start: continue
        if q.get('last_pre_kickoff_odd') is not None:
            q['close_status']='CLOSE_RADAR_CERTIFIED_LAST_BETFLAG_PRE_KICKOFF'
            q['close_at']=q.get('last_pre_kickoff_at'); q['close_odd']=q.get('last_pre_kickoff_odd'); closed+=1
    hist.append({'at':now,'keys':list(current_keys),'events':list(event_ids),'source_healthy':scan_healthy})
    state['recent_scans']=hist[-2:]
    state.update({'schema_version':'betflag-open-close-watch-v2','generated_at':now,'last_scan_at':now,'source_healthy':scan_healthy,'rows_seen':len(rows),'transport':transport,'policy':{'true_open_betflag_official':'Only with an explicit BetFlag source opening field or independently verifiable BetFlag historical proof.','open_radar_certificata':'Promoted only when the exact quote was absent in two consecutive healthy scans <=90s apart while the fixture itself was already present, then appeared.','close':'Last observed BetFlag quote strictly before parsed kickoff.'}})
    if errors: state['last_errors']=errors
    else: state.pop('last_errors',None)
    return {'rows':len(rows),'new':new_count,'certified_open':certified_open,'changes':changes,'closed':closed,'errors':len(errors)}

def acquire_lock(path):
    try:
        fd=os.open(str(path),os.O_CREAT|os.O_EXCL|os.O_WRONLY); os.write(fd,str(os.getpid()).encode()); os.close(fd); return True
    except FileExistsError:
        try:
            age=time.time()-path.stat().st_mtime
            if age>180: path.unlink(missing_ok=True); return acquire_lock(path)
        except Exception: pass
        return False

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--once',action='store_true'); ap.add_argument('--window-seconds',type=int,default=50); ap.add_argument('--interval',type=int,default=20); ap.add_argument('--state-dir',default=None)
    args=ap.parse_args(); d=pathlib.Path(args.state_dir) if args.state_dir else default_state_dir(); d.mkdir(parents=True,exist_ok=True)
    lock=d/'watcher.lock'
    if not acquire_lock(lock):
        print(json.dumps({'status':'already_running'})); return
    try:
        p=d/'betflag-open-close-watch.json'
        try: state=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        except Exception: state={}
        started=time.time(); totals={'rows':0,'new':0,'certified_open':0,'changes':0,'closed':0,'errors':0,'scans':0}
        while True:
            r=one_scan(state); totals['scans']+=1
            for k in ('rows','new','certified_open','changes','closed','errors'): totals[k]+=r[k]
            tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(p)
            if args.once or time.time()-started+args.interval>args.window_seconds: break
            time.sleep(args.interval)
        print(json.dumps({'status':'ok',**totals,'state_file':str(p)},ensure_ascii=False))
    finally:
        lock.unlink(missing_ok=True)
if __name__=='__main__': main()
