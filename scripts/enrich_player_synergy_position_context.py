#!/usr/bin/env python3
import json
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


synergy = load(SRC, {'matches': []})
lineups = load(LINEUPS, {'matches': []})
lookup = by_match(lineups)

for m in synergy.get('matches') or []:
    current = lookup.get(('id', str(m.get('match_market_id')))) or lookup.get(('name', norm(m.get('match')))) or {}
    lineup = current.get('lineup') or {}
    m['xi_fingerprint'] = lineup.get('xi_fingerprint') or lineup.get('xi_name_fingerprint')
    m['source_lineup_generated_at'] = lineups.get('generated_at')
    m['source_lineup_status'] = current.get('status')

    starter_total = 0
    baseline_covered = 0
    pair_covered = 0
    multi_position_covered = 0
    for team in m.get('teams') or []:
        for p in team.get('players') or []:
            starter_total += 1
            base = p.get('baseline') or {}
            apps = int(base.get('appearances') or 0)
            if apps >= 2:
                baseline_covered += 1

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
            for row in p.get('teammate_splits') or []:
                with_q = row.get('with_teammate') or {}
                without_q = row.get('without_teammate') or {}
                n_with = int(row.get('co_starts') or with_q.get('starts') or 0)
                n_without = int(without_q.get('appearances') or 0)
                delta = safe_float(row.get('delta_xg_per90'))
                co_target_minutes = int(with_q.get('minutes') or 0)
                pairs.append({
                    **row,
                    'co_starts': n_with,
                    'co_start_target_minutes': co_target_minutes,
                    'co_start_rate_vs_target_starts': round(n_with / max(1, int(base.get('starts') or 0)), 3),
                    'without_sample_matches': n_without,
                    'shrunk_delta_xg_per90': shrink(delta, n_with, n_without),
                    'sample_confidence': confidence(n_with, n_without),
                    'signal_usable_as_modifier': bool(n_with >= 2 and n_without >= 2 and delta is not None),
                })
            pairs.sort(key=lambda r: ((r.get('shrunk_delta_xg_per90') if r.get('shrunk_delta_xg_per90') is not None else -999), r.get('co_starts') or 0), reverse=True)
            p['teammate_splits'] = pairs
            p['best_supported_teammates'] = [r for r in pairs if r.get('signal_usable_as_modifier')][:3]
            if pairs:
                pair_covered += 1

    coverage = round(baseline_covered / max(1, starter_total), 3)
    m['synergy_quality'] = {
        'starter_total': starter_total,
        'baseline_covered_players': baseline_covered,
        'baseline_coverage': coverage,
        'players_with_teammate_split': pair_covered,
        'players_with_multi_position_split': multi_position_covered,
        'ready': bool(starter_total >= 20 and coverage >= 0.60 and m.get('xi_fingerprint')),
        'policy': 'Teammate/position deltas are shrunk toward zero. LOW samples are context modifiers only and never standalone betting edges.'
    }

synergy['schema'] = 'radar-player-synergy-position-v2'
synergy['enriched_at'] = NOW.isoformat()
synergy['method_v2'] = 'Adds current-XI fingerprint, baseline coverage, co-start target minutes/rates, with-vs-without sample confidence, shrinkage toward zero, and supported position splits.'
synergy['policy'] = 'Context modifier only. Require current XI match. Small samples are shrunk toward zero and cannot create a standalone edge.'
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
        }
        for m in synergy.get('matches') or []
    ],
}
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
