import json, pathlib, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE = 'https://radar-betflag-v7.p-ceresetti.workers.dev'
OUT = pathlib.Path('feed/betflag-discovery-regression-status.json')
SUPPORTED = {'Marc','Marcatore 1T','Marcatore 2T','1° Marcatore','1° Marcatore o Sostituto','Marcatore o Sostituto','Marcatore Plus'}

def now():
    return datetime.now(timezone.utc).isoformat()

def rome_date():
    return datetime.now(ZoneInfo('Europe/Rome')).strftime('%d-%m-%Y')

def get_json(path, params=None, timeout=35):
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    started = time.monotonic()
    status = None; body = None; error = None
    try:
        req = urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'RadarBetFlagRegression/3.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.status
            raw = r.read(20_000_000).decode('utf-8','replace')
            body = json.loads(raw)
    except urllib.error.HTTPError as e:
        status = e.code
        try: body = json.loads(e.read(20_000_000).decode('utf-8','replace'))
        except Exception: body = None
        error = f'HTTPError {e.code}'
    except Exception as e:
        error = f'{type(e).__name__}: {e}'
    return {'url':url,'status':status,'elapsed_ms':round((time.monotonic()-started)*1000),'error':error,'body':body}

def row_key(r):
    return '|'.join(str(r.get(k)) for k in ('event_id','odds_id','selection_id','requested_market','line'))

def find_index_candidate(fixtures):
    for fixture in fixtures:
        mmid = fixture.get('match_market_id')
        if not mmid or fixture.get('exact_fixture_identity_available') is not True:
            continue
        for player in fixture.get('players') or []:
            pname = player.get('player')
            if not pname:
                continue
            for market in player.get('markets') or []:
                mname = market.get('market')
                if mname not in SUPPORTED:
                    continue
                for quote in market.get('quotes') or []:
                    if str(quote.get('selection') or '').lower() in ('si','sì') and quote.get('odd') is not None:
                        return {
                            'match': fixture.get('match'),
                            'match_market_id': mmid,
                            'player': pname,
                            'market': mname,
                            'selection': quote.get('selection'),
                            'line': quote.get('line'),
                            'scan_odd': quote.get('odd')
                        }
    return None

