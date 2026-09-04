#!/usr/bin/env python3
import json, pathlib, re, unicodedata
from collections import defaultdict
from datetime import datetime, timezone

FEED=pathlib.Path('feed')
SRC=FEED/'betflag-residential-current.json'
OUT=FEED/'betflag-player-market-coverage.json'
try:data=json.loads(SRC.read_text(encoding='utf-8'))
except Exception:data={'rows':[],'markets':{},'source_healthy':False}

def norm(v):
 s=unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower()
 return ' '.join(re.sub(r'[^a-z0-9]+',' ',s).split())

# Required families are semantic. A family is considered observed only when an actual BetFlag row is present.
FAMILIES={
 'ANYTIME':['marc','marcatore'],
 'SCORER_1H':['marcatore 1t','marcatore 1 tempo'],
 'SCORER_2H':['marcatore 2t','marcatore 2 tempo'],
 'SCORER_PLUS':['marcatore plus','marc plus'],
 'SCORER_OR_SUB':['marcatore o sostituto','marc o sost'],
 'FIRST_SCORER':['primo marcatore','1 marc'],
 'GOAL_OR_ASSIST':['gol o assist'],
 'ASSIST':['assist'],
 'GOAL_AND_ASSIST':['gol e assist'],
 'SHOTS':['tiri totali giocatore','u o tiri totali giocatore'],
 'SOT':['tiri in porta giocatore','u o tiri in porta giocatore'],
 'SHOTS_1H':['tiri 1t','tiri primo tempo'],
 'SOT_1H':['tiri in porta 1t','tiri in porta primo tempo'],
 'PLAYER_COMBO':['combo','assist o sostituto o marcatore','marcatore e']
}
rows=data.get('rows') or []
observed=defaultdict(set); markets=defaultdict(set)
for r in rows:
 if not isinstance(r,dict):continue
 m=norm(r.get('market')); fixture=str(r.get('match_market_id') or norm(r.get('match')))
 markets[fixture].add(m)
 for fam,needles in FAMILIES.items():
  if any(x in m for x in needles): observed[fixture].add(fam)
fixtures=[]
for fixture in sorted(markets):
 present=sorted(observed[fixture]); missing=sorted(set(FAMILIES)-set(present))
 fixtures.append({'fixture_identity':fixture,'market_names':sorted(x for x in markets[fixture] if x),'families_present':present,'families_not_observed':missing,'coverage_ratio':round(len(present)/len(FAMILIES),3),'status':'COMPLETE' if not missing else 'PARTIAL'})
market_targets={k:{'http_status':v.get('status'),'rows':v.get('rows'),'target':v.get('target')} for k,v in (data.get('markets') or {}).items() if isinstance(v,dict)}
payload={'schema':'betflag-player-market-coverage-v1','generated_at':datetime.now(timezone.utc).isoformat(),'source_healthy':bool(data.get('source_healthy')),'required_semantic_families':sorted(FAMILIES),'collector_targets':market_targets,'fixture_count':len(fixtures),'fixtures':fixtures,'rule':'NOT OBSERVED never means unavailable. A missing family requires recovery/discovery before a complete player-market scan can be claimed.'}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'source_healthy':payload['source_healthy'],'fixtures':len(fixtures),'partial':sum(x['status']=='PARTIAL' for x in fixtures)},ensure_ascii=False))
