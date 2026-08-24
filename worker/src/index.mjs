const UPSTREAM_BASE = 'https://odss-api.com/api/v1';

const ALLOWED_PARAMS = {
  sports: [],
  bookmakers: [],
  leagues: ['sport'],
  odds: [
    'sport', 'market', 'league', 'bookmakers', 'event_id', 'state',
    'limit', 'offset', 'content', 'player', 'q'
  ],
  history: ['event_id', 'book', 'market', 'from', 'to', 'limit']
};

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type',
  'Access-Control-Max-Age': '86400'
};

function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...CORS_HEADERS,
      ...extraHeaders
    }
  });
}

async function secureEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || !a || !b) return false;
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([
    crypto.subtle.digest('SHA-256', enc.encode(a)),
    crypto.subtle.digest('SHA-256', enc.encode(b))
  ]);
  const aa = new Uint8Array(ha);
  const bb = new Uint8Array(hb);
  let diff = 0;
  for (let i = 0; i < aa.length; i += 1) diff |= aa[i] ^ bb[i];
  return diff === 0;
}

async function isAuthorized(request, env, url) {
  const expected = env.BRIDGE_TOKEN;
  if (!expected) return false;

  const queryToken = url.searchParams.get('token') || '';
  if (await secureEqual(queryToken, expected)) return true;

  const auth = request.headers.get('Authorization') || '';
  const bearer = auth.replace(/^Bearer\s+/i, '');
  return secureEqual(bearer, expected);
}

function buildUpstreamUrl(endpoint, incomingUrl) {
  const upstream = new URL(`${UPSTREAM_BASE}/${endpoint}`);
  const allowed = ALLOWED_PARAMS[endpoint] || [];

  for (const key of allowed) {
    for (const value of incomingUrl.searchParams.getAll(key)) {
      if (value !== '') upstream.searchParams.append(key, value);
    }
  }

  return upstream;
}

async function proxyEndpoint(endpoint, request, env, incomingUrl) {
  if (!env.ODSS_API_KEY) {
    return json({ error: 'Worker misconfigured: missing ODSS_API_KEY' }, 500);
  }

  const upstreamUrl = buildUpstreamUrl(endpoint, incomingUrl);
  const response = await fetch(upstreamUrl, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      'x-api-key': env.ODSS_API_KEY,
      'User-Agent': 'RadarGoldBetBridge/5.0'
    }
  });

  const headers = new Headers(response.headers);
  headers.set('Access-Control-Allow-Origin', '*');
  headers.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
  headers.set('Access-Control-Allow-Headers', 'Authorization, Content-Type');
  headers.set('Cache-Control', 'no-store');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (request.method !== 'GET') {
      return json({ error: 'Method not allowed' }, 405, { Allow: 'GET, OPTIONS' });
    }

    const url = new URL(request.url);
    const endpoint = url.pathname.replace(/^\/+|\/+$/g, '') || 'health';

    if (endpoint === 'health') {
      return json({
        ok: true,
        service: 'radar-goldbet',
        version: '5.0-player-props',
        player_props_forwarding: true,
        endpoints: ['/health', '/sports', '/bookmakers', '/leagues', '/odds', '/history'],
        odds_params: ALLOWED_PARAMS.odds
      });
    }

    if (!(endpoint in ALLOWED_PARAMS)) {
      return json({
        error: 'Endpoint non valido',
        endpoints: ['/health', '/sports', '/bookmakers', '/leagues', '/odds', '/history']
      }, 404);
    }

    if (!(await isAuthorized(request, env, url))) {
      return json({ error: 'Unauthorized' }, 401);
    }

    try {
      return await proxyEndpoint(endpoint, request, env, url);
    } catch (error) {
      console.error(JSON.stringify({
        event: 'upstream_error',
        endpoint,
        message: error instanceof Error ? error.message : String(error)
      }));
      return json({ error: 'Upstream request failed' }, 502);
    }
  }
};
