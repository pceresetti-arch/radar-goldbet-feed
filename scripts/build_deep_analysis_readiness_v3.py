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
        ids=m.get('match_market_ids') or []
        if isinstance(ids,list):
            for mid in ids:
                if mid not in (None,''):
                    out[('id',str(mid))]=m
        if norm(m.get('match')):
            out[('name', norm(m.get('match')))] = m
    return out


def find(m, idx):
    return idx.get(('id', str(m.get('match_market_id')))) or idx.get(('name', norm(m.get('match')))) or {}


# Rebuild V2 first, then harden its player lane with the explicit per-fixture BetFlag
# coverage contract and finally the XI-aligned synergy gate.
cp = subprocess.run([sys.executable, 'scripts/build_deep_analysis_readiness.py'], check=False)
if cp.returncode != 0:
    raise SystemExit(cp.returncode)

base = load('deep-analysis-readiness.json', {'matches': []})
synergy = load('player-synergy-position-current.json', {'matches': []})
betflag = load('betflag-fixtures-index.json', {'fixtures': []})
SYN = index(synergy.get('matches'))
BF = index(betflag.get('fixtures'))
synergy_age = age_minutes(synergy.get('enriched_at') or synergy.get('generated_at'))
synergy_fresh = synergy_age is not None and synergy_age <= 45

ready_player = []
for m in base.get('matches') or []:
    bf = find(m, BF)
    standard_count = int(bf.get('standard_count') or 0)
    player_count = int(bf.get('player_props_count') or bf.get('player_count') or 0)
    combo_count = int(bf.get('combo_props_count') or 0)
    standard_coverage = bool(bf.get('standard_coverage_complete')) if 'standard_coverage_complete' in bf else standard_count > 0
    player_coverage = bool(bf.get('player_coverage_complete')) if 'player_coverage_complete' in bf else player_count > 0
    combo_coverage = bool(bf.get('combo_coverage_complete')) if 'combo_coverage_complete' in bf else combo_count > 0

    # Empty rows can never be interpreted as complete. This deliberately overrides legacy
    # generic coverage_complete/player_count semantics from older worker snapshots.
    standard_coverage = bool(standard_coverage and standard_count > 0)
    player_coverage = bool(player_coverage and player_count > 0)
    combo_coverage = bool(combo_coverage and combo_count > 0)
    m['betflag_standard_count'] = standard_count
    m['player_count'] = player_count
    m['player_quote_count'] = player_count
    m['combo_quote_count'] = combo_count
    m['betflag_standard_coverage_complete'] = standard_coverage
    m['betflag_player_coverage_complete'] = player_coverage
    m['betflag_combo_coverage_complete'] = combo_coverage
    m['player_props_available'] = player_coverage
    m['player_props_ready'] = player_coverage
    m['combo_props_available'] = combo_coverage
    m['combo_market_bet_ready'] = False

    s = find(m, SYN)
    quality = s.get('synergy_quality') if isinstance(s.get('synergy_quality'), dict) else {}
    current_fp = m.get('xi_fingerprint')
    synergy_fp = s.get('xi_fingerprint')
    xi_match = bool(current_fp and synergy_fp and current_fp == synergy_fp)
    coverage = float(quality.get('baseline_coverage') or 0.0)
    context_present = bool(s)
    synergy_ready = bool(context_present and synergy_fresh and xi_match and quality.get('ready') and coverage >= 0.60)

    # Reconstruct player prerequisites from explicit current fields instead of trusting the
    # legacy V2 counters. Standard deep-analysis readiness remains unchanged.
    player_context_ready = bool(
        m.get('player_context_available') and
        m.get('player_context_fresh') and
        m.get('player_context_matches_current_xi')
    )
    player_lane_pre_synergy = bool(m.get('analysis_total_ready') and player_coverage and player_context_ready)
    player_lane_ready = bool(player_lane_pre_synergy and synergy_ready)
    combo_lane_ready = bool(player_lane_ready and combo_coverage)

    m['player_synergy_position_available'] = context_present
    m['player_synergy_position_fresh'] = synergy_fresh
    m['player_synergy_position_age_minutes'] = synergy_age
    m['player_synergy_position_xi_match'] = xi_match
    m['player_synergy_position_ready'] = synergy_ready
    m['player_synergy_position_coverage'] = coverage
    m['player_synergy_position_quality'] = quality
    m['player_synergy_position_schema'] = synergy.get('schema')
    m['player_lane_ready_pre_synergy'] = player_lane_pre_synergy
    m['player_lane_ready'] = player_lane_ready
    m['player_market_bet_ready'] = player_lane_ready
    m['combo_market_bet_ready'] = combo_lane_ready

    warnings = list(m.get('warnings') or [])
    if not player_coverage:
        warnings.append('PLAYER_PROPS_FIXTURE_COVERAGE_INCOMPLETE')
    if player_coverage and not combo_coverage:
        warnings.append('COMBO_PROPS_NOT_OBSERVED_FIXTURE_SPECIFICALLY')
    if player_coverage and not context_present:
        warnings.append('PLAYER_SYNERGY_POSITION_CONTEXT_MISSING')
    elif player_coverage and not synergy_fresh:
        warnings.append('PLAYER_SYNERGY_POSITION_CONTEXT_STALE')
    elif player_coverage and not xi_match:
        warnings.append('PLAYER_SYNERGY_POSITION_CONTEXT_XI_MISMATCH')
    elif player_coverage and not quality.get('ready'):
        warnings.append('PLAYER_SYNERGY_POSITION_CONTEXT_LOW_COVERAGE')
    m['warnings'] = list(dict.fromkeys(warnings))

    if m.get('analysis_total_ready'):
        if combo_lane_ready:
            m['analysis_scope'] = 'FULL_WITH_PLAYER_AND_COMBO_MATCHUP_SYNERGY_POSITION_CONTEXT_EXACT_BETFLAG_PRICE_REQUIRED'
        elif player_lane_ready:
            m['analysis_scope'] = 'FULL_WITH_PLAYER_MATCHUP_SYNERGY_POSITION_CONTEXT_EXACT_BETFLAG_PRICE_REQUIRED_COMBO_PENDING'
        elif player_coverage:
            m['analysis_scope'] = 'STANDARD_READY_PLAYER_CONTEXT_OR_SYNERGY_PENDING'
        else:
            m['analysis_scope'] = 'STANDARD_READY_PLAYER_PROPS_COVERAGE_PENDING'

    strip = str(m.get('readiness_strip') or '')
    extra = (
        f'BetFlag player {"OK" if player_coverage else "WARN"} rows={player_count} | '
        f'Combo {"OK" if combo_coverage else "WARN"} rows={combo_count} | '
        f'Synergy/position {"OK" if synergy_ready else "WARN"} cov={coverage:.2f}'
    )
    if extra not in strip:
        m['readiness_strip'] = (strip + ' | ' + extra).strip(' |')
    if player_lane_ready:
        ready_player.append(m)

