const UPSTREAM_BASE = 'https://odss-api.com/api/v1';
const SHARED_AAMS_BASE = 'https://sportservice.betflag.it/api/sport/pregame';
const AAMS_AGG_TOURNAMENT = 1334500001;

const ALLOWED_PARAMS = {
  sports: [],
  bookmakers: [],
  leagues: ['sport'],
  odds: [
    'sport', 'market', 'league', 'bookmakers', 'event_id', 'state',
    'limit', 'offset', 'content', 'player', 'q'
  ],
  history: ['event_id', 'book', 'market', 'from', 'to', 'limit']
};

const CORE_PLAYER_TARGETS = [
  [2484, 13825, 'Marcatore Plus'],
  [2484, 19405, 'Marcatore o Sostituto'],
  [2484, 22884, 'Marc'],
  [2484, 13819, '1° Marcatore'],
  [2484, 19403, '1° Marcatore o Sostituto'],
  [2484, 13820, 'Marcatore 1T'],
  [2484, 13826, 'Marcatore 2T']
];

const EXTRA_PLAYER_TARGETS = [
  [2484, 13821, 'Doppietta'],
  [2484, 13822, 'Tripletta'],
  [2484, 13816, 'U/O Tiri in porta Plus'],
  [2484, 13817, 'U/O Tiri Totali Plus'],
  [2484, 19401, 'Assist o Sostituto'],
  [2484, 13495, 'U/O Tiri In Porta Giocatore'],
  [2484, 13496, 'U/O Tiri Totali Giocatore'],
  [2484, 13823, 'Assist'],
  [2484, 13824, 'Gol e Assist'],
  [2487, 13509, 'U/O Parate Giocatore']
];

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type',
  'Access-Control-Max-Age': '86400'
};

function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...CORS_HEADERS,
      ...extraHeaders
    }
  });
}

function clampInt(value, fallback, min, max) {
  const parsed = Number.parseInt(String(value ?? ''), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, parsed));
}

async function secureEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || !a || !b) return false;
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([
    crypto.subtle.digest('SHA-256', enc.encode(a)),
    crypto.subtle.digest('SHA-256', enc.encode(b))
  ]);
  const aa = new Uint8Array(ha);
  const bb = new Uint8Array(hb);
  let diff = 0;
  for (let i = 0; i < aa.length; i += 1) diff |= aa[i] ^ bb[i];
  return diff === 0;
}

async function isAuthorized(request, env, url) {
  const expected = env.BRIDGE_TOKEN;
  if (!expected) return false;

  const queryToken = url.searchParams.get('token') || '';
  if (await secureEqual(queryToken, expected)) return true;

  const auth = request.headers.get('Authorization') || '';
  const bearer = auth.replace(/^Bearer\s+/i, '');
  return secureEqual(bearer, expected);
}

function buildUpstreamUrl(endpoint, incomingUrl) {
  const upstream = new URL(`${UPSTREAM_BASE}/${endpoint}`);
  const allowed = ALLOWED_PARAMS[endpoint] || [];

  for (const key of allowed) {
    for (const value of incomingUrl.searchParams.getAll(key)) {
      if (value !== '') upstream.searchParams.append(key, value);
    }
  }

  return upstream;
}

async function fetchJson(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort('timeout'), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const text = await response.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text.slice(0, 2000) };
    }
    return { status: response.status, ok: response.ok, data };
  } finally {
    clearTimeout(timer);
  }
}

async function proxyEndpoint(endpoint, request, env, incomingUrl) {
  if (!env.ODSS_API_KEY) {
    return json({ error: 'Worker misconfigured: missing ODSS_API_KEY' }, 500);
  }

  const upstreamUrl = buildUpstreamUrl(endpoint, incomingUrl);
  const response = await fetch(upstreamUrl, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      'x-api-key': env.ODSS_API_KEY,
      'User-Agent': 'RadarGoldBetBridge/6.0'
    }
  });

  const headers = new Headers(response.headers);
  headers.set('Access-Control-Allow-Origin', '*');
  headers.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
  headers.set('Access-Control-Allow-Headers', 'Authorization, Content-Type');
  headers.set('Cache-Control', 'no-store');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

