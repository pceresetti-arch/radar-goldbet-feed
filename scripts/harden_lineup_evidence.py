#!/usr/bin/env python3
import hashlib, json, pathlib, re, unicodedata
from datetime import datetime, timezone

P=pathlib.Path('feed/lineups-current.json')
CACHE=pathlib.Path('feed/lineups-last-certified.json')
if not P.exists(): raise SystemExit('lineups-current.json missing')
now=datetime.now(timezone.utc).isoformat()
data=json.loads(P.read_text(encoding='utf-8'))
try: cache=json.loads(CACHE.read_text(encoding='utf-8'))
except Exception: cache={'matches':{}}
last=cache.setdefault('matches',{})

PRIMARY={'OFFICIAL_CLUB','CLUB_OFFICIAL','OFFICIAL_LEAGUE','LEAGUE_OFFICIAL','OFFICIAL_FEDERATION','FEDERATION_OFFICIAL'}

def norm(v):
 s=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower()
 return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())

def key(m): return str(m.get('match_market_id') or m.get('match_event_id') or norm(m.get('match')))

def names_fp(m):
 teams=((m.get('lineup') or {}).get('teams') or [])
 if len(teams)<2:return None
 parts=[]
 for t in teams[:2]:
  names=sorted(norm((p or {}).get('name')) for p in (t.get('starters') or []) if (p or {}).get('name'))
  if len(names)!=11:return None
  parts.append(','.join(names))
 return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:20]

def evidence_rows(m,fp):
 out=[]
 raw=m.get('source_evidence')
 if isinstance(raw,list):
  for e in raw:
   if isinstance(e,dict): out.append(dict(e))
 elif isinstance(raw,dict):
  for provider,meta in raw.items():
   if provider in {'polled_at','cross_source_agreement'}: continue
   if isinstance(meta,dict): out.append({'provider':meta.get('provider') or provider,**meta})
 source=str(m.get('source') or '').strip()
 for provider in re.split(r'\s*\+\s*',source):
  if provider and not any(norm(e.get('provider'))==norm(provider) for e in out):
   out.append({'provider':provider,'captured_at':m.get('confirmed_at') or data.get('generated_at'),'xi_fingerprint':fp})
 for e in out:
  e.setdefault('captured_at',m.get('confirmed_at') or data.get('generated_at'))
  e.setdefault('xi_fingerprint',fp)
 return out

counts={}
for m in data.get('matches') or []:
 if not isinstance(m,dict):continue
 fp=names_fp(m)
 if fp:
  (m.get('lineup') or {})['xi_name_fingerprint']=fp
 ev=evidence_rows(m,fp)
 # Independent providers only; aliases from the same provider do not count twice.
 providers={norm(e.get('provider')) for e in ev if e.get('provider') and e.get('xi_fingerprint')==fp}
 source_class=str(m.get('source_class') or m.get('source_type') or '').upper()
 primary=source_class in PRIMARY or bool(m.get('official_primary_source')) or any(str(e.get('source_class') or '').upper() in PRIMARY or e.get('official_primary_source') for e in ev)
 ln=m.get('lineup') or {}
 standard=bool(ln.get('confirmed')) and bool(ln.get('complete_11v11')) and str(ln.get('lineup_type') or '').lower()=='standard' and not bool(ln.get('historical_reference'))
 if standard and primary:
  conf='CERTIFIED_PRIMARY'; status='SOURCE_CONFIRMED'
 elif standard and len(providers)>=2:
  conf='CERTIFIED_CROSSCHECK'; status='CROSS_CONFIRMED'
 elif standard:
  conf='PROVIDER_ONLY'; status='SOURCE_CONFIRMED'
 elif bool(ln.get('historical_reference')):
  conf='PREDICTED'; status=m.get('status') or 'REFERENCE_PREVIOUS_XI'
 else:
  conf='MISSING'; status=m.get('status') or 'NOT_AVAILABLE'
 # Never let a weaker refresh erase the last certified XI; keep it separately for audit only.
 k=key(m)
 if conf.startswith('CERTIFIED') and fp:
  last[k]={'captured_at':now,'match':m.get('match'),'xi_fingerprint':fp,'lineup':ln,'source_evidence':ev,'xi_source_confidence':conf}
 elif k in last:
  m['last_certified_xi_available']=True
  m['last_certified_xi_fingerprint']=last[k].get('xi_fingerprint')
 m['source_evidence']=ev
 m['independent_xi_provider_count']=len(providers)
 m['xi_source_confidence']=conf
 m['status']=status
 counts[conf]=counts.get(conf,0)+1

data['lineup_hardening']={'schema':'radar-lineup-evidence-v2','generated_at':now,'rule':'primary official source OR >=2 independent providers matching canonical starter-name fingerprint','counts':counts}
P.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
cache['generated_at']=now
CACHE.write_text(json.dumps(cache,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(data['lineup_hardening'],ensure_ascii=False))
