import json, pathlib, re, unicodedata, hashlib
from datetime import datetime, timezone
from betflag_session_transport import BetFlagTransport

BASE='https://sportservice.betflag.it/api/sport/pregame'
AGG=1334500001
STATIC_TARGETS={
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

OPEN_FIELD_NAMES={
 'openingodd','openodd','initialodd','originalodd','startingodd','startodd',
 'oddopen','oddopening','oddinitial','oddoriginal'
}


def norm(v):
 s=unicodedata.normalize('NFD',str(v or ''))
 s=''.join(c for c in s if unicodedata.category(c)!='Mn').lower().replace('°','')
 return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())


def compact_key(v):
 return re.sub(r'[^a-z0-9]+','',norm(v))


def scalar_map(d):
 if not isinstance(d,dict): return {}
 return {str(k):v for k,v in d.items() if v is None or isinstance(v,(str,int,float,bool))}


def explicit_open_field(*dicts):
 for d in dicts:
  if not isinstance(d,dict): continue
  for k,v in d.items():
   if compact_key(k) in OPEN_FIELD_NAMES and isinstance(v,(int,float)) and v>1:
    return str(k),v
 return None,None


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


def player_market_family(name):
 n=norm(name)
 if not n: return None
 if ('marcatore' in n or n.startswith('marc ') or n=='marc') and ('1t' in n or 'primo tempo' in n): return 'MARCATORE_1T'
 if ('marcatore' in n or n.startswith('marc ') or n=='marc') and ('2t' in n or 'secondo tempo' in n): return 'MARCATORE_2T'
 if ('1 marcatore' in n or 'primo marcatore' in n) and ('sost' in n): return 'PRIMO_MARCATORE_O_SOSTITUTO'
 if '1 marcatore' in n or 'primo marcatore' in n: return 'PRIMO_MARCATORE'
 if ('assist' in n and 'sost' in n) and ('marc' in n or 'marcatore' in n): return 'ASSIST_O_SOST_O_MARC_PLUS'
 if ('marcatore' in n or n.startswith('marc ')) and 'sost' in n: return 'MARCATORE_O_SOSTITUTO'
 if 'assist' in n and 'sost' in n: return 'ASSIST_O_SOSTITUTO'
 if ('gol' in n or 'goal' in n) and 'assist' in n and (' o ' in f' {n} ' or 'oppure' in n): return 'GOL_O_ASSIST'
 if ('gol' in n or 'goal' in n) and 'assist' in n: return 'GOL_E_ASSIST'
 if 'assist' in n: return 'ASSIST'
 if ('tiri in porta' in n or 'shots on target' in n) and ('1t' in n or 'primo tempo' in n): return 'TIRI_IN_PORTA_1T'
 if ('tiri totali' in n or 'total shots' in n) and ('1t' in n or 'primo tempo' in n): return 'TIRI_TOTALI_1T'
 if 'tiri in porta' in n or 'shots on target' in n: return 'TIRI_IN_PORTA'
 if 'tiri totali' in n or 'total shots' in n: return 'TIRI_TOTALI'
 if 'parate' in n or 'saves' in n: return 'PARATE'
 if 'doppietta' in n: return 'DOPPIETTA'
 if 'tripletta' in n: return 'TRIPLETTA'
 if 'marcatore' in n and 'plus' in n: return 'MARCATORE_PLUS'
 if n in ('marc','marcatore') or 'anytime scorer' in n: return 'MARCATORE_ANYTIME'
 if 'marcatore' in n or 'marc o sost' in n or 'segna ' in n: return 'SCORER_OTHER'
 return None


