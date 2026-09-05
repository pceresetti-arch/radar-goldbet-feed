#!/usr/bin/env python3
import json
import math
import pathlib
import re
import unicodedata
from datetime import datetime, timezone

ROOT = pathlib.Path('feed')
SRC = ROOT / 'player-synergy-position-current.json'
LINEUPS = ROOT / 'lineups-current.json'
OUT = ROOT / 'player-synergy-position-current.json'
SUMMARY = ROOT / 'player-synergy-position-current-summary.json'
NOW = datetime.now(timezone.utc)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(v)))


def shrink(delta, n_with, n_without, prior_matches=4.0):
    if delta is None:
        return None
    effective = min(float(n_with or 0), float(n_without or 0))
    weight = effective / (effective + prior_matches) if effective > 0 else 0.0
    return round(float(delta) * weight, 3)


def confidence(n_with, n_without):
    n_with = int(n_with or 0)
    n_without = int(n_without or 0)
    effective = min(n_with, n_without)
    if effective >= 5:
        return 'MEDIUM'
    if effective >= 3:
        return 'LOW_MEDIUM'
    return 'LOW'


def by_match(payload):
    out = {}
    for m in payload.get('matches') or []:
        if m.get('match_market_id') not in (None, ''):
            out[('id', str(m.get('match_market_id')))] = m
        if norm(m.get('match')):
            out[('name', norm(m.get('match')))] = m
    return out


def current_starter_maps(current):
    by_team = {}
    all_ids = set()
    all_names = set()
    for team in ((current.get('lineup') or {}).get('teams') or []):
        tid = str(team.get('team_id') or '')
        ids = set()
        names = set()
        for p in team.get('starters') or []:
            if p.get('id') not in (None, ''):
                ids.add(str(p.get('id')))
                all_ids.add(str(p.get('id')))
            if p.get('name'):
                names.add(norm(p.get('name')))
                all_names.add(norm(p.get('name')))
        by_team[tid] = {'ids': ids, 'names': names}
    return by_team, all_ids, all_names


def scorer_allocation(base, synergy_delta):
    """0-100 contextual scorer-allocation index. Modifier only; not a calibrated probability."""
    xg90 = safe_float(base.get('xg_per90')) or 0.0
    shots90 = safe_float(base.get('shots_per90')) or 0.0
    sot90 = safe_float(base.get('sot_per90')) or 0.0
    apps = int(base.get('appearances') or 0)
    starts = int(base.get('starts') or 0)
    minutes = int(base.get('minutes') or 0)
    avg_mins = minutes / max(1, apps)

    xg_component = clamp(xg90 / 0.70)
    shot_component = clamp(shots90 / 4.0)
    sot_component = clamp(sot90 / 2.0)
    minutes_component = clamp((avg_mins - 45.0) / 45.0)
    start_component = clamp(starts / max(1, apps))
    synergy_component = clamp(0.5 + (float(synergy_delta or 0.0) / 0.30))

    raw = (
        0.34 * xg_component +
        0.20 * shot_component +
        0.18 * sot_component +
        0.12 * minutes_component +
        0.08 * start_component +
        0.08 * synergy_component
    )
    return round(100.0 * clamp(raw), 1)


def route_market(base, allocation):
    xg90 = safe_float(base.get('xg_per90')) or 0.0
    shots90 = safe_float(base.get('shots_per90')) or 0.0
    sot90 = safe_float(base.get('sot_per90')) or 0.0
    if allocation >= 68 and xg90 >= 0.42:
        return 'SCORER_FIRST_THEN_PLAYER_MATRIX'
    if (shots90 >= 3.2 or sot90 >= 1.35) and xg90 < 0.42:
        return 'SHOTS_SOT_FIRST_THEN_SCORER'
    if allocation >= 55:
        return 'FULL_PLAYER_MATRIX_NO_SINGLE_MARKET_PRIORITY'
    return 'PLAYER_MATRIX_CAUTION_NO_STANDALONE_SCORER_EDGE'


synergy = load(SRC, {'matches': []})
lineups = load(LINEUPS, {'matches': []})
lookup = by_match(lineups)

