from pathlib import Path

# Canonical deploy patch: exact FINAL GATE accepts stable BetFlag match-event identity
# and retries direct BetFlag acquisition before declaring a quote unavailable.
p = Path('worker/src/index.mjs')
s = p.read_text(encoding='utf-8')

changed = False

old = """function filterBetflagRows(rows, url, { exactPlayer = false, exactMarket = false } = {}) {\n  const matchMarketId = normalized(url.searchParams.get('match_market_id'));\n  const q = normalized(url.searchParams.get('q'));"""
new = """function filterBetflagRows(rows, url, { exactPlayer = false, exactMarket = false } = {}) {\n  const matchMarketId = normalized(url.searchParams.get('match_market_id'));\n  const eventId = normalized(url.searchParams.get('event_id'));\n  const q = normalized(url.searchParams.get('q'));"""
if old in s:
    s = s.replace(old, new, 1)
    changed = True

old = """  for (const row of rows || []) {\n    if (matchMarketId && normalized(row.match_market_id) !== matchMarketId) continue;\n    if (player) {"""
new = """  for (const row of rows || []) {\n    if (matchMarketId && normalized(row.match_market_id) !== matchMarketId) continue;\n    if (eventId && normalized(row.match_event_id || row.event_id) !== eventId) continue;\n    if (player) {"""
if old in s:
    s = s.replace(old, new, 1)
    changed = True

old = """function validateExactPriceQuery(url) {\n  const player = String(url.searchParams.get('player') || '').trim();\n  const market = String(url.searchParams.get('market') || '').trim();\n  const q = String(url.searchParams.get('q') || '').trim();\n  const matchMarketId = String(url.searchParams.get('match_market_id') || '').trim();\n  if (!player) return 'player is required';\n  if (!market) return 'market is required';\n  if (!matchMarketId && q.length < 3) return 'Specify match_market_id or q with at least 3 characters';"""
new = """function validateExactPriceQuery(url) {\n  const player = String(url.searchParams.get('player') || '').trim();\n  const market = String(url.searchParams.get('market') || '').trim();\n  const q = String(url.searchParams.get('q') || '').trim();\n  const matchMarketId = String(url.searchParams.get('match_market_id') || '').trim();\n  const eventId = String(url.searchParams.get('event_id') || '').trim();\n  if (!player) return 'player is required';\n  if (!market) return 'market is required';\n  if (!matchMarketId && !eventId && q.length < 3) return 'Specify event_id, match_market_id, or q with at least 3 characters';"""
if old in s:
    s = s.replace(old, new, 1)
    changed = True

old_price = """async function publicPlayerPrice(url) {\n  const error = validateExactPriceQuery(url);\n  if (error) return json({ error }, 400);\n  const target = resolvePlayerTarget(url.searchParams.get('market'));\n  const payload = await fetchBetflagTargets([target]);\n  let rows = filterBetflagRows(payload.rows, url, { exactPlayer: true, exactMarket: true });\n  const requestedSelection = String(url.searchParams.get('selection') || '').trim();\n  const requestedLine = String(url.searchParams.get('line') || '').trim();\n  if (!requestedSelection && rows.length > 1) {\n    const yesRows = rows.filter((row) => normalized(row.selection) === 'si');\n    if (yesRows.length === 1) rows = yesRows;\n  }\n  if (!requestedLine && rows.length > 1 && rows.some((row) => row.line != null)) {\n    // Keep ambiguity explicit for line-based markets: caller must supply line.\n  }\n  const row = rows.length === 1 ? rows[0] : null;\n  const certificate = await certificateFor(row, payload, rows.length);\n  return json({\n    generated_at: payload.generated_at,\n    served_at: new Date().toISOString(),\n    source_class: payload.source_class,\n    source: payload.source,\n    betflag_direct: true,\n    goldbet_direct: false,\n    upstream_elapsed_ms: payload.elapsed_ms,\n    target: { tab: target[0], slot: target[1], market: target[2] },\n    returned: rows.length,\n    price_gate_eligible: certificate.price_gate_eligible,\n    certificate,\n    quote: row,\n    candidates: rows.length === 1 ? undefined : rows.slice(0, 25),\n    note: certificate.price_gate_eligible\n      ? 'Certified fresh BetFlag/AAMS operational player price.'\n      : 'No unique fresh exact quote; do not classify BET from this response.'\n  }, row ? 200 : 404, { 'Cache-Control': 'no-store' });\n}"""

new_price = """async function publicPlayerPrice(url) {\n  const error = validateExactPriceQuery(url);\n  if (error) return json({ error }, 400);\n  const target = resolvePlayerTarget(url.searchParams.get('market'));\n  const requestedSelection = String(url.searchParams.get('selection') || '').trim();\n  const requestedLine = String(url.searchParams.get('line') || '').trim();\n  const attempts = [];\n  let payload = null;\n  let rows = [];\n\n  for (let attempt = 1; attempt <= 3; attempt += 1) {\n    payload = await fetchBetflagTargets([target]);\n    rows = filterBetflagRows(payload.rows, url, { exactPlayer: true, exactMarket: true });\n    if (!requestedSelection && rows.length > 1) {\n      const yesRows = rows.filter((row) => normalized(row.selection) === 'si');\n      if (yesRows.length === 1) rows = yesRows;\n    }\n    if (!requestedLine && rows.length > 1 && rows.some((row) => row.line != null)) {\n      // Keep ambiguity explicit for line-based markets: caller must supply line.\n    }\n    attempts.push({\n      attempt,\n      source_healthy: Boolean(payload.source_healthy),\n      source_rows: payload.row_count,\n      exact_rows: rows.length,\n      upstream_elapsed_ms: payload.elapsed_ms\n    });\n    if (payload.source_healthy && rows.length === 1) break;\n    if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 180 * attempt));\n  }\n\n  const row = rows.length === 1 ? rows[0] : null;\n  const certificate = await certificateFor(row, payload, rows.length);\n  return json({\n    generated_at: payload.generated_at,\n    served_at: new Date().toISOString(),\n    source_class: payload.source_class,\n    source: payload.source,\n    betflag_direct: true,\n    goldbet_direct: false,\n    upstream_elapsed_ms: payload.elapsed_ms,\n    acquisition_attempts: attempts,\n    target: { tab: target[0], slot: target[1], market: target[2] },\n    returned: rows.length,\n    price_gate_eligible: certificate.price_gate_eligible,\n    certificate,\n    quote: row,\n    candidates: rows.length === 1 ? undefined : rows.slice(0, 25),\n    note: certificate.price_gate_eligible\n      ? 'Certified fresh BetFlag/AAMS operational player price.'\n      : 'No unique fresh exact quote after direct retries; do not classify BET from this response.'\n  }, row ? 200 : 404, { 'Cache-Control': 'no-store' });\n}"""

if old_price in s:
    s = s.replace(old_price, new_price, 1)
    changed = True

if "const eventId = normalized(url.searchParams.get('event_id'));" not in s:
    raise SystemExit('event_id filter patch not present')
if "const eventId = String(url.searchParams.get('event_id') || '').trim();" not in s:
    raise SystemExit('event_id exact validation patch not present')
if "acquisition_attempts: attempts" not in s:
    raise SystemExit('exact-price retry patch not present')

if changed:
    p.write_text(s, encoding='utf-8')
    print('Patched BetFlag exact identity and retry logic')
else:
    print('BetFlag exact identity and retry patch already present')
