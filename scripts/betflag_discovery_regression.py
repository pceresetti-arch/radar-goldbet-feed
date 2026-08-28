import json, pathlib, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone

BASE = 'https://radar-betflag-v7.p-ceresetti.workers.dev'
OUT = pathlib.Path('feed/betflag-discovery-regression-status.json')
SUPPORTED = {'Marc','Marcatore 1T','Marcatore 2T','1° Marcatore','1° Marcatore o Sostituto','Marcatore o Sostituto','Marcatore Plus'}

def now():
    return datetime.now(timezone.utc).isoformat()

def get_json(path, params=None, timeout=35):
    url = BASE + path
    if params:
        url += '?' + urllib.parse.urlencode(params)
    started = time.monotonic()
    status = None; body = None; error = None
    try:
        req = urllib.request.Request(url, headers={'Accept':'application/json','User-Agent':'RadarBetFlagRegression/1.0'})
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

def main():
    checks = {}
    worker_src = pathlib.Path('worker/src/index.mjs').read_text(encoding='utf-8')
    bridge_src = pathlib.Path('.github/workflows/radar-betflag-v7-live-bridge.yml').read_text(encoding='utf-8')

    checks['static_default_full'] = "const mode = url.searchParams.get('full') === '0' ? 'core' : 'full';" in worker_src
    checks['static_player_search'] = 'row.player, row.requested_market, row.market, row.selection' in worker_src
    checks['static_offset_slice'] = 'filtered.slice(offset, offset + limit)' in worker_src
    checks['static_pagination_metadata'] = 'next_offset' in worker_src and 'has_more' in worker_src
    checks['static_noncore_targets'] = all(x in worker_src for x in ['U/O Tiri In Porta Giocatore','U/O Tiri Totali Giocatore','Assist','Gol e Assist'])
    checks['bridge_forces_full'] = "params.setdefault('full','1')" in bridge_src
    checks['bridge_paginates'] = "while True:" in bridge_src and "page['offset']=offset" in bridge_src
    checks['bridge_min_page_500'] = 'max(500,min(1000,page_limit))' in bridge_src

    health = get_json('/health')
    hb = health.get('body') if isinstance(health.get('body'), dict) else {}
    checks['health_200'] = health.get('status') == 200
    checks['health_version'] = hb.get('version') == '7.0-betflag-operational'
    checks['health_exact_enabled'] = hb.get('exact_player_price_proof') is True

    page1 = get_json('/live/player-props', {'q':'Marc','full':'1','limit':100,'offset':0})
    b1 = page1.get('body') if isinstance(page1.get('body'), dict) else {}
    rows1 = b1.get('rows') if isinstance(b1.get('rows'), list) else []
    checks['discovery_200'] = page1.get('status') == 200
    checks['discovery_source_healthy'] = b1.get('source_healthy') is True
    checks['discovery_fresh'] = isinstance(b1.get('freshness'), dict) and b1['freshness'].get('fresh') is True
    checks['discovery_mode_full'] = b1.get('mode') == 'full'
    checks['discovery_nonempty'] = len(rows1) > 0

    pag = b1.get('pagination') if isinstance(b1.get('pagination'), dict) else {}
    if pag.get('next_offset') is not None:
        page2 = get_json('/live/player-props', {'q':'Marc','full':'1','limit':100,'offset':pag.get('next_offset')})
        b2 = page2.get('body') if isinstance(page2.get('body'), dict) else {}
        rows2 = b2.get('rows') if isinstance(b2.get('rows'), list) else []
        keys1 = {row_key(r) for r in rows1}; keys2 = {row_key(r) for r in rows2}
        checks['pagination_runtime'] = page2.get('status') == 200 and len(rows2) > 0 and keys1.isdisjoint(keys2)
    else:
        checks['pagination_runtime'] = True

    candidate = None
    for r in rows1:
        if r.get('requested_market') in SUPPORTED and str(r.get('selection') or '').lower() in ('si','sì') and r.get('player') and r.get('match_market_id'):
            candidate = r; break
    checks['dynamic_candidate_found'] = candidate is not None

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

        exact = get_json('/live/player-price', {
            'match_market_id': candidate['match_market_id'],
            'player': candidate['player'],
            'market': candidate['requested_market'],
            'selection': candidate['selection']
        })
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
            'proof_id': cert.get('proof_id')
        }
    else:
        for key in ['player_lookup_runtime','exact_200','exact_unique','exact_source_healthy','exact_fresh','exact_fingerprint','exact_price_gate_eligible']:
            checks[key] = False

    ready = all(checks.values())
    payload = {
        'schema_version':'betflag-discovery-regression-v1',
        'generated_at': now(),
        'worker_base': BASE,
        'ready': ready,
        'status': 'READY' if ready else 'PIPELINE_DEGRADED',
        'contract': {
            'full_markets_default': True,
            'player_search_required': True,
            'pagination_required': True,
            'dynamic_exact_price_required': True,
            'fixture_hardcoding': False
        },
        'checks': checks,
        'sample_dynamic_exact': sample,
        'rule': 'PRE-MATCH must not claim complete player-prop coverage when ready=false.'
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
