import json, pathlib, re, unicodedata, urllib.request
from datetime import datetime, timezone

BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001
H={'Accept':'application/json,text/plain,*/*','x-api-version':'1.0','X-Auth-Token':'','X-Brand':'3','X-IdCanale':'0','Origin':'https://www.betflag.it','Referer':'https://www.betflag.it/','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'}

def norm(v):
 s=unicodedata.normalize('NFD',str(v or '')); s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower()
 return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())

def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values(): yield from walk(v)
 elif isinstance(x,list):
  for v in x: yield from walk(v)

def get(url):
 req=urllib.request.Request(url,headers=H)
 with urllib.request.urlopen(req,timeout=30) as r: return r.status,json.loads(r.read().decode())

def family(name):
 n=norm(name)
 if n in ('1x2','esito finale','esito finale 1x2') or ('1x2' in n and 'tempo' not in n): return '1X2'
 if ('under over' in n or 'over under' in n or n in ('u o','totale gol')) and 'giocatore' not in n: return 'OVER_UNDER'
 if 'goal no goal' in n or 'gol no gol' in n or n in ('goal nogoal','btts'): return 'GOAL_NO_GOAL'
 if 'team total' in n or 'totale squadra' in n: return 'TEAM_TOTAL'
 if 'handicap' in n: return 'HANDICAP'
 if 'doppia chance' in n: return 'DOUBLE_CHANCE'
 return None

def main():
 now=datetime.now(timezone.utc).isoformat(); rows=[]; markets_seen={}; status=None
 try:
  status,data=get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
  for ev in walk(data):
   if not isinstance(ev,dict) or ev.get('mi') is None or not ev.get('en') or str(ev.get('en')).startswith('('): continue
   mm=ev.get('mmkW') or {}; mks=mm.values() if isinstance(mm,dict) else (mm if isinstance(mm,list) else [])
   for mk in mks:
    if not isinstance(mk,dict): continue
    mn=mk.get('mn'); fam=family(mn)
    if not fam: continue
    markets_seen[str(mn)]=markets_seen.get(str(mn),0)+1
    spd=mk.get('spd') or {}; spreads=spd.items() if isinstance(spd,dict) else enumerate(spd if isinstance(spd,list) else [])
    for line,spr in spreads:
     if not isinstance(spr,dict): continue
     for q in spr.get('asl') or []:
      odd=q.get('ov')
      if not isinstance(odd,(int,float)): continue
      rows.append({'event_id':ev.get('ei'),'match_market_id':ev.get('mi'),'match':ev.get('en'),'match_start':ev.get('ed'),'family':fam,'market':mn,'line':None if str(line) in ('0','0.0') else line,'selection':q.get('sn'),'odd':odd,'selection_id':q.get('si'),'market_id':q.get('mi'),'odds_id':q.get('oi')})
 except Exception as e:
  error=repr(e)
 else: error=None
 out={'schema_version':'betflag-standard-markets-v1','generated_at':now,'source_class':'BETFLAG_AAMS_DIRECT','source_healthy':status==200,'priority':['1X2','OVER_UNDER'],'secondary':['GOAL_NO_GOAL','TEAM_TOTAL','HANDICAP','DOUBLE_CHANCE'],'status':status,'markets_seen':markets_seen,'rows':rows}
 if error: out['error']=error
 p=pathlib.Path('feed'); p.mkdir(exist_ok=True)
 (p/'betflag-standard-current.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'source_healthy':out['source_healthy'],'rows':len(rows),'families':{f:sum(1 for r in rows if r['family']==f) for f in sorted(set(r['family'] for r in rows))}},ensure_ascii=False))
if __name__=='__main__': main()
