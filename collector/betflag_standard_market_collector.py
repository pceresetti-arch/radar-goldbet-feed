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
 with urllib.request.urlopen(req,timeout=20) as r: return r.status,json.loads(r.read().decode())

def family(name):
 n=norm(name)
 if n=='1x2' or (n.startswith('1x2 ') and 'tempo' not in n): return '1X2'
 if n in ('u o','under over','over under','totale gol') or n.startswith('u o ') or 'under over' in n or 'over under' in n: return 'OVER_UNDER'
 if n in ('gg ng','goal no goal','gol no gol','btts') or 'gg ng' in n or 'goal no goal' in n or 'gol no gol' in n: return 'GOAL_NO_GOAL'
 if n in ('dc','doppia chance') or 'doppia chance' in n: return 'DOUBLE_CHANCE'
 if 'team total' in n or 'totale squadra' in n or 'gol squadra' in n: return 'TEAM_TOTAL'
 if 'handicap' in n: return 'HANDICAP'
 return None

def slots_from_lmtw(data):
 out=[]; seen=set()
 for tab in (data.get('lmtW') or []) if isinstance(data,dict) else []:
  if not isinstance(tab,dict): continue
  tb=tab.get('tbI'); tbn=tab.get('tbN')
  for item in tab.get('lotb') or []:
   if not isinstance(item,dict): continue
   ti=item.get('ti'); sn=item.get('sn'); fam=family(sn)
   if fam and tb is not None and ti is not None and (tb,ti) not in seen:
    seen.add((tb,ti)); out.append({'tab_id':tb,'tab_name':tbn,'slot_id':ti,'slot_name':sn,'family':fam})
 # Primary families first. Limit keeps the scheduled residential run bounded.
 rank={'1X2':0,'OVER_UNDER':1,'GOAL_NO_GOAL':2,'DOUBLE_CHANCE':3,'TEAM_TOTAL':4,'HANDICAP':5}
 out.sort(key=lambda x:(rank.get(x['family'],9),str(x.get('tab_name')),int(x.get('slot_id') or 0)))
 return out[:40]

def extract(data, slot, rows, markets_seen, all_market_names, dedupe):
 for ev in walk(data):
  if not isinstance(ev,dict) or ev.get('mi') is None or not ev.get('en') or str(ev.get('en')).startswith('('): continue
  mm=ev.get('mmkW') or {}; mks=mm.values() if isinstance(mm,dict) else (mm if isinstance(mm,list) else [])
  for mk in mks:
   if not isinstance(mk,dict): continue
   mn=mk.get('mn') or slot.get('slot_name'); all_market_names[str(mn)]=all_market_names.get(str(mn),0)+1
   fam=family(mn) or slot.get('family')
   if fam not in ('1X2','OVER_UNDER','GOAL_NO_GOAL','DOUBLE_CHANCE','TEAM_TOTAL','HANDICAP'): continue
   markets_seen[str(mn)]=markets_seen.get(str(mn),0)+1
   spd=mk.get('spd') or {}; spreads=spd.items() if isinstance(spd,dict) else enumerate(spd if isinstance(spd,list) else [])
   for line,spr in spreads:
    if not isinstance(spr,dict): continue
    real_line=spr.get('sl') if spr.get('sl') not in (None,'','0','0.0',0,0.0) else line
    if str(real_line) in ('0','0.0'): real_line=None
    for q in spr.get('asl') or []:
     odd=q.get('ov')
     if not isinstance(odd,(int,float)): continue
     key=(str(ev.get('mi')),str(mn),str(real_line),str(q.get('sn')),str(q.get('si')))
     if key in dedupe: continue
     dedupe.add(key)
     rows.append({'event_id':ev.get('ei'),'match_market_id':ev.get('mi'),'match':ev.get('en'),'match_start':ev.get('ed'),'family':fam,'market':mn,'line':real_line,'selection':q.get('sn'),'odd':odd,'selection_id':q.get('si'),'market_id':q.get('mi'),'odds_id':q.get('oi'),'betflag_tab_id':slot.get('tab_id'),'betflag_slot_id':slot.get('slot_id')})

def main():
 now=datetime.now(timezone.utc).isoformat(); rows=[]; markets_seen={}; all_market_names={}; status=None; errors=[]; slot_results=[]; dedupe=set()
 try:
  status,base=get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
  slots=slots_from_lmtw(base)
  # lmtW gives BetFlag's real tab/slot identifiers: no guessed market IDs.
  for slot in slots:
   try:
    st,data=get(f"{BASE}/getOverviewEventsAams/0/1/0/{AGG}/{slot['tab_id']}/{slot['slot_id']}/0?channelId=0")
    before=len(rows)
    if st==200: extract(data,slot,rows,markets_seen,all_market_names,dedupe)
    slot_results.append({**slot,'status':st,'rows':len(rows)-before})
   except Exception as e:
    errors.append({'slot':slot,'error':repr(e)})
    slot_results.append({**slot,'status':None,'rows':0,'error':repr(e)})
 except Exception as e:
  base=None; slots=[]; errors.append({'stage':'base','error':repr(e)})
 families={f:sum(1 for r in rows if r['family']==f) for f in sorted(set(r['family'] for r in rows))}
 out={'schema_version':'betflag-standard-markets-v2','generated_at':now,'source_class':'BETFLAG_AAMS_DIRECT','source_healthy':status==200 and len(rows)>0,'priority':['1X2','OVER_UNDER'],'secondary':['GOAL_NO_GOAL','TEAM_TOTAL','HANDICAP','DOUBLE_CHANCE'],'status':status,'slot_catalog':slots,'slot_results':slot_results,'markets_seen':markets_seen,'all_market_names_seen':dict(sorted(all_market_names.items(),key=lambda kv:(-kv[1],kv[0]))),'families':families,'rows':rows}
 if errors: out['errors']=errors
 p=pathlib.Path('feed'); p.mkdir(exist_ok=True)
 (p/'betflag-standard-current.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'source_healthy':out['source_healthy'],'slots':len(slots),'rows':len(rows),'families':families,'slot_results':slot_results},ensure_ascii=False))
if __name__=='__main__': main()
