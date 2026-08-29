from pathlib import Path

p = Path('worker/src/index.mjs')
s = p.read_text(encoding='utf-8')
changed = False

replacements = [
(
"""async function getCachedBetflagStandard(request, ctx) {
  const cache = caches.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.pathname = '/_radar_cache/betflag-standard-index/v1';
  cacheUrl.search = '';
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return { payload: await cached.json(), cache: 'HIT' };
  const payload = await fetchBetflagStandard();
  const response = json(payload, 200, { 'Cache-Control': `public, s-maxage=${BETFLAG_SCAN_CACHE_SECONDS}, max-age=0` });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return { payload, cache: 'MISS' };
}""",
"""async function getCachedBetflagStandard(request, ctx) {
  const cache = caches.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.pathname = '/_radar_cache/betflag-standard-index/v2';
  cacheUrl.search = '';
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return { payload: await cached.json(), cache: 'HIT' };
  const payload = await fetchBetflagStandard();
  const cacheable = Boolean(payload.source_healthy && Number(payload.row_count || 0) > 0);
  if (cacheable) {
    const response = json(payload, 200, { 'Cache-Control': `public, s-maxage=${BETFLAG_SCAN_CACHE_SECONDS}, max-age=0` });
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
  }
  return { payload, cache: cacheable ? 'MISS:CACHED_HEALTHY' : 'MISS:NOT_CACHED_UNHEALTHY' };
}"""
),
(
"""async function getCachedBetflagAggregate(request, mode, ctx) {
  const cache = caches.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.pathname = `/_radar_cache/betflag-player-props/${mode}`;
  cacheUrl.search = '';
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return { payload: await cached.json(), cache: 'HIT' };
  const payload = await fetchBetflagAggregate(mode);
  const response = json(payload, 200, { 'Cache-Control': `public, s-maxage=${BETFLAG_SCAN_CACHE_SECONDS}, max-age=0` });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return { payload, cache: 'MISS' };
}""",
"""async function getCachedBetflagAggregate(request, mode, ctx) {
  const cache = caches.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.pathname = `/_radar_cache/betflag-player-props-v2/${mode}`;
  cacheUrl.search = '';
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return { payload: await cached.json(), cache: 'HIT' };
  const payload = await fetchBetflagAggregate(mode);
  const cacheable = Boolean(payload.source_healthy && Number(payload.row_count || 0) > 0);
  if (cacheable) {
    const response = json(payload, 200, { 'Cache-Control': `public, s-maxage=${BETFLAG_SCAN_CACHE_SECONDS}, max-age=0` });
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
  }
  return { payload, cache: cacheable ? 'MISS:CACHED_HEALTHY' : 'MISS:NOT_CACHED_UNHEALTHY' };
}"""
),
(
"""async function getCachedPlayerIndex(request, url, ctx) {
  const requestedDate = String(url.searchParams.get('date') || '').trim();
  const cache = caches.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.pathname = '/_radar_cache/betflag-player-index/v2';
  cacheUrl.search = requestedDate ? `?date=${encodeURIComponent(requestedDate)}` : '';
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return { document: await cached.json(), cache: 'HIT' };

  const { payload, cache: aggregateCache } = await getCachedBetflagAggregate(request, 'full', ctx);
  const scopedRows = filterPlayerIndexRows(payload.rows, url);
  const document = buildPlayerIndexDocument(payload, scopedRows, requestedDate);
  const response = json(document, 200, { 'Cache-Control': `public, s-maxage=${BETFLAG_INDEX_CACHE_SECONDS}, max-age=0` });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return { document, cache: `MISS:${aggregateCache}` };
}""",
"""async function getCachedPlayerIndex(request, url, ctx) {
  const requestedDate = String(url.searchParams.get('date') || '').trim();
  const cache = caches.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.pathname = '/_radar_cache/betflag-player-index/v3';
  cacheUrl.search = requestedDate ? `?date=${encodeURIComponent(requestedDate)}` : '';
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return { document: await cached.json(), cache: 'HIT' };

  const { payload, cache: aggregateCache } = await getCachedBetflagAggregate(request, 'full', ctx);
  const scopedRows = filterPlayerIndexRows(payload.rows, url);
  const document = buildPlayerIndexDocument(payload, scopedRows, requestedDate);
  const cacheable = Boolean(document.coverage_static && Number(document.coverage?.scoped_source_rows || 0) > 0);
  if (cacheable) {
    const response = json(document, 200, { 'Cache-Control': `public, s-maxage=${BETFLAG_INDEX_CACHE_SECONDS}, max-age=0` });
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
  }
  return { document, cache: `MISS:${aggregateCache}:${cacheable ? 'CACHED_HEALTHY' : 'NOT_CACHED_INCOMPLETE'}` };
}"""
)
]

for old, new in replacements:
    if old in s:
        s = s.replace(old, new, 1)
        changed = True

required = [
    "betflag-standard-index/v2",
    "betflag-player-props-v2/${mode}",
    "betflag-player-index/v3",
    "MISS:NOT_CACHED_UNHEALTHY",
    "NOT_CACHED_INCOMPLETE",
]
for marker in required:
    if marker not in s:
        raise SystemExit(f'BetFlag cache-health patch missing marker: {marker}')

if changed:
    p.write_text(s, encoding='utf-8')
    print('Patched BetFlag cache policy: unhealthy/empty payloads are never cached')
else:
    print('BetFlag cache-health patch already present')
