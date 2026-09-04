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
synergy=load('player-synergy-position-current.json',{'matches':[]})
errors=[]; warnings=[]

schema=str(ready.get('schema') or '')
if schema.startswith(('radar-deep-analysis-readiness-v3','radar-deep-analysis-readiness-v4')) and not str(synergy.get('schema') or '').startswith('radar-player-synergy-position-v2'):
 warnings.append({'code':'SYNERGY_V2_ARTIFACT_MISSING_OR_NOT_ENRICHED','schema':synergy.get('schema')})

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
 player_ready=bool(m.get('player_market_bet_ready'))
 combo_ready=bool(m.get('combo_market_bet_ready'))
 explicit_player=('betflag_player_coverage_complete' in m)
 player_coverage=bool(m.get('betflag_player_coverage_complete')) if explicit_player else m.get('betflag_market_completeness')=='COMPLETE'
 combo_coverage=bool(m.get('betflag_combo_coverage_complete'))
 player_count=int(m.get('player_count') or m.get('player_quote_count') or 0)
 combo_count=int(m.get('combo_quote_count') or 0)

 if player_ready and not player_coverage:
  errors.append({'match':m.get('match'),'code':'PLAYER_BET_READY_WITHOUT_EXPLICIT_PLAYER_COVERAGE'})
 if player_ready and player_count<=0:
  errors.append({'match':m.get('match'),'code':'PLAYER_BET_READY_WITH_ZERO_PLAYER_ROWS'})
 if combo_ready and not player_ready:
  errors.append({'match':m.get('match'),'code':'COMBO_BET_READY_WITHOUT_PLAYER_LANE'})
 if combo_ready and not combo_coverage:
  errors.append({'match':m.get('match'),'code':'COMBO_BET_READY_WITHOUT_FIXTURE_COMBO_COVERAGE'})
 if combo_ready and combo_count<=0:
  errors.append({'match':m.get('match'),'code':'COMBO_BET_READY_WITH_ZERO_COMBO_ROWS'})
 if m.get('movement_based_claims_allowed') and str(m.get('movement_certification') or '') in {'CURRENT_ONLY','FIRST_SEEN_CURRENT','MISSING',''}:
  errors.append({'match':m.get('match'),'code':'MOVEMENT_CLAIM_WITHOUT_CERTIFICATE'})
 if m.get('player_lane_ready') and not m.get('player_context_matches_current_xi'):
  errors.append({'match':m.get('match'),'code':'PLAYER_CONTEXT_XI_MISMATCH'})
 if player_ready and not m.get('player_synergy_position_ready'):
  errors.append({'match':m.get('match'),'code':'PLAYER_BET_READY_WITHOUT_SYNERGY_POSITION'})
 if player_ready and not m.get('player_synergy_position_xi_match'):
  errors.append({'match':m.get('match'),'code':'PLAYER_BET_READY_WITH_SYNERGY_XI_MISMATCH'})
 if player_ready and float(m.get('player_synergy_position_coverage') or 0)<0.60:
  errors.append({'match':m.get('match'),'code':'PLAYER_BET_READY_WITH_LOW_SYNERGY_COVERAGE','coverage':m.get('player_synergy_position_coverage')})
 if m.get('analysis_total_ready') and not m.get('betflag_standard_current_fresh'):
  errors.append({'match':m.get('match'),'code':'FULL_READY_WITH_STALE_CURRENT'})

if coverage and not coverage.get('source_healthy'):
 warnings.append({'code':'BETFLAG_PLAYER_COVERAGE_SOURCE_UNHEALTHY'})
partial=sum(1 for x in coverage.get('fixtures') or [] if x.get('status')!='COMPLETE')
if partial:warnings.append({'code':'PARTIAL_PLAYER_MARKET_FIXTURES','count':partial})

report={'schema':'radar-pipeline-validation-v3-player-combo-coverage','generated_at':datetime.now(timezone.utc).isoformat(),'valid':not errors,'error_count':len(errors),'warning_count':len(warnings),'errors':errors,'warnings':warnings}
(F/'radar-pipeline-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
if errors: sys.exit(2)
