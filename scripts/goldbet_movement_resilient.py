#!/usr/bin/env python3
import concurrent.futures, difflib, hashlib, json, os, pathlib, re, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.isoformat()
ROME = ZoneInfo('Europe/Rome')
ROOT = pathlib.Path('feed')
STATE = ROOT / 'goldbet-movement-resilient-state.json'
CURRENT = ROOT / 'goldbet-movement-resilient-current.json'
QUERY_OUT = ROOT / 'radar-movement-current.json'
REQUEST = pathlib.Path('radar-movement-request.json')
TRUEOPEN = ROOT / 'diretta-goldbet-true-open-index.json'
BASE = 'https://radar-goldbet.p-ceresetti.workers.dev/odds'
TOKEN = os.environ.get('BRIDGE_TOKEN', '').strip()
if not TOKEN:
    raise SystemExit('Missing BRIDGE_TOKEN')
ROOT.mkdir(exist_ok=True)


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    except Exception:
        return default


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(fc|cf|sc|ac|afc|club|calcio|football|fk|bk)\b', ' ', s)
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def event_score(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    A, B = set(a.split()), set(b.split())
    jac = len(A & B) / max(1, len(A | B))
    return max(seq, .72 * seq + .28 * jac)


def fnum(v):
    try:
        return float(v)
    except Exception:
        return None


def same_line(a, b):
    if a is None and b is None:
        return True
    aa, bb = fnum(a), fnum(b)
    if aa is not None and bb is not None:
        return abs(aa - bb) < 1e-9
    return str(a) == str(b)


def identity(o):
    raw = '|'.join(str(o.get(x) if o.get(x) is not None else '') for x in
                   ('source', 'bookmaker', 'event_id', 'market', 'line', 'scope', 'period', 'selection'))
    return hashlib.sha1(raw.encode()).hexdigest()[:24]


def relevant_market(m):
    s = str(m or '').lower()
    return any(x in s for x in ('1x2', 'over', 'under', 'goal', 'btts', 'double', 'doppia', 'total', 'totale'))


def page(off):
    qs = urllib.parse.urlencode({'token': TOKEN, 'bookmakers': 'goldbet', 'state': 'prematch', 'limit': '2000', 'offset': str(off)})
    req = urllib.request.Request(BASE + '?' + qs, headers={'Accept': 'application/json', 'User-Agent': 'RadarGoldBetMovementResilient/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=75) as r:
            d = json.loads(r.read().decode('utf-8', 'replace'))
            return {'offset': off, 'status': r.status, 'count': d.get('count'), 'rows': d.get('odds') or [], 'error': None}
    except Exception as e:
        return {'offset': off, 'status': None, 'count': None, 'rows': [], 'error': f'{type(e).__name__}: {e}'[:240]}


# Full direct-GoldBet scan. A complete scan is what makes absence proof meaningful.
offsets = list(range(0, 30000, 2000))
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    pages = list(ex.map(page, offsets))
errors = [p for p in pages if p['error']]
total = max([int(p.get('count') or 0) for p in pages] or [0])
needed_offsets = set(range(0, ((max(total, 1) - 1) // 2000 + 1) * 2000, 2000)) if total else set()
returned_offsets = {p['offset'] for p in pages if not p['error']}
scan_complete = bool(total >= 0 and (not needed_offsets or needed_offsets.issubset(returned_offsets)))
rows = []
for p in pages:
    if not p['error'] and (total == 0 or p['offset'] < total):
        rows.extend(p['rows'])

observations = []
for r in rows:
    if not isinstance(r, dict) or not relevant_market(r.get('market')):
        continue
    st = parse_dt(r.get('commence_time'))
    if st and (st < NOW - timedelta(hours=18) or st > NOW + timedelta(days=14)):
        continue
    bms = r.get('bookmakers') or []
    bm = None
    if isinstance(bms, list):
        bm = next((b for b in bms if isinstance(b, dict) and str(b.get('key', '')).lower() == 'goldbet'), None)
    elif isinstance(bms, dict):
        bm = bms.get('goldbet') or bms
    if not isinstance(bm, dict):
        continue
    outs = bm.get('outcomes') or {}
    if not isinstance(outs, dict):
        continue
    for sel, price in outs.items():
        try:
            price = float(price)
        except Exception:
            continue
        observations.append({
            'source': 'GOLDBET_DIRECT_STANDARD', 'bookmaker': 'goldbet',
            'event_id': r.get('event_id'), 'event': r.get('event') or f"{r.get('home_team','')} - {r.get('away_team','')}",
            'league': r.get('league'), 'start_time': r.get('commence_time'), 'market': r.get('market'),
            'line': r.get('line'), 'scope': r.get('scope'), 'period': r.get('period'), 'selection': str(sel),
            'price': price, 'source_last_update': bm.get('last_update')
        })

old = load(STATE, {})
records = old.get('records') if isinstance(old, dict) else {}
if not isinstance(records, dict):
    records = {}
prev = old.get('last_healthy_scan') if isinstance(old, dict) else None
prev_keys = set((prev or {}).get('keys') or []) if isinstance(prev, dict) else set()
prev_at = parse_dt((prev or {}).get('captured_at')) if isinstance(prev, dict) else None
absence_window_ok = bool(prev_at and scan_complete and 0 <= (NOW - prev_at).total_seconds() <= 12 * 60)

# Diretta/Flashscore GoldBet opening is an independent way to recover a genuine bookmaker opening.
to = load(TRUEOPEN, {})
true_events = to.get('events') if isinstance(to, dict) else {}
if not isinstance(true_events, dict):
    true_events = {}


def true_open_match(rec, row):
    if not isinstance(row, dict):
        return False
    m = str(rec.get('market') or '').lower()
    sel = str(rec.get('selection') or '').upper()
    period = str(rec.get('period') or '').lower()
    scope = str(rec.get('scope') or '').lower()
    if period and period not in ('full_time', 'fulltime', 'match', 'ft'):
        return False
    bt, rs = row.get('market'), str(row.get('selection') or '').upper()
    if sel != rs:
        return False
    if bt == 'HOME_DRAW_AWAY':
        return m == '1x2'
    if bt == 'BOTH_TEAMS_TO_SCORE':
        return m in ('btts', 'both_teams_to_score', 'goal_no_goal') or 'btts' in m or 'goal' in m
    if bt == 'OVER_UNDER':
        if 'team' in m or scope in ('home_team', 'away_team'):
            return False
        return ('total' in m or 'over' in m or 'under' in m) and same_line(rec.get('line'), row.get('line'))
    if bt == 'DOUBLE_CHANCE':
        return 'double' in m or 'doppia' in m
    return False


checkpoints = (120, 75, 60, 40, 30, 15)
new_count = changed_count = checkpoint_updates = 0
current_keys = set()
for o in observations:
    k = identity(o)
    current_keys.add(k)
    st = parse_dt(o.get('start_time'))
    mt = None if not st else round((st - NOW).total_seconds() / 60, 2)
    rec = records.get(k)
    if not isinstance(rec, dict):
        direct_cert = bool(absence_window_ok and k not in prev_keys)
        rec = {
            'key': k, 'source': o['source'], 'bookmaker': 'goldbet', 'event_id': o.get('event_id'),
            'event': o.get('event'), 'league': o.get('league'), 'start_time': o.get('start_time'),
            'market': o.get('market'), 'line': o.get('line'), 'scope': o.get('scope'), 'period': o.get('period'),
            'selection': o.get('selection'), 'first_seen_at': NOW_ISO, 'first_seen_price': o['price'],
            'current_price': o['price'], 'last_change_at': NOW_ISO, 'change_count': 0,
            'min_price': o['price'], 'max_price': o['price'], 'changes': [], 'checkpoints': {}, 'request_snapshots': [],
            'direct_open_status': 'TRUE_OPEN_CERTIFIED_WITHIN_SCAN_INTERVAL' if direct_cert else 'FIRST_SEEN_ONLY',
            'direct_open_price': o['price'] if direct_cert else None,
            'direct_open_absent_at': (prev or {}).get('captured_at') if direct_cert else None,
            'direct_open_seen_at': NOW_ISO if direct_cert else None,
        }
        records[k] = rec
        new_count += 1
    else:
        try:
            different = abs(float(rec.get('current_price')) - o['price']) > 1e-9
        except Exception:
            different = rec.get('current_price') != o['price']
        if different:
            rec.setdefault('changes', []).append({'from': rec.get('current_price'), 'to': o['price'], 'at': NOW_ISO, 'minutes_to_start': mt})
            rec['changes'] = rec['changes'][-120:]
            rec['current_price'] = o['price']
            rec['last_change_at'] = NOW_ISO
            rec['change_count'] = int(rec.get('change_count') or 0) + 1
            rec['min_price'] = min(float(rec.get('min_price', o['price'])), o['price'])
            rec['max_price'] = max(float(rec.get('max_price', o['price'])), o['price'])
            changed_count += 1
    rec['last_observed_at'] = NOW_ISO
    rec['last_observed_minutes_to_start'] = mt
    rec['source_last_update'] = o.get('source_last_update')

    # Keep the closest observed snapshot to each checkpoint, not the first one in a broad bucket.
    if mt is not None:
        cps = rec.setdefault('checkpoints', {})
        for cp in checkpoints:
            dist = abs(mt - cp)
            if dist <= 7.5:
                oldcp = cps.get(f'T-{cp}')
                olddist = fnum((oldcp or {}).get('distance_from_target_min')) if isinstance(oldcp, dict) else None
                if olddist is None or dist + 1e-9 < olddist:
                    quality = 'EXACT_NEAR' if dist <= 1.5 else ('GOOD' if dist <= 3.0 else ('ACCEPTABLE' if dist <= 5.0 else 'FALLBACK'))
                    cps[f'T-{cp}'] = {'price': o['price'], 'captured_at': NOW_ISO, 'minutes_to_start': mt,
                                      'target_minutes': cp, 'distance_from_target_min': round(dist, 2), 'quality': quality}
                    checkpoint_updates += 1

    tev = true_events.get(str(rec.get('event_id') or ''))
    if isinstance(tev, dict) and tev.get('status') == 'TRUE_OPEN_CERTIFIED':
        for row in tev.get('rows') or []:
            if true_open_match(rec, row):
                rec['true_open_status'] = 'TRUE_OPEN_CERTIFIED_GOLDBET_DIRETTA'
                rec['true_open_price'] = row.get('true_open')
                rec['true_open_source'] = 'Diretta/Flashscore GoldBet bookmaker opening'
                rec['true_open_certified_at'] = tev.get('certified_at')
                rec['true_open_flashscore_event_id'] = tev.get('flashscore_event_id')
                break

# Drop old fixtures; preserve enough history for retrospective checks.
records = {k: r for k, r in records.items() if not (parse_dt(r.get('start_time')) and parse_dt(r.get('start_time')) < NOW - timedelta(days=10))}

last_healthy_scan = old.get('last_healthy_scan') if isinstance(old, dict) else None
if scan_complete:
    last_healthy_scan = {'captured_at': NOW_ISO, 'keys': sorted(current_keys), 'row_count': len(observations), 'endpoint_total': total}

state = {
    'schema_version': 'goldbet-movement-resilient-v1.0', 'generated_at': NOW_ISO,
    'scan_complete': scan_complete, 'page_errors': errors, 'endpoint_total': total,
    'observation_count': len(observations), 'new_count': new_count, 'changed_count': changed_count,
    'checkpoint_updates': checkpoint_updates, 'last_healthy_scan': last_healthy_scan, 'records': records
}
STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

# Compact hot feed for imminent fixtures, easy for ChatGPT/GitHub connector to read.
hot = {}
for r in records.values():
    if r.get('source') != 'GOLDBET_DIRECT_STANDARD':
        continue
    st = parse_dt(r.get('start_time'))
    mt = None if not st else round((st - NOW).total_seconds() / 60, 1)
    if mt is None or mt < -15 or mt > 180:
        continue
    eid = str(r.get('event_id') or '')
    g = hot.setdefault(eid, {'event_id': r.get('event_id'), 'event': r.get('event'), 'league': r.get('league'),
                             'start_time': r.get('start_time'), 'minutes_to_start': mt, 'markets': []})
    cps = r.get('checkpoints') or {}
    oq = 'TRUE_OPEN_CERTIFIED' if r.get('true_open_status') == 'TRUE_OPEN_CERTIFIED_GOLDBET_DIRETTA' else r.get('direct_open_status', 'FIRST_SEEN_ONLY')
    op = r.get('true_open_price') if r.get('true_open_status') == 'TRUE_OPEN_CERTIFIED_GOLDBET_DIRETTA' else (r.get('direct_open_price') if r.get('direct_open_status') == 'TRUE_OPEN_CERTIFIED_WITHIN_SCAN_INTERVAL' else None)
    g['markets'].append({'market': r.get('market'), 'line': r.get('line'), 'scope': r.get('scope'), 'period': r.get('period'),
                         'selection': r.get('selection'), 'opening_quality': oq, 'true_open': op,
                         'first_seen': r.get('first_seen_price'), 'first_seen_at': r.get('first_seen_at'),
                         'T-40': cps.get('T-40'), 'T-30': cps.get('T-30'), 'current': r.get('current_price'),
                         'current_at': r.get('last_observed_at'), 'changes': r.get('change_count')})
current = {'schema_version': 'goldbet-movement-hot-v1.0', 'generated_at': NOW_ISO, 'scan_complete': scan_complete,
           'source_class': 'GOLDBET_DIRECT_STANDARD', 'bookmaker': 'GoldBet', 'fixtures': sorted(hot.values(), key=lambda x: x.get('start_time') or '')}
CURRENT.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')

# On-demand compact query. Every request produces a decision-time snapshot from this same live scan.
req = load(REQUEST, {})
queries = req.get('queries') if isinstance(req, dict) else []
if not isinstance(queries, list):
    queries = []
results = []
for q in queries[:40]:
    if not isinstance(q, dict):
        continue
    qevent, qeid = q.get('event'), str(q.get('event_id') or '')
    candidates = []
    for r in records.values():
        if r.get('source') != 'GOLDBET_DIRECT_STANDARD':
            continue
        if qeid and str(r.get('event_id') or '') != qeid:
            continue
        score = 1.0 if qeid else event_score(qevent, r.get('event'))
        if not qeid and score < .58:
            continue
        if q.get('market') and norm(q.get('market')) != norm(r.get('market')):
            continue
        if 'line' in q and q.get('line') is not None and not same_line(q.get('line'), r.get('line')):
            continue
        if q.get('period') and norm(q.get('period')) != norm(r.get('period')):
            continue
        if q.get('scope') and norm(q.get('scope')) != norm(r.get('scope')):
            continue
        if q.get('selection') and norm(q.get('selection')) != norm(r.get('selection')):
            continue
        candidates.append((score, r))
    candidates.sort(key=lambda x: x[0], reverse=True)
    for score, r in candidates[:50]:
        snap = {'price': r.get('current_price'), 'captured_at': NOW_ISO, 'source_last_update': r.get('source_last_update')}
        rs = r.setdefault('request_snapshots', [])
        rs.append({'request_id': req.get('request_id'), **snap})
        r['request_snapshots'] = rs[-25:]
        cps = r.get('checkpoints') or {}
        diretta_cert = r.get('true_open_status') == 'TRUE_OPEN_CERTIFIED_GOLDBET_DIRETTA' and r.get('true_open_price') is not None
        direct_cert = r.get('direct_open_status') == 'TRUE_OPEN_CERTIFIED_WITHIN_SCAN_INTERVAL' and r.get('direct_open_price') is not None
        if diretta_cert:
            open_price, open_status, open_source = r.get('true_open_price'), 'TRUE_OPEN_CERTIFIED', r.get('true_open_source')
        elif direct_cert:
            open_price, open_status, open_source = r.get('direct_open_price'), 'TRUE_OPEN_CERTIFIED_WITHIN_SCAN_INTERVAL', 'GoldBet direct healthy-scan absence->appearance proof'
        else:
            open_price, open_status, open_source = r.get('first_seen_price'), 'FIRST_SEEN_ONLY', 'GoldBet direct first observed; NOT certified true open'
        try:
            delta = round(float(r.get('current_price')) - float(open_price), 3)
            pp = round((1/float(r.get('current_price')) - 1/float(open_price))*100, 3)
        except Exception:
            delta = pp = None
        results.append({'request_query': q, 'match_score': round(score, 4), 'event_id': r.get('event_id'), 'event': r.get('event'),
                        'league': r.get('league'), 'start_time': r.get('start_time'), 'bookmaker': 'GoldBet', 'source': 'GOLDBET_DIRECT_STANDARD',
                        'market': r.get('market'), 'line': r.get('line'), 'scope': r.get('scope'), 'period': r.get('period'), 'selection': r.get('selection'),
                        'open_status': open_status, 'open_price': open_price, 'open_source': open_source,
                        'first_seen_price': r.get('first_seen_price'), 'first_seen_at': r.get('first_seen_at'),
                        'T-40': cps.get('T-40'), 'T-30': cps.get('T-30'), 'request_snapshot': snap,
                        'current_price': r.get('current_price'), 'last_observed_at': r.get('last_observed_at'),
                        'price_delta_open_to_current': delta, 'implied_probability_delta_pp': pp,
                        'change_count': r.get('change_count'), 'changes': r.get('changes') or [],
                        'movement_complete': bool(open_status.startswith('TRUE_OPEN') and cps.get('T-40') and r.get('current_price') is not None)})

# Persist request snapshots added above as part of state.
state['records'] = records
STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
query_out = {'schema_version': 'radar-movement-query-v1.0', 'request_id': req.get('request_id'), 'requested_at': req.get('requested_at'),
             'generated_at': NOW_ISO, 'rome_time': datetime.now(ROME).isoformat(), 'scan_complete': scan_complete,
             'source': 'GOLDBET_DIRECT_STANDARD', 'same_bookmaker_enforced': True, 'same_identity_enforced': True,
             'result_count': len(results), 'results': results,
             'contract': {'true_open_never_invented': True, 'first_seen_not_equal_true_open': True,
                          'checkpoint_policy': 'closest observed snapshot within 7.5m; distance and quality always exposed',
                          'request_snapshot': 'fresh GoldBet direct scan performed in this workflow run'}}
QUERY_OUT.write_text(json.dumps(query_out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'generated_at': NOW_ISO, 'scan_complete': scan_complete, 'endpoint_total': total, 'observations': len(observations),
                  'new': new_count, 'changed': changed_count, 'checkpoint_updates': checkpoint_updates,
                  'hot_fixtures': len(hot), 'query_results': len(results)}, ensure_ascii=False, indent=2))