function aamsHeaders() {
  return {
    'User-Agent': 'Mozilla/5.0 RadarGoldBetFastPath/6.0',
    Accept: 'application/json,text/plain,*/*',
    'x-api-version': '1.0',
    'X-Auth-Token': '',
    'X-Brand': '3',
    'X-IdCanale': '0',
    Origin: 'https://www.betflag.it',
    Referer: 'https://www.betflag.it/'
  };
}

function parsePlayerEventName(name) {
  const raw = String(name || '').trim();
  const match = raw.match(/^\(([^)]+)\)\s*(.*)$/);
  return match ? [match[1].trim(), match[2].trim()] : ['', raw];
}

function marketRows(event) {
  const rows = [];
  const mm = event?.mmkW;
  const markets = Array.isArray(mm) ? mm : (mm && typeof mm === 'object' ? Object.values(mm) : []);
  for (const market of markets) {
    if (!market || typeof market !== 'object') continue;
    const marketName = String(market.mn || '').trim();
    const spd = market.spd;
    const spreads = Array.isArray(spd)
      ? spd.map((value, index) => [index, value])
      : (spd && typeof spd === 'object' ? Object.entries(spd) : []);
    for (const [spreadKey, spread] of spreads) {
      if (!spread || typeof spread !== 'object') continue;
      for (const quote of spread.asl || []) {
        if (!quote || typeof quote !== 'object' || quote.ov == null) continue;
        rows.push({
          market: marketName,
          line: String(spreadKey) === '0.0' ? null : spreadKey,
          selection: quote.sn,
          odd: quote.ov,
          selection_id: quote.si,
          selection_type: quote.sti,
          market_type: quote.mti,
          market_id: quote.mi,
          odds_id: quote.oi
        });
      }
    }
  }
  return rows;
}

function buildMatchMap(standard) {
  const matchMap = new Map();
  function walk(node) {
    if (Array.isArray(node)) {
      for (const value of node) walk(value);
      return;
    }
    if (!node || typeof node !== 'object') return;
    const sportName = String(node.sn || '').toLowerCase();
    const eventName = String(node.en || '');
    if (node.mi != null && eventName && !sportName.startsWith('giocatori') && !eventName.startsWith('(')) {
      if (node.si === 1 || node.si === '1' || sportName === 'calcio') {
        matchMap.set(String(node.mi), {
          event_id: node.ei,
          match: node.en,
          start_time: node.ed,
          tournament_id: node.ti,
          league: node.td,
          category: node.cd,
          match_market_id: node.mi,
          authority_id: node.tai
        });
      }
    }
    for (const value of Object.values(node)) walk(value);
  }
  walk(standard);
  return matchMap;
}

function collectPlayerRows(data, requestedMarket, matchMap, fetchedAt, seen) {
  const rows = [];
  function walk(node) {
    if (Array.isArray(node)) {
      for (const value of node) walk(value);
      return;
    }
    if (!node || typeof node !== 'object') return;
    if ('ei' in node && 'en' in node && String(node.sn || '').toLowerCase().startsWith('giocatori')) {
      const [matchCode, player] = parsePlayerEventName(node.en);
      const match = matchMap.get(String(node.mi));
      const base = {
        event_id: node.ei,
        player_event: node.en,
        match_code: matchCode,
        player,
        start_time: node.ed,
        league: node.td,
        tournament_id: node.ti,
        category_id: node.ci,
        authority_id: node.tai,
        match_market_id: node.mi,
        match: match?.match || null,
        match_event_id: match?.event_id || null,
        match_start: match?.start_time || node.ed,
        requested_market: requestedMarket
      };
      for (const quote of marketRows(node)) {
        const key = [node.ei, quote.market, String(quote.line), quote.selection, quote.odd, quote.odds_id].join('|');
        if (seen.has(key)) continue;
        seen.add(key);
        rows.push({ ...base, ...quote, fetched_at: fetchedAt });
      }
    }
    for (const value of Object.values(node)) walk(value);
  }
  walk(data);
  return rows;
}

