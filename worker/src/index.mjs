const UPSTREAM_BASE = 'https://odss-api.com/api/v1';
const BETFLAG_AAMS_BASE = 'https://sportservice.betflag.it/api/sport/pregame';
const AAMS_AGG_TOURNAMENT = 1334500001;
const BETFLAG_EXACT_FRESHNESS_SECONDS = 45;
const BETFLAG_SCAN_CACHE_SECONDS = 12;
const BETFLAG_INDEX_CACHE_SECONDS = 20;
const GOLDBET_CACHE_SECONDS = 8;

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

const PLAYER_TARGETS = [
  [2484, 13825, 'Marcatore Plus'],
  [2484, 19405, 'Marcatore o Sostituto'],
  [2484, 22884, 'Marc'],
  [2484, 13819, '1° Marcatore'],
  [2484, 19403, '1° Marcatore o Sostituto'],
  [2484, 13820, 'Marcatore 1T'],
  [2484, 13826, 'Marcatore 2T'],
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

const CORE_TARGET_LABELS = new Set([
  'Marcatore Plus', 'Marcatore o Sostituto', 'Marc', '1° Marcatore',
  '1° Marcatore o Sostituto', 'Marcatore 1T', 'Marcatore 2T'
]);

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

function normalized(value) {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[’']/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

function canonicalMarket(value) {
  const n = normalized(value)
    .replace(/°/g, '')
    .replace(/\bprimo\b/g, '1')
    .replace(/\bsecondo\b/g, '2');
  const aliases = new Map([
    ['marcatore', 'marc'], ['marcatore anytime', 'marc'], ['anytime', 'marc'], ['marc', 'marc'],
    ['marcatore 1t', 'marcatore 1t'], ['marcatore primo tempo', 'marcatore 1t'], ['marcatore 1 tempo', 'marcatore 1t'],
    ['marcatore 2t', 'marcatore 2t'], ['marcatore secondo tempo', 'marcatore 2t'], ['marcatore 2 tempo', 'marcatore 2t'],
    ['primo marcatore', '1 marcatore'], ['1 marcatore', '1 marcatore'], ['1 marcatore o sostituto', '1 marcatore o sostituto'],
    ['marcatore o sostituto', 'marcatore o sostituto'], ['marc o sost', 'marcatore o sostituto'],
    ['marcatore plus', 'marcatore plus'], ['assist', 'assist'], ['assist o sostituto', 'assist o sostituto'],
    ['gol e assist', 'gol e assist'], ['goal e assist', 'gol e assist'],
    ['doppietta', 'doppietta'], ['tripletta', 'tripletta'],
    ['u/o tiri totali giocatore', 'u/o tiri totali giocatore'], ['tiri totali giocatore', 'u/o tiri totali giocatore'],
    ['u/o tiri in porta giocatore', 'u/o tiri in porta giocatore'], ['tiri in porta giocatore', 'u/o tiri in porta giocatore'],
    ['u/o tiri totali plus', 'u/o tiri totali plus'], ['u/o tiri in porta plus', 'u/o tiri in porta plus'],
    ['u/o parate giocatore', 'u/o parate giocatore']
  ]);
  return aliases.get(n) || n;
}

function resolvePlayerTarget(market) {
  const wanted = canonicalMarket(market);
  for (const target of PLAYER_TARGETS) {
    if (canonicalMarket(target[2]) === wanted) return target;
  }
  return null;
}

async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return [...digest].map((b) => b.toString(16).padStart(2, '0')).join('');
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
  return secureEqual(auth.replace(/^Bearer\s+/i, ''), expected);
}

function buildUpstreamUrl(endpoint, incomingUrl) {
  const upstream = new URL(`${UPSTREAM_BASE}/${endpoint}`);
  for (const key of ALLOWED_PARAMS[endpoint] || []) {
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
    let data;
    try { data = JSON.parse(text); } catch { data = { raw: text.slice(0, 2000) }; }
    return { status: response.status, ok: response.ok, data };
  } finally {
    clearTimeout(timer);
  }
}

async function proxyEndpoint(endpoint, request, env, incomingUrl) {
  if (!env.ODSS_API_KEY) return json({ error: 'Worker misconfigured: missing ODSS_API_KEY' }, 500);
  const response = await fetch(buildUpstreamUrl(endpoint, incomingUrl), {
    method: 'GET',
    headers: { Accept: 'application/json', 'x-api-key': env.ODSS_API_KEY, 'User-Agent': 'RadarGoldBetBridge/7.0' }
  });
  const headers = new Headers(response.headers);
  Object.entries(CORS_HEADERS).forEach(([k, v]) => headers.set(k, v));
  headers.set('Cache-Control', 'no-store');
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

function betflagHeaders() {
  return {
    'User-Agent': 'Mozilla/5.0 RadarBetFlagOperational/7.0',
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
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (!node || typeof node !== 'object') return;
    const sportName = normalized(node.sn);
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
    Object.values(node).forEach(walk);
  }
  walk(standard);
  return matchMap;
}

function collectPlayerRows(data, requestedMarket, matchMap, fetchedAt, seen = new Set()) {
  const rows = [];
  function walk(node) {
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (!node || typeof node !== 'object') return;
    if ('ei' in node && 'en' in node && normalized(node.sn).startsWith('giocatori')) {
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
    Object.values(node).forEach(walk);
  }
  walk(data);
  return rows;
}

function standardBetflagUrl() {
  return `${BETFLAG_AAMS_BASE}/getOverviewEventsAams/0/1/0/${AAMS_AGG_TOURNAMENT}/0/0/0?channelId=0`;
}

function targetBetflagUrl(target) {
  const [tab, slot] = target;
  return `${BETFLAG_AAMS_BASE}/getOverviewEventsAams/0/-1/0/${AAMS_AGG_TOURNAMENT}/${tab}/${slot}/0?channelId=0`;
}


function standardNorm(value) {
  return normalized(value).replace(/[^a-z0-9]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function standardMarketFamily(name) {
  const n = standardNorm(name);
  if (n === '1x2' || (n.startsWith('1x2 ') && !n.includes('tempo'))) return '1X2';
  if (['u o', 'under over', 'over under', 'totale gol'].includes(n) || n.startsWith('u o ') || n.includes('under over') || n.includes('over under')) return 'OVER_UNDER';
  if (['gg ng', 'goal no goal', 'gol no gol', 'btts'].includes(n) || n.includes('gg ng') || n.includes('goal no goal') || n.includes('gol no gol')) return 'GOAL_NO_GOAL';
  if (n === 'dc' || n === 'doppia chance' || n.includes('doppia chance')) return 'DOUBLE_CHANCE';
  if (n.includes('team total') || n.includes('totale squadra') || n.includes('gol squadra')) return 'TEAM_TOTAL';
  if (n.includes('handicap')) return 'HANDICAP';
  return null;
}

function standardMarketScope(name, family) {
  const n = standardNorm(name);
  if (family === 'OVER_UNDER') {
    if (['u o', 'under over', 'over under', 'totale gol'].includes(n)) return 'CORE_GOALS_TOTAL';
    if (n.includes('angol') || n.includes('corner')) return 'CORNERS_TOTAL';
    if (n.includes('cartell') || n.includes('card')) return 'CARDS_TOTAL';
    if (n.includes('tiro') || n.includes('shot')) return 'SHOTS_TOTAL';
    return 'OTHER_TOTAL';
  }
  return 'CORE';
}

function standardSlotsFromLmtW(data) {
  const candidates = [];
  const tabs = data && typeof data === 'object' && Array.isArray(data.lmtW) ? data.lmtW : [];
  for (const tab of tabs) {
    if (!tab || typeof tab !== 'object') continue;
    const tabId = tab.tbI;
    const tabName = tab.tbN;
    for (const item of tab.lotb || []) {
      if (!item || typeof item !== 'object') continue;
      const slotId = item.ti;
      const slotName = item.sn;
      const family = standardMarketFamily(slotName);
      if (family && tabId != null && slotId != null) {
        candidates.push({ tab_id: tabId, tab_name: tabName, slot_id: slotId, slot_name: slotName, family, market_scope: standardMarketScope(slotName, family) });
      }
    }
  }
  const rank = { '1X2': 0, 'OVER_UNDER': 1, 'GOAL_NO_GOAL': 2, 'DOUBLE_CHANCE': 3, 'TEAM_TOTAL': 4, 'HANDICAP': 5 };
  const canonicalRank = (x) => {
    const n = standardNorm(x.slot_name);
    if (x.family === 'OVER_UNDER') {
      if (x.market_scope === 'CORE_GOALS_TOTAL' && n === 'u o') return 0;
      if (x.market_scope === 'CORE_GOALS_TOTAL') return 1;
      return 9;
    }
    return 0;
  };
  candidates.sort((a, b) => {
    const aa = [standardNorm(a.tab_name) === 'principali' ? 0 : 1, rank[a.family] ?? 9, canonicalRank(a), Number(a.slot_id || 0)];
    const bb = [standardNorm(b.tab_name) === 'principali' ? 0 : 1, rank[b.family] ?? 9, canonicalRank(b), Number(b.slot_id || 0)];
    for (let i = 0; i < aa.length; i += 1) if (aa[i] !== bb[i]) return aa[i] - bb[i];
    return 0;
  });
  const out = [];
  const seen = new Set();
  for (const x of candidates) {
    if (seen.has(x.family)) continue;
    if (x.family === 'OVER_UNDER' && x.market_scope !== 'CORE_GOALS_TOTAL') continue;
    seen.add(x.family);
    out.push(x);
    if (out.length >= 6) break;
  }
  return out;
}

function standardTargetBetflagUrl(slot) {
  return `${BETFLAG_AAMS_BASE}/getOverviewEventsAams/0/1/0/${AAMS_AGG_TOURNAMENT}/${slot.tab_id}/${slot.slot_id}/0?channelId=0`;
}

function collectStandardRows(data, slot, fetchedAt, seen = new Set()) {
  const rows = [];
  function walk(node) {
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (!node || typeof node !== 'object') return;
    const eventName = String(node.en || '');
    if (node.mi != null && eventName && !eventName.startsWith('(')) {
      const mm = node.mmkW;
      const markets = Array.isArray(mm) ? mm : (mm && typeof mm === 'object' ? Object.values(mm) : []);
      for (const market of markets) {
        if (!market || typeof market !== 'object') continue;
        const marketName = String(market.mn || slot.slot_name || '').trim();
        const family = standardMarketFamily(marketName) || slot.family;
        const scope = standardMarketScope(marketName, family);
        if (!['1X2','OVER_UNDER','GOAL_NO_GOAL','DOUBLE_CHANCE','TEAM_TOTAL','HANDICAP'].includes(family)) continue;
        if (family === 'OVER_UNDER' && slot.market_scope === 'CORE_GOALS_TOTAL' && scope !== 'CORE_GOALS_TOTAL') continue;
        const spd = market.spd;
        const spreads = Array.isArray(spd) ? spd.map((value, index) => [index, value]) : (spd && typeof spd === 'object' ? Object.entries(spd) : []);
        for (const [spreadKey, spread] of spreads) {
          if (!spread || typeof spread !== 'object') continue;
          let realLine = spread.sl;
          if (realLine == null || realLine === '' || String(realLine) === '0' || String(realLine) === '0.0') realLine = spreadKey;
          if (String(realLine) === '0' || String(realLine) === '0.0') realLine = null;
          for (const quote of spread.asl || []) {
            if (!quote || typeof quote !== 'object' || typeof quote.ov !== 'number') continue;
            const key = [node.mi, marketName, String(realLine), quote.sn, quote.si].join('|');
            if (seen.has(key)) continue;
            seen.add(key);
            rows.push({
              event_id: node.ei,
              match_market_id: node.mi,
              match: eventName,
              match_start: node.ed,
              league: node.td || null,
              family,
              market_scope: scope,
              market: marketName,
              line: realLine,
              selection: quote.sn,
              odd: quote.ov,
              selection_id: quote.si,
              market_id: quote.mi,
              odds_id: quote.oi,
              betflag_tab_id: slot.tab_id,
              betflag_slot_id: slot.slot_id,
              fetched_at: fetchedAt
            });
          }
        }
      }
    }
    Object.values(node).forEach(walk);
  }
  walk(data);
  return rows;
}

async function fetchBetflagStandard() {
  const started = Date.now();
  const fetchedAt = new Date().toISOString();
  const headers = betflagHeaders();
  const baseResult = await fetchJson(standardBetflagUrl(), { headers }, 16000);
  const slots = standardSlotsFromLmtW(baseResult.data);
  const results = await Promise.all(slots.map((slot) => fetchJson(standardTargetBetflagUrl(slot), { headers }, 16000)));
  const rows = [];
  const seen = new Set();
  const slotResults = [];
  for (let i = 0; i < slots.length; i += 1) {
    const added = results[i].ok ? collectStandardRows(results[i].data, slots[i], fetchedAt, seen) : [];
    rows.push(...added);
    slotResults.push({ ...slots[i], status: results[i].status, ok: results[i].ok, rows_added: added.length });
  }
  return {
    generated_at: fetchedAt,
    source_class: 'BETFLAG_AAMS_DIRECT',
    source: 'sportservice.betflag.it direct AAMS standard market service',
    source_url_host: 'sportservice.betflag.it',
    betflag_direct: true,
    goldbet_direct: false,
    source_healthy: Boolean(baseResult.ok && slots.length > 0 && results.every((result) => result.ok)),
    market_rows_available: rows.length > 0,
    elapsed_ms: Date.now() - started,
    base_status: baseResult.status,
    slot_catalog: slots,
    slot_results: slotResults,
    row_count: rows.length,
    rows
  };
}

async function getCachedBetflagStandard(request, ctx) {
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
  return { payload, cache: cacheable ? 'MISS:CACHED_HEALTHY' : 'MISS:NOT_CACHED_EMPTY_OR_UNHEALTHY' };
}

function filterStandardIndexRows(rows, url) {
  const date = String(url.searchParams.get('date') || '').trim();
  const q = standardNorm(url.searchParams.get('q'));
  const matchMarketId = String(url.searchParams.get('match_market_id') || '').trim();
  return (rows || []).filter((row) => {
    if (date && !String(row.match_start || '').startsWith(date)) return false;
    if (matchMarketId && String(row.match_market_id || '') !== matchMarketId) return false;
    if (q) {
      const hay = standardNorm([row.match, row.league, row.family, row.market, row.selection].join(' '));
      if (!q.split(/\s+/).filter(Boolean).every((term) => hay.includes(term))) return false;
    }
    return true;
  });
}

function buildStandardIndexDocument(payload, rows, requestedDate) {
  const fixtureMap = new Map();
  for (const row of rows || []) {
    const key = String(row.match_market_id || '').trim() || `${standardNorm(row.match)}|${row.match_start || ''}`;
    let fixture = fixtureMap.get(key);
    if (!fixture) {
      fixture = {
        fixture_key: row.match_market_id ? `mi:${row.match_market_id}` : `match:${key}`,
        match_market_id: row.match_market_id || null,
        event_id: row.event_id || null,
        match: row.match || null,
        start_time: row.match_start || null,
        league: row.league || null,
        standard: []
      };
      fixtureMap.set(key, fixture);
    }
    fixture.standard.push({
      family: row.family,
      market_scope: row.market_scope,
      market: row.market,
      line: row.line ?? null,
      selection: row.selection,
      odd: row.odd,
      selection_id: row.selection_id ?? null,
      market_id: row.market_id ?? null,
      odds_id: row.odds_id ?? null
    });
  }
  const fixtures = [...fixtureMap.values()].sort((a,b) => String(a.start_time || '').localeCompare(String(b.start_time || '')) || String(a.match || '').localeCompare(String(b.match || '')));
  return {
    generated_at: payload.generated_at,
    source_class: payload.source_class,
    source: payload.source,
    source_healthy: payload.source_healthy,
    index_version: 'standard-index-v1',
    coverage_scope: requestedDate ? { type: 'date', date: requestedDate } : { type: 'all' },
    coverage: {
      source_rows: payload.row_count,
      scoped_rows: rows.length,
      fixtures: fixtures.length,
      slots: payload.slot_catalog,
      slot_results: payload.slot_results
    },
    fixtures
  };
}

async function fetchBetflagTargets(targets) {
  const started = Date.now();
  const fetchedAt = new Date().toISOString();
  const headers = betflagHeaders();
  const [standardResult, ...targetResults] = await Promise.all([
    fetchJson(standardBetflagUrl(), { headers }, 16000),
    ...targets.map((target) => fetchJson(targetBetflagUrl(target), { headers }, 16000))
  ]);
  const matchMap = buildMatchMap(standardResult.data);
  const rows = [];
  const seen = new Set();
  const calls = [];
  for (let i = 0; i < targets.length; i += 1) {
    const target = targets[i];
    const result = targetResults[i];
    const added = collectPlayerRows(result.data, target[2], matchMap, fetchedAt, seen);
    rows.push(...added);
    calls.push({ tab: target[0], slot: target[1], label: target[2], status: result.status, ok: result.ok, rows_added: added.length });
  }
  const sourceHealthy = standardResult.ok && targetResults.every((result) => result.ok);
  return {
    generated_at: fetchedAt,
    source_class: 'BETFLAG_AAMS_DIRECT',
    source: 'sportservice.betflag.it direct AAMS player service',
    source_url_host: 'sportservice.betflag.it',
    betflag_direct: true,
    goldbet_direct: false,
    source_healthy: sourceHealthy,
    price_gate_eligible_at_fetch: sourceHealthy && rows.length > 0,
    freshness_policy_seconds: BETFLAG_EXACT_FRESHNESS_SECONDS,
    elapsed_ms: Date.now() - started,
    match_map_count: matchMap.size,
    row_count: rows.length,
    standard_status: standardResult.status,
    calls,
    rows
  };
}

async function fetchBetflagAggregate(mode = 'core') {
  const targets = mode === 'full' ? PLAYER_TARGETS : PLAYER_TARGETS.filter((target) => CORE_TARGET_LABELS.has(target[2]));
  return fetchBetflagTargets(targets);
}

async function getCachedBetflagAggregate(request, mode, ctx) {
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
  return { payload, cache: cacheable ? 'MISS:CACHED_HEALTHY' : 'MISS:NOT_CACHED_EMPTY_OR_UNHEALTHY' };
}

function sourceFreshness(generatedAt) {
  const ts = Date.parse(String(generatedAt || ''));
  const ageSeconds = Number.isFinite(ts) ? Math.max(0, (Date.now() - ts) / 1000) : Number.POSITIVE_INFINITY;
  return {
    age_seconds: Number.isFinite(ageSeconds) ? Math.round(ageSeconds * 10) / 10 : null,
    max_age_seconds: BETFLAG_EXACT_FRESHNESS_SECONDS,
    fresh: Number.isFinite(ageSeconds) && ageSeconds <= BETFLAG_EXACT_FRESHNESS_SECONDS
  };
}

function filterBetflagRows(rows, url, { exactPlayer = false, exactMarket = false } = {}) {
  const matchMarketId = normalized(url.searchParams.get('match_market_id'));
  const eventId = normalized(url.searchParams.get('event_id'));
  const q = normalized(url.searchParams.get('q'));
  const player = normalized(url.searchParams.get('player'));
  const market = canonicalMarket(url.searchParams.get('market'));
  const league = normalized(url.searchParams.get('league'));
  const selection = normalized(url.searchParams.get('selection'));
  const line = normalized(url.searchParams.get('line'));
  const limit = clampInt(url.searchParams.get('limit'), 300, 1, 1000);
  const offset = clampInt(url.searchParams.get('offset'), 0, 0, 100000);
  const filtered = [];
  for (const row of rows || []) {
    if (matchMarketId && normalized(row.match_market_id) !== matchMarketId) continue;
    if (eventId && normalized(row.match_event_id || row.event_id) !== eventId) continue;
    if (player) {
      const rp = normalized(row.player);
      if (exactPlayer ? rp !== player : !rp.includes(player)) continue;
    }
    if (market) {
      const rm = canonicalMarket(row.requested_market || row.market);
      if (exactMarket ? rm !== market : !rm.includes(market)) continue;
    }
    if (league && !normalized(row.league).includes(league)) continue;
    if (selection && normalized(row.selection) !== selection) continue;
    if (line && normalized(row.line) !== line) continue;
    if (q) {
      const haystack = [row.match, row.match_code, row.league, row.player, row.requested_market, row.market, row.selection].map(normalized).join(' ');
      const terms = q.split(/\s+/).filter(Boolean);
      if (!terms.every((term) => haystack.includes(term))) continue;
    }
    filtered.push(row);
  }
  return filtered.slice(offset, offset + limit);
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

function validateExactPriceQuery(url) {
  const player = String(url.searchParams.get('player') || '').trim();
  const market = String(url.searchParams.get('market') || '').trim();
  const q = String(url.searchParams.get('q') || '').trim();
  const matchMarketId = String(url.searchParams.get('match_market_id') || '').trim();
  const eventId = String(url.searchParams.get('event_id') || '').trim();
  if (!player) return 'player is required';
  if (!market) return 'market is required';
  if (!matchMarketId && !eventId && q.length < 3) return 'Specify event_id, match_market_id, or q with at least 3 characters';
  if (!resolvePlayerTarget(market)) return `Unsupported player market: ${market}`;
  return null;
}

async function certificateFor(row, payload, exactCount) {
  const freshness = sourceFreshness(payload.generated_at);
  const canonical = {
    source_class: payload.source_class,
    source_host: payload.source_url_host,
    fetched_at: payload.generated_at,
    match: row?.match || null,
    match_market_id: row?.match_market_id || null,
    match_event_id: row?.match_event_id || null,
    player: row?.player || null,
    requested_market: row?.requested_market || null,
    market: row?.market || null,
    line: row?.line ?? null,
    selection: row?.selection || null,
    odd: row?.odd ?? null,
    selection_id: row?.selection_id ?? null,
    market_id: row?.market_id ?? null,
    odds_id: row?.odds_id ?? null
  };
  const fingerprint = await sha256Hex(JSON.stringify(canonical));
  const eligible = Boolean(payload.source_healthy && freshness.fresh && exactCount === 1 && row && row.odd != null);
  return {
    proof_id: `bf-${fingerprint.slice(0, 20)}`,
    sha256: fingerprint,
    exact_identity_match: exactCount === 1,
    source_healthy: Boolean(payload.source_healthy),
    freshness,
    price_gate_eligible: eligible,
    canonical
  };
}

function filterPlayerIndexRows(rows, url) {
  const wantedDate = String(url.searchParams.get('date') || '').trim();
  if (!wantedDate) return rows || [];
  return (rows || []).filter((row) => String(row.match_start || row.start_time || '').startsWith(wantedDate));
}

function buildCompactPlayerIndex(rows) {
  const fixtureMap = new Map();
  const marketLabels = new Set();
  const playerKeys = new Set();
  const mappingCounts = {
    standard_match: 0,
    match_code_fallback: 0,
    fixture_id_fallback: 0,
    composite_identity_fallback: 0,
    missing_stable_identity: 0,
    missing_player: 0
  };
  let unmappedRows = 0;

  for (const row of rows || []) {
    const fixtureId = String(row.match_market_id || '').trim();
    const matchCode = String(row.match_code || '').trim();
    const startTime = String(row.match_start || row.start_time || '').trim();
    const league = String(row.league || '').trim();
    const playerName = String(row.player || '').trim();
    const standardMatchName = String(row.match || '').trim();

    if (!playerName) {
      mappingCounts.missing_player += 1;
      unmappedRows += 1;
      continue;
    }

    let fixtureKey = '';
    let identitySource = '';
    if (fixtureId) {
      fixtureKey = `mi:${fixtureId}`;
      identitySource = 'MATCH_MARKET_ID';
    } else if (matchCode && startTime) {
      fixtureKey = `code:${normalized(matchCode)}|${startTime}`;
      identitySource = 'MATCH_CODE_START';
      mappingCounts.composite_identity_fallback += 1;
    } else {
      mappingCounts.missing_stable_identity += 1;
      unmappedRows += 1;
      continue;
    }

    let matchName = standardMatchName;
    let mappingStatus = 'STANDARD_MATCH';
    if (standardMatchName) {
      mappingCounts.standard_match += 1;
    } else if (matchCode) {
      matchName = matchCode;
      mappingStatus = 'MATCH_CODE_FALLBACK';
      mappingCounts.match_code_fallback += 1;
    } else {
      matchName = `AAMS ${fixtureId || fixtureKey}`;
      mappingStatus = 'FIXTURE_ID_FALLBACK';
      mappingCounts.fixture_id_fallback += 1;
    }

    let fixture = fixtureMap.get(fixtureKey);
    if (!fixture) {
      fixture = {
        fixture_key: fixtureKey,
        match_market_id: fixtureId || null,
        match_event_id: row.match_event_id || null,
        match_code: matchCode || null,
        match: matchName,
        mapping_status: mappingStatus,
        exact_fixture_identity_available: Boolean(fixtureId),
        start_time: startTime || null,
        league: league || null,
        players: new Map()
      };
      fixtureMap.set(fixtureKey, fixture);
    } else if (fixture.mapping_status !== 'STANDARD_MATCH' && standardMatchName) {
      fixture.match = standardMatchName;
      fixture.mapping_status = 'STANDARD_MATCH';
      fixture.match_event_id = row.match_event_id || fixture.match_event_id;
    }

    const playerKey = normalized(playerName);
    playerKeys.add(`${fixtureKey}|${playerKey}`);
    let player = fixture.players.get(playerKey);
    if (!player) {
      player = { player: playerName, markets: new Map() };
      fixture.players.set(playerKey, player);
    }

    const marketLabel = String(row.requested_market || row.market || '').trim();
    const marketKey = canonicalMarket(marketLabel);
    marketLabels.add(marketLabel);
    let market = player.markets.get(marketKey);
    if (!market) {
      market = { market: marketLabel, quotes: [] };
      player.markets.set(marketKey, market);
    }
    market.quotes.push({
      line: row.line ?? null,
      selection: row.selection || null,
      odd: row.odd ?? null
    });
  }

  const fixtures = [...fixtureMap.values()].map((fixture) => ({
    fixture_key: fixture.fixture_key,
    match_market_id: fixture.match_market_id,
    match_event_id: fixture.match_event_id,
    match_code: fixture.match_code,
    match: fixture.match,
    mapping_status: fixture.mapping_status,
    exact_fixture_identity_available: fixture.exact_fixture_identity_available,
    start_time: fixture.start_time,
    league: fixture.league,
    players: [...fixture.players.values()]
      .map((player) => ({
        player: player.player,
        markets: [...player.markets.values()]
          .map((market) => ({
            market: market.market,
            quotes: market.quotes.sort((a, b) => String(a.line ?? '').localeCompare(String(b.line ?? '')) || String(a.selection ?? '').localeCompare(String(b.selection ?? '')))
          }))
          .sort((a, b) => a.market.localeCompare(b.market))
      }))
      .sort((a, b) => a.player.localeCompare(b.player))
  })).sort((a, b) => String(a.start_time || '').localeCompare(String(b.start_time || '')) || a.match.localeCompare(b.match));

  return {
    fixtures,
    fixture_count: fixtures.length,
    exact_fixture_count: fixtures.filter((fixture) => fixture.exact_fixture_identity_available).length,
    fallback_fixture_count: fixtures.filter((fixture) => fixture.mapping_status !== 'STANDARD_MATCH').length,
    player_fixture_count: playerKeys.size,
    market_labels: [...marketLabels].sort(),
    mapping_counts: mappingCounts,
    unmapped_rows: unmappedRows
  };
}

function buildPlayerIndexDocument(payload, scopedRows, requestedDate) {
  const compact = buildCompactPlayerIndex(scopedRows);
  const calls = Array.isArray(payload.calls) ? payload.calls : [];
  const missingTargets = calls.filter((call) => !call.ok).map((call) => call.label);
  const coverageStatic = Boolean(
    payload.source_healthy && calls.length === PLAYER_TARGETS.length &&
    missingTargets.length === 0 && compact.unmapped_rows === 0
  );
  return {
    generated_at: payload.generated_at,
    source_class: payload.source_class,
    source: payload.source,
    source_healthy: payload.source_healthy,
    index_version: 'player-index-v2',
    coverage_static: coverageStatic,
    coverage_scope: requestedDate ? { type: 'date', date: requestedDate } : { type: 'all' },
    exact_price_endpoint: '/live/player-price',
    coverage: {
      targets_expected: PLAYER_TARGETS.length,
      targets_called: calls.length,
      targets_ok: calls.filter((call) => call.ok).length,
      missing_targets: missingTargets,
      source_rows: payload.row_count,
      scoped_source_rows: scopedRows.length,
      indexed_rows: Math.max(0, scopedRows.length - compact.unmapped_rows),
      unmapped_rows: compact.unmapped_rows,
      mapping_counts: compact.mapping_counts,
      fixtures: compact.fixture_count,
      exact_fixtures: compact.exact_fixture_count,
      fallback_fixtures: compact.fallback_fixture_count,
      player_fixtures: compact.player_fixture_count,
      markets_present: compact.market_labels
    },
    fixtures: compact.fixtures
  };
}

async function getCachedPlayerIndex(request, url, ctx) {
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
}

async function publicPlayerIndex(request, url, ctx) {
  const { document, cache } = await getCachedPlayerIndex(request, url, ctx);
  const freshness = sourceFreshness(document.generated_at);
  const coverageComplete = Boolean(document.coverage_static && freshness.fresh);
  return json({
    ...document,
    served_at: new Date().toISOString(),
    cache,
    freshness,
    coverage_complete: coverageComplete,
    ready_for_discovery: coverageComplete,
    discovery_contract: {
      single_call_index: true,
      max_index_cache_seconds: BETFLAG_INDEX_CACHE_SECONDS,
      exact_price_no_cache: true,
      fallback_mapping_allowed: true,
      no_quote_rows_dropped: document.coverage?.unmapped_rows === 0
    }
  }, 200, { 'Cache-Control': 'no-store' });
}

async function publicPlayerProps(request, url, ctx) {
  const error = validatePublicQuery(url);
  if (error) return json({ error }, 400);
  const mode = url.searchParams.get('full') === '0' ? 'core' : 'full';
  const { payload, cache } = await getCachedBetflagAggregate(request, mode, ctx);
  const rows = filterBetflagRows(payload.rows, url);
  const limit = clampInt(url.searchParams.get('limit'), 300, 1, 1000);
  const offset = clampInt(url.searchParams.get('offset'), 0, 0, 100000);
  const freshness = sourceFreshness(payload.generated_at);
  return json({
    generated_at: payload.generated_at,
    served_at: new Date().toISOString(),
    cache,
    source_class: payload.source_class,
    source: payload.source,
    betflag_direct: true,
    goldbet_direct: false,
    source_healthy: payload.source_healthy,
    freshness,
    scan_price_gate_capable: Boolean(payload.source_healthy && freshness.fresh),
    price_gate_rule: 'Use /live/player-price for exact fixture+player+market certification before BET.',
    mode,
    upstream_elapsed_ms: payload.elapsed_ms,
    total_source_rows: payload.row_count,
    returned: rows.length,
    pagination: {
      limit,
      offset,
      has_more: rows.length === limit,
      next_offset: rows.length === limit ? offset + rows.length : null
    },
    rows
  }, 200, { 'Cache-Control': 'no-store' });
}

async function publicPlayerPrice(url) {
  const error = validateExactPriceQuery(url);
  if (error) return json({ error }, 400);
  const target = resolvePlayerTarget(url.searchParams.get('market'));
  const requestedSelection = String(url.searchParams.get('selection') || '').trim();
  const requestedLine = String(url.searchParams.get('line') || '').trim();
  const attempts = [];
  let payload = null;
  let rows = [];

  for (let attempt = 1; attempt <= 3; attempt += 1) {
    payload = await fetchBetflagTargets([target]);
    rows = filterBetflagRows(payload.rows, url, { exactPlayer: true, exactMarket: true });
    if (!requestedSelection && rows.length > 1) {
      const yesRows = rows.filter((row) => normalized(row.selection) === 'si');
      if (yesRows.length === 1) rows = yesRows;
    }
    if (!requestedLine && rows.length > 1 && rows.some((row) => row.line != null)) {
      // Keep ambiguity explicit for line-based markets: caller must supply line.
    }
    attempts.push({
      attempt,
      source_healthy: Boolean(payload.source_healthy),
      source_rows: payload.row_count,
      exact_rows: rows.length,
      upstream_elapsed_ms: payload.elapsed_ms
    });
    if (payload.source_healthy && rows.length === 1) break;
    if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 180 * attempt));
  }

  if (!(payload?.source_healthy && rows.length === 1)) {
    const aggregatePayload = await fetchBetflagAggregate('full');
    let aggregateRows = filterBetflagRows(aggregatePayload.rows, url, { exactPlayer: true, exactMarket: true });
    if (!requestedSelection && aggregateRows.length > 1) {
      const yesRows = aggregateRows.filter((row) => normalized(row.selection) === 'si');
      if (yesRows.length === 1) aggregateRows = yesRows;
    }
    attempts.push({
      attempt: 'full_aggregate_fallback',
      acquisition_mode: 'FULL_AGGREGATE_FALLBACK',
      source_healthy: Boolean(aggregatePayload.source_healthy),
      source_rows: aggregatePayload.row_count,
      exact_rows: aggregateRows.length,
      upstream_elapsed_ms: aggregatePayload.elapsed_ms
    });
    if (aggregatePayload.source_healthy && aggregateRows.length === 1) {
      payload = aggregatePayload;
      rows = aggregateRows;
    }
  }

  const row = rows.length === 1 ? rows[0] : null;
  const certificate = await certificateFor(row, payload, rows.length);
  return json({
    generated_at: payload.generated_at,
    served_at: new Date().toISOString(),
    source_class: payload.source_class,
    source: payload.source,
    betflag_direct: true,
    goldbet_direct: false,
    upstream_elapsed_ms: payload.elapsed_ms,
    acquisition_attempts: attempts,
    target: { tab: target[0], slot: target[1], market: target[2] },
    returned: rows.length,
    price_gate_eligible: certificate.price_gate_eligible,
    certificate,
    quote: row,
    candidates: rows.length === 1 ? undefined : rows.slice(0, 25),
    note: certificate.price_gate_eligible
      ? 'Certified fresh BetFlag/AAMS operational player price.'
      : 'No unique fresh exact quote after direct retries; do not classify BET from this response.'
  }, row ? 200 : 404, { 'Cache-Control': 'no-store' });
}


async function publicStandardIndex(request, url, ctx) {
  const requestedDate = String(url.searchParams.get('date') || '').trim();
  const { payload, cache } = await getCachedBetflagStandard(request, ctx);
  const rows = filterStandardIndexRows(payload.rows, url);
  const document = buildStandardIndexDocument(payload, rows, requestedDate);
  const freshness = sourceFreshness(document.generated_at);
  return json({
    ...document,
    served_at: new Date().toISOString(),
    cache,
    freshness,
    coverage_complete: Boolean(document.source_healthy && freshness.fresh && document.coverage?.fixtures > 0),
    ready_for_discovery: Boolean(document.source_healthy && freshness.fresh && document.coverage?.fixtures > 0)
  }, 200, { 'Cache-Control': 'no-store' });
}

async function getDirectGoldbetData(url, env) {
  if (!env.ODSS_API_KEY) throw new Error('Missing ODSS_API_KEY');
  const upstream = new URL(`${UPSTREAM_BASE}/odds`);
  for (const key of ['sport', 'market', 'league', 'event_id', 'content', 'player', 'q']) {
    const value = url.searchParams.get(key);
    if (value) upstream.searchParams.set(key, value);
  }
  upstream.searchParams.set('bookmakers', 'goldbet');
  upstream.searchParams.set('state', url.searchParams.get('state') || 'prematch');
  upstream.searchParams.set('limit', String(clampInt(url.searchParams.get('limit'), 250, 1, 500)));
  upstream.searchParams.set('offset', String(clampInt(url.searchParams.get('offset'), 0, 0, 100000)));
  const started = Date.now();
  const result = await fetchJson(upstream.toString(), {
    headers: { Accept: 'application/json', 'x-api-key': env.ODSS_API_KEY, 'User-Agent': 'RadarGoldBetFastPath/7.0' }
  }, 15000);
  return {
    generated_at: new Date().toISOString(),
    source_class: 'GOLDBET_DIRECT_ODSS',
    source: 'odss-api direct bookmaker filter',
    goldbet_direct: true,
    price_gate_eligible: result.ok,
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
  const response = json(payload, 200, { 'Cache-Control': `public, s-maxage=${GOLDBET_CACHE_SECONDS}, max-age=0` });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return { payload, cache: 'MISS' };
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
  const [directResult, betflagResult] = await Promise.allSettled([
    getCachedDirectGoldbet(request, url, env, ctx),
    getCachedBetflagAggregate(request, mode, ctx)
  ]);
  const directGoldbet = directResult.status === 'fulfilled'
    ? { ...directResult.value.payload, cache: directResult.value.cache }
    : { source_class: 'GOLDBET_DIRECT_ODSS', goldbet_direct: true, price_gate_eligible: false, error: String(directResult.reason) };
  let betflagPlayerProps;
  if (betflagResult.status === 'fulfilled') {
    const payload = betflagResult.value.payload;
    const rows = filterBetflagRows(payload.rows, url);
    const freshness = sourceFreshness(payload.generated_at);
    betflagPlayerProps = {
      generated_at: payload.generated_at,
      cache: betflagResult.value.cache,
      source_class: payload.source_class,
      source: payload.source,
      betflag_direct: true,
      source_healthy: payload.source_healthy,
      freshness,
      exact_price_endpoint: '/live/player-price',
      returned: rows.length,
      rows
    };
  } else {
    betflagPlayerProps = { source_class: 'BETFLAG_AAMS_DIRECT', betflag_direct: true, price_gate_eligible: false, error: String(betflagResult.reason) };
  }
  return json({
    generated_at: new Date().toISOString(),
    elapsed_ms: Date.now() - started,
    contract: {
      standard_markets_primary: 'GoldBet direct when fresh and mapped',
      player_props_primary: 'BetFlag/AAMS direct operational source',
      player_props_final_gate: 'Requires unique fresh certificate from /live/player-price',
      goldbet_player_crosscheck: 'Use direct GoldBet when available as calibration/cross-check, not as a prerequisite.'
    },
    direct_goldbet: directGoldbet,
    betflag_player_props: betflagPlayerProps
  });
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS_HEADERS });
    if (request.method !== 'GET') return json({ error: 'Method not allowed' }, 405, { Allow: 'GET, OPTIONS' });

    const url = new URL(request.url);
    const endpoint = url.pathname.replace(/^\/+|\/+$/g, '') || 'health';

    if (endpoint === 'health') {
      return json({
        ok: true,
        service: 'radar-goldbet',
        version: '7.0-betflag-operational',
        player_props_forwarding: true,
        public_fast_path: true,
        exact_player_price_proof: true,
        cache_ttl_seconds: { direct_goldbet: GOLDBET_CACHE_SECONDS, betflag_scan: BETFLAG_SCAN_CACHE_SECONDS, betflag_exact: 0 },
        freshness_policy_seconds: { betflag_exact_price: BETFLAG_EXACT_FRESHNESS_SECONDS },
        provenance_contract: {
          BETFLAG_AAMS_DIRECT: 'primary operational player-prop source; exact fresh unique quote is eligible for FINAL GATE',
          GOLDBET_DIRECT_ODSS: 'direct GoldBet source when fresh/mapped; player props used as cross-check when available'
        },
        endpoints: [
          '/health', '/live/goldbet', '/live/standard-index', '/live/player-index', '/live/player-props', '/live/player-price', '/live/fixture',
          '/sports', '/bookmakers', '/leagues', '/odds', '/history'
        ],
        protected_endpoints: ['/sports', '/bookmakers', '/leagues', '/odds', '/history'],
        odds_params: ALLOWED_PARAMS.odds
      });
    }

    try {
      if (endpoint === 'live/standard-index') return await publicStandardIndex(request, url, ctx);
      if (endpoint === 'live/player-index') return await publicPlayerIndex(request, url, ctx);
      if (endpoint === 'live/player-props') return await publicPlayerProps(request, url, ctx);
      if (endpoint === 'live/player-price') return await publicPlayerPrice(url);
      if (endpoint === 'live/goldbet') return await publicGoldbet(request, url, env, ctx);
      if (endpoint === 'live/fixture') return await publicFixture(request, url, env, ctx);
    } catch (error) {
      console.error(JSON.stringify({ event: 'fast_path_error', endpoint, message: error instanceof Error ? error.message : String(error) }));
      return json({ error: 'Fast path request failed' }, 502);
    }

    if (!(endpoint in ALLOWED_PARAMS)) {
      return json({
        error: 'Endpoint non valido',
        endpoints: [
          '/health', '/live/goldbet', '/live/standard-index', '/live/player-index', '/live/player-props', '/live/player-price', '/live/fixture',
          '/sports', '/bookmakers', '/leagues', '/odds', '/history'
        ]
      }, 404);
    }

    if (!(await isAuthorized(request, env, url))) return json({ error: 'Unauthorized' }, 401);
    try {
      return await proxyEndpoint(endpoint, request, env, url);
    } catch (error) {
      console.error(JSON.stringify({ event: 'upstream_error', endpoint, message: error instanceof Error ? error.message : String(error) }));
      return json({ error: 'Upstream request failed' }, 502);
    }
  }
};
