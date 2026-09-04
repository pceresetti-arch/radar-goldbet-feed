import json
import pathlib
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone

from betflag_session_transport import BetFlagTransport

BASE = 'https://sportservice.betflag.it/api/sport/pregame'
AGG = 1334500001
FEED = pathlib.Path('feed')
PLAYER_FEED = FEED / 'betflag-residential-current.json'
OUT = FEED / 'betflag-combo-fixture-structure.json'


def norm(v):
    s = unicodedata.normalize('NFD', str(v or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower().replace('°', '')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def walk(x, path='root'):
    if isinstance(x, dict):
        yield path, x
        for k, v in x.items():
            yield from walk(v, f'{path}.{k}')
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from walk(v, f'{path}[{i}]')


def marketish(v):
    n = norm(v)
    return bool(re.search(r'marcat|marc |assist|giocator|player|combo|doppietta|tripletta|tiri|parate|segna', n))


def overview_fixtures(std):
    out = {}
    for _, x in walk(std):
        en = str(x.get('en') or '')
        if x.get('mi') is None or not en or en.startswith('('):
            continue
        out.setdefault(norm(en), {'match': en, 'nodes': []})['nodes'].append({k: x.get(k) for k in ('ei','mi','ti','tai','ed','en')})
    return out


def player_candidates():
    if not PLAYER_FEED.exists():
        return []
    data = json.loads(PLAYER_FEED.read_text(encoding='utf-8-sig'))
    counts = Counter(r.get('match') for r in data.get('rows') or [] if r.get('match'))
    rows = [{'match': m, 'player_rows': n} for m, n in counts.items()]
    rows.sort(key=lambda r: (-r['player_rows'], r['match']))
    return rows[:12]


def best_node(nodes):
    return sorted(nodes, key=lambda x: sum(x.get(k) is not None for k in ('tai','ti','mi','ei')), reverse=True)[0] if nodes else None


def summarize_dict(path, x):
    vals = {}
    for k, v in x.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            sv = str(v)
            vals[k] = sv[:180]
    return {
        'path': path,
        'keys': sorted(x.keys()),
        'scalar_values': vals,
        'list_lengths': {k: len(v) for k, v in x.items() if isinstance(v, list)},
        'dict_keys': {k: sorted(v.keys())[:40] for k, v in x.items() if isinstance(v, dict)},
    }


def diagnostics(body):
    market_nodes = []
    selection_nodes = []
    key_counts = Counter()
    for path, x in walk(body):
        for k in x.keys():
            key_counts[k] += 1
        scalar_text = ' | '.join(str(v) for v in x.values() if isinstance(v, (str, int, float)))
        if marketish(scalar_text) and len(market_nodes) < 80:
            market_nodes.append(summarize_dict(path, x))
        # Selection/odd candidates independent of the currently assumed nesting.
        if any(k in x for k in ('ov','odd','price','quota')) and len(selection_nodes) < 80:
            selection_nodes.append(summarize_dict(path, x))
    return {
        'top_keys': key_counts.most_common(80),
        'market_nodes': market_nodes,
        'selection_like_nodes': selection_nodes,
        'market_node_count_captured': len(market_nodes),
        'selection_node_count_captured': len(selection_nodes),
    }


def main():
    client = BetFlagTransport(timeout=20)
    out = {
        'schema_version': 'betflag-combo-fixture-structure-v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source_class': 'BETFLAG_AAMS_DIRECT',
        'purpose': 'Discover fixture-specific market/selection nesting without assuming that asl lives under the market-name node.',
        'fixtures': [],
        'source_healthy': False,
    }
    try:
        st, overview = client.get(f'{BASE}/getOverviewEventsAams/0/1/0/{AGG}/0/0/0?channelId=0')
        out['overview_status'] = st
        if st != 200:
            raise RuntimeError(f'overview HTTP {st}')
        fixtures = overview_fixtures(overview)
        for cand in player_candidates():
            f = fixtures.get(norm(cand['match']))
            row = {**cand, 'resolved': bool(f), 'sections': []}
            if not f:
                out['fixtures'].append(row)
                continue
            node = best_node(f['nodes'])
            row['ids'] = node
            if not node or any(node.get(k) is None for k in ('ti','mi','ei')):
                row['error'] = 'missing detail identifiers'
                out['fixtures'].append(row)
                continue
            tai = node.get('tai') or 0
            # Section 0 currently returns the broad market tree; 2484 is kept as
            # a targeted special/player candidate when exposed by BetFlag.
            for sec in (0, 2484):
                url = f"{BASE}/getDetailsEventAams/{tai}/{node['ti']}/{node['mi']}/{node['ei']}/{sec}/0?channelId=0"
                try:
                    status, body = client.get(url)
                    row['sections'].append({'section': sec, 'status': status, 'diagnostics': diagnostics(body) if status == 200 else None})
                except Exception as e:
                    row['sections'].append({'section': sec, 'status': None, 'error': repr(e)})
            out['fixtures'].append(row)
        out['resolved_fixture_count'] = sum(1 for r in out['fixtures'] if r.get('resolved'))
        out['source_healthy'] = True
    except Exception as e:
        out['error'] = repr(e)
    finally:
        out['transport'] = client.diagnostics()
        client.close()
    FEED.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'source_healthy': out.get('source_healthy'), 'resolved_fixture_count': out.get('resolved_fixture_count'), 'fixture_count': len(out.get('fixtures') or [])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