base['schema'] = 'radar-deep-analysis-readiness-v4-betflag-coverage-synergy'
base['generated_at_v3'] = NOW.isoformat()
base['contract'] = (
    str(base.get('contract') or '') +
    ' V4: player BET readiness requires explicit fixture-specific BetFlag player_coverage_complete with concrete player rows; Combo BET readiness separately requires combo_coverage_complete with concrete SCORER_COMBO/PLAYER_COMBO rows. Empty player/combo arrays are never COMPLETE. Player readiness additionally requires fresh XI-aligned Player Synergy & Position Context with >=60% baseline coverage.'
)
base['betflag_player_combo_coverage_policy'] = {
    'input': 'feed/betflag-fixtures-index.json',
    'player_rule': 'player_coverage_complete=true AND player_props_count>0',
    'combo_rule': 'combo_coverage_complete=true AND combo_props_count>0',
    'generic_coverage_rule': 'never use generic coverage_complete as a substitute for player/combo completeness',
    'not_observed_rule': 'NOT OBSERVED is pending/recovery, never equivalent to unavailable',
}
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
base['combo_lane_ready_count'] = sum(1 for m in base.get('matches') or [] if m.get('combo_market_bet_ready'))

ROOT.mkdir(exist_ok=True)
(ROOT / 'deep-analysis-readiness.json').write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding='utf-8')
summary = {k: v for k, v in base.items() if k != 'matches'}
summary['ready_matches'] = [
    {k: m.get(k) for k in (
        'match_market_id','match','league','start_time','minutes_to_start','readiness','analysis_scope','decision_mode',
        'xi_source_confidence','player_lane_ready','combo_market_bet_ready','betflag_player_coverage_complete','betflag_combo_coverage_complete',
        'player_synergy_position_ready','player_synergy_position_coverage','readiness_strip'
    )}
    for m in base.get('matches') or [] if m.get('readiness') == 'READY_DEEP_ANALYSIS'
]
summary['player_lane_ready_matches'] = [
    {k: m.get(k) for k in (
        'match_market_id','match','league','start_time','minutes_to_start','player_lane_ready','player_market_bet_ready','combo_market_bet_ready',
        'player_count','combo_quote_count','betflag_player_coverage_complete','betflag_combo_coverage_complete',
        'player_synergy_position_ready','player_synergy_position_coverage','xi_source_confidence','movement_certification'
    )}
    for m in ready_player
]
(ROOT / 'deep-analysis-readiness-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({
    'schema': base['schema'],
    'match_count': len(base.get('matches') or []),
    'player_lane_ready_count': len(ready_player),
    'combo_lane_ready_count': base['combo_lane_ready_count'],
    'synergy_age_minutes': synergy_age,
    'synergy_fresh': synergy_fresh,
}, ensure_ascii=False, indent=2))