async function fetchAamsAggregate(mode = 'core') {
  const started = Date.now();
  const fetchedAt = new Date().toISOString();
  const targets = mode === 'full' ? [...CORE_PLAYER_TARGETS, ...EXTRA_PLAYER_TARGETS] : CORE_PLAYER_TARGETS;
  const standardUrl = `${SHARED_AAMS_BASE}/getOverviewEventsAams/0/1/0/${AAMS_AGG_TOURNAMENT}/0/0/0?channelId=0`;
  const targetUrls = targets.map(([tab, slot, label]) => ({
    tab,
    slot,
    label,
    url: `${SHARED_AAMS_BASE}/getOverviewEventsAams/0/-1/0/${AAMS_AGG_TOURNAMENT}/${tab}/${slot}/0?channelId=0`
  }));

  const headers = aamsHeaders();
  const [standardResult, ...targetResults] = await Promise.all([
    fetchJson(standardUrl, { headers }, 16000),
    ...targetUrls.map((target) => fetchJson(target.url, { headers }, 16000))
  ]);

  const matchMap = buildMatchMap(standardResult.data);
  const seen = new Set();
  const rows = [];
  const calls = [];
  for (let i = 0; i < targetUrls.length; i += 1) {
    const target = targetUrls[i];
    const result = targetResults[i];
    const added = collectPlayerRows(result.data, target.label, matchMap, fetchedAt, seen);
    rows.push(...added);
    calls.push({ label: target.label, status: result.status, ok: result.ok, rows_added: added.length });
  }

  return {
    generated_at: fetchedAt,
    source_class: 'SHARED_AAMS',
    source: 'shared AAMS player service',
    goldbet_direct: false,
    price_gate_eligible: false,
    mode,
    elapsed_ms: Date.now() - started,
    match_map_count: matchMap.size,
    row_count: rows.length,
    calls,
    rows
  };
}

async function getCachedAamsAggregate(request, mode, ctx) {
  const cache = caches.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.pathname = `/_radar_cache/aams-player-props/${mode}`;
  cacheUrl.search = '';
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) {
    return { payload: await cached.json(), cache: 'HIT' };
  }

  const payload = await fetchAamsAggregate(mode);
  const response = json(payload, 200, { 'Cache-Control': 'public, s-maxage=12, max-age=0' });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return { payload, cache: 'MISS' };
}

function filterAamsRows(rows, url) {
  const matchMarketId = String(url.searchParams.get('match_market_id') || '').trim().toLowerCase();
  const q = String(url.searchParams.get('q') || '').trim().toLowerCase();
  const player = String(url.searchParams.get('player') || '').trim().toLowerCase();
  const market = String(url.searchParams.get('market') || '').trim().toLowerCase();
  const league = String(url.searchParams.get('league') || '').trim().toLowerCase();
  const limit = clampInt(url.searchParams.get('limit'), 300, 1, 1000);

  const filtered = [];
  for (const row of rows || []) {
    if (matchMarketId && String(row.match_market_id || '').toLowerCase() !== matchMarketId) continue;
    if (player && !String(row.player || '').toLowerCase().includes(player)) continue;
    if (market && !String(row.market || '').toLowerCase().includes(market)) continue;
    if (league && !String(row.league || '').toLowerCase().includes(league)) continue;
    if (q) {
      const haystack = [row.match, row.match_code, row.player, row.league].map((x) => String(x || '').toLowerCase()).join(' ');
      const terms = q.split(/\s+/).filter(Boolean);
      if (!terms.every((term) => haystack.includes(term))) continue;
    }
    filtered.push(row);
    if (filtered.length >= limit) break;
  }
  return filtered;
}