for m in synergy.get('matches') or []:
    current = lookup.get(('id', str(m.get('match_market_id')))) or lookup.get(('name', norm(m.get('match')))) or {}
    lineup = current.get('lineup') or {}
    m['xi_fingerprint'] = lineup.get('xi_fingerprint') or lineup.get('xi_name_fingerprint')
    m['source_lineup_generated_at'] = lineups.get('generated_at')
    m['source_lineup_status'] = current.get('status')
    starter_maps, all_starter_ids, all_starter_names = current_starter_maps(current)

    starter_total = 0
    baseline_covered = 0
    pair_covered = 0
    multi_position_covered = 0
    player_gate_rows = []
    for team in m.get('teams') or []:
        tid = str(team.get('team_id') or '')
        current_team = starter_maps.get(tid, {'ids': set(), 'names': set()})
        for p in team.get('players') or []:
            starter_total += 1
            base = p.get('baseline') or {}
            apps = int(base.get('appearances') or 0)
            if apps >= 2:
                baseline_covered += 1

            pid = str(p.get('player_id') or '')
            pname = norm(p.get('player'))
            in_current_xi = bool((pid and pid in current_team['ids']) or (pname and pname in current_team['names']))
            p['current_xi_status'] = 'STARTER_CONFIRMED' if in_current_xi else 'NOT_IN_CURRENT_STARTING_XI'
            p['ordinary_player_market_eligible'] = in_current_xi
            p['plus_market_requires_explicit_substitution_rule_check'] = True

            bxg = safe_float(base.get('xg_per90'))
            enriched_positions = []
            for row in p.get('position_splits') or []:
                mins = int(row.get('minutes') or 0)
                apps_role = int(row.get('appearances') or 0)
                xg90 = safe_float(row.get('xg_per90'))
                delta = None if bxg is None or xg90 is None else round(xg90 - bxg, 3)
                weight = min(1.0, mins / 360.0)
                enriched_positions.append({
                    **row,
                    'delta_xg_per90_vs_baseline': delta,
                    'shrunk_delta_xg_per90': None if delta is None else round(delta * weight, 3),
                    'sample_weight': round(weight, 3),
                    'sample_confidence': 'MEDIUM' if mins >= 450 and apps_role >= 5 else ('LOW_MEDIUM' if mins >= 270 and apps_role >= 3 else 'LOW'),
                })
            enriched_positions.sort(key=lambda r: ((r.get('shrunk_delta_xg_per90') if r.get('shrunk_delta_xg_per90') is not None else -999), r.get('minutes') or 0), reverse=True)
            p['position_splits'] = enriched_positions
            p['best_supported_position'] = next((r for r in enriched_positions if (r.get('minutes') or 0) >= 180), enriched_positions[0] if enriched_positions else None)
            if len([r for r in enriched_positions if (r.get('minutes') or 0) >= 90]) >= 2:
                multi_position_covered += 1

            pairs = []
            current_pair_deltas = []
            for row in p.get('teammate_splits') or []:
                with_q = row.get('with_teammate') or {}
                without_q = row.get('without_teammate') or {}
                n_with = int(row.get('co_starts') or with_q.get('starts') or 0)
                n_without = int(without_q.get('appearances') or 0)
                delta = safe_float(row.get('delta_xg_per90'))
                co_target_minutes = int(with_q.get('minutes') or 0)
                qid = str(row.get('teammate_id') or '')
                qname = norm(row.get('teammate'))
                teammate_in_current_xi = bool((qid and qid in current_team['ids']) or (qname and qname in current_team['names']))
                shrunk = shrink(delta, n_with, n_without)
                usable = bool(n_with >= 2 and n_without >= 2 and delta is not None)
                if teammate_in_current_xi and usable and shrunk is not None:
                    current_pair_deltas.append(shrunk)
                pairs.append({
                    **row,
                    'co_starts': n_with,
                    'co_start_target_minutes': co_target_minutes,
                    'co_start_rate_vs_target_starts': round(n_with / max(1, int(base.get('starts') or 0)), 3),
                    'without_sample_matches': n_without,
                    'shrunk_delta_xg_per90': shrunk,
                    'sample_confidence': confidence(n_with, n_without),
                    'signal_usable_as_modifier': usable,
                    'teammate_in_current_xi': teammate_in_current_xi,
                })
            pairs.sort(key=lambda r: ((r.get('shrunk_delta_xg_per90') if r.get('shrunk_delta_xg_per90') is not None else -999), r.get('co_starts') or 0), reverse=True)
            p['teammate_splits'] = pairs
            p['best_supported_teammates'] = [r for r in pairs if r.get('signal_usable_as_modifier')][:3]
            p['current_xi_supported_teammates'] = [r for r in pairs if r.get('signal_usable_as_modifier') and r.get('teammate_in_current_xi')][:3]
            if pairs:
                pair_covered += 1

            current_synergy_delta = round(sum(current_pair_deltas) / len(current_pair_deltas), 3) if current_pair_deltas else 0.0
            allocation = scorer_allocation(base, current_synergy_delta)
            route = route_market(base, allocation)
            gate_signal = 'NEUTRAL'
            if in_current_xi and allocation >= 72 and current_synergy_delta >= 0.03:
                gate_signal = 'ALLOW_MODEST_GATE_RELAXATION_AFTER_PRICE_VALIDATION'
            elif allocation < 48 or current_synergy_delta <= -0.05:
                gate_signal = 'TIGHTEN_SCORER_GATE_OR_ROUTE_TO_SHOTS_SOT'

            p['scorer_allocation_context'] = {
                'score_0_100': allocation,
                'current_xi_teammate_delta_xg_per90_shrunk_mean': current_synergy_delta,
                'market_route': route,
                'adaptive_gate_signal': gate_signal,
                'calibration_status': 'CONTEXT_INDEX_NOT_PROBABILITY',
                'policy': 'Never create a BET alone. Combine with matchup, minutes, penalties/set pieces, exact BetFlag price and final probability/fair calculation.'
            }
            player_gate_rows.append({
                'player_id': p.get('player_id'),
                'player': p.get('player'),
                'team_id': team.get('team_id'),
                'team': team.get('team'),
                'current_xi_status': p['current_xi_status'],
                'ordinary_player_market_eligible': p['ordinary_player_market_eligible'],
                'scorer_allocation_score': allocation,
                'market_route': route,
                'adaptive_gate_signal': gate_signal,
            })

    coverage = round(baseline_covered / max(1, starter_total), 3)
    m['player_final_gate_context'] = {
        'ordinary_market_rule': 'BLOCK any ordinary scorer/shots/SOT/assist BET when selected player is not in the current certified starting XI unless the specific market explicitly permits bench players and the analysis models expected substitute minutes.',
        'plus_market_rule': 'For BetFlag Marcatore Plus or substitute-linked markets, verify exact bookmaker substitution settlement rules separately; starting-XI status alone is not sufficient settlement logic.',
        'current_starter_ids': sorted(all_starter_ids),
        'current_starter_names_normalized': sorted(all_starter_names),
        'players': player_gate_rows,
    }
    m['synergy_quality'] = {
        'starter_total': starter_total,
        'baseline_covered_players': baseline_covered,
        'baseline_coverage': coverage,
        'players_with_teammate_split': pair_covered,
        'players_with_multi_position_split': multi_position_covered,
        'ready': bool(starter_total >= 20 and coverage >= 0.60 and m.get('xi_fingerprint')),
        'policy': 'Teammate/position deltas are shrunk toward zero. LOW samples are context modifiers only and never standalone betting edges.'
    }

