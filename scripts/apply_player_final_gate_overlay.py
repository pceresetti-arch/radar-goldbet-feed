#!/usr/bin/env python3
import json
import pathlib
import re
import unicodedata
from datetime import datetime, timezone

ROOT = pathlib.Path('feed')
READY = ROOT / 'deep-analysis-readiness.json'
SUMMARY = ROOT / 'deep-analysis-readiness-summary.json'
SYN = ROOT / 'player-synergy-position-current.json'
NOW = datetime.now(timezone.utc)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def index(rows):
    out = {}
    for m in rows or []:
        if m.get('match_market_id') not in (None, ''):
            out[('id', str(m.get('match_market_id')))] = m
        n = norm(m.get('match'))
        if n:
            out[('name', n)] = m
    return out


def find(m, idx):
    return idx.get(('id', str(m.get('match_market_id')))) or idx.get(('name', norm(m.get('match')))) or {}


ready = load(READY, {'matches': []})
synergy = load(SYN, {'matches': []})
SYN_IDX = index(synergy.get('matches'))

for m in ready.get('matches') or []:
    s = find(m, SYN_IDX)
    gate = s.get('player_final_gate_context') if isinstance(s.get('player_final_gate_context'), dict) else {}
    players = gate.get('players') if isinstance(gate.get('players'), list) else []
    eligible = [p for p in players if p.get('ordinary_player_market_eligible')]
    blocked = [p for p in players if not p.get('ordinary_player_market_eligible')]
    scorer_first = [p for p in eligible if p.get('market_route') == 'SCORER_FIRST_THEN_PLAYER_MATRIX']
    volume_first = [p for p in eligible if p.get('market_route') == 'SHOTS_SOT_FIRST_THEN_SCORER']
    relax = [p for p in eligible if p.get('adaptive_gate_signal') == 'ALLOW_MODEST_GATE_RELAXATION_AFTER_PRICE_VALIDATION']
    tighten = [p for p in eligible if p.get('adaptive_gate_signal') == 'TIGHTEN_SCORER_GATE_OR_ROUTE_TO_SHOTS_SOT']

    m['per_player_final_gate_available'] = bool(gate and players)
    m['ordinary_player_market_requires_current_xi_player_match'] = True
    m['ordinary_player_market_block_if_player_not_current_starter'] = True
    m['plus_market_requires_separate_betflag_substitution_rule_check'] = True
    m['eligible_current_xi_player_count'] = len(eligible)
    m['blocked_nonstarter_player_count'] = len(blocked)
    m['scorer_first_candidate_count'] = len(scorer_first)
    m['shots_sot_first_candidate_count'] = len(volume_first)
    m['adaptive_gate_relax_candidate_count'] = len(relax)
    m['adaptive_gate_tighten_candidate_count'] = len(tighten)
    m['player_final_gate_context'] = gate

    warnings = list(m.get('warnings') or [])
    if m.get('player_lane_ready') and not gate:
        warnings.append('PLAYER_FINAL_GATE_CONTEXT_MISSING')
    if blocked:
        warnings.append('NONSTARTER_PLAYER_MARKETS_MUST_BE_BLOCKED_OR_EXPLICITLY_REMODELED')
    m['warnings'] = list(dict.fromkeys(warnings))

    if m.get('player_lane_ready') and gate:
        m['player_decision_contract'] = (
            'Before any player BET: selected player must match the current certified XI for ordinary markets; '
            'use scorer-allocation routing; validate minutes/role/penalties/set pieces; require exact current BetFlag price. '
            'Marcatore Plus/substitute-linked markets require separate settlement/substitution-rule validation.'
        )

ready['schema'] = str(ready.get('schema') or 'radar-deep-analysis-readiness') + '-player-final-gate-overlay-v1'
ready['player_final_gate_overlay_at'] = NOW.isoformat()
ready['player_final_gate_policy'] = {
    'ordinary_markets': 'Block player BET when selected player is not in current certified XI, unless that exact market explicitly supports bench-player participation and substitute minutes are modeled.',
    'plus_markets': 'Do not apply ordinary scorer settlement assumptions. Validate BetFlag Plus/substitute-linked rules separately.',
    'scorer_allocation': 'Team attacking strength cannot substitute for individual xG/shot/SOT share and XI-aligned teammate/position context.',
    'market_routing': 'High volume with weaker xG routes to shots/SOT first; strong xG plus allocation routes scorer first; otherwise evaluate full player matrix.',
    'adaptive_gate': 'Context signal only. Modest relaxation/tightening is allowed only after calibrated probability/fair and exact price validation; never create an edge from the signal alone.',
}
READY.write_text(json.dumps(ready, ensure_ascii=False, indent=2), encoding='utf-8')

summary = {k: v for k, v in ready.items() if k != 'matches'}
summary['ready_matches'] = [
    {
        'match_market_id': m.get('match_market_id'),
        'match': m.get('match'),
        'player_lane_ready': m.get('player_lane_ready'),
        'per_player_final_gate_available': m.get('per_player_final_gate_available'),
        'eligible_current_xi_player_count': m.get('eligible_current_xi_player_count'),
        'scorer_first_candidate_count': m.get('scorer_first_candidate_count'),
        'shots_sot_first_candidate_count': m.get('shots_sot_first_candidate_count'),
        'adaptive_gate_relax_candidate_count': m.get('adaptive_gate_relax_candidate_count'),
        'adaptive_gate_tighten_candidate_count': m.get('adaptive_gate_tighten_candidate_count'),
    }
    for m in ready.get('matches') or [] if m.get('readiness') == 'READY_DEEP_ANALYSIS'
]
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'schema': ready['schema'],
    'ready_matches': len(summary['ready_matches']),
    'player_final_gate_matches': sum(1 for m in ready.get('matches') or [] if m.get('per_player_final_gate_available')),
}, ensure_ascii=False, indent=2))
