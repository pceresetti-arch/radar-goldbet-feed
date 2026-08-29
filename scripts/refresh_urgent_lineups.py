#!/usr/bin/env python3
import difflib
import hashlib
import json
import pathlib
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from curl_cffi import requests

NOW = datetime.now(timezone.utc)
LINEUPS = pathlib.Path('feed/lineups-current.json')
SUMMARY = pathlib.Path('feed/lineups-current-summary.json')
URGENT_TO_MIN = 85.0

HEADERS = {
    'Accept': 'application/json,text/plain,*/*',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36',
}


def get_json(url, referer):
    h = dict(HEADERS)
    h['Referer'] = referer
    r = requests.get(url, headers=h, impersonate='chrome', timeout=18)
    r.raise_for_status()
    return r.json(), r.status_code


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(fc|cf|sc|ac|afc|cd|fk|bk|calcio|club|deportivo|sporting|united|city|pr|sp|rj|mg)\b', ' ', s)
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def side_score(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    A, B = set(a.split()), set(b.split())
    jac = len(A & B) / max(1, len(A | B))
    cont = 1.0 if a in b or b in a else 0.0
    return .62 * seq + .23 * jac + .15 * cont


def split_match(s):
    for sep in (' - ', ' vs ', ' v '):
        if sep in str(s):
            return tuple(x.strip() for x in str(s).split(sep, 1))
    return str(s), ''


def parse_iso(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def mins_to_start(m):
    dt = parse_iso(m.get('start_utc'))
    if not dt:
        return None
    return (dt - NOW).total_seconds() / 60.0


def player_name(row):
    return row.get('name') or (row.get('player') or {}).get('name') or row.get('playerName')


def normalize_player(row, bench=False):
    n = player_name(row)
    if not n:
        return None
    pl = row.get('player') or {}
    out = {
        'name': n,
        'id': row.get('id') or pl.get('id'),
        'shirt_number': row.get('shirtNumber') or row.get('shirt') or row.get('jerseyNumber'),
    }
    if not bench:
        out.update({
            'position_id': row.get('positionId') or row.get('position') or pl.get('position'),
            'usual_position_id': row.get('usualPlayingPositionId') or pl.get('position'),
            'horizontal_layout': row.get('horizontalLayout'),
            'vertical_layout': row.get('verticalLayout'),
        })
    return out


def name_fingerprint(teams):
    if len(teams) < 2:
        return None
    parts = []
    for t in teams[:2]:
        names = sorted(norm(p.get('name')) for p in (t.get('starters') or []) if p.get('name'))
        parts.append(norm(t.get('team_name')) + ':' + ','.join(names))
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:20]


def provider_fingerprint(teams):
    if len(teams) < 2:
        return None
    parts = []
    for t in teams[:2]:
        ids = [str(p.get('id') or norm(p.get('name'))) for p in (t.get('starters') or [])]
        parts.append(str(t.get('team_id') or norm(t.get('team_name'))) + ':' + ','.join(ids))
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()[:20]


def normalize_fotmob_team(t):
    if not isinstance(t, dict):
        return None
    starters, bench = [], []
    for r in (t.get('starters') or t.get('players') or t.get('startingXI') or []):
        if isinstance(r, dict):
            p = normalize_player(r)
            if p:
                starters.append(p)
    for r in (t.get('bench') or t.get('substitutes') or t.get('subs') or []):
        if isinstance(r, dict):
            p = normalize_player(r, bench=True)
            if p:
                bench.append(p)
    return {
        'team_id': t.get('id') or t.get('teamId'),
        'team_name': t.get('name') or t.get('teamName'),
        'formation': t.get('formation'),
        'starters': starters,
        'bench': bench,
        'raw_keys': list(t.keys()),
    }


def parse_fotmob_lineup(line):
    if not isinstance(line, dict) or not line:
        return None
    teams = []
    if isinstance(line.get('homeTeam'), dict) or isinstance(line.get('awayTeam'), dict):
        for key in ('homeTeam', 'awayTeam'):
            nt = normalize_fotmob_team(line.get(key))
            if nt:
                teams.append(nt)
    else:
        rawteams = line.get('lineups') or line.get('teams') or []
        for t in rawteams if isinstance(rawteams, list) else []:
            nt = normalize_fotmob_team(t)
            if nt:
                teams.append(nt)
    complete = len(teams) >= 2 and all(len(t.get('starters') or []) == 11 for t in teams[:2])
    lineup_type = str(line.get('lineupType') or '').strip()
    provider_source = str(line.get('source') or '').strip()
    historical = lineup_type.lower() in {'laststarting11', 'predicted', 'probable', 'expected'} or any(
        x in provider_source.lower() for x in ('laststarting', 'predicted', 'probable')
    )
    confirmed = complete and lineup_type.lower() == 'standard' and not historical
    return {
        'present': bool(teams),
        'complete_11v11': complete,
        'confirmed': confirmed,
        'historical_reference': historical,
        'lineup_type': lineup_type,
        'provider_source': provider_source or 'FotMob',
        'teams': teams,
        'xi_fingerprint': provider_fingerprint(teams),
        'xi_name_fingerprint': name_fingerprint(teams),
        'raw_keys': list(line.keys()),
    }


def parse_sofa_lineup(data, event):
    if not isinstance(data, dict) or data.get('confirmed') is not True:
        return None
    teams = []
    for side, team_key in (('home', 'homeTeam'), ('away', 'awayTeam')):
        raw = data.get(side) or {}
        players = raw.get('players') or []
        starters, bench = [], []
        for r in players:
            if not isinstance(r, dict):
                continue
            p = normalize_player(r, bench=bool(r.get('substitute')))
            if not p:
                continue
            if r.get('substitute'):
                bench.append(p)
            else:
                starters.append(p)
        evteam = event.get(team_key) or {}
        teams.append({
            'team_id': evteam.get('id'),
            'team_name': evteam.get('name'),
            'formation': raw.get('formation'),
            'starters': starters,
            'bench': bench,
            'raw_keys': list(raw.keys()),
        })
    complete = len(teams) == 2 and all(len(t.get('starters') or []) == 11 for t in teams)
    if not complete:
        return None
    return {
        'present': True,
        'complete_11v11': True,
        'confirmed': True,
        'historical_reference': False,
        'lineup_type': 'standard',
        'provider_source': 'Sofascore confirmed',
        'teams': teams,
        'xi_fingerprint': provider_fingerprint(teams),
        'xi_name_fingerprint': name_fingerprint(teams),
        'raw_keys': list(data.keys()),
    }


def is_official(m):
    ln = (m or {}).get('lineup') or {}
    return (
        m.get('status') in ('SOURCE_CONFIRMED', 'CROSS_CONFIRMED')
        and ln.get('confirmed') is True
        and ln.get('complete_11v11') is True
        and str(ln.get('lineup_type') or '').lower() == 'standard'
    )


def team_names(lineup, side):
    try:
        idx = 0 if side == 'home' else 1
        return [norm(p.get('name')) for p in lineup['teams'][idx].get('starters') or [] if p.get('name')]
    except Exception:
        return []


def lineup_agreement(a, b):
    scores = []
    for side in ('home', 'away'):
        A, B = team_names(a, side), team_names(b, side)
        used = set()
        matched = 0
        for x in A:
            best_j, best_s = None, 0.0
            for j, y in enumerate(B):
                if j in used:
                    continue
                s = difflib.SequenceMatcher(None, x, y).ratio()
                if s > best_s:
                    best_j, best_s = j, s
            if best_j is not None and best_s >= .72:
                used.add(best_j)
                matched += 1
        scores.append(matched)
    return {'home_matches': scores[0], 'away_matches': scores[1], 'cross_confirmed': min(scores) >= 10}


def fetch_fotmob(match):
    fm_id = ((match.get('fotmob_match') or {}).get('id'))
    if not fm_id:
        return None, None
    try:
        data, status = get_json(
            f'https://www.fotmob.com/api/data/matchDetails?matchId={fm_id}',
            'https://www.fotmob.com/'
        )
        parsed = parse_fotmob_lineup(((data.get('content') or {}).get('lineup') or {}))
        return parsed, {'provider': 'FotMob', 'match_id': fm_id, 'http_status': status}
    except Exception as e:
        return None, {'provider': 'FotMob', 'match_id': fm_id, 'error': type(e).__name__ + ': ' + str(e)[:180]}


def sofa_schedule(date_str):
    urls = [
        f'https://api.sofascore.com/api/v1/sport/football/scheduled-events/{date_str}',
        f'https://www.sofascore.com/api/v1/sport/football/scheduled-events/{date_str}',
    ]
    for url in urls:
        try:
            data, status = get_json(url, 'https://www.sofascore.com/')
            events = data.get('events') or []
            if isinstance(events, list):
                return events, {'provider': 'Sofascore', 'schedule_url': url, 'http_status': status}
        except Exception:
            pass
    return [], {'provider': 'Sofascore', 'error': 'SCHEDULE_UNAVAILABLE'}


def best_sofa_event(match, events):
    th, ta = split_match(match.get('match'))
    target_dt = parse_iso(match.get('start_utc'))
    if not target_dt:
        return None
    winner = None
    for ev in events:
        if not isinstance(ev, dict):
            continue
        home = (ev.get('homeTeam') or {}).get('name')
        away = (ev.get('awayTeam') or {}).get('name')
        ts = ev.get('startTimestamp')
        try:
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        except Exception:
            continue
        hs, ass = side_score(th, home), side_score(ta, away)
        mins = abs((dt - target_dt).total_seconds()) / 60.0
        if mins > 180 or hs < .45 or ass < .45:
            continue
        score = .88 * ((hs + ass) / 2.0) + .12 * max(0.0, 1.0 - mins / 180.0)
        if winner is None or score > winner['score']:
            winner = {'event': ev, 'score': score, 'time_delta_min': mins}
    return winner if winner and winner['score'] >= .62 else None


def fetch_sofa(match, events):
    chosen = best_sofa_event(match, events)
    if not chosen:
        return None, {'provider': 'Sofascore', 'error': 'EVENT_NOT_MATCHED'}
    ev = chosen['event']
    event_id = ev.get('id')
    if not event_id:
        return None, {'provider': 'Sofascore', 'error': 'EVENT_ID_MISSING'}
    try:
        data, status = get_json(
            f'https://api.sofascore.com/api/v1/event/{event_id}/lineups',
            'https://www.sofascore.com/'
        )
        parsed = parse_sofa_lineup(data, ev)
        return parsed, {
            'provider': 'Sofascore',
            'event_id': event_id,
            'http_status': status,
            'match_score': round(chosen['score'], 4),
            'time_delta_min': round(chosen['time_delta_min'], 1),
            'confirmed': bool(data.get('confirmed')) if isinstance(data, dict) else False,
        }
    except Exception as e:
        return None, {'provider': 'Sofascore', 'event_id': event_id, 'error': type(e).__name__ + ': ' + str(e)[:180]}


if not LINEUPS.exists():
    raise SystemExit('feed/lineups-current.json missing')

payload = json.loads(LINEUPS.read_text(encoding='utf-8'))
matches = payload.get('matches') or []
urgent = []
for i, m in enumerate(matches):
    if not isinstance(m, dict):
        continue
    mins = mins_to_start(m)
    if mins is not None:
        m['minutes_to_start'] = round(mins, 1)
    if mins is not None and 0.0 < mins <= URGENT_TO_MIN:
        urgent.append((i, m))

# Schedule discovery is only needed for the small urgent set and only once per date.
dates = sorted({parse_iso(m.get('start_utc')).date().isoformat() for _, m in urgent if parse_iso(m.get('start_utc'))})
sofa_by_date = {}
sofa_schedule_meta = {}
for d in dates:
    sofa_by_date[d], sofa_schedule_meta[d] = sofa_schedule(d)


def probe_one(item):
    i, m = item
    fm, fm_meta = fetch_fotmob(m)
    dt = parse_iso(m.get('start_utc'))
    events = sofa_by_date.get(dt.date().isoformat(), []) if dt else []
    sofa, sofa_meta = fetch_sofa(m, events)
    return i, fm, fm_meta, sofa, sofa_meta

results = []
with ThreadPoolExecutor(max_workers=min(12, max(1, len(urgent)))) as ex:
    futures = [ex.submit(probe_one, item) for item in urgent]
    for fut in as_completed(futures):
        results.append(fut.result())

changes = []
for i, fm, fm_meta, sofa, sofa_meta in results:
    m = matches[i]
    before_official = is_official(m)
    before_fp = ((m.get('lineup') or {}).get('xi_name_fingerprint') or (m.get('lineup') or {}).get('xi_fingerprint'))
    existing = m.get('lineup') or {}
    evidence = {'polled_at': NOW.isoformat(), 'fotmob': fm_meta, 'sofascore': sofa_meta}

    # Prefer a fresh confirmed FotMob standard XI because its layout coordinates
    # feed the tactical layer. Use Sofascore as independent confirmation/fallback.
    chosen = None
    source = m.get('source')
    status = m.get('status')
    if fm and fm.get('confirmed'):
        chosen = fm
        source = 'FotMob'
        status = 'SOURCE_CONFIRMED'
        if sofa and sofa.get('confirmed'):
            agree = lineup_agreement(fm, sofa)
            evidence['cross_source_agreement'] = agree
            if agree['cross_confirmed']:
                source = 'FotMob+Sofascore'
                status = 'CROSS_CONFIRMED'
    elif sofa and sofa.get('confirmed'):
        if before_official and existing.get('confirmed'):
            agree = lineup_agreement(existing, sofa)
            evidence['cross_source_agreement'] = agree
            if agree['cross_confirmed']:
                chosen = existing
                source = str(m.get('source') or 'Primary') + '+Sofascore'
                status = 'CROSS_CONFIRMED'
            else:
                chosen = existing
        else:
            chosen = sofa
            source = 'Sofascore'
            status = 'SOURCE_CONFIRMED'

    if chosen and chosen.get('confirmed'):
        new_fp = chosen.get('xi_name_fingerprint') or chosen.get('xi_fingerprint')
        changed = bool(before_official and before_fp and new_fp and before_fp != new_fp)
        m['lineup'] = chosen
        m['status'] = status
        m['source'] = source
        m['source_evidence'] = evidence
        m['confirmed_at'] = m.get('confirmed_at') if before_official and not changed else NOW.isoformat()
        m['xi_changed_after_confirmation'] = changed
        m['retained_from_previous'] = False
        if not before_official or changed or status == 'CROSS_CONFIRMED':
            changes.append({
                'match': m.get('match'),
                'minutes_to_start': m.get('minutes_to_start'),
                'before_official': before_official,
                'after_status': status,
                'source': source,
                'xi_changed': changed,
            })
    else:
        m['urgent_source_evidence'] = evidence

payload['generated_at'] = NOW.isoformat()
payload['urgent_refresh'] = {
    'schema': 'radar-urgent-lineup-refresh-v1',
    'generated_at': NOW.isoformat(),
    'window_minutes': [0, URGENT_TO_MIN],
    'target_count': len(urgent),
    'sources': ['FotMob', 'Sofascore'],
    'schedule_meta': sofa_schedule_meta,
    'changes': changes,
}
counts = {}
for m in matches:
    if isinstance(m, dict):
        counts[m.get('status') or 'UNKNOWN'] = counts.get(m.get('status') or 'UNKNOWN', 0) + 1
payload['status_counts'] = counts
LINEUPS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

summary = {k: v for k, v in payload.items() if k != 'matches'}
summary['matches'] = [
    {k: m.get(k) for k in ('match','start_time','league','minutes_to_start','status','match_market_id','confirmed_at','xi_changed_after_confirmation','target_origin','source')}
    for m in matches if isinstance(m, dict)
]
SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(payload['urgent_refresh'], ensure_ascii=False, indent=2))
