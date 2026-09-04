#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

worker = Path('worker/src/index.mjs')
patcher = Path('scripts/patch_betflag_dynamic_player_discovery.py')

if not worker.exists() or not patcher.exists():
    raise SystemExit('required source files missing')

# The patch is intentionally idempotent: CI may run it after the worker has
# already been persisted with the discovery layer.
subprocess.run([sys.executable, str(patcher)], check=True)
text = worker.read_text(encoding='utf-8')

required = [
    'RADAR_DYNAMIC_PLAYER_DISCOVERY_V1',
    'function playerMarketFamily(name)',
    'function playerSlotsFromLmtW(data)',
    'function mergePlayerTargets(seedTargets, discovered)',
    "discovery_source: 'DYNAMIC_LMTW'",
    'unknown_player_like_slots: discovery.unknown',
    'effective_target_count: effectiveTargets.length',
]
for token in required:
    if token not in text:
        raise SystemExit(f'missing dynamic discovery token: {token}')

# Protect the static compatibility seed: dynamic discovery extends it, never
# removes it, so known player markets remain available if lmtW is incomplete.
for seed in [
    "[2484, 13825, 'Marcatore Plus']",
    "[2484, 22884, 'Marc']",
    "[2484, 13820, 'Marcatore 1T']",
    "[2484, 13826, 'Marcatore 2T']",
    "[2484, 13823, 'Assist']",
    "[2484, 13824, 'Gol e Assist']",
]:
    if seed not in text:
        raise SystemExit(f'static compatibility seed lost: {seed}')

# Semantic coverage assertions are source-level on purpose: this test can run
# without calling BetFlag and still catches accidental classifier regressions.
semantic_needles = {
    'PRIMO_MARCATORE': "return 'PRIMO_MARCATORE';",
    'MARCATORE_1T': "return 'MARCATORE_1T';",
    'MARCATORE_2T': "return 'MARCATORE_2T';",
    'GOL_O_ASSIST': "return 'GOL_O_ASSIST';",
    'GOL_E_ASSIST': "return 'GOL_E_ASSIST';",
    'ASSIST': "return 'ASSIST';",
    'ASSIST_O_SOST_O_MARC_PLUS': "return 'ASSIST_O_SOST_O_MARC_PLUS';",
    'TIRI_TOTALI': "return 'TIRI_TOTALI';",
    'TIRI_IN_PORTA': "return 'TIRI_IN_PORTA';",
    'TIRI_TOTALI_1T': "return 'TIRI_TOTALI_1T';",
    'TIRI_IN_PORTA_1T': "return 'TIRI_IN_PORTA_1T';",
}
for family, needle in semantic_needles.items():
    if needle not in text:
        raise SystemExit(f'missing semantic family {family}')

# Basic syntax check when Node is available in CI.
try:
    subprocess.run(['node', '--check', str(worker)], check=True)
except FileNotFoundError:
    pass

print('dynamic BetFlag player discovery regression: PASS')