async function getDirectGoldbetData(url, env) {
  if (!env.ODSS_API_KEY) throw new Error('Missing ODSS_API_KEY');
  const upstream = new URL(`${UPSTREAM_BASE}/odds`);
  const copyKeys = ['sport', 'market', 'league', 'event_id', 'content', 'player', 'q'];
  for (const key of copyKeys) {
    const value = url.searchParams.get(key);
    if (value) upstream.searchParams.set(key, value);
  }
  upstream.searchParams.set('bookmakers', 'goldbet');
  upstream.searchParams.set('state', url.searchParams.get('state') || 'prematch');
  upstream.searchParams.set('limit', String(clampInt(url.searchParams.get('limit'), 250, 1, 500)));
  upstream.searchParams.set('offset', String(clampInt(url.searchParams.get('offset'), 0, 0, 100000)));

  const started = Date.now();
  const result = await fetchJson(upstream.toString(), {
    headers: {
      Accept: 'application/json',
      'x-api-key': env.ODSS_API_KEY,
      'User-Agent': 'RadarGoldBetFastPath/6.0'
    }
  }, 15000);

  return {
    generated_at: new Date().toISOString(),
    source_class: 'GOLDBET_DIRECT_ODSS',
    source: 'odss-api direct bookmaker filter',
    goldbet_direct: true,
    price_gate_eligible: true,
    upstream_status: result.status,
    elapsed_ms: Date.now() - started,
    data: result.data
  };
}

async function getCachedDirectGoldbet(request, url, env, ctx) {
  const cache = caches.default;
  const cacheUrl = new URL(request.url);
  cacheUrl.pathname = '/_radar_cache/goldbet-direct';
  cacheUrl.searchParams.delete('token');
  cacheUrl.searchParams.set('limit', String(clampInt(url.searchParams.get('limit'), 250, 1, 500)));
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return { payload: await cached.json(), cache: 'HIT' };

  const payload = await getDirectGoldbetData(url, env);
  const response = json(payload, 200, { 'Cache-Control': 'public, s-maxage=8, max-age=0' });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return { payload, cache: 'MISS' };
}

function validatePublicQuery(url) {
  const q = String(url.searchParams.get('q') || '').trim();
  const eventId = String(url.searchParams.get('event_id') || '').trim();
  const player = String(url.searchParams.get('player') || '').trim();
  const matchMarketId = String(url.searchParams.get('match_market_id') || '').trim();
  if (!eventId && !player && !matchMarketId && q.length < 3) {
    return 'Specify event_id, match_market_id, player, or q with at least 3 characters';
  }
  return null;
}

async function publicPlayerProps(request, url, ctx) {
  const error = validatePublicQuery(url);
  if (error) return json({ error }, 400);
  const mode = url.searchParams.get('full') === '1' ? 'full' : 'core';
  const { payload, cache } = await getCachedAamsAggregate(request, mode, ctx);
  const rows = filterAamsRows(payload.rows, url);
  return json({
    generated_at: payload.generated_at,
    served_at: new Date().toISOString(),
    cache,
    source_class: payload.source_class,
    source: payload.source,
    goldbet_direct: false,
    price_gate_eligible: false,
    note: 'Preliminary player-market scan only. Do not use as GoldBet final price gate.',
    mode,
    upstream_elapsed_ms: payload.elapsed_ms,
    total_source_rows: payload.row_count,
    returned: rows.length,
    rows
  }, 200, { 'Cache-Control': 'no-store' });
}

async function publicGoldbet(request, url, env, ctx) {
  const error = validatePublicQuery(url);
  if (error) return json({ error }, 400);
  const { payload, cache } = await getCachedDirectGoldbet(request, url, env, ctx);
  return json({ ...payload, cache, served_at: new Date().toISOString() }, 200, { 'Cache-Control': 'no-store' });
}

