#!/usr/bin/env python3
import concurrent.futures
import json
import math
import pathlib
from collections import defaultdict, Counter
from datetime import datetime, timezone

from curl_cffi import requests

ROOT = pathlib.Path('feed')
NOW = datetime.now(timezone.utc)
LOOKBACK = 6
MAX_TARGET_MATCHES = 6
FM_H = {
    'Accept': 'application/json,text/plain,*/*',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
    'Referer': 'https://www.fotmob.com/'
}


def load(name, default):
    p = ROOT / name
    try:
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
    except Exception:
        return default


def fm_json(url):
    r = requests.get(url, headers=FM_H, impersonate='chrome', timeout=25)
    r.raise_for_status()
    return r.json()


def safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float)) and math.isfinite(x)]
    return round(sum(xs) / len(xs), 4) if xs else None


def team_id_from(t):
    if not isinstance(t, dict):
        return None
    return t.get('id') or t.get('teamId')


def lineup_teams(detail):
    line = ((detail.get('content') or {}).get('lineup') or {}) if isinstance(detail, dict) else {}
    out = []
    if isinstance(line.get('homeTeam'), dict):
        out.append(line['homeTeam'])
    if isinstance(line.get('awayTeam'), dict):
        out.append(line['awayTeam'])
    return out


def fixture_candidates(team_payload, target_team_id):
    found = {}
    def walk(x):
        if isinstance(x, dict):
            mid = x.get('id') or x.get('matchId')
            home = x.get('home') or x.get('homeTeam')
            away = x.get('away') or x.get('awayTeam')
            status = x.get('status') or {}
            finished = status.get('finished') if isinstance(status, dict) else None
            if finished is None:
                reason = str((status.get('reason') if isinstance(status, dict) else '') or '').lower()
                finished = reason in {'ft', 'aet', 'pen', 'finished', 'full-time'}
            hid = team_id_from(home); aid = team_id_from(away)
            if mid is not None and finished and str(target_team_id) in {str(hid), str(aid)}:
                ts = None
                if isinstance(status, dict):
                    ts = status.get('utcTime') or status.get('startDateStr')
                found[str(mid)] = {'match_id': int(mid), 'time': ts}
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(team_payload)
    def key(r):
        s = str(r.get('time') or '')
        return s
    return sorted(found.values(), key=key, reverse=True)[:LOOKBACK]


def sub_time(player, typ):
    perf = player.get('performance') or {}
    events = perf.get('substitutionEvents') or []
    for e in events:
        if isinstance(e, dict) and str(e.get('type')) == typ:
            try:
                return int(e.get('time'))
            except Exception:
                pass
    return None


def player_minutes(player, starter):
    if starter:
        out = sub_time(player, 'subOut')
        return min(90, max(1, out)) if out is not None else 90
    inn = sub_time(player, 'subIn')
    out = sub_time(player, 'subOut')
    if inn is None:
        return 0
    end = min(90, out) if out is not None else 90
    return max(0, end - inn)


def extract_match(detail):
    general = detail.get('general') or {}
    content = detail.get('content') or {}
    teams = lineup_teams(detail)
    players = {}
    team_players = defaultdict(list)
    for ti, team in enumerate(teams):
        tid = team_id_from(team)
        for starter, key in ((True, 'starters'), (False, 'subs')):
            for p in team.get(key) or []:
                if not isinstance(p, dict):
                    continue
                pid = p.get('id')
                if pid is None:
                    continue
                pos = p.get('verticalLayout') or p.get('horizontalLayout') or {}
                row = {
                    'player_id': pid,
                    'name': p.get('name'),
                    'team_id': tid,
                    'starter': starter,
                    'minutes': player_minutes(p, starter),
                    'position_id': p.get('positionId'),
                    'usual_position_id': p.get('usualPlayingPositionId'),
                    'pos_x': safe_float(pos.get('x')),
                    'pos_y': safe_float(pos.get('y')),
                }
                players[str(pid)] = row
                team_players[str(tid)].append(row)
    shots = []
    for s in ((content.get('shotmap') or {}).get('shots') or []):
        if not isinstance(s, dict):
            continue
        shots.append({
            'team_id': s.get('teamId'), 'player_id': s.get('playerId'), 'player_name': s.get('playerName'),
            'x': safe_float(s.get('x')), 'y': safe_float(s.get('y')),
            'xg': safe_float(s.get('expectedGoals')) or 0.0,
            'on_target': bool(s.get('isOnTarget')), 'event_type': s.get('eventType'),
            'shot_type': s.get('shotType'), 'situation': s.get('situation'), 'period': s.get('period'),
        })
    home = general.get('homeTeam') or {}
    away = general.get('awayTeam') or {}
    return {
        'match_id': general.get('matchId'),
        'home_team_id': team_id_from(home), 'away_team_id': team_id_from(away),
        'players': players, 'team_players': dict(team_players), 'shots': shots,
    }


