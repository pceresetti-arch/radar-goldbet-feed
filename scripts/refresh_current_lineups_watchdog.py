#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys
import time
from datetime import datetime, timezone

BASE_SCRIPT = pathlib.Path('scripts/refresh_current_lineups_resilient.py')
LINEUPS = pathlib.Path('feed/lineups-current.json')
SUMMARY = pathlib.Path('feed/lineups-current-summary.json')
WATCHDOG = pathlib.Path('feed/lineup-watchdog-current.json')
POSTXI = pathlib.Path('feed/post-xi-refresh-request.json')

MAX_ATTEMPTS = 4
POLL_INTERVAL_SECONDS = 45
URGENT_FROM_MIN = -5
URGENT_TO_MIN = 80


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {} if default is None else default


def key_of(m):
    return str(m.get('match_market_id') or m.get('match_event_id') or m.get('match') or '')


def is_official(m):
    if not isinstance(m, dict) or m.get('status') not in ('SOURCE_CONFIRMED', 'CROSS_CONFIRMED'):
        return False
    ln = m.get('lineup') or {}
    return bool(ln.get('confirmed')) and str(ln.get('lineup_type') or '').lower() == 'standard' and bool(ln.get('complete_11v11'))


def fingerprint(m):
    return ((m or {}).get('lineup') or {}).get('xi_fingerprint')


def match_map(payload):
    return {key_of(m): m for m in (payload.get('matches') or []) if isinstance(m, dict) and key_of(m)}


def urgent_missing(payload):
    out = []
    for m in payload.get('matches') or []:
        if not isinstance(m, dict):
            continue
        try:
            mins = float(m.get('minutes_to_start'))
        except Exception:
            continue
        if URGENT_FROM_MIN <= mins <= URGENT_TO_MIN and not is_official(m):
            out.append({
                'match': m.get('match'),
                'match_market_id': m.get('match_market_id'),
                'match_event_id': m.get('match_event_id'),
                'minutes_to_start': mins,
                'status': m.get('status'),
                'source': m.get('source'),
                'fotmob_match_id': ((m.get('fotmob_match') or {}).get('id')),
            })
    return out


def detect_events(before, after):
    bmap, amap = match_map(before), match_map(after)
    events = []
    for k, cur in amap.items():
        prev = bmap.get(k) or {}
        cur_off, prev_off = is_official(cur), is_official(prev)
        cur_fp, prev_fp = fingerprint(cur), fingerprint(prev)
        event_type = None
        if cur_off and not prev_off:
            event_type = 'XI_OFFICIAL_DETECTED'
        elif cur_off and prev_off and cur_fp and prev_fp and cur_fp != prev_fp:
            event_type = 'XI_OFFICIAL_CHANGED'
        if event_type:
            events.append({
                'event': event_type,
                'detected_at': now_iso(),
                'match': cur.get('match'),
                'league': cur.get('league'),
                'start_time': cur.get('start_time'),
                'minutes_to_start': cur.get('minutes_to_start'),
                'match_market_id': cur.get('match_market_id'),
                'match_event_id': cur.get('match_event_id'),
                'source': cur.get('source'),
                'provider_match_id': ((cur.get('fotmob_match') or {}).get('id')),
                'previous_status': prev.get('status'),
                'current_status': cur.get('status'),
                'previous_xi_fingerprint': prev_fp,
                'current_xi_fingerprint': cur_fp,
                'confirmed_at': cur.get('confirmed_at'),
            })
    return events


def run_base():
    cp = subprocess.run([sys.executable, str(BASE_SCRIPT)], check=False)
    if cp.returncode != 0:
        raise SystemExit(cp.returncode)
    return load_json(LINEUPS, {})


pathlib.Path('feed').mkdir(exist_ok=True)
initial = load_json(LINEUPS, {'matches': []})
reference = initial
attempt_records = []
all_events = []
final_payload = initial

for attempt in range(1, MAX_ATTEMPTS + 1):
    started = now_iso()
    final_payload = run_base()
    events = detect_events(reference, final_payload)
    missing = urgent_missing(final_payload)
    attempt_records.append({
        'attempt': attempt,
        'started_at': started,
        'finished_at': now_iso(),
        'official_count': sum(1 for m in (final_payload.get('matches') or []) if is_official(m)),
        'urgent_unconfirmed_count': len(missing),
        'events': events,
    })
    all_events.extend(events)

    # The moment a new/changed official XI is detected, stop the burst so the
    # workflow can commit immediately and workflow_run consumers can rebuild
    # tactical/player/readiness layers without waiting for unrelated fixtures.
    if events:
        break
    if not missing or attempt >= MAX_ATTEMPTS:
        break

    reference = final_payload
    time.sleep(POLL_INTERVAL_SECONDS)

remaining = urgent_missing(final_payload)
watchdog = {
    'schema': 'radar-lineup-watchdog-v1',
    'generated_at': now_iso(),
    'source_strategy': 'FotMob standard 11v11 official XI through resilient canonical fixture matcher; burst polling near kickoff',
    'official_definition': 'SOURCE_CONFIRMED/CROSS_CONFIRMED + lineupType=standard + complete 11v11',
    'poll_policy': {
        'base_schedule': 'GitHub cron every 5 minutes',
        'urgent_window_minutes': [URGENT_FROM_MIN, URGENT_TO_MIN],
        'max_attempts_per_run': MAX_ATTEMPTS,
        'interval_seconds': POLL_INTERVAL_SECONDS,
        'stop_immediately_on_official_transition': True,
    },
    'attempt_count': len(attempt_records),
    'attempts': attempt_records,
    'events': all_events,
    'post_xi_required': bool(all_events),
    'urgent_unconfirmed_remaining': remaining,
    'target_count': len(final_payload.get('matches') or []),
}
WATCHDOG.write_text(json.dumps(watchdog, ensure_ascii=False, indent=2), encoding='utf-8')

postxi = {
    'schema': 'radar-post-xi-refresh-request-v1',
    'generated_at': watchdog['generated_at'],
    'required': bool(all_events),
    'reason': 'Official XI detected or changed; rebuild tactical roles, player context and deep-analysis readiness immediately.' if all_events else 'No new official XI transition in this watchdog run.',
    'events': all_events,
}
POSTXI.write_text(json.dumps(postxi, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(watchdog, ensure_ascii=False, indent=2))
