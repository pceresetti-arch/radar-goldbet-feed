export const QUOTE_SOURCE_ROLE = Object.freeze({
  PRIMARY: 'PRIMARY_OPERATIONAL',
  CROSSCHECK: 'CROSSCHECK_NON_BLOCKING',
  FALLBACK: 'FALLBACK_OPERATIONAL'
});

const SOURCE_PRIORITY = [
  { match: /betflag|aams|adm/i, role: QUOTE_SOURCE_ROLE.PRIMARY, priority: 1 },
  { match: /goldbet/i, role: QUOTE_SOURCE_ROLE.CROSSCHECK, priority: 2 }
];

export function classifyQuoteSource(source = '') {
  for (const rule of SOURCE_PRIORITY) {
    if (rule.match.test(String(source))) return { role: rule.role, priority: rule.priority };
  }
  return { role: QUOTE_SOURCE_ROLE.FALLBACK, priority: 99 };
}

function validPrice(row) {
  return row && Number.isFinite(Number(row.price)) && Number(row.price) > 1 && row.fetched_at;
}

export function chooseOperationalQuote(quotes = []) {
  const valid = quotes
    .filter(validPrice)
    .map((quote) => ({ ...quote, ...classifyQuoteSource(quote.source || quote.bookmaker || '') }))
    .sort((a, b) => a.priority - b.priority);

  const primary = valid.find((quote) => quote.role === QUOTE_SOURCE_ROLE.PRIMARY);
  if (primary) {
    return {
      ok: true,
      operational_quote: primary,
      blocked_by_goldbet: false,
      crosschecks: valid.filter((quote) => quote.role === QUOTE_SOURCE_ROLE.CROSSCHECK)
    };
  }

  const fallback = valid.find((quote) => quote.role === QUOTE_SOURCE_ROLE.FALLBACK);
  if (fallback) {
    return {
      ok: true,
      operational_quote: fallback,
      blocked_by_goldbet: false,
      crosschecks: valid.filter((quote) => quote.role === QUOTE_SOURCE_ROLE.CROSSCHECK),
      warning: 'PRIMARY_BETFLAG_AAMS_UNAVAILABLE_USING_EXPLICIT_FALLBACK'
    };
  }

  return {
    ok: false,
    operational_quote: null,
    blocked_by_goldbet: false,
    crosschecks: valid.filter((quote) => quote.role === QUOTE_SOURCE_ROLE.CROSSCHECK),
    reason: 'NO_OPERATIONAL_QUOTE_RECOVERED'
  };
}

export function compareGoldBet(primaryQuote, crosschecks = [], materialDelta = 0.08) {
  if (!primaryQuote || !Number.isFinite(Number(primaryQuote.price))) return [];
  return crosschecks.map((quote) => {
    const delta = Number(quote.price) - Number(primaryQuote.price);
    return {
      source: quote.source || quote.bookmaker || 'GoldBet',
      price: Number(quote.price),
      delta,
      material: Math.abs(delta) >= materialDelta
    };
  });
}
