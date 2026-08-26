#!/usr/bin/env python3
import datetime
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://radar-betflag-v7.p-ceresetti.workers.dev/live/player-price'

CASES = [
    ('biereth_anytime_1', {'q': 'Monaco Gornik', 'player': 'Mika Biereth', 'market': 'Marcatore', 'selection': 'Si'}),
    ('biereth_anytime_2', {'q': 'Monaco Gornik', 'player': 'Mika Biereth', 'market': 'Marcatore', 'selection': 'Si'}),
    ('biereth_1t', {'q': 'Monaco Gornik', 'player': 'Mika Biereth', 'market': 'Marcatore 1T', 'selection': 'Si'}),
    ('negative_control_wrong_player', {'q': 'Monaco Gornik', 'player': 'Mika Biereth XXX', 'market': 'Marcatore', 'selection': 'Si'}),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36 RadarRealtimeTest/1.0',
    'Accept': 'application/json,text/plain,*/*',
}


def request_case(label, params):
    url = BASE + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=HEADERS)
    started = time.perf_counter()
    status = None
    body = b''
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read()
    total = time.perf_counter() - started
    try:
        d = json.loads(body.decode('utf-8'))
    except Exception:
        d = {}
    cert = d.get('certificate') or {}
    quote = d.get('quote') or {}
    return {
        'label': label,
        'http_code': status,
        'total_seconds': round(total, 4),
        'generated_at': d.get('generated_at'),
        'served_at': d.get('served_at'),
        'source_class': d.get('source_class'),
        'upstream_elapsed_ms': d.get('upstream_elapsed_ms'),
        'returned': d.get('returned'),
        'price_gate_eligible': d.get('price_gate_eligible'),
        'proof_id': cert.get('proof_id'),
        'exact_identity_match': cert.get('exact_identity_match'),
        'source_healthy': cert.get('source_healthy'),
        'freshness': cert.get('freshness'),
        'quote': {
            'match': quote.get('match'),
            'match_event_id': quote.get('match_event_id'),
            'match_market_id': quote.get('match_market_id'),
            'player': quote.get('player'),
            'requested_market': quote.get('requested_market'),
            'market': quote.get('market'),
            'selection': quote.get('selection'),
            'line': quote.get('line'),
            'odd': quote.get('odd'),
            'selection_id': quote.get('selection_id'),
            'market_id': quote.get('market_id'),
            'odds_id': quote.get('odds_id'),
        },
    }


def main():
    results = []
    for idx, (label, params) in enumerate(CASES):
        results.append(request_case(label, params))
        if idx == 0:
            time.sleep(1)

    positive = results[:3]
    negative = results[3]
    latencies = [c['total_seconds'] for c in positive]
    upstream = [c['upstream_elapsed_ms'] for c in positive if isinstance(c.get('upstream_elapsed_ms'), (int, float))]

    q1 = positive[0].get('quote') or {}
    q2 = positive[1].get('quote') or {}
    identity_keys = ['match_event_id', 'match_market_id', 'player', 'requested_market', 'selection', 'selection_id', 'market_id', 'odds_id']
    identity_stable = all(q1.get(k) == q2.get(k) for k in identity_keys)
    price_stable = q1.get('odd') == q2.get('odd')

    summary = {
        'positive_all_http_200': all(c.get('http_code') == 200 for c in positive),
        'positive_all_unique_exact': all(c.get('returned') == 1 and c.get('exact_identity_match') is True for c in positive),
        'positive_all_price_gate_eligible': all(c.get('price_gate_eligible') is True for c in positive),
        'negative_control_rejected': negative.get('http_code') == 404 and negative.get('returned') == 0 and negative.get('price_gate_eligible') is False,
        'repeat_identity_stable': identity_stable,
        'repeat_price_stable': price_stable,
        'mean_total_seconds': round(statistics.mean(latencies), 4),
        'median_total_seconds': round(statistics.median(latencies), 4),
        'max_total_seconds': round(max(latencies), 4),
        'mean_upstream_ms': round(statistics.mean(upstream), 1) if upstream else None,
    }

    report = {
        'schema_version': 'quote-realtime-test-v1',
        'tested_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'worker': 'radar-betflag-v7',
        'endpoint': '/live/player-price',
        'summary': summary,
        'cases': results,
    }

    Path('feed').mkdir(exist_ok=True)
    Path('feed/quote-realtime-test-latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