def discover_player_targets(std):
 """Read BetFlag lmtW and keep all player/scorer tabs plus explicit player-like slots."""
 out=[]; unknown=[]; seen=set()
 for node in walk(std):
  tabs=node.get('lmtW') if isinstance(node,dict) else None
  if not isinstance(tabs,list): continue
  for tab in tabs:
   if not isinstance(tab,dict): continue
   tab_id=tab.get('tbI'); tab_name=str(tab.get('tbN') or '')
   tab_n=norm(tab_name)
   tab_like=bool(re.search(r'giocator|player|marcator|speciali giocatori|combo marc',tab_n))
   for item in tab.get('lotb') or []:
    if not isinstance(item,dict): continue
    slot=item.get('ti'); name=str(item.get('sn') or '').strip()
    if tab_id is None or slot is None or not name: continue
    family=player_market_family(name)
    name_like=bool(re.search(r'giocator|player|marcat|marc o sost|assist|tiri|parate|doppietta|tripletta|segna',norm(name)))
    if not (tab_like or family or name_like): continue
    key=(int(tab_id),int(slot))
    if key in seen: continue
    seen.add(key)
    row={'tab':int(tab_id),'slot':int(slot),'market':name,'tab_name':tab_name,'family':family,'discovery_source':'DYNAMIC_LMTW'}
    out.append(row)
    if family is None: unknown.append(row.copy())
 return out,unknown


def merge_targets(discovered):
 merged=[]; seen=set()
 for key,(tab,slot,name) in STATIC_TARGETS.items():
  ident=(int(tab),int(slot)); seen.add(ident)
  merged.append({'key':key,'tab':int(tab),'slot':int(slot),'market':name,'family':player_market_family(name),'discovery_source':'STATIC_SEED'})
 for row in discovered:
  ident=(row['tab'],row['slot'])
  if ident in seen: continue
  seen.add(ident)
  merged.append({'key':f"dynamic:{row['tab']}:{row['slot']}",**row})
 return merged


def extract_market(data,matches,target_name,diag):
 rows=[]
 for x in walk(data):
  en=str(x.get('en') or '')
  sn=norm(x.get('sn'))
  if 'ei' not in x or not en.startswith('(') or not sn.startswith('giocatori'): continue
  player=re.sub(r'^\([^)]+\)\s*','',en).strip()
  match=matches.get(str(x.get('mi')))
  matchname=(match or {}).get('en')
  matchstart=(match or {}).get('ed') or x.get('ed')
  mm=x.get('mmkW') or {}
  markets=mm.values() if isinstance(mm,dict) else mm
  for mk in markets:
   if norm(mk.get('mn'))!=norm(target_name): continue
   diag['market_keys'].update(str(k) for k in mk.keys())
   spd=mk.get('spd') or {}
   spreads=spd.items() if isinstance(spd,dict) else enumerate(spd)
   for line,spr in spreads:
    if not isinstance(spr,dict): continue
    diag['spread_keys'].update(str(k) for k in spr.keys())
    for q in spr.get('asl') or []:
     if q.get('ov') is None: continue
     diag['quote_keys'].update(str(k) for k in q.keys())
     if len(diag['quote_samples'])<12: diag['quote_samples'].append(scalar_map(q))
     open_field,open_odd=explicit_open_field(q,spr,mk)
     if open_field: diag['explicit_open_fields'][open_field]=diag['explicit_open_fields'].get(open_field,0)+1
     rows.append({
      'event_id':x.get('ei'),'player_event':en,'player':player,
      'match_market_id':x.get('mi'),'match':matchname,'match_start':matchstart,
      'market':mk.get('mn'),'market_family':player_market_family(mk.get('mn')),
      'line':None if str(line) in ('0','0.0') else line,
      'selection':q.get('sn'),'odd':q.get('ov'),'selection_id':q.get('si'),
      'market_id':q.get('mi'),'odds_id':q.get('oi'),
      'betflag_opening_odd':open_odd,'betflag_opening_odd_field':open_field
     })
 return rows


