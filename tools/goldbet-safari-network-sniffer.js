// One-time Safari Shortcuts diagnostic for GoldBet player-prop API discovery.
// It only reports resource origins/paths and query PARAMETER NAMES.
// It deliberately strips query values, fragments, cookies and page storage.

const entries = performance.getEntriesByType('resource') || [];
const interesting = /(api|sport|bet|odd|quota|quote|market|event|match|player|scorer|marc|manifest|prematch|palins|scommess|signalr|socket|feed|price)/i;

function safeUrl(raw) {
  try {
    const u = new URL(raw, location.href);
    const keys = [...new Set([...u.searchParams.keys()])].sort();
    return {
      host: u.host,
      path: u.pathname,
      queryKeys: keys,
      origin: u.origin
    };
  } catch (_) {
    return null;
  }
}

const rows = [];
const seen = new Set();

for (const e of entries) {
  const type = String(e.initiatorType || 'resource');
  const s = safeUrl(e.name);
  if (!s) continue;

  const probe = `${s.host}${s.path}`;
  const relevantType = /fetch|xmlhttprequest|script|other/i.test(type);
  if (!relevantType && !interesting.test(probe)) continue;
  if (!interesting.test(probe) && !/fetch|xmlhttprequest/i.test(type)) continue;

  const key = `${type}|${s.host}|${s.path}|${s.queryKeys.join(',')}`;
  if (seen.has(key)) continue;
  seen.add(key);

  rows.push({
    type,
    host: s.host,
    path: s.path,
    queryKeys: s.queryKeys
  });
}

rows.sort((a,b) => {
  const ax = /fetch|xmlhttprequest/i.test(a.type) ? 0 : 1;
  const bx = /fetch|xmlhttprequest/i.test(b.type) ? 0 : 1;
  return ax - bx || a.host.localeCompare(b.host) || a.path.localeCompare(b.path);
});

const output = {
  pageHost: location.host,
  pagePath: location.pathname,
  found: rows.length,
  resources: rows.slice(0, 120)
};

completion(JSON.stringify(output, null, 2));
