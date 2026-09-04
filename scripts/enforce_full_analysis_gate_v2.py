#!/usr/bin/env python3
import json
from pathlib import Path

FEED = Path('feed')
READINESS = FEED / 'deep-analysis-readiness.json'
SUMMARY = FEED / 'deep-analysis-readiness-summary.json'

ALLOWED_XI = {'CERTIFIED_PRIMARY', 'CERTIFIED_CROSSCHECK'}
ALLOWED_MOVEMENT = {
    'TRUE_OPEN_CURRENT_T30', 'TRUE_OPEN_CURRENT',
    'OPEN_RADAR_CURRENT_T30', 'OPEN_RADAR_CURRENT',
    'FIRST_SEEN_CURRENT', 'CURRENT_ONLY', 'MISSING'
}


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def unique(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out

payload = load(READINESS, {'matches': []})
rows = payload.get('matches') or payload.get('fixtures') or []
if not isinstance(rows, list):
    rows = []

stats = {
    'checked': 0,
    'full_ready': 0,
    'player_bet_ready': 0,
    'blocked_xi': 0,
    'blocked_betflag_current': 0,
    'blocked_player_matrix': 0,
    'blocked_post_xi_delta': 0,
    'movement_missing': 0,
}

for row in rows:
    if not isinstance(row, dict):
        continue
    stats['checked'] += 1
    hard = list(row.get('hard_blocks') or [])
    warnings = list(row.get('warnings') or [])

    xi = row.get('xi_source_confidence') or 'MISSING'
    xi_ok = xi in ALLOWED_XI and bool(row.get('official_standard_xi')) and bool(row.get('lineup_ready'))
    if not xi_ok:
        hard.append('XI_NOT_CERTIFIED_PRIMARY_OR_CROSSCHECK')
        stats['blocked_xi'] += 1

    current_ok = bool(row.get('betflag_standard_ready')) and bool(row.get('betflag_standard_current_fresh'))
    if not current_ok:
        hard.append('BETFLAG_EXACT_CURRENT_NOT_READY')
        stats['blocked_betflag_current'] += 1

    movement = row.get('movement_certification') or 'MISSING'
    if movement not in ALLOWED_MOVEMENT:
        movement = 'MISSING'
        row['movement_certification'] = movement
    if movement == 'MISSING':
        warnings.append('MOVEMENT_AUDIT_MISSING')
        stats['movement_missing'] += 1

    post_xi_ok = bool(row.get('post_xi_delta_ready', True))
    if not post_xi_ok:
        hard.append('POST_XI_DELTA_NOT_RECOMPUTED')
        stats['blocked_post_xi_delta'] += 1

    market_complete = row.get('betflag_market_completeness') == 'COMPLETE'
    player_props_ready = bool(row.get('player_props_ready'))
    player_context_ready = bool(row.get('player_context_matches_current_xi')) and bool(row.get('player_context_fresh'))
    player_bet_ready = xi_ok and current_ok and post_xi_ok and market_complete and player_props_ready and player_context_ready

    if player_props_ready and not market_complete:
        hard.append('BETFLAG_PLAYER_MATRIX_INCOMPLETE')
        stats['blocked_player_matrix'] += 1
    if player_props_ready and not player_context_ready:
        hard.append('PLAYER_CONTEXT_NOT_SYNCED_TO_CURRENT_XI')

    tactical_ok = bool(row.get('tactical_ready'))
    if not tactical_ok:
        hard.append('TACTICAL_LAYER_NOT_READY')

    row['hard_blocks'] = unique(hard)
    row['warnings'] = unique(warnings)
    row['player_market_bet_ready'] = bool(player_bet_ready and not row['hard_blocks'])
    row['analysis_total_ready'] = bool(xi_ok and current_ok and post_xi_ok and tactical_ok and not row['hard_blocks'])

    if row['analysis_total_ready']:
        stats['full_ready'] += 1
    if row['player_market_bet_ready']:
        stats['player_bet_ready'] += 1

    if row['hard_blocks']:
        row['decision_mode'] = 'ATTESA_DATA_GAP'
        row['readiness'] = row['hard_blocks'][0]
    elif movement in {'CURRENT_ONLY', 'FIRST_SEEN_CURRENT'}:
        row['decision_mode'] = 'BET_PRICE_ONLY_ELIGIBLE'
    else:
        row['decision_mode'] = 'FULL_ELIGIBLE'

    row['readiness_strip_v2'] = ' | '.join([
        f"Fixture {'OK' if row.get('betflag_fixture_mapped') else 'BLOCK'}",
        f"XI {'OK' if xi_ok else 'BLOCK'} {xi}",
        f"BetFlag CURRENT {'OK' if current_ok else 'BLOCK'}",
        f"Props {'OK' if market_complete and player_props_ready else 'WARN'} {row.get('betflag_market_completeness','MISSING')}",
        f"Movement {'OK' if movement not in {'MISSING','CURRENT_ONLY','FIRST_SEEN_CURRENT'} else 'WARN'} {movement}",
        f"Tactical {'OK' if tactical_ok else 'BLOCK'}",
        f"Player context {'OK' if player_context_ready else 'WARN'}",
        '1H model REQUIRED_AT_ANALYSIS',
        'Price gate REQUIRED_AT_FINAL_GATE',
    ])

payload['matches'] = rows
payload['enforcement'] = {
    'contract': 'RADAR_FULL_ANALYSIS_GATE_V2 + RADAR_DATA_ACQUISITION_HARDENING_V1',
    'strict_xi_evidence': True,
    'exact_betflag_current_required': True,
    'complete_player_matrix_required_for_player_bet': True,
    'post_xi_recompute_required': True,
    'movement_missing_never_silenced': True,
    'stats': stats,
}
READINESS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

summary = load(SUMMARY, {})
summary['gate_v2_enforcement'] = payload['enforcement']
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(payload['enforcement'], ensure_ascii=False))