def beta_smoothed(successes, trials, a, b):
    return round((successes + a) / (trials + a + b), 4) if trials >= 0 else None


def role_zone(x, y):
    if x is None or y is None:
        return None
    lateral = 'LEFT' if x < .34 else ('RIGHT' if x > .66 else 'CENTER')
    depth = 'DEFENSIVE' if y < .42 else ('ATTACKING' if y > .72 else 'MIDFIELD')
    return f'{depth}_{lateral}'


def shot_zone(x, y):
    if x is None or y is None:
        return 'UNKNOWN'
    lateral = 'LEFT' if y < 22.67 else ('RIGHT' if y > 45.33 else 'CENTER')
    if x >= 101:
        depth = 'SIX_YARD'
    elif x >= 88:
        depth = 'BOX'
    elif x >= 73:
        depth = 'FINAL_THIRD_OUTSIDE_BOX'
    else:
        depth = 'DEEP'
    return f'{depth}_{lateral}'


def aggregate_player(pid, match_features):
    appearances = []
    shots = []
    for mf in match_features:
        p = mf['players'].get(str(pid))
        if p:
            appearances.append(p)
        for s in mf['shots']:
            if str(s.get('player_id')) == str(pid):
                shots.append(s)
    starts = [p for p in appearances if p['starter']]
    base = starts if starts else appearances
    mins = [p['minutes'] for p in base]
    n = len(base)
    p60 = beta_smoothed(sum(m >= 60 for m in mins), n, 4, 1)
    p75 = beta_smoothed(sum(m >= 75 for m in mins), n, 3, 2)
    p90 = beta_smoothed(sum(m >= 90 for m in mins), n, 2, 3)
    pos_x = mean([p['pos_x'] for p in starts]); pos_y = mean([p['pos_y'] for p in starts])
    sx = mean([s['x'] for s in shots]); sy = mean([s['y'] for s in shots])
    situations = Counter(str(s.get('situation') or 'UNKNOWN') for s in shots)
    shot_types = Counter(str(s.get('shot_type') or 'UNKNOWN') for s in shots)
    return {
        'sample_matches': len(match_features), 'appearances': len(appearances), 'starts': len(starts),
        'start_rate': round(len(starts) / max(1, len(match_features)), 3),
        'avg_minutes_when_selected': mean(mins),
        'p60_preliminary': p60, 'p75_preliminary': p75, 'p90_preliminary': p90,
        'minutes_model_status': 'PRELIMINARY_UNCALIBRATED',
        'historical_start_pos_x': pos_x, 'historical_start_pos_y': pos_y,
        'historical_role_zone': role_zone(pos_x, pos_y),
        'shots': len(shots), 'shot_xg': round(sum(s['xg'] for s in shots), 3),
        'shots_on_target': sum(1 for s in shots if s['on_target']),
        'shot_origin_x': sx, 'shot_origin_y': sy, 'dominant_shot_zone': None if not shots else Counter(shot_zone(s['x'], s['y']) for s in shots).most_common(1)[0][0],
        'shot_situations': dict(situations), 'shot_types': dict(shot_types),
    }


def concession_map(opponent_team_id, match_features):
    rows = []
    for mf in match_features:
        for s in mf['shots']:
            if str(s.get('team_id')) != str(opponent_team_id):
                rows.append(s)
    by_zone = defaultdict(lambda: {'shots': 0, 'xg': 0.0, 'on_target': 0, 'goals': 0, 'first_half_shots': 0})
    by_situation = defaultdict(lambda: {'shots': 0, 'xg': 0.0})
    for s in rows:
        z = shot_zone(s['x'], s['y']); b = by_zone[z]
        b['shots'] += 1; b['xg'] += s['xg']; b['on_target'] += int(s['on_target'])
        b['goals'] += int(str(s.get('event_type')) == 'Goal')
        b['first_half_shots'] += int(str(s.get('period')) == 'FirstHalf')
        sit = str(s.get('situation') or 'UNKNOWN'); by_situation[sit]['shots'] += 1; by_situation[sit]['xg'] += s['xg']
    nm = max(1, len(match_features))
    zones = []
    for z, b in by_zone.items():
        zones.append({
            'zone': z, 'shots': b['shots'], 'xg': round(b['xg'], 3), 'on_target': b['on_target'], 'goals': b['goals'],
            'first_half_shots': b['first_half_shots'], 'shots_per_match': round(b['shots'] / nm, 3), 'xg_per_match': round(b['xg'] / nm, 3)
        })
    zones.sort(key=lambda r: (r['xg_per_match'], r['shots_per_match']), reverse=True)
    situations = [{**{'situation': k}, **{'shots': v['shots'], 'xg': round(v['xg'], 3), 'xg_per_match': round(v['xg']/nm, 3)}} for k, v in by_situation.items()]
    situations.sort(key=lambda r: r['xg_per_match'], reverse=True)
    return {'sample_matches': len(match_features), 'conceded_shots': len(rows), 'zones': zones, 'situations': situations}


