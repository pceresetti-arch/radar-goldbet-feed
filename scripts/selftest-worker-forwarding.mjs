import worker from '../worker/src/index.mjs';

const originalFetch = globalThis.fetch;
const calls = [];

globalThis.fetch = async (url, init = {}) => {
  calls.push({ url: String(url), init });
  return new Response(JSON.stringify({ ok: true, odds: [] }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
};

try {
  const env = {
    BRIDGE_TOKEN: 'bridge-test-secret',
    ODSS_API_KEY: 'upstream-test-secret'
  };

  const request = new Request(
    'https://radar-goldbet.p-ceresetti.workers.dev/odds' +
    '?token=bridge-test-secret' +
    '&bookmakers=goldbet' +
    '&state=prematch' +
    '&content=player' +
    '&player=Aubameyang' +
    '&event_id=test-event-123' +
    '&market=scorer' +
    '&limit=2000' +
    '&junk=must-not-forward'
  );

  const response = await worker.fetch(request, env);
  if (response.status !== 200) throw new Error(`unexpected status ${response.status}`);
  if (calls.length !== 1) throw new Error(`expected 1 upstream call, got ${calls.length}`);

  const upstream = new URL(calls[0].url);
  const expected = {
    bookmakers: 'goldbet',
    state: 'prematch',
    content: 'player',
    player: 'Aubameyang',
    event_id: 'test-event-123',
    market: 'scorer',
    limit: '2000'
  };

  for (const [key, value] of Object.entries(expected)) {
    if (upstream.searchParams.get(key) !== value) {
      throw new Error(`${key} not forwarded correctly: ${upstream.searchParams.get(key)}`);
    }
  }

  if (upstream.searchParams.has('token')) throw new Error('bridge token leaked upstream');
  if (upstream.searchParams.has('junk')) throw new Error('unknown parameter leaked upstream');

  const headers = new Headers(calls[0].init.headers || {});
  if (headers.get('x-api-key') !== env.ODSS_API_KEY) throw new Error('ODSS API key header missing');

  const health = await worker.fetch(new Request('https://radar-goldbet.p-ceresetti.workers.dev/health'), env);
  const healthJson = await health.json();
  for (const key of ['content', 'player', 'q']) {
    if (!healthJson.odds_params.includes(key)) throw new Error(`health contract missing ${key}`);
  }

  console.log(JSON.stringify({
    ok: true,
    forwarded_url: upstream.pathname + upstream.search,
    token_forwarded: upstream.searchParams.has('token'),
    unknown_forwarded: upstream.searchParams.has('junk'),
    health_version: healthJson.version,
    player_props_forwarding: healthJson.player_props_forwarding
  }, null, 2));
} finally {
  globalThis.fetch = originalFetch;
}
