import json, pathlib, re, urllib.request
from datetime import datetime, timezone

BASE='https://sportservice.betflag.it/api/sport/pregame'
H={'Accept':'application/json,text/plain,*/*','x-api-version':'1.0','X-Auth-Token':'','X-Brand':'3','X-IdCanale':'0','Origin':'https://www.betflag.it','Referer':'https://www.betflag.it/','User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'}
TERMS=('over','under','goal','gol','doppia','chance','handicap','totale','total','1x2','esito')

def get(url):
 req=urllib.request.Request(url,headers=H)
 with urllib.request.urlopen(req,timeout=30) as r: return r.status,json.loads(r.read().decode())

def walk(x,path='$'):
 if isinstance(x,dict):
  yield path,x
  for k,v in x.items(): yield from walk(v,f'{path}.{k}')
 elif isinstance(x,list):
  for i,v in enumerate(x): yield from walk(v,f'{path}[{i}]')

def main():
 now=datetime.now(timezone.utc).isoformat(); out={'generated_at':now,'source':'BETFLAG_AAMS_DIRECT','status':None,'matches':[]}
 try:
  st,data=get(f'{BASE}/getProgram?channelId=0'); out['status']=st
  seen=set()
  for path,d in walk(data):
   scalars={str(k):v for k,v in d.items() if isinstance(v,(str,int,float,bool)) or v is None}
   text=' '.join(str(v).lower() for v in scalars.values() if isinstance(v,str))
   if any(t in text for t in TERMS):
    sig=json.dumps(scalars,sort_keys=True,ensure_ascii=False)
    if sig in seen: continue
    seen.add(sig); out['matches'].append({'path':path,'fields':scalars})
  out['source_healthy']=st==200
 except Exception as e:
  out['source_healthy']=False; out['error']=repr(e)
 p=pathlib.Path('feed'); p.mkdir(exist_ok=True)
 (p/'betflag-market-catalog-probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'source_healthy':out.get('source_healthy'),'status':out.get('status'),'matches':len(out['matches'])},ensure_ascii=False))
if __name__=='__main__': main()
