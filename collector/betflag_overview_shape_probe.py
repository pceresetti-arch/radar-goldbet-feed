import json, pathlib, urllib.request
from datetime import datetime, timezone
BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001
H={'Accept':'application/json,text/plain,*/*','x-api-version':'1.0','X-Auth-Token':'','X-Brand':'3','X-IdCanale':'0','Origin':'https://www.betflag.it','Referer':'https://www.betflag.it/','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'}
def get(url):
 req=urllib.request.Request(url,headers=H)
 with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.loads(r.read().decode())
def walk(x,path='$'):
 if isinstance(x,dict):
  yield path,x
  for k,v in x.items(): yield from walk(v,f'{path}.{k}')
 elif isinstance(x,list):
  for i,v in enumerate(x): yield from walk(v,f'{path}[{i}]')
def main():
 st,data=get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
 samples=[]
 for p,d in walk(data):
  if isinstance(d,dict) and d.get('mi') is not None and d.get('en') and not str(d.get('en')).startswith('('):
   samples.append({'path':p,'event':d})
   if len(samples)>=3: break
 out={'generated_at':datetime.now(timezone.utc).isoformat(),'status':st,'top_type':type(data).__name__,'top_keys':list(data.keys()) if isinstance(data,dict) else None,'samples':samples}
 pathlib.Path('feed').mkdir(exist_ok=True)
 pathlib.Path('feed/betflag-overview-shape-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':st,'samples':len(samples),'event_keys':[sorted(s['event'].keys()) for s in samples]},ensure_ascii=False))
if __name__=='__main__': main()