def main():
    checks = {}
    today = rome_date()
    worker_src = pathlib.Path('worker/src/index.mjs').read_text(encoding='utf-8')
    bridge_src = pathlib.Path('.github/workflows/radar-betflag-v7-live-bridge.yml').read_text(encoding='utf-8')

    checks['static_default_full'] = "const mode = url.searchParams.get('full') === '0' ? 'core' : 'full';" in worker_src
    checks['static_player_search'] = 'row.player, row.requested_market, row.market, row.selection' in worker_src
    checks['static_offset_slice'] = 'filtered.slice(offset, offset + limit)' in worker_src
    checks['static_pagination_metadata'] = 'next_offset' in worker_src and 'has_more' in worker_src
    checks['static_noncore_targets'] = all(x in worker_src for x in ['U/O Tiri In Porta Giocatore','U/O Tiri Totali Giocatore','Assist','Gol e Assist'])
    checks['static_index_endpoint'] = "endpoint === 'live/player-index'" in worker_src and 'buildCompactPlayerIndex' in worker_src
    checks['static_index_v2_mapping'] = "index_version: 'player-index-v2'" in worker_src and 'mapping_status' in worker_src and 'exact_fixture_identity_available' in worker_src
    checks['static_index_cache'] = 'BETFLAG_INDEX_CACHE_SECONDS = 20' in worker_src and 'betflag-player-index/v2' in worker_src
    checks['bridge_prefers_index'] = "mode=str(req.get('mode') or 'player_index')" in bridge_src and "mode=='player_index'" in bridge_src
    checks['bridge_today_scoped'] = "ZoneInfo('Europe/Rome')" in bridge_src and "params.setdefault('date'" in bridge_src
    checks['bridge_forces_full'] = "params.setdefault('full','1')" in bridge_src
    checks['bridge_paginates'] = "while True:" in bridge_src and "page['offset']=offset" in bridge_src
    checks['bridge_min_page_500'] = 'max(500,min(1000,page_limit))' in bridge_src

    health = get_json('/health')
    hb = health.get('body') if isinstance(health.get('body'), dict) else {}
    checks['health_200'] = health.get('status') == 200
    checks['health_version'] = hb.get('version') == '7.0-betflag-operational'
    checks['health_exact_enabled'] = hb.get('exact_player_price_proof') is True
    checks['health_index_advertised'] = '/live/player-index' in (hb.get('endpoints') or [])

    index_cold = get_json('/live/player-index', {'date': today}, timeout=45)
    ib = index_cold.get('body') if isinstance(index_cold.get('body'), dict) else {}
    coverage = ib.get('coverage') if isinstance(ib.get('coverage'), dict) else {}
    fixtures = ib.get('fixtures') if isinstance(ib.get('fixtures'), list) else []
    scope = ib.get('coverage_scope') if isinstance(ib.get('coverage_scope'), dict) else {}
    checks['index_200'] = index_cold.get('status') == 200
    checks['index_source_healthy'] = ib.get('source_healthy') is True
    checks['index_fresh'] = isinstance(ib.get('freshness'), dict) and ib['freshness'].get('fresh') is True
    checks['index_version'] = ib.get('index_version') == 'player-index-v2'
    checks['index_today_scope'] = scope.get('type') == 'date' and scope.get('date') == today
    checks['index_coverage_complete'] = ib.get('coverage_complete') is True and ib.get('ready_for_discovery') is True
    checks['index_all_targets'] = coverage.get('targets_expected') == coverage.get('targets_ok') and coverage.get('targets_expected', 0) > 0
    checks['index_no_unmapped_rows'] = coverage.get('unmapped_rows') == 0
    checks['index_all_scoped_rows_indexed'] = coverage.get('indexed_rows') == coverage.get('scoped_source_rows')
    checks['index_nonempty'] = len(fixtures) > 0 and coverage.get('scoped_source_rows', 0) > 0

    index_warm = get_json('/live/player-index', {'date': today}, timeout=20)
    wb = index_warm.get('body') if isinstance(index_warm.get('body'), dict) else {}
    checks['index_warm_200'] = index_warm.get('status') == 200
    checks['index_warm_cache_hit'] = str(wb.get('cache') or '').startswith('HIT')
    checks['index_warm_fast'] = index_warm.get('elapsed_ms') is not None and index_warm.get('elapsed_ms') <= 1500
    checks['index_warm_same_generation'] = wb.get('generated_at') == ib.get('generated_at')

    page1 = get_json('/live/player-props', {'q':'Marc','full':'1','limit':100,'offset':0})
    b1 = page1.get('body') if isinstance(page1.get('body'), dict) else {}
    rows1 = b1.get('rows') if isinstance(b1.get('rows'), list) else []
    checks['fallback_discovery_200'] = page1.get('status') == 200
    checks['fallback_discovery_source_healthy'] = b1.get('source_healthy') is True
    checks['fallback_discovery_fresh'] = isinstance(b1.get('freshness'), dict) and b1['freshness'].get('fresh') is True
    checks['fallback_discovery_mode_full'] = b1.get('mode') == 'full'
    checks['fallback_discovery_nonempty'] = len(rows1) > 0

    pag = b1.get('pagination') if isinstance(b1.get('pagination'), dict) else {}
    if pag.get('next_offset') is not None:
        page2 = get_json('/live/player-props', {'q':'Marc','full':'1','limit':100,'offset':pag.get('next_offset')})
        b2 = page2.get('body') if isinstance(page2.get('body'), dict) else {}
        rows2 = b2.get('rows') if isinstance(b2.get('rows'), list) else []
        keys1 = {row_key(r) for r in rows1}; keys2 = {row_key(r) for r in rows2}
        checks['pagination_runtime'] = page2.get('status') == 200 and len(rows2) > 0 and keys1.isdisjoint(keys2)
    else:
        checks['pagination_runtime'] = True

    candidate = find_index_candidate(fixtures)
    checks['dynamic_index_candidate_found'] = candidate is not None
    sample = None
    if candidate:
        player_lookup = get_json('/live/player-props', {
            'player': candidate['player'], 'match_market_id': candidate['match_market_id'], 'full':'1', 'limit':1000
        })
        pb = player_lookup.get('body') if isinstance(player_lookup.get('body'), dict) else {}
        prows = pb.get('rows') if isinstance(pb.get('rows'), list) else []
        checks['player_lookup_runtime'] = player_lookup.get('status') == 200 and any(
            str(r.get('player')) == str(candidate.get('player')) and str(r.get('match_market_id')) == str(candidate.get('match_market_id')) for r in prows
        )

        params = {
            'match_market_id': candidate['match_market_id'],
            'player': candidate['player'],
            'market': candidate['market'],
            'selection': candidate['selection']
        }
        if candidate.get('line') is not None:
            params['line'] = candidate['line']
        exact = get_json('/live/player-price', params)
        eb = exact.get('body') if isinstance(exact.get('body'), dict) else {}
        cert = eb.get('certificate') if isinstance(eb.get('certificate'), dict) else {}
        checks['exact_200'] = exact.get('status') == 200
        checks['exact_unique'] = eb.get('returned') == 1 and cert.get('exact_identity_match') is True
        checks['exact_source_healthy'] = cert.get('source_healthy') is True
        checks['exact_fresh'] = isinstance(cert.get('freshness'), dict) and cert['freshness'].get('fresh') is True
        checks['exact_fingerprint'] = bool(cert.get('proof_id')) and bool(cert.get('sha256'))
        checks['exact_price_gate_eligible'] = eb.get('price_gate_eligible') is True and cert.get('price_gate_eligible') is True
        canon = cert.get('canonical') if isinstance(cert.get('canonical'), dict) else {}
        sample = {
            'match': canon.get('match'), 'match_market_id': canon.get('match_market_id'), 'player': canon.get('player'),
            'market': canon.get('requested_market'), 'selection': canon.get('selection'), 'odd': canon.get('odd'),
            'scan_odd': candidate.get('scan_odd'), 'proof_id': cert.get('proof_id')
        }
    else:
        for key in ['player_lookup_runtime','exact_200','exact_unique','exact_source_healthy','exact_fresh','exact_fingerprint','exact_price_gate_eligible']:
            checks[key] = False

    ready = all(checks.values())
    payload = {
        'schema_version':'betflag-discovery-regression-v3-fast-index',
        'generated_at': now(),
        'worker_base': BASE,
        'rome_date': today,
        'ready': ready,
        'status': 'READY' if ready else 'PIPELINE_DEGRADED',
        'contract': {
            'preferred_discovery': '/live/player-index?date=DD-MM-YYYY',
            'single_call_index_required': True,
            'today_scoped_required': True,
            'coverage_complete_required': True,
            'no_dropped_quote_rows_required': True,
            'warm_index_target_ms': 1500,
            'full_markets_default': True,
            'pagination_fallback_required': True,
            'dynamic_exact_price_required': True,
            'fixture_hardcoding': False
        },
        'performance': {
            'index_first_elapsed_ms': index_cold.get('elapsed_ms'),
            'index_warm_elapsed_ms': index_warm.get('elapsed_ms'),
            'fallback_discovery_elapsed_ms': page1.get('elapsed_ms'),
            'index_first_cache': ib.get('cache'),
            'index_warm_cache': wb.get('cache')
        },
        'coverage': coverage,
        'checks': checks,
        'sample_dynamic_exact': sample,
        'rule': 'PRE-MATCH uses today-scoped player-index first; if ready=false or coverage_complete=false, declare PIPELINE_DEGRADED and do not infer no-bet from incomplete coverage.'
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