lineups = load('lineups-current.json', {'matches': []})
targets = [m for m in (lineups.get('matches') or []) if m.get('status') in ('SOURCE_CONFIRMED', 'CROSS_CONFIRMED') and (m.get('lineup') or {}).get('confirmed')]
targets.sort(key=lambda m: abs(float(m.get('minutes_to_start') or 9999)))
targets = targets[:MAX_TARGET_MATCHES]

team_ids = set()
for m in targets:
    for t in (m.get('lineup') or {}).get('teams') or []:
        if t.get('team_id') is not None:
            team_ids.add(str(t['team_id']))

team_payloads = {}
errors = []
for tid in team_ids:
    try:
        team_payloads[tid] = fm_json(f'https://www.fotmob.com/api/data/teams?id={tid}&ccode3=ITA')
    except Exception as e:
        errors.append({'source': 'team', 'team_id': tid, 'error': type(e).__name__ + ': ' + str(e)[:160]})

team_match_ids = {}
all_match_ids = set()
for tid, payload in team_payloads.items():
    vals = fixture_candidates(payload, tid)
    mids = [v['match_id'] for v in vals]
    team_match_ids[tid] = mids
    all_match_ids.update(mids)


def fetch_detail(mid):
    try:
        return str(mid), extract_match(fm_json(f'https://www.fotmob.com/api/data/matchDetails?matchId={mid}')), None
    except Exception as e:
        return str(mid), None, type(e).__name__ + ': ' + str(e)[:160]

features = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    for mid, feat, err in ex.map(fetch_detail, sorted(all_match_ids)):
        if feat:
            features[mid] = feat
        elif err:
            errors.append({'source': 'matchDetails', 'match_id': mid, 'error': err})

out_matches = []
for m in targets:
    teams = (m.get('lineup') or {}).get('teams') or []
    if len(teams) < 2:
        continue
    home, away = teams[0], teams[1]
    enriched_teams = []
    for current, opponent in ((home, away), (away, home)):
        tid, oid = str(current.get('team_id')), str(opponent.get('team_id'))
        own_hist = [features[str(mid)] for mid in team_match_ids.get(tid, []) if str(mid) in features]
        opp_hist = [features[str(mid)] for mid in team_match_ids.get(oid, []) if str(mid) in features]
        player_context = []
        for p in current.get('starters') or []:
            pid = p.get('id')
            ctx = aggregate_player(pid, own_hist) if pid is not None else {}
            player_context.append({
                'player_id': pid, 'player': p.get('name'), 'current_position_id': p.get('position_id'),
                'current_usual_position_id': p.get('usual_position_id'), **ctx
            })
        enriched_teams.append({
            'team_id': current.get('team_id'), 'team': current.get('team_name'),
            'recent_match_ids': team_match_ids.get(tid, []), 'recent_match_features_available': len(own_hist),
            'players': player_context,
            'opponent_concession_map': concession_map(opponent.get('team_id'), opp_hist),
            'opponent_recent_match_ids': team_match_ids.get(oid, []),
        })
    out_matches.append({
        'match_market_id': m.get('match_market_id'), 'match_event_id': m.get('match_event_id'), 'match': m.get('match'),
        'league': m.get('league'), 'start_time': m.get('start_time'), 'minutes_to_start': m.get('minutes_to_start'),
        'xi_fingerprint': (m.get('lineup') or {}).get('xi_fingerprint'),
        'context_status': 'AVAILABLE' if enriched_teams else 'NOT_AVAILABLE',
        'teams': enriched_teams,
    })

payload = {
    'generated_at': NOW.isoformat(),
    'method': 'FotMob recent team matches + standard historical lineups + substitution events + shotmaps',
    'lookback_matches_per_team': LOOKBACK,
    'target_count': len(targets), 'context_match_count': len(out_matches),
    'model_policy': 'Minutes probabilities are preliminary/unvalidated and may adjust confidence/risk only; never create standalone betting edge until OOS validation.',
    'position_policy': 'Historical starting coordinates and shot origins are contextual proxies; not GPS tracking or full average-position heatmaps.',
    'errors': errors,
    'matches': out_matches,
}
ROOT.mkdir(exist_ok=True)
(ROOT / 'player-matchup-context-current.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
summary = {k: v for k, v in payload.items() if k != 'matches'}
summary['matches'] = [{'match': x['match'], 'start_time': x['start_time'], 'context_status': x['context_status'], 'teams': [{'team': t['team'], 'history': t['recent_match_features_available'], 'players': len(t['players']), 'concession_zones': len(t['opponent_concession_map']['zones'])} for t in x['teams']]} for x in out_matches]
(ROOT / 'player-matchup-context-current-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))
