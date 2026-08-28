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

bridge = Path('.github/workflows/radar-betflag-v7-live-bridge.yml')
b = bridge.read_text(encoding='utf-8')
old = """              for params in queries:
                  params={k:v for k,v in (params or {}).items() if v is not None and str(v)!=''}
                  params.setdefault('limit', req.get('limit', 500))
                  url=BASE+'/live/player-props?'+urllib.parse.urlencode(params, doseq=True)
                  calls.append(get_json(url))
"""
new = """              for params in queries:
                  params={k:v for k,v in (params or {}).items() if v is not None and str(v)!=''}
                  params.setdefault('full', '1')
                  try: page_limit=int(params.get('limit', req.get('limit', 500)))
                  except Exception: page_limit=500
                  page_limit=max(1,min(1000,page_limit))
                  params['limit']=page_limit
                  try: offset=max(0,int(params.get('offset',0)))
                  except Exception: offset=0
                  pages=0
                  while True:
                      page=dict(params); page['offset']=offset
                      url=BASE+'/live/player-props?'+urllib.parse.urlencode(page, doseq=True)
                      call=get_json(url); calls.append(call); pages+=1
                      body=call.get('body') if isinstance(call.get('body'),dict) else {}
                      returned=int(body.get('returned') or 0)
                      pagination=body.get('pagination') if isinstance(body.get('pagination'),dict) else {}
                      next_offset=pagination.get('next_offset')
                      if call.get('http_status')!=200 or returned < page_limit or next_offset is None:
                          break
                      if pages>=12:
                          raise SystemExit('discovery pagination safety limit reached (12 pages)')
                      offset=int(next_offset)
"""
if old not in b:
    raise SystemExit('Bridge patch pattern not found')
b = b.replace(old, new, 1)
bridge.write_text(b, encoding='utf-8')

print('BetFlag discovery v8 patch applied')
