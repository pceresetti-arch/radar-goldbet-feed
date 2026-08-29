import json, pathlib, urllib.request, urllib.error
from datetime import datetime, timezone
BASE='https://sportservice.betflag.it/api/sport/pregame'; AGG=1334500001
H={'Accept':'application/json,text/plain,*/*','x-api-version':'1.0','X-Auth-Token':'','X-Brand':'3','X-IdCanale':'0','Origin':'https://www.betflag.it','Referer':'https://www.betflag.it/','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'}
CAND=[(2454,0),(2454,13617),(2454,30056),(2454,13617,30056),(0,13617),(0,30056)]
def get(path):
 req=urllib.request.Request(BASE+path,headers=H)
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.loads(r.read().decode())
 except urllib.error.HTTPError as e:return e.code,None
 except Exception:return None,None
def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values():yield from walk(v)
 elif isinstance(x,list):
  for v in x:yield from walk(v)
def inspect(data):
 markets={}; keys={}; events=0
 for d in walk(data):
  if not isinstance(d,dict):continue
  if d.get('en') and d.get('mi') is not None and not str(d.get('en')).startswith('('):events+=1
  if d.get('mn'):
   n=str(d.get('mn')); markets[n]=markets.get(n,0)+1
   keys[n]=sorted(str(k) for k in d.keys())
 return {'events':events,'markets':markets,'market_keys':keys}
def main():
 out={'generated_at':datetime.now(timezone.utc).isoformat(),'results':[]}
 paths=[]
 for c in CAND:
  if len(c)==2:
   a,b=c; paths.append(f'/getOverviewEventsAams/0/-1/0/{AGG}/{a}/{b}/0?channelId=0')
   paths.append(f'/getOverviewEventsAams/0/1/0/{AGG}/{a}/{b}/0?channelId=0')
  else:
   a,b,c3=c; paths.append(f'/getOverviewEventsAams/0/{c3}/0/{AGG}/{a}/{b}/0?channelId=0')
 for p in paths:
  st,data=get(p); row={'path':p,'status':st}
  if data is not None: row.update(inspect(data))
  out['results'].append(row)
 pathlib.Path('feed').mkdir(exist_ok=True)
 pathlib.Path('feed/betflag-standard-slots-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'results':[{'path':r['path'],'status':r['status'],'events':r.get('events'),'markets':r.get('markets')} for r in out['results']]},ensure_ascii=False))
if __name__=='__main__':main()
