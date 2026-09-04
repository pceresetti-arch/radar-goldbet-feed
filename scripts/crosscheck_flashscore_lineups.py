#!/usr/bin/env python3
import difflib
import json
import pathlib
import re
import unicodedata
from datetime import datetime, timezone

from curl_cffi import requests

LINEUPS = pathlib.Path('feed/lineups-current.json')
SUMMARY = pathlib.Path('feed/lineups-current-summary.json')
OUT = pathlib.Path('feed/flashscore-lineup-crosscheck.json')
NOW = datetime.now(timezone.utc)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.8',
    'Referer': 'https://www.flashscore.com/',
    'Origin': 'https://www.flashscore.com',
    'x-fsign': 'SW9D1eZo',
}


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def split_match(s):
    for sep in (' - ', ' vs ', ' v '):
        if sep in str(s):
            return tuple(x.strip() for x in str(s).split(sep, 1))
    return str(s), ''


def side_score(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    A, B = set(a.split()), set(b.split())
    jac = len(A & B) / max(1, len(A | B))
    cont = 1.0 if a in b or b in a else 0.0
    return .62 * seq + .23 * jac + .15 * cont


def get_text(url):
    r = requests.get(url, headers=HEADERS, impersonate='chrome', timeout=18)
    return r.status_code, r.text


def flashscore_matches(day=0):
    urls = [
        f'https://local-global.flashscore.ninja/2/x/feed/f_1_{day}_3_en_1',
        f'https://local-global.flashscore.ninja/2/x/feed/f_1_{day}_3_it_1',
    ]
    last = None
    for u in urls:
        try:
            st, txt = get_text(u)
            if st != 200 or 'AA÷' not in txt:
                last = {'url': u, 'status': st, 'bytes': len(txt)}
                continue
            events = []
            for b in txt.split('~AA÷')[1:]:
                eid = b.split('¬', 1)[0]
                fields = {}
                for part in b.split('¬'):
                    if '÷' in part:
                        k, v = part.split('÷', 1)
                        fields[k] = v
                if eid and fields.get('AE') and fields.get('AF'):
                    events.append({'id': eid, 'home': fields.get('AE'), 'away': fields.get('AF'), 'raw_start': fields.get('AD')})
            return events, {'url': u, 'status': st, 'event_count': len(events)}
        except Exception as e:
            last = {'url': u, 'error': type(e).__name__ + ': ' + str(e)[:180]}
    return [], last or {'error': 'FLASH_DISCOVERY_FAILED'}


def best_event(match, events):
    h, a = split_match(match)
    best = None
    for e in events:
        s = (side_score(h, e.get('home')) + side_score(a, e.get('away'))) / 2.0
        if best is None or s > best[0]:
            best = (s, e)
    return (best[1], best[0]) if best and best[0] >= .72 else (None, 0.0)


def starter_names(lineup, side):
    teams = lineup.get('teams') or []
    idx = 0 if side == 'home' else 1
    if len(teams) <= idx:
        return []
    return [str(p.get('name') or '').strip() for p in teams[idx].get('starters') or [] if p.get('name')]


def text_name_match(name, normalized_text):
    n = norm(name)
    if not n:
        return False
    if n in normalized_text:
        return True
    parts = [x for x in n.split() if len(x) >= 3]
    if len(parts) >= 2 and all(x in normalized_text for x in parts[-2:]):
        return True
    # Initial + surname/provider formatting tolerance: the final token must be
    # present and one additional meaningful token must agree.
    return bool(parts and parts[-1] in normalized_text and sum(1 for x in parts[:-1] if x in normalized_text) >= 1)


def explicit_starting_lineup(text):
    low = norm(text)
    predicted = any(x in low for x in ('predicted lineup', 'probable lineup', 'expected lineup', 'possible lineup'))
    final_marker = any(x in low for x in ('starting lineups', 'starting lineup', 'starting xi', 'lineups confirmed', 'confirmed lineup'))
    return final_marker and not predicted, predicted, final_marker


def crosscheck(match, events):
    ev, match_score = best_event(match.get('match'), events)
    result = {
        'provider': 'Diretta/Flashscore',
        'matched': bool(ev),
        'match_score': round(match_score, 4),
        'cross_confirmed': False,
    }
    if not ev:
        return result
    result['event'] = ev
    urls = [
        f'https://local-global.flashscore.ninja/2/x/feed/df_li_1_{ev["id"]}',
        f'https://2.ds.lsapp.eu/pq_graphql?_hash=dlie2&eventId={ev["id"]}&projectId=2',
    ]
    bodies = []
    attempts = []
    for u in urls:
        try:
            st, txt = get_text(u)
            attempts.append({'url': u, 'status': st, 'bytes': len(txt)})
            if st == 200 and txt:
                bodies.append(txt)
        except Exception as e:
            attempts.append({'url': u, 'error': type(e).__name__ + ': ' + str(e)[:160]})
    result['attempts'] = attempts
    if not bodies:
        return result

    combined = '\n'.join(bodies)
    norm_text = norm(combined)
    final_ok, predicted, final_marker = explicit_starting_lineup(combined)
    result['explicit_final_starting_marker'] = final_marker
    result['predicted_marker'] = predicted

    lineup = match.get('lineup') or {}
    home = starter_names(lineup, 'home')
    away = starter_names(lineup, 'away')
    hm = [n for n in home if text_name_match(n, norm_text)]
    am = [n for n in away if text_name_match(n, norm_text)]
    result['home_starters_expected'] = len(home)
    result['away_starters_expected'] = len(away)
    result['home_name_matches'] = len(hm)
    result['away_name_matches'] = len(am)
    result['home_missing'] = [n for n in home if n not in hm]
    result['away_missing'] = [n for n in away if n not in am]
    result['cross_confirmed'] = bool(
        final_ok and len(home) == 11 and len(away) == 11 and len(hm) >= 10 and len(am) >= 10
    )
    result['policy'] = 'Upgrade only with explicit final starting-lineup marker, no predicted/probable marker, complete existing 11v11 and >=10/11 name agreement per side.'
    return result


def main():
    if not LINEUPS.exists():
        raise SystemExit('feed/lineups-current.json missing')
    payload = json.loads(LINEUPS.read_text(encoding='utf-8'))
    matches = payload.get('matches') or []
    flash0, meta0 = flashscore_matches(0)
    flash1, meta1 = flashscore_matches(1)
    events = flash0 + [x for x in flash1 if x.get('id') not in {e.get('id') for e in flash0}]
    audit = {
        'schema': 'radar-flashscore-lineup-crosscheck-v1',
        'generated_at': NOW.isoformat(),
        'schedule_meta': [meta0, meta1],
        'policy': 'Flashscore is an independent XI cross-check, never a standalone official source. Predicted/probable lineups are explicitly rejected.',
        'targets': [],
        'upgrades': [],
    }
    for m in matches:
        try:
            mins = float(m.get('minutes_to_start'))
        except Exception:
            mins = None
        if mins is None or not (0 < mins <= 100):
            continue
        lineup = m.get('lineup') or {}
        if not (lineup.get('confirmed') and lineup.get('complete_11v11') and str(lineup.get('lineup_type') or '').lower() == 'standard'):
            continue
        row = crosscheck(m, events)
        row.update({'match': m.get('match'), 'match_market_id': m.get('match_market_id'), 'minutes_to_start': mins, 'status_before': m.get('status'), 'source_before': m.get('source')})
        audit['targets'].append(row)
        evidence = m.get('source_evidence') if isinstance(m.get('source_evidence'), dict) else {}
        evidence['flashscore'] = row
        m['source_evidence'] = evidence
        if row.get('cross_confirmed') and m.get('status') == 'SOURCE_CONFIRMED':
            m['status'] = 'CROSS_CONFIRMED'
            source = str(m.get('source') or 'Provider')
            if 'Flashscore' not in source:
                source += '+Flashscore'
            m['source'] = source
            m['cross_confirmed_at'] = NOW.isoformat()
            audit['upgrades'].append({'match': m.get('match'), 'match_market_id': m.get('match_market_id'), 'source': source, 'home_matches': row.get('home_name_matches'), 'away_matches': row.get('away_name_matches')})
    payload['generated_at'] = NOW.isoformat()
    payload['flashscore_crosscheck'] = {
        'generated_at': NOW.isoformat(),
        'target_count': len(audit['targets']),
        'upgrade_count': len(audit['upgrades']),
        'policy': audit['policy'],
    }
    LINEUPS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {k: v for k, v in payload.items() if k != 'matches'}
    summary['matches'] = [
        {k: m.get(k) for k in ('match','start_time','league','minutes_to_start','status','match_market_id','confirmed_at','xi_changed_after_confirmation','target_origin','source')}
        for m in matches if isinstance(m, dict)
    ]
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'target_count': len(audit['targets']), 'upgrade_count': len(audit['upgrades']), 'upgrades': audit['upgrades']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
