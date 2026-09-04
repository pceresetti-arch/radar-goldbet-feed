#!/usr/bin/env python3
import json
import pathlib
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone

ROOT = pathlib.Path('feed')
NOW = datetime.now(timezone.utc)


def load(name, default):
    p = ROOT / name
    try:
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:
        return default


def dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def age_minutes(s):
    d = dt(s)
    return None if not d else round((NOW - d).total_seconds() / 60.0, 1)


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def index(rows):
    out = {}
    for m in rows or []:
        if m.get('match_market_id') not in (None, ''):
            out[('id', str(m.get('match_market_id')))] = m
        if norm(m.get('match')):
            out[('name', norm(m.get('match')))] = m
    return out


def find(m, idx):
    return idx.get(('id', str(m.get('match_market_id')))) or idx.get(('name', norm(m.get('match')))) or {}


# Rebuild the canonical V2 gate first so this file is always the final consumer,
# not a stale post-processor of an older readiness snapshot.
cp = subprocess.run([sys.executable, 'scripts/build_deep_analysis_readiness.py'], check=False)
if cp.returncode != 0:
    raise SystemExit(cp.returncode)

base = load('deep-analysis-readiness.json', {'matches': []})
synergy = load('player-synergy-position-current.json', {'matches': []})
SYN = index(synergy.get('matches'))
synergy_age = age_minutes(synergy.get('enriched_at') or synergy.get('generated_at'))
synergy_fresh = synergy_age is not None and synergy_age <= 45

ready_player = []
for m in base.get('matches') or []:
    s = find(m, SYN)
    quality = s.get('synergy_quality') if isinstance(s.get('synergy_quality'), dict) else {}
    current_fp = m.get('xi_fingerprint')
    synergy_fp = s.get('xi_fingerprint')
    xi_match = bool(current_fp and synergy_fp and current_fp == synergy_fp)
    coverage = float(quality.get('baseline_coverage') or 0.0)
    context_present = bool(s)
    synergy_ready = bool(context_present and synergy_fresh and xi_match and quality.get('ready') and coverage >= 0.60)

    was_player_lane_ready = bool(m.get('player_lane_ready'))
    player_lane_ready = bool(was_player_lane_ready and synergy_ready)
    m['player_synergy_position_available'] = context_present
    m['player_synergy_position_fresh'] = synergy_fresh
    m['player_synergy_position_age_minutes'] = synergy_age
    m['player_synergy_position_xi_match'] = xi_match
    m['player_synergy_position_ready'] = synergy_ready
    m['player_synergy_position_coverage'] = coverage
    m['player_synergy_position_quality'] = quality
    m['player_synergy_position_schema'] = synergy.get('schema')
    m['player_lane_ready_pre_synergy'] = was_player_lane_ready
    m['player_lane_ready'] = player_lane_ready
    m['player_market_bet_ready'] = player_lane_ready

    warnings = list(m.get('warnings') or [])
    if m.get('player_props_ready') and not context_present:
        warnings.append('PLAYER_SYNERGY_POSITION_CONTEXT_MISSING')
    elif m.get('player_props_ready') and not synergy_fresh:
        warnings.append('PLAYER_SYNERGY_POSITION_CONTEXT_STALE')
    elif m.get('player_props_ready') and not xi_match:
        warnings.append('PLAYER_SYNERGY_POSITION_CONTEXT_XI_MISMATCH')
    elif m.get('player_props_ready') and not quality.get('ready'):
        warnings.append('PLAYER_SYNERGY_POSITION_CONTEXT_LOW_COVERAGE')
    m['warnings'] = list(dict.fromkeys(warnings))

    if m.get('analysis_total_ready'):
        if player_lane_ready:
            m['analysis_scope'] = 'FULL_WITH_PLAYER_MATCHUP_SYNERGY_POSITION_CONTEXT_EXACT_BETFLAG_PRICE_REQUIRED'
        elif m.get('player_props_ready'):
            m['analysis_scope'] = 'STANDARD_READY_PLAYER_CONTEXT_OR_SYNERGY_PENDING'

    strip = str(m.get('readiness_strip') or '')
    extra = f'Synergy/position {"OK" if synergy_ready else "WARN"} cov={coverage:.2f}'
    if extra not in strip:
        m['readiness_strip'] = (strip + ' | ' + extra).strip(' |')
    if player_lane_ready:
        ready_player.append(m)

base['schema'] = 'radar-deep-analysis-readiness-v3-synergy-position'
base['generated_at_v3'] = NOW.isoformat()
base['contract'] = (
    str(base.get('contract') or '') +
    ' V3: player-market BET readiness additionally requires fresh Player Synergy & Position Context aligned to the current XI fingerprint with >=60% recent-history baseline coverage. Teammate/position deltas are shrinkage context modifiers only.'
)
base['synergy_position_policy'] = {
    'input': 'feed/player-synergy-position-current.json',
    'max_age_minutes': 45,
    'minimum_baseline_coverage': 0.60,
    'require_current_xi_fingerprint_match': True,
    'small_sample_policy': 'shrink deltas toward zero; LOW samples cannot create standalone edge',
    'standard_market_gate_effect': 'none; only player-market BET readiness is blocked',
}
base.setdefault('input_freshness_minutes', {})['player_synergy_position'] = synergy_age
base.setdefault('freshness_limits_minutes', {})['player_synergy_position'] = 45
base['player_lane_ready_count'] = len(ready_player)
base['player_lane_ready_matches'] = ready_player

ROOT.mkdir(exist_ok=True)
(ROOT / 'deep-analysis-readiness.json').write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding='utf-8')
summary = {k: v for k, v in base.items() if k != 'matches'}
summary['ready_matches'] = [
    {k: m.get(k) for k in (
        'match_market_id','match','league','start_time','minutes_to_start','readiness','analysis_scope','decision_mode',
        'xi_source_confidence','player_lane_ready','player_synergy_position_ready','player_synergy_position_coverage','readiness_strip'
    )}
    for m in base.get('matches') or [] if m.get('readiness') == 'READY_DEEP_ANALYSIS'
]
summary['player_lane_ready_matches'] = [
    {k: m.get(k) for k in (
        'match_market_id','match','league','start_time','minutes_to_start','player_lane_ready','player_market_bet_ready',
        'player_synergy_position_ready','player_synergy_position_coverage','xi_source_confidence','movement_certification'
    )}
    for m in ready_player
]
(ROOT / 'deep-analysis-readiness-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'schema': base['schema'],
    'match_count': len(base.get('matches') or []),
    'player_lane_ready_count': len(ready_player),
    'synergy_age_minutes': synergy_age,
    'synergy_fresh': synergy_fresh,
}, ensure_ascii=False, indent=2))
