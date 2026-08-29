import json, pathlib, re, unicodedata, hashlib, urllib.request
from datetime import datetime, timezone

BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001
TARGETS={
 'marcatore':(2484,22884,'Marc'),
 'marcatore 1t':(2484,13820,'Marcatore 1T'),
 'marcatore 2t':(2484,13826,'Marcatore 2T'),
 'marcatore plus':(2484,13825,'Marcatore Plus'),
 'marcatore o sostituto':(2484,19405,'Marcatore o Sostituto'),
 'assist':(2484,13823,'Assist'),
 'gol e assist':(2484,13824,'Gol e Assist'),
 'tiri in porta giocatore':(2484,13495,'U/O Tiri In Porta Giocatore'),
 'tiri totali giocatore':(2484,13496,'U/O Tiri Totali Giocatore'),
}
H={
 'Accept':'application/json,text/plain,*/*',
 'x-api-version':'1.0','X-Auth-Token':'','X-Brand':'3','X-IdCanale':'0',
 'Origin':'https://www.betflag.it','Referer':'https://www.betflag.it/',
 'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36'
}

def norm(v):
 s=unicodedata.normalize('NFD',str(v or ''))
 s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower().replace('°','')
 return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())

def get(url):
 req=urllib.request.Request(url,headers=H)
 with urllib.request.urlopen(req,timeout=30) as r:
  return r.status,json.loads(r.read().decode())

def walk(x):
 if isinstance(x,dict):
  yield x
  for v in x.values(): yield from walk(v)
 elif isinstance(x,list):
  for v in x: yield from walk(v)

def extract_matches(std):
 out={}
 for x in walk(std):
  if x.get('mi') is not None and x.get('en') and not str(x.get('en')).startswith('('):
   out[str(x['mi'])]=x
 return out

def extract_market(data,matches,target_name):
 rows=[]
 for x in walk(data):
  en=str(x.get('en') or '')
  sn=norm(x.get('sn'))
  if 'ei' not in x or not en.startswith('(') or not sn.startswith('giocatori'): continue
  player=re.sub(r'^\([^)]+\)\s*','',en).strip()
  match=matches.get(str(x.get('mi')))
  matchname=(match or {}).get('en')
  mm=x.get('mmkW') or {}
  markets=mm.values() if isinstance(mm,dict) else mm
  for mk in markets:
   if norm(mk.get('mn'))!=norm(target_name): continue
   spd=mk.get('spd') or {}
   spreads=spd.items() if isinstance(spd,dict) else enumerate(spd)
   for line,spr in spreads:
    for q in spr.get('asl') or []:
     if q.get('ov') is None: continue
     rows.append({
      'event_id':x.get('ei'),'player_event':en,'player':player,
      'match_market_id':x.get('mi'),'match':matchname,'match_start':x.get('ed'),
      'market':mk.get('mn'),'line':None if str(line) in ('0','0.0') else line,
      'selection':q.get('sn'),'odd':q.get('ov'),'selection_id':q.get('si'),
      'market_id':q.get('mi'),'odds_id':q.get('oi')
     })
 return rows

def main():
 now=datetime.now(timezone.utc).isoformat()
 result={'schema_version':'betflag-residential-feed-v1','generated_at':now,'source_class':'BETFLAG_AAMS_DIRECT','source':'sportservice.betflag.it via residential self-hosted runner','source_healthy':False,'standard_status':None,'markets':{},'rows':[]}
 try:
  st,std=get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
  result['standard_status']=st
  matches=extract_matches(std)
  ok=0
  for key,(tab,slot,name) in TARGETS.items():
   try:
    status,data=get(f'{BASE}/getOverviewEventsAams/0/-1/0/{AGG}/{tab}/{slot}/0?channelId=0')
    rows=extract_market(data,matches,name) if status==200 else []
    result['markets'][key]={'status':status,'rows':len(rows),'target':{'tab':tab,'slot':slot,'market':name}}
    result['rows'].extend(rows)
    if status==200: ok+=1
   except Exception as e:
    result['markets'][key]={'status':None,'rows':0,'error':repr(e),'target':{'tab':tab,'slot':slot,'market':name}}
  result['source_healthy']=st==200 and ok>0
 except Exception as e:
  result['error']=repr(e)

 canonical=json.dumps({'generated_at':result['generated_at'],'rows':result['rows']},sort_keys=True,ensure_ascii=False)
 result['sha256']=hashlib.sha256(canonical.encode()).hexdigest()
 p=pathlib.Path('feed'); p.mkdir(exist_ok=True)
 (p/'betflag-residential-current.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 hist=p/'betflag-residential-history'; hist.mkdir(exist_ok=True)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 (hist/f'{stamp}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'source_healthy':result['source_healthy'],'rows':len(result['rows']),'generated_at':result['generated_at']},ensure_ascii=False))

if __name__=='__main__': main()
