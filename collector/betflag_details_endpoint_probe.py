import json, pathlib, urllib.request, urllib.error
from datetime import datetime, timezone

BASE='https://sportservice.betflag.it/api/sport/pregame'
H={'Accept':'application/json,text/plain,*/*','x-api-version':'1.0','X-Auth-Token':'','X-Brand':'3','X-IdCanale':'0','Origin':'https://www.betflag.it','Referer':'https://www.betflag.it/','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'}
AGG=1334500001
EI='16045531'
MI='36351.3174'

def fetch(path):
 url=BASE+path
 req=urllib.request.Request(url,headers=H)
 try:
  with urllib.request.urlopen(req,timeout=20) as r:
   raw=r.read().decode(errors='replace')
   try: data=json.loads(raw)
   except Exception: data=None
   return {'path':path,'status':r.status,'content_type':r.headers.get('content-type'),'length':len(raw),'sample':raw[:300],'json':data}
 except urllib.error.HTTPError as e:
  raw=e.read().decode(errors='replace') if e.fp else ''
  return {'path':path,'status':e.code,'length':len(raw),'sample':raw[:300]}
 except Exception as e:
  return {'path':path,'status':None,'error':repr(e)}

def names(x,out):
 if isinstance(x,dict):
  for k,v in x.items():
   if k in ('mn','sn','n','name') and isinstance(v,str): out.add(v)
   names(v,out)
 elif isinstance(x,list):
  for v in x: names(v,out)

def main():
 patterns=[
  f'/getDetailsEventAams/{EI}?channelId=0',
  f'/getDetailsEventAams/{MI}?channelId=0',
  f'/getDetailsEventAams/0/{EI}?channelId=0',
  f'/getDetailsEventAams/0/{MI}?channelId=0',
  f'/getDetailsEventAams/0/1/0/{AGG}/{EI}/0/0?channelId=0',
  f'/getDetailsEventAams/0/1/0/{AGG}/{MI}/0/0?channelId=0',
  f'/getDetailsEventAams/0/-1/0/{AGG}/{EI}/0/0?channelId=0',
  f'/getDetailsEventAams/0/-1/0/{AGG}/{MI}/0/0?channelId=0',
  f'/getDetailsEventAams/0/1/0/{EI}/0/0/0?channelId=0',
  f'/getDetailsEventAams/0/1/0/{MI}/0/0/0?channelId=0',
  f'/getDetailsEventAams/{AGG}/{EI}?channelId=0',
  f'/getDetailsEventAams/{AGG}/{MI}?channelId=0'
 ]
 results=[]
 for p in patterns:
  r=fetch(p); ns=set();
  if r.get('json') is not None: names(r['json'],ns)
  r['names']=sorted(ns)[:100]; r.pop('json',None); results.append(r)
 out={'generated_at':datetime.now(timezone.utc).isoformat(),'event_id':EI,'match_market_id':MI,'results':results}
 pathlib.Path('feed').mkdir(exist_ok=True)
 pathlib.Path('feed/betflag-details-endpoint-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'results':[{'path':r['path'],'status':r['status'],'length':r.get('length'),'names':r.get('names',[])[:8]} for r in results]},ensure_ascii=False))
if __name__=='__main__': main()
