export const MARKET_STATUS = Object.freeze({
  QUOTED_RECOVERED: 'QUOTED_RECOVERED',
  NOT_QUOTED_CONFIRMED: 'NOT_QUOTED_CONFIRMED',
  ACQUISITION_FAILED: 'ACQUISITION_FAILED',
  UNCERTAIN: 'UNCERTAIN'
});

const TERMINAL_OK = new Set([
  MARKET_STATUS.QUOTED_RECOVERED,
  MARKET_STATUS.NOT_QUOTED_CONFIRMED
]);

export function validateMarketEvidence(market) {
  if (!market || !market.market_key) {
    return { ok: false, reason: 'MISSING_MARKET_KEY' };
  }
  if (!Object.values(MARKET_STATUS).includes(market.status)) {
    return { ok: false, reason: 'INVALID_MARKET_STATUS' };
  }

  const attempts = Array.isArray(market.attempts) ? market.attempts : [];

  if (market.status === MARKET_STATUS.QUOTED_RECOVERED) {
    if (!Number.isFinite(Number(market.price)) || Number(market.price) <= 1) {
      return { ok: false, reason: 'QUOTED_WITHOUT_VALID_PRICE' };
    }
    if (!market.source || !market.fetched_at) {
      return { ok: false, reason: 'QUOTED_WITHOUT_SOURCE_PROOF' };
    }
  }

  if (market.status === MARKET_STATUS.NOT_QUOTED_CONFIRMED) {
    const positiveAbsenceChecks = attempts.filter((a) =>
      a && a.result === 'MARKET_ABSENT' && a.source
    );
    if (positiveAbsenceChecks.length < 2) {
      return { ok: false, reason: 'NON_QUOTED_NOT_SUFFICIENTLY_PROVEN' };
    }
    if (!market.event_structure_checked) {
      return { ok: false, reason: 'EVENT_STRUCTURE_NOT_CHECKED' };
    }
  }

  return { ok: true, reason: null };
}

export function evaluateDataGate(requiredMarketKeys, marketStates) {
  const byKey = new Map((marketStates || []).map((m) => [m.market_key, m]));
  const missing = [];
  const blocked = [];
  const invalid = [];
  const available = [];
  const confirmedNotQuoted = [];

  for (const marketKey of requiredMarketKeys || []) {
    const market = byKey.get(marketKey);
    if (!market) {
      missing.push(marketKey);
      continue;
    }

    const validation = validateMarketEvidence(market);
    if (!validation.ok) {
      invalid.push({ market_key: marketKey, reason: validation.reason });
      continue;
    }

    if (!TERMINAL_OK.has(market.status)) {
      blocked.push({ market_key: marketKey, status: market.status });
      continue;
    }

    if (market.status === MARKET_STATUS.QUOTED_RECOVERED) available.push(marketKey);
    if (market.status === MARKET_STATUS.NOT_QUOTED_CONFIRMED) confirmedNotQuoted.push(marketKey);
  }

  const pass = missing.length === 0 && blocked.length === 0 && invalid.length === 0;

  return {
    pass,
    status: pass ? 'DATA_GATE_PASS' : 'DATA_GATE_BLOCKED',
    available,
    confirmed_not_quoted: confirmedNotQuoted,
    missing,
    blocked,
    invalid
  };
}
