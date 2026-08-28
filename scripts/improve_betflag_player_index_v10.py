from pathlib import Path

p = Path('worker/src/index.mjs')
s = p.read_text(encoding='utf-8')

const_anchor = "const BETFLAG_SCAN_CACHE_SECONDS = 12;\n"
if "BETFLAG_INDEX_CACHE_SECONDS" not in s:
    if const_anchor not in s:
        raise SystemExit('cache constant anchor not found')
    s = s.replace(const_anchor, const_anchor + "const BETFLAG_INDEX_CACHE_SECONDS = 20;\n", 1)

start = s.index('function buildCompactPlayerIndex(rows) {')
end = s.index('async function publicPlayerProps(request, url, ctx) {', start)

block = r'''function filterPlayerIndexRows(rows, url) {
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

'''

s = s[:start] + block + s[end:]
p.write_text(s, encoding='utf-8')
print('BetFlag player-index v10 patch applied')
