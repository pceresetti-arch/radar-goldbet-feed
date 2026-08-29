from pathlib import Path

p = Path('worker/src/index.mjs')
s = p.read_text(encoding='utf-8')

if "async function publicStandardIndex" in s:
    print('BetFlag standard index already present')
    raise SystemExit(0)

anchor1 = "async function fetchBetflagTargets(targets) {"
insert1 = r'''
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
    source_healthy: Boolean(baseResult.ok && rows.length > 0),
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
  cacheUrl.pathname = '/_radar_cache/betflag-standard-index/v1';
  cacheUrl.search = '';
  const cacheKey = new Request(cacheUrl.toString(), { method: 'GET' });
  const cached = await cache.match(cacheKey);
  if (cached) return { payload: await cached.json(), cache: 'HIT' };
  const payload = await fetchBetflagStandard();
  const response = json(payload, 200, { 'Cache-Control': `public, s-maxage=${BETFLAG_SCAN_CACHE_SECONDS}, max-age=0` });
  ctx.waitUntil(cache.put(cacheKey, response.clone()));
  return { payload, cache: 'MISS' };
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

'''
if anchor1 not in s:
    raise SystemExit('anchor1 not found')
s = s.replace(anchor1, insert1 + anchor1, 1)

anchor2 = "async function getDirectGoldbetData(url, env) {"
insert2 = r'''
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

'''
if anchor2 not in s:
    raise SystemExit('anchor2 not found')
s = s.replace(anchor2, insert2 + anchor2, 1)

route_anchor = "      if (endpoint === 'live/player-index') return await publicPlayerIndex(request, url, ctx);"
if route_anchor not in s:
    raise SystemExit('route anchor not found')
s = s.replace(route_anchor, "      if (endpoint === 'live/standard-index') return await publicStandardIndex(request, url, ctx);\n" + route_anchor, 1)

s = s.replace("'/health', '/live/goldbet', '/live/player-index', '/live/player-props', '/live/player-price', '/live/fixture',", "'/health', '/live/goldbet', '/live/standard-index', '/live/player-index', '/live/player-props', '/live/player-price', '/live/fixture',")

p.write_text(s, encoding='utf-8')
print('Patched worker with BetFlag standard index endpoint')
