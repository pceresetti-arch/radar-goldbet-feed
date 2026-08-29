import argparse
import json
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX = ROOT / 'feed' / 'betflag-fixtures-index.json'


def norm(value):
    s = unicodedata.normalize('NFD', str(value or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fail(status, **extra):
    out = {'status': status, **extra}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(2)


def choose_fixture(index, query):
    q = norm(query)
    exact = [f for f in index.get('fixtures', []) if norm(f.get('match')) == q]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        fail('MATCH_AMBIGUOUS', query=query, matches=[x.get('match') for x in exact])

    qtokens = set(q.split())
    scored = []
    for f in index.get('fixtures', []):
        mtokens = set(norm(f.get('match')).split())
        if not qtokens or not mtokens:
            continue
        score = len(qtokens & mtokens) / len(qtokens | mtokens)
        if score >= 0.55:
            scored.append((score, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        fail('FIXTURE_NOT_FOUND', query=query)
    if len(scored) > 1 and abs(scored[0][0] - scored[1][0]) < 0.08:
        fail('MATCH_AMBIGUOUS', query=query, matches=[x[1].get('match') for x in scored[:5]])
    return scored[0][1]


def fresh_flag(v):
    if isinstance(v, dict):
        return bool(v.get('fresh'))
    return bool(v)


def validate_source(index, doc, player=False):
    if not index.get('source_healthy') or not doc.get('source_healthy'):
        fail('ACQUISITION_FAILED', reason='source_unhealthy')
    key = 'player_freshness' if player else 'standard_freshness'
    dkey = 'player' if player else 'standard'
    idx_fresh = fresh_flag(index.get(key))
    doc_fresh = fresh_flag((doc.get('freshness') or {}).get(dkey))
    if not idx_fresh or not doc_fresh:
        fail('ACQUISITION_FAILED', reason='stale_snapshot')
    if doc.get('source_class') != 'BETFLAG_AAMS_DIRECT':
        fail('ACQUISITION_FAILED', reason='unexpected_source_class', source_class=doc.get('source_class'))


def resolve_player(doc, player, market, selection='Si', line=None):
    pnorm = norm(player)
    candidates = [p for p in doc.get('players', []) if norm(p.get('player')) == pnorm]
    if not candidates:
        if not doc.get('players'):
            fail('MARKET_NOT_EXPOSED', reason='player_props_empty', player=player)
        fail('PLAYER_NOT_EXPOSED_OR_NAMING_MISMATCH', player=player)
    if len(candidates) > 1:
        fail('PLAYER_AMBIGUOUS', player=player)

    p = candidates[0]
    mnorm = norm(market)
    markets = [m for m in p.get('markets', []) if norm(m.get('market')) == mnorm]
    if not markets:
        fail('MARKET_NOT_QUOTED', player=p.get('player'), market=market)

    quotes = []
    for m in markets:
        for q in m.get('quotes', []):
            if norm(q.get('selection')) != norm(selection):
                continue
            if line is not None and norm(q.get('line')) != norm(line):
                continue
            if float(q.get('odd') or 0) > 0:
                quotes.append(q)
    if not quotes:
        fail('SELECTION_NOT_QUOTED', player=p.get('player'), market=market, selection=selection, line=line)
    if len(quotes) > 1 and line is None:
        fail('LINE_REQUIRED', player=p.get('player'), market=market, available_lines=[q.get('line') for q in quotes])
    q = quotes[0]
    return {
        'status': 'BETFLAG_QUOTE_RECOVERED',
        'source_class': doc.get('source_class'),
        'match': doc.get('match'),
        'match_start': doc.get('match_start'),
        'player': p.get('player'),
        'market': market,
        'selection': q.get('selection'),
        'line': q.get('line'),
        'odd': q.get('odd'),
        'generated_at': doc.get('generated_at'),
    }


def resolve_standard(doc, market, selection, line=None):
    mnorm = norm(market)
    rows = []
    for r in doc.get('standard', []):
        if norm(r.get('market')) != mnorm and norm(r.get('family')) != mnorm:
            continue
        if norm(r.get('selection')) != norm(selection):
            continue
        if line is not None and norm(r.get('line')) != norm(line):
            continue
        if float(r.get('odd') or 0) > 0:
            rows.append(r)
    if not rows:
        fail('MARKET_NOT_QUOTED', market=market, selection=selection, line=line)
    if len(rows) > 1 and line is None:
        fail('LINE_REQUIRED', market=market, available_lines=sorted({r.get('line') for r in rows}))
    r = rows[0]
    return {
        'status': 'BETFLAG_QUOTE_RECOVERED',
        'source_class': doc.get('source_class'),
        'match': doc.get('match'),
        'match_start': doc.get('match_start'),
        'market': r.get('market'),
        'family': r.get('family'),
        'selection': r.get('selection'),
        'line': r.get('line'),
        'odd': r.get('odd'),
        'generated_at': doc.get('generated_at'),
    }


def main():
    ap = argparse.ArgumentParser(description='Resolve a BetFlag quote from the current v7 fixture feed.')
    ap.add_argument('--match', required=True)
    ap.add_argument('--market', required=True)
    ap.add_argument('--selection', default='Si')
    ap.add_argument('--line')
    ap.add_argument('--player')
    args = ap.parse_args()

    if not INDEX.exists():
        fail('ACQUISITION_FAILED', reason='fixture_index_missing')
    index = load_json(INDEX)
    fixture = choose_fixture(index, args.match)
    path = ROOT / fixture['file']
    if not path.exists():
        fail('ACQUISITION_FAILED', reason='fixture_file_missing', file=fixture.get('file'))
    doc = load_json(path)

    validate_source(index, doc, player=bool(args.player))
    if args.player:
        out = resolve_player(doc, args.player, args.market, args.selection, args.line)
    else:
        out = resolve_standard(doc, args.market, args.selection, args.line)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
