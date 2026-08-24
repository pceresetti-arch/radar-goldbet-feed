const fs = require('fs');

const apiKey = process.env.ODDSPAPI_KEY || process.env.ODDS_API_KEY || '';
const base = process.env.ODDSPAPI_BASE || 'https://api.oddspapi.io/v4';
const bookmaker = process.env.BOOKMAKER || 'goldbet';
const state = process.env.STATE || 'prematch';
const limit = Number(process.env.LIMIT || 2000);
const matchTerms = (process.env.MATCH_TERMS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
const leagueTerms = (process.env.LEAGUE_TERMS || '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
const maxPages = Number(process.env.MAX_PAGES || 20);

if (!apiKey) {
  console.error('Missing ODDSPAPI_KEY/ODDS_API_KEY');
  process.exit(2);
}

function flattenText(obj) {
  try { return JSON.stringify(obj).toLowerCase(); } catch { return ''; }
}

function matches(rec) {
  const text = flattenText(rec);
  const mt = matchTerms.length === 0 || matchTerms.every(t => text.includes(t));
  const lt = leagueTerms.length === 0 || leagueTerms.every(t => text.includes(t));
  return mt && lt;
}

async function getJson(url) {
  const r = await fetch(url, { headers: { 'x-api-key': apiKey, authorization: `Bearer ${apiKey}` } });
  const text = await r.text();
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${text.slice(0,500)}`);
  return JSON.parse(text);
}

(async () => {
  const out = [];
  let totalSeen = 0;
  let count = null;
  for (let page = 0; page < maxPages; page++) {
    const offset = page * limit;
    const u = new URL(`${base.replace(/\/$/, '')}/odds`);
    u.searchParams.set('bookmakers', bookmaker);
    u.searchParams.set('state', state);
    u.searchParams.set('limit', String(limit));
    u.searchParams.set('offset', String(offset));

    const data = await getJson(u.toString());
    count = Number(data.count ?? data.total ?? count ?? 0);
    const records = Array.isArray(data) ? data : (data.odds || data.results || data.data || []);
    totalSeen += records.length;
    for (const rec of records) if (matches(rec)) out.push(rec);

    console.log(`page=${page} offset=${offset} records=${records.length} matches=${out.length} total=${count ?? '?'}`);
    if (out.length && matchTerms.length) break;
    if (records.length < limit) break;
    if (count && offset + records.length >= count) break;
  }

  const result = {
    generated_at: new Date().toISOString(),
    provider: 'oddspapi',
    bookmaker,
    state,
    match_terms: matchTerms,
    league_terms: leagueTerms,
    source_records_scanned: totalSeen,
    source_count: count,
    filtered_records: out.length,
    odds: out
  };
  fs.mkdirSync('feed', { recursive: true });
  fs.writeFileSync('feed/latest.json', JSON.stringify(result, null, 2));
  fs.writeFileSync('feed/latest.meta.json', JSON.stringify({
    generated_at: result.generated_at,
    paginated: true,
    bookmaker,
    state,
    limit,
    max_pages: maxPages,
    match_terms: matchTerms,
    league_terms: leagueTerms
  }, null, 2));
})();
