from pathlib import Path

# Canonical deploy patch: exact FINAL GATE accepts stable BetFlag match event identity.
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

if "const eventId = normalized(url.searchParams.get('event_id'));" not in s:
    raise SystemExit('event_id filter patch not present')
if "const eventId = String(url.searchParams.get('event_id') || '').trim();" not in s:
    raise SystemExit('event_id exact validation patch not present')

if changed:
    p.write_text(s, encoding='utf-8')
    print('Patched BetFlag exact price identity with event_id support')
else:
    print('BetFlag exact event identity patch already present')