def main():
 now=datetime.now(timezone.utc).isoformat()
 diag={'quote_keys':set(),'market_keys':set(),'spread_keys':set(),'quote_samples':[],'explicit_open_fields':{}}
 result={
  'schema_version':'betflag-residential-feed-v4','generated_at':now,
  'source_class':'BETFLAG_AAMS_DIRECT',
  'source':'sportservice.betflag.it via residential self-hosted runner',
  'source_healthy':False,'standard_status':None,'markets':{},'rows':[]
 }
 client=BetFlagTransport(timeout=30)
 try:
  st,std=client.get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
  result['standard_status']=st
  matches=extract_matches(std)
  discovered,unknown=discover_player_targets(std) if st==200 else ([],[])
  targets=merge_targets(discovered)
  ok=0; dynamic_queried=0; dynamic_with_rows=0; dynamic_rows=0; active_dynamic=[]
  for target in targets:
   key=target['key']; tab=target['tab']; slot=target['slot']; name=target['market']; source=target['discovery_source']
   if source=='DYNAMIC_LMTW': dynamic_queried+=1
   try:
    status,data=client.get(f'{BASE}/getOverviewEventsAams/0/-1/0/{AGG}/{tab}/{slot}/0?channelId=0')
    rows=extract_market(data,matches,name,diag) if status==200 else []
    result['markets'][key]={'status':status,'rows':len(rows),'target':{'tab':tab,'slot':slot,'market':name,'family':target.get('family')},'discovery_source':source}
    result['rows'].extend(rows)
    if status==200: ok+=1
    if source=='DYNAMIC_LMTW' and rows:
     dynamic_with_rows+=1; dynamic_rows+=len(rows)
     active_dynamic.append({'tab':tab,'slot':slot,'market':name,'family':target.get('family'),'rows':len(rows)})
   except Exception as e:
    result['markets'][key]={'status':None,'rows':0,'error':repr(e),'target':{'tab':tab,'slot':slot,'market':name,'family':target.get('family')},'discovery_source':source}
  result['discovery']={
   'enabled':True,'source':'lmtW',
   'static_seed_count':len(STATIC_TARGETS),
   'dynamic_catalog_count':len(discovered),
   'dynamic_only_count':max(0,len(targets)-len(STATIC_TARGETS)),
   'effective_target_count':len(targets),
   'dynamic_targets_queried':dynamic_queried,
   'dynamic_targets_with_rows':dynamic_with_rows,
   'dynamic_rows':dynamic_rows,
   'unknown_player_like_slot_count':len(unknown),
   'unknown_player_like_slots':unknown[:100],
   'active_dynamic_targets':sorted(active_dynamic,key=lambda x:(-x['rows'],x['market']))[:100],
  }
  result['source_healthy']=st==200 and ok>0
 except Exception as e:
  result['error']=repr(e)
 finally:
  result['transport']=client.diagnostics()
  client.close()

 diagnostics={
  'schema_version':'betflag-opening-field-diagnostics-v1',
  'generated_at':now,'source_healthy':result.get('source_healthy'),
  'quote_keys':sorted(diag['quote_keys']),'market_keys':sorted(diag['market_keys']),
  'spread_keys':sorted(diag['spread_keys']),'explicit_open_fields':diag['explicit_open_fields'],
  'quote_samples':diag['quote_samples']
 }
 result['opening_field_diagnostics']=diagnostics
 canonical=json.dumps({'generated_at':result['generated_at'],'rows':result['rows']},sort_keys=True,ensure_ascii=False)
 result['sha256']=hashlib.sha256(canonical.encode()).hexdigest()
 p=pathlib.Path('feed'); p.mkdir(exist_ok=True)
 (p/'betflag-residential-current.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (p/'betflag-opening-field-diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
 hist=p/'betflag-residential-history'; hist.mkdir(exist_ok=True)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 (hist/f'{stamp}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({
  'source_healthy':result['source_healthy'],'rows':len(result['rows']),
  'generated_at':result['generated_at'],'transport':result.get('transport'),
  'discovery':result.get('discovery'),
  'explicit_open_fields':diagnostics['explicit_open_fields'],'quote_keys':diagnostics['quote_keys']
 },ensure_ascii=False))

if __name__=='__main__': main()
