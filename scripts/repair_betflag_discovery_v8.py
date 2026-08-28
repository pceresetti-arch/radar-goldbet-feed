from pathlib import Path

worker = Path('worker/src/index.mjs')
s = worker.read_text(encoding='utf-8')

replacements = [
    (
        "  const limit = clampInt(url.searchParams.get('limit'), 300, 1, 1000);\n  const filtered = [];",
        "  const limit = clampInt(url.searchParams.get('limit'), 300, 1, 1000);\n  const offset = clampInt(url.searchParams.get('offset'), 0, 0, 100000);\n  const filtered = [];",
    ),
    (
        "      const haystack = [row.match, row.match_code, row.league].map(normalized).join(' ');",
        "      const haystack = [row.match, row.match_code, row.league, row.player, row.requested_market, row.market, row.selection].map(normalized).join(' ');",
    ),
    (
        "    filtered.push(row);\n    if (filtered.length >= limit) break;\n  }\n  return filtered;\n}",
        "    filtered.push(row);\n  }\n  return filtered.slice(offset, offset + limit);\n}",
    ),
    (
        "  const mode = url.searchParams.get('full') === '1' ? 'full' : 'core';\n  const { payload, cache } = await getCachedBetflagAggregate(request, mode, ctx);\n  const rows = filterBetflagRows(payload.rows, url);\n  const freshness = sourceFreshness(payload.generated_at);",
        "  const mode = url.searchParams.get('full') === '0' ? 'core' : 'full';\n  const { payload, cache } = await getCachedBetflagAggregate(request, mode, ctx);\n  const rows = filterBetflagRows(payload.rows, url);\n  const limit = clampInt(url.searchParams.get('limit'), 300, 1, 1000);\n  const offset = clampInt(url.searchParams.get('offset'), 0, 0, 100000);\n  const freshness = sourceFreshness(payload.generated_at);",
    ),
    (
        "    returned: rows.length,\n    rows",
        "    returned: rows.length,\n    pagination: {\n      limit,\n      offset,\n      has_more: rows.length === limit,\n      next_offset: rows.length === limit ? offset + rows.length : null\n    },\n    rows",
    ),
]

for old, new in replacements:
    if old not in s:
        raise SystemExit('Worker patch pattern not found: ' + old[:180])
    s = s.replace(old, new, 1)
worker.write_text(s, encoding='utf-8')

print('BetFlag Worker discovery v8 patch applied')
