import argparse
import json
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUS = ROOT / 'feed' / 'betflag-live-status.json'
CANONICAL_INDEX = ROOT / 'feed' / 'betflag-residential-fixtures-index.json'
COMPAT_INDEX = ROOT / 'feed' / 'betflag-fixtures-index.json'


def norm(value):
    s = unicodedata.normalize('NFD', str(value or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())


def load_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail('ACQUISITION_FAILED', reason='json_unreadable', file=str(path.relative_to(ROOT)), error=str(exc))


def fail(status, **extra):
    out = {'status': status, **extra}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(2)


def relative(path):
    try:
        return str(path.relative_to(ROOT)).replace('\\', '/')
    except ValueError:
        return str(path)


def resolve_index_path():
    candidates = []
    if STATUS.exists():
        status = load_json(STATUS)
        contract = status.get('read_contract') or {}
        declared = contract.get('fixture_index')
        if declared:
            candidates.append(ROOT / declared)
    candidates.extend([CANONICAL_INDEX, COMPAT_INDEX])

    seen = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            return path
    fail(
        'ACQUISITION_FAILED',
        reason='fixture_index_missing',
        attempted=[relative(p) for p in candidates],
    )


def choose_fixture(index, query=None, match_market_id=None):
    fixtures = index.get('fixtures', [])
    if match_market_id:
        wanted = str(match_market_id)
        exact_id = []
        for f in fixtures:
            ids = [str(x) for x in (f.get('match_market_ids') or [])]
            if not ids and f.get('match_market_id') is not None:
                ids = [str(f.get('match_market_id'))]
            if wanted in ids:
                exact_id.append(f)
        if len(exact_id) == 1:
            return exact_id[0]
        if len(exact_id) > 1:
            fail('MATCH_AMBIGUOUS', match_market_id=wanted, matches=[x.get('match') for x in exact_id])
        fail('FIXTURE_NOT_FOUND', match_market_id=wanted)

    if not query:
        fail('QUERY_REQUIRED', reason='match_or_match_market_id_required')

    q = norm(query)
    exact = [f for f in fixtures if norm(f.get('match')) == q]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        fail('MATCH_AMBIGUOUS', query=query, matches=[x.get('match') for x in exact])

    qtokens = set(q.split())
    scored = []
    for f in fixtures:
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


def validate_source(index, fixture, doc, player=False):
    if not index.get('source_healthy') or not doc.get('source_healthy'):
        fail('ACQUISITION_FAILED', reason='source_unhealthy')
    if index.get('source_class') not in (None, 'BETFLAG_AAMS_DIRECT'):
        fail('ACQUISITION_FAILED', reason='unexpected_index_source_class', source_class=index.get('source_class'))
    if doc.get('source_class') != 'BETFLAG_AAMS_DIRECT':
        fail('ACQUISITION_FAILED', reason='unexpected_source_class', source_class=doc.get('source_class'))

    if fixture.get('identity_consistent') is False or doc.get('identity_consistent') is False:
        fail('ACQUISITION_FAILED', reason='fixture_identity_inconsistent', match=doc.get('match'))
    if fixture.get('price_gate_fixture_eligible') is False or doc.get('price_gate_fixture_eligible') is False:
        fail('ACQUISITION_FAILED', reason='fixture_not_price_gate_eligible', match=doc.get('match'))

    if not index.get('generated_at') or not doc.get('generated_at'):
        fail('ACQUISITION_FAILED', reason='snapshot_timestamp_missing')

    if norm(fixture.get('match')) and norm(doc.get('match')) and norm(fixture.get('match')) != norm(doc.get('match')):
        fail(
            'ACQUISITION_FAILED',
            reason='fixture_document_mismatch',
            index_match=fixture.get('match'),
            document_match=doc.get('match'),
        )

    if player:
        if int(fixture.get('player_props_count') or fixture.get('player_count') or 0) <= 0 or not doc.get('players'):
            fail('MARKET_NOT_EXPOSED', reason='player_props_empty', match=doc.get('match'))
    else:
        if int(fixture.get('standard_count') or 0) <= 0 or not doc.get('standard'):
            fail('MARKET_NOT_EXPOSED', reason='standard_markets_empty', match=doc.get('match'))


def resolve_player(doc, player, market, selection='Si', line=None):
    pnorm = norm(player)
    candidates = [p for p in doc.get('players', []) if norm(p.get('player')) == pnorm]
    if not candidates:
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
        fail('LINE_REQUIRED', player=p.get('player'), market=market, available_lines=sorted({q.get('line') for q in quotes}))
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


def load_fixture(index_path, match=None, match_market_id=None, player=False):
    index = load_json(index_path)
    if not index.get('source_healthy'):
        fail('ACQUISITION_FAILED', reason='index_source_unhealthy', index_file=relative(index_path))
    fixture = choose_fixture(index, query=match, match_market_id=match_market_id)
    rel = fixture.get('file')
    if not rel:
        fail('ACQUISITION_FAILED', reason='fixture_file_pointer_missing', match=fixture.get('match'))
    path = ROOT / rel
    if not path.exists():
        fail('ACQUISITION_FAILED', reason='fixture_file_missing', file=rel)
    doc = load_json(path)
    validate_source(index, fixture, doc, player=player)
    return index, fixture, path, doc


def self_test():
    index_path = resolve_index_path()
    index = load_json(index_path)
    if not index.get('source_healthy'):
        fail('ACQUISITION_FAILED', reason='index_source_unhealthy', index_file=relative(index_path))

    candidates = [
        f for f in index.get('fixtures', [])
        if f.get('price_gate_fixture_eligible') is not False and int(f.get('standard_count') or 0) > 0 and f.get('file')
    ]
    if not candidates:
        fail('ACQUISITION_FAILED', reason='no_gate_eligible_fixture_for_self_test', index_file=relative(index_path))

    last_error = None
    for fixture in candidates:
        path = ROOT / fixture['file']
        if not path.exists():
            last_error = {'reason': 'fixture_file_missing', 'file': fixture['file']}
            continue
        doc = load_json(path)
        if not doc.get('source_healthy') or doc.get('identity_consistent') is False or doc.get('price_gate_fixture_eligible') is False:
            last_error = {'reason': 'sample_fixture_not_healthy', 'file': fixture['file']}
            continue
        print(json.dumps({
            'status': 'BETFLAG_READER_CONTRACT_OK',
            'index_file': relative(index_path),
            'index_generated_at': index.get('generated_at'),
            'fixture_count': len(index.get('fixtures', [])),
            'sample_match': doc.get('match'),
            'sample_fixture_file': fixture.get('file'),
            'sample_generated_at': doc.get('generated_at'),
        }, ensure_ascii=False, indent=2))
        return
    fail('ACQUISITION_FAILED', reason='self_test_no_readable_fixture', detail=last_error)


def main():
    ap = argparse.ArgumentParser(description='Resolve a BetFlag quote from the canonical current fixture feed.')
    ap.add_argument('--match')
    ap.add_argument('--match-market-id')
    ap.add_argument('--market')
    ap.add_argument('--selection', default='Si')
    ap.add_argument('--line')
    ap.add_argument('--player')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return

    if not args.match and not args.match_market_id:
        fail('QUERY_REQUIRED', reason='match_or_match_market_id_required')
    if not args.market:
        fail('QUERY_REQUIRED', reason='market_required')

    index_path = resolve_index_path()
    index, fixture, path, doc = load_fixture(
        index_path,
        match=args.match,
        match_market_id=args.match_market_id,
        player=bool(args.player),
    )

    if args.player:
        out = resolve_player(doc, args.player, args.market, args.selection, args.line)
    else:
        out = resolve_standard(doc, args.market, args.selection, args.line)

    out.update({
        'index_file': relative(index_path),
        'fixture_file': fixture.get('file'),
        'identity_consistent': doc.get('identity_consistent'),
        'price_gate_fixture_eligible': doc.get('price_gate_fixture_eligible'),
    })
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
