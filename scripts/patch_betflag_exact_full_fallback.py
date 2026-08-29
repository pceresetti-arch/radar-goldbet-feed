from pathlib import Path

p = Path('worker/src/index.mjs')
s = p.read_text(encoding='utf-8')

marker = "acquisition_mode: 'FULL_AGGREGATE_FALLBACK'"
if marker in s:
    print('BetFlag exact full-aggregate fallback already present')
    raise SystemExit(0)

anchor = """  const row = rows.length === 1 ? rows[0] : null;\n  const certificate = await certificateFor(row, payload, rows.length);"""
replacement = """  if (!(payload?.source_healthy && rows.length === 1)) {\n    const aggregatePayload = await fetchBetflagAggregate('full');\n    let aggregateRows = filterBetflagRows(aggregatePayload.rows, url, { exactPlayer: true, exactMarket: true });\n    if (!requestedSelection && aggregateRows.length > 1) {\n      const yesRows = aggregateRows.filter((row) => normalized(row.selection) === 'si');\n      if (yesRows.length === 1) aggregateRows = yesRows;\n    }\n    attempts.push({\n      attempt: 'full_aggregate_fallback',\n      acquisition_mode: 'FULL_AGGREGATE_FALLBACK',\n      source_healthy: Boolean(aggregatePayload.source_healthy),\n      source_rows: aggregatePayload.row_count,\n      exact_rows: aggregateRows.length,\n      upstream_elapsed_ms: aggregatePayload.elapsed_ms\n    });\n    if (aggregatePayload.source_healthy && aggregateRows.length === 1) {\n      payload = aggregatePayload;\n      rows = aggregateRows;\n    }\n  }\n\n  const row = rows.length === 1 ? rows[0] : null;\n  const certificate = await certificateFor(row, payload, rows.length);"""

if anchor not in s:
    raise SystemExit('publicPlayerPrice retry anchor not found')

s = s.replace(anchor, replacement, 1)
p.write_text(s, encoding='utf-8')
print('Patched BetFlag exact full-aggregate direct fallback')