async function publicFixture(request, url, env, ctx) {
  const error = validatePublicQuery(url);
  if (error) return json({ error }, 400);
  const mode = url.searchParams.get('full') === '1' ? 'full' : 'core';
  const started = Date.now();
  const [directResult, aamsResult] = await Promise.allSettled([
    getCachedDirectGoldbet(request, url, env, ctx),
    getCachedAamsAggregate(request, mode, ctx)
  ]);

  let directGoldbet;
  if (directResult.status === 'fulfilled') {
    directGoldbet = { ...directResult.value.payload, cache: directResult.value.cache };
  } else {
    directGoldbet = {
      source_class: 'GOLDBET_DIRECT_ODSS',
      goldbet_direct: true,
      price_gate_eligible: false,
      error: directResult.reason instanceof Error ? directResult.reason.message : String(directResult.reason)
    };
  }

  let sharedPlayerProps;
  if (aamsResult.status === 'fulfilled') {
    const payload = aamsResult.value.payload;
    const rows = filterAamsRows(payload.rows, url);
    sharedPlayerProps = {
      generated_at: payload.generated_at,
      cache: aamsResult.value.cache,
      source_class: payload.source_class,
      source: payload.source,
      goldbet_direct: false,
      price_gate_eligible: false,
      mode,
      returned: rows.length,
      rows
    };
  } else {
    sharedPlayerProps = {
      source_class: 'SHARED_AAMS',
      goldbet_direct: false,
      price_gate_eligible: false,
      error: aamsResult.reason instanceof Error ? aamsResult.reason.message : String(aamsResult.reason)
    };
  }

  return json({
    generated_at: new Date().toISOString(),
    elapsed_ms: Date.now() - started,
    contract: {
      final_price_gate_source: 'GOLDBET_DIRECT_ODSS only',
      shared_aams_role: 'candidate discovery / market sanity only'
    },
    direct_goldbet: directGoldbet,
    shared_player_props: sharedPlayerProps
  });
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (request.method !== 'GET') {
      return json({ error: 'Method not allowed' }, 405, { Allow: 'GET, OPTIONS' });
    }

    const url = new URL(request.url);
    const endpoint = url.pathname.replace(/^\/+|\/+$/g, '') || 'health';

    if (endpoint === 'health') {
      return json({
        ok: true,
        service: 'radar-goldbet',
        version: '6.0-fast-path',
        player_props_forwarding: true,
        public_fast_path: true,
        cache_ttl_seconds: { direct_goldbet: 8, shared_aams: 12 },
        provenance_contract: {
          GOLDBET_DIRECT_ODSS: 'eligible for final price gate when a matching quote is returned',
          SHARED_AAMS: 'never eligible for GoldBet final price gate'
        },
        endpoints: [
          '/health', '/live/goldbet', '/live/player-props', '/live/fixture',
          '/sports', '/bookmakers', '/leagues', '/odds', '/history'
        ],
        protected_endpoints: ['/sports', '/bookmakers', '/leagues', '/odds', '/history'],
        odds_params: ALLOWED_PARAMS.odds
      });
    }

    try {
      if (endpoint === 'live/player-props') return await publicPlayerProps(request, url, ctx);
      if (endpoint === 'live/goldbet') return await publicGoldbet(request, url, env, ctx);
      if (endpoint === 'live/fixture') return await publicFixture(request, url, env, ctx);
    } catch (error) {
      console.error(JSON.stringify({
        event: 'fast_path_error',
        endpoint,
        message: error instanceof Error ? error.message : String(error)
      }));
      return json({ error: 'Fast path request failed' }, 502);
    }

    if (!(endpoint in ALLOWED_PARAMS)) {
      return json({
        error: 'Endpoint non valido',
        endpoints: [
          '/health', '/live/goldbet', '/live/player-props', '/live/fixture',
          '/sports', '/bookmakers', '/leagues', '/odds', '/history'
        ]
      }, 404);
    }

    if (!(await isAuthorized(request, env, url))) {
      return json({ error: 'Unauthorized' }, 401);
    }

    try {
      return await proxyEndpoint(endpoint, request, env, url);
    } catch (error) {
      console.error(JSON.stringify({
        event: 'upstream_error',
        endpoint,
        message: error instanceof Error ? error.message : String(error)
      }));
      return json({ error: 'Upstream request failed' }, 502);
    }
  }
};