synergy['schema'] = 'radar-player-synergy-position-v3-scorer-allocation'
synergy['enriched_at'] = NOW.isoformat()
synergy['method_v3'] = 'Adds current-XI per-player eligibility, teammate-in-current-XI synergy, scorer allocation context, player-market routing and adaptive gate signals on top of shrinkage-aware position/teammate splits.'
synergy['policy'] = 'Context modifier only. Require current XI match. Small samples are shrunk toward zero and cannot create a standalone edge. Player-market route/gate signals are not calibrated probabilities.'
synergy['retrofit_2026_09_04'] = {
    'lessons': [
        'TEAM_ATTACKING_ENVIRONMENT_IS_NOT_PLAYER_SCORING_SHARE',
        'BLOCK_OR_REMODEL_PLAYER_IF_NOT_IN_CERTIFIED_CURRENT_XI',
        'ROUTE_HIGH_VOLUME_LOW_XG_PLAYERS_TOWARD_SHOTS_OR_SOT',
        'ALLOW_ONLY_MODEST_CONTEXTUAL_GATE_RELAXATION_FOR_STRONG_XI_ALIGNED_SCORER_ALLOCATION',
    ]
}
ROOT.mkdir(exist_ok=True)
OUT.write_text(json.dumps(synergy, ensure_ascii=False, indent=2), encoding='utf-8')

summary = {
    'schema': synergy['schema'],
    'generated_at': synergy.get('generated_at'),
    'enriched_at': synergy.get('enriched_at'),
    'target_count': len(synergy.get('matches') or []),
    'matches': [
        {
            'match_market_id': m.get('match_market_id'),
            'match': m.get('match'),
            'xi_fingerprint': m.get('xi_fingerprint'),
            'synergy_quality': m.get('synergy_quality'),
            'player_final_gate_context': m.get('player_final_gate_context'),
        }
        for m in synergy.get('matches') or []
    ],
}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
