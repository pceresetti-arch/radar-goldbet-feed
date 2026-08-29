#!/usr/bin/env python3
import json
import pathlib
import subprocess
import sys
import time
from datetime import datetime, timezone

BASE_SCRIPT = pathlib.Path('scripts/refresh_current_lineups_resilient.py')
URGENT_SCRIPT = pathlib.Path('scripts/refresh_urgent_lineups.py')
LINEUPS = pathlib.Path('feed/lineups-current.json')
WATCHDOG = pathlib.Path('feed/lineup-watchdog-current.json')
POSTXI = pathlib.Path('feed/post-xi-refresh-request.json')

# One complete target-discovery pass per workflow. If official XI is still
# missing close to kickoff, subsequent checks are lightweight direct probes of
# only the imminent fixtures, using FotMob plus Sofascore fallback/cross-check.
MAX_ATTEMPTS = 6
POLL_INTERVAL_SECONDS = 35
URGENT_FROM_MIN = 0.0
URGENT_TO_MIN = 80.0
POST_XI_ACTIONABLE_FROM_MIN = 0.0
POST_XI_ACTIONABLE_TO_MIN = 100.0


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
    return (
        bool(ln.get('confirmed'))
        and str(ln.get('lineup_type') or '').lower() == 'standard'
        and bool(ln.get('complete_11v11'))
    )


def fingerprint(m):
    ln = ((m or {}).get('lineup') or {})
    return ln.get('xi_name_fingerprint') or ln.get('xi_fingerprint')


def match_map(payload):
    return {
        key_of(m): m
        for m in (payload.get('matches') or [])
        if isinstance(m, dict) and key_of(m)
    }


def numeric_minutes(m):
    try:
        return float((m or {}).get('minutes_to_start'))
    except Exception:
        return None


def actionable_minutes(m):
    mins = numeric_minutes(m)
    return mins is not None and POST_XI_ACTIONABLE_FROM_MIN < mins <= POST_XI_ACTIONABLE_TO_MIN


def urgent_missing(payload):
    out = []
    for m in payload.get('matches') or []:
        if not isinstance(m, dict):
            continue
        mins = numeric_minutes(m)
        if mins is None:
            continue
        if URGENT_FROM_MIN < mins <= URGENT_TO_MIN and not is_official(m):
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
        if not event_type:
            continue

        mins = numeric_minutes(cur)
        actionable = actionable_minutes(cur)
        events.append({
            'event': event_type,
            'detected_at': now_iso(),
            'match': cur.get('match'),
            'league': cur.get('league'),
            'start_time': cur.get('start_time'),
            'minutes_to_start': mins,
            'match_market_id': cur.get('match_market_id'),
            'match_event_id': cur.get('match_event_id'),
            'source': cur.get('source'),
            'source_status': cur.get('status'),
            'provider_match_id': ((cur.get('fotmob_match') or {}).get('id')),
            'previous_status': prev.get('status'),
            'current_status': cur.get('status'),
            'previous_xi_fingerprint': prev_fp,
            'current_xi_fingerprint': cur_fp,
            'confirmed_at': cur.get('confirmed_at'),
            'actionable_for_post_xi': actionable,
            'actionability_reason': (
                'PRE_KICKOFF_OFFICIAL_XI_TRANSITION'
                if actionable
                else 'AUDIT_ONLY_MATCH_ALREADY_STARTED_OR_OUTSIDE_POST_XI_WINDOW'
            ),
        })
    return events


def run_script(path):
    cp = subprocess.run([sys.executable, str(path)], check=False)
    if cp.returncode != 0:
        raise SystemExit(cp.returncode)
    return load_json(LINEUPS, {})


pathlib.Path('feed').mkdir(exist_ok=True)
initial = load_json(LINEUPS, {'matches': []})
reference = initial
attempt_records = []
all_events = []
actionable_events = []

# Attempt 1: one complete canonical discovery pass.
started = now_iso()
final_payload = run_script(BASE_SCRIPT)
missing = urgent_missing(final_payload)

