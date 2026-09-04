#!/usr/bin/env python3
import json, pathlib, sys
from datetime import datetime, timezone

F=pathlib.Path('feed')
def load(name,default):
 try:return json.loads((F/name).read_text(encoding='utf-8'))
 except Exception:return default

lineups=load('lineups-current.json',{'matches':[]})
ready=load('deep-analysis-readiness.json',{'matches':[]})
coverage=load('betflag-player-market-coverage.json',{})
errors=[]; warnings=[]

for m in lineups.get('matches') or []:
 if not isinstance(m,dict):continue
 conf=m.get('xi_source_confidence')
 n=int(m.get('independent_xi_provider_count') or 0)
 if conf=='CERTIFIED_CROSSCHECK' and n<2:
  errors.append({'match':m.get('match'),'code':'FALSE_CROSS_CONFIRMED','providers':n})
 if conf=='CERTIFIED_PRIMARY' and not (m.get('official_primary_source') or str(m.get('source_class') or '').upper().startswith(('OFFICIAL_','CLUB_OFFICIAL','LEAGUE_OFFICIAL','FEDERATION_OFFICIAL')) or any((e or {}).get('official_primary_source') or str((e or {}).get('source_class') or '').upper().startswith(('OFFICIAL_','CLUB_OFFICIAL','LEAGUE_OFFICIAL','FEDERATION_OFFICIAL')) for e in (m.get('source_evidence') or []) if isinstance(e,dict))):
  errors.append({'match':m.get('match'),'code':'PRIMARY_WITHOUT_PRIMARY_EVIDENCE'})

for m in ready.get('matches') or []:
 if not isinstance(m,dict):continue
 if m.get('player_market_bet_ready') and m.get('betflag_market_completeness')!='COMPLETE':
  errors.append({'match':m.get('match'),'code':'PLAYER_BET_READY_WITH_INCOMPLETE_MARKETS'})
 if m.get('movement_based_claims_allowed') and str(m.get('movement_certification') or '') in {'CURRENT_ONLY','FIRST_SEEN_CURRENT','MISSING',''}:
  errors.append({'match':m.get('match'),'code':'MOVEMENT_CLAIM_WITHOUT_CERTIFICATE'})
 if m.get('player_lane_ready') and not m.get('player_context_matches_current_xi'):
  errors.append({'match':m.get('match'),'code':'PLAYER_CONTEXT_XI_MISMATCH'})
 if m.get('analysis_total_ready') and not m.get('betflag_standard_current_fresh'):
  errors.append({'match':m.get('match'),'code':'FULL_READY_WITH_STALE_CURRENT'})

if coverage and not coverage.get('source_healthy'):
 warnings.append({'code':'BETFLAG_PLAYER_COVERAGE_SOURCE_UNHEALTHY'})
partial=sum(1 for x in coverage.get('fixtures') or [] if x.get('status')!='COMPLETE')
if partial:warnings.append({'code':'PARTIAL_PLAYER_MARKET_FIXTURES','count':partial})

report={'schema':'radar-pipeline-validation-v1','generated_at':datetime.now(timezone.utc).isoformat(),'valid':not errors,'error_count':len(errors),'warning_count':len(warnings),'errors':errors,'warnings':warnings}
(F/'radar-pipeline-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
if errors: sys.exit(2)
