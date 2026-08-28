from pathlib import Path

p = Path('worker/src/index.mjs')
s = p.read_text(encoding='utf-8')

anchor = "async function publicPlayerProps(request, url, ctx) {"
if anchor not in s:
    raise SystemExit('publicPlayerProps anchor not found')

insert = r'''function buildCompactPlayerIndex(rows) {
  const fixtureMap = new Map();
  const marketLabels = new Set();
  const playerKeys = new Set();
  let unmappedRows = 0;

  for (const row of rows || []) {
    const fixtureId = String(row.match_market_id || '');
    const playerName = String(row.player || '').trim();
    const matchName = String(row.match || '').trim();
    if (!fixtureId || !playerName || !matchName) {
      unmappedRows += 1;
      continue;
    }

    let fixture = fixtureMap.get(fixtureId);
    if (!fixture) {
      fixture = {
        match_market_id: fixtureId,
        match_event_id: row.match_event_id || null,
        match: matchName,
        start_time: row.match_start || row.start_time || null,
        league: row.league || null,
        players: new Map()
      };
      fixtureMap.set(fixtureId, fixture);
    }

    const playerKey = normalized(playerName);
    playerKeys.add(`${fixtureId}|${playerKey}`);
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
    match_market_id: fixture.match_market_id,
    match_event_id: fixture.match_event_id,
    match: fixture.match,
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
    player_fixture_count: playerKeys.size,
    market_labels: [...marketLabels].sort(),
    unmapped_rows: unmappedRows
  };
}

async function publicPlayerIndex(request, url, ctx) {
  const { payload, cache } = await getCachedBetflagAggregate(request, 'full', ctx);
  const freshness = sourceFreshness(payload.generated_at);
  const compact = buildCompactPlayerIndex(payload.rows);
  const calls = Array.isArray(payload.calls) ? payload.calls : [];
  const missingTargets = calls.filter((call) => !call.ok).map((call) => call.label);
  const coverageComplete = Boolean(
    payload.source_healthy && freshness.fresh &&
    calls.length === PLAYER_TARGETS.length && missingTargets.length === 0 &&
    compact.unmapped_rows === 0
  );

  return json({
    generated_at: payload.generated_at,
    served_at: new Date().toISOString(),
    cache,
    source_class: payload.source_class,
    source: payload.source,
    source_healthy: payload.source_healthy,
    freshness,
    index_version: 'player-index-v1',
    coverage_complete: coverageComplete,
    ready_for_discovery: coverageComplete,
    exact_price_endpoint: '/live/player-price',
    coverage: {
      targets_expected: PLAYER_TARGETS.length,
      targets_called: calls.length,
      targets_ok: calls.filter((call) => call.ok).length,
      missing_targets: missingTargets,
      source_rows: payload.row_count,
      indexed_rows: Math.max(0, payload.row_count - compact.unmapped_rows),
      unmapped_rows: compact.unmapped_rows,
      fixtures: compact.fixture_count,
      player_fixtures: compact.player_fixture_count,
      markets_present: compact.market_labels
    },
    fixtures: compact.fixtures
  }, 200, { 'Cache-Control': 'no-store' });
}

'''

s = s.replace(anchor, insert + anchor, 1)

old = "          '/health', '/live/goldbet', '/live/player-props', '/live/player-price', '/live/fixture',"
new = "          '/health', '/live/goldbet', '/live/player-index', '/live/player-props', '/live/player-price', '/live/fixture',"
if s.count(old) < 2:
    raise SystemExit('endpoint list anchors not found twice')
s = s.replace(old, new)

old_route = "      if (endpoint === 'live/player-props') return await publicPlayerProps(request, url, ctx);"
new_route = "      if (endpoint === 'live/player-index') return await publicPlayerIndex(request, url, ctx);\n      if (endpoint === 'live/player-props') return await publicPlayerProps(request, url, ctx);"
if old_route not in s:
    raise SystemExit('route anchor not found')
s = s.replace(old_route, new_route, 1)

p.write_text(s, encoding='utf-8')
print('BetFlag player index v9 patch applied')