# If anything imminent is still unresolved, immediately run the lightweight
# dual-source probe before waiting. This can promote a Sofascore-confirmed XI
# even when FotMob has not published its standard lineup yet.
if missing:
    final_payload = run_script(URGENT_SCRIPT)

events = detect_events(reference, final_payload)
actionable_now = [e for e in events if e.get('actionable_for_post_xi')]
missing = urgent_missing(final_payload)
attempt_records.append({
    'attempt': 1,
    'mode': 'FULL_DISCOVERY_PLUS_IMMEDIATE_URGENT_FALLBACK' if missing or events else 'FULL_DISCOVERY',
    'started_at': started,
    'finished_at': now_iso(),
    'official_count': sum(1 for m in (final_payload.get('matches') or []) if is_official(m)),
    'urgent_unconfirmed_count': len(missing),
    'events': events,
    'actionable_events': actionable_now,
})
all_events.extend(events)
actionable_events.extend(actionable_now)
reference = final_payload

# Attempts 2..N: no global rediscovery. Probe only imminent fixture IDs.
if not actionable_now and missing:
    for attempt in range(2, MAX_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_SECONDS)
        started = now_iso()
        final_payload = run_script(URGENT_SCRIPT)
        events = detect_events(reference, final_payload)
        actionable_now = [e for e in events if e.get('actionable_for_post_xi')]
        missing = urgent_missing(final_payload)
        attempt_records.append({
            'attempt': attempt,
            'mode': 'URGENT_DIRECT_DUAL_SOURCE',
            'started_at': started,
            'finished_at': now_iso(),
            'official_count': sum(1 for m in (final_payload.get('matches') or []) if is_official(m)),
            'urgent_unconfirmed_count': len(missing),
            'events': events,
            'actionable_events': actionable_now,
        })
        all_events.extend(events)
        actionable_events.extend(actionable_now)
        reference = final_payload
        if actionable_now or not missing:
            break

remaining = urgent_missing(final_payload)
watchdog = {
    'schema': 'radar-lineup-watchdog-v3',
    'generated_at': now_iso(),
    'source_strategy': 'One canonical full discovery; then targeted FotMob + Sofascore confirmed XI probes for imminent unresolved fixtures',
    'official_definition': 'SOURCE_CONFIRMED/CROSS_CONFIRMED + lineupType=standard + complete 11v11',
    'poll_policy': {
        'base_schedule': 'GitHub cron every 5 minutes',
        'urgent_window_minutes': [URGENT_FROM_MIN, URGENT_TO_MIN],
        'post_xi_actionable_window_minutes': [POST_XI_ACTIONABLE_FROM_MIN, POST_XI_ACTIONABLE_TO_MIN],
        'max_attempts_per_run': MAX_ATTEMPTS,
        'interval_seconds': POLL_INTERVAL_SECONDS,
        'full_discovery_attempts_per_run': 1,
        'subsequent_attempt_mode': 'targeted imminent fixtures only',
        'secondary_source': 'Sofascore confirmed=true',
        'stop_immediately_on_actionable_official_transition': True,
        'started_matches_are_audit_only': True,
    },
    'attempt_count': len(attempt_records),
    'attempts': attempt_records,
    'observed_events': all_events,
    'actionable_events': actionable_events,
    'post_xi_required': bool(actionable_events),
    'urgent_unconfirmed_remaining': remaining,
    'target_count': len(final_payload.get('matches') or []),
}
WATCHDOG.write_text(json.dumps(watchdog, ensure_ascii=False, indent=2), encoding='utf-8')

postxi = {
    'schema': 'radar-post-xi-refresh-request-v3',
    'generated_at': watchdog['generated_at'],
    'required': bool(actionable_events),
    'reason': (
        'Pre-kickoff official XI detected or changed; rebuild tactical roles, player context and deep-analysis readiness immediately.'
        if actionable_events
        else 'No actionable pre-kickoff official XI transition in this watchdog run.'
    ),
    'events': actionable_events,
    'observed_audit_events': [e for e in all_events if not e.get('actionable_for_post_xi')],
}
POSTXI.write_text(json.dumps(postxi, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(watchdog, ensure_ascii=False, indent=2))
