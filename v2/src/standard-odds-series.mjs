export const OPEN_STATUS = Object.freeze({
  TRUE_OPEN_CERTIFIED: 'TRUE_OPEN_CERTIFIED',
  OPEN_CAPTURED_NEAR_PUBLICATION: 'OPEN_CAPTURED_NEAR_PUBLICATION',
  FIRST_SEEN_ONLY: 'FIRST_SEEN_ONLY',
  OPEN_UNKNOWN: 'OPEN_UNKNOWN'
});

export function validateSnapshot(snapshot, { maxAgeSeconds = 180 } = {}) {
  if (!snapshot) return { ok: false, reason: 'MISSING_SNAPSHOT' };
  if (!snapshot.bookmaker || !snapshot.market_key) return { ok: false, reason: 'MISSING_IDENTITY' };
  if (!Number.isFinite(Number(snapshot.price)) || Number(snapshot.price) <= 1) return { ok: false, reason: 'INVALID_PRICE' };
  if (!snapshot.fetched_at) return { ok: false, reason: 'MISSING_FETCH_TIME' };
  const age = (Date.now() - Date.parse(snapshot.fetched_at)) / 1000;
  if (!Number.isFinite(age)) return { ok: false, reason: 'INVALID_FETCH_TIME' };
  if (age > maxAgeSeconds) return { ok: false, reason: 'STALE_CURRENT' };
  return { ok: true, age_seconds: Math.max(0, Math.round(age)) };
}

export function buildMovementSeries({ opening, current, checkpoints = [] } = {}) {
  if (!opening || opening.status !== OPEN_STATUS.TRUE_OPEN_CERTIFIED) {
    return { ok: false, status: 'MOVEMENT_INCOMPLETE', reason: 'TRUE_OPEN_NOT_CERTIFIED' };
  }
  if (!current) return { ok: false, status: 'MOVEMENT_INCOMPLETE', reason: 'CURRENT_MISSING' };
  if (opening.bookmaker !== current.bookmaker || opening.market_key !== current.market_key) {
    return { ok: false, status: 'MOVEMENT_INCOMPLETE', reason: 'SAME_BOOK_SAME_MARKET_VIOLATION' };
  }
  const currentValidation = validateSnapshot(current);
  if (!currentValidation.ok) {
    return { ok: false, status: 'MOVEMENT_INCOMPLETE', reason: currentValidation.reason };
  }
  const validCheckpoints = checkpoints
    .filter((cp) => cp && cp.bookmaker === opening.bookmaker && cp.market_key === opening.market_key)
    .sort((a, b) => Date.parse(a.fetched_at) - Date.parse(b.fetched_at));
  const openPrice = Number(opening.price);
  const currentPrice = Number(current.price);
  return {
    ok: true,
    status: 'MOVEMENT_CERTIFIED',
    bookmaker: opening.bookmaker,
    market_key: opening.market_key,
    true_open: openPrice,
    current: currentPrice,
    absolute_change: Number((currentPrice - openPrice).toFixed(3)),
    implied_probability_change_pp: Number(((1 / currentPrice - 1 / openPrice) * 100).toFixed(3)),
    checkpoints: validCheckpoints,
    current_age_seconds: currentValidation.age_seconds
  };
}

export function chooseOperationalCurrent({ betflag, goldbet } = {}) {
  const bf = validateSnapshot(betflag || null);
  if (bf.ok) return { source: 'BETFLAG_AAMS_DIRECT', snapshot: betflag, validation: bf };
  const gb = validateSnapshot(goldbet || null);
  if (gb.ok) return { source: 'GOLDBET_DIRECT_FALLBACK', snapshot: goldbet, validation: gb };
  return {
    source: null,
    snapshot: null,
    validation: {
      ok: false,
      reason: `NO_FRESH_STANDARD_PRICE:BETFLAG=${bf.reason};GOLDBET=${gb.reason}`
    }
  };
}
