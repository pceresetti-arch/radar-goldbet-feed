import assert from 'node:assert/strict';
import { OPEN_STATUS, buildMovementSeries, chooseOperationalCurrent } from '../src/standard-odds-series.mjs';

const now = new Date().toISOString();
const marketKey = 'match:123|ft|1x2|home';

const betflag = { bookmaker: 'betflag', market_key: marketKey, price: 2.15, fetched_at: now };
const goldbet = { bookmaker: 'goldbet', market_key: marketKey, price: 2.14, fetched_at: now };
const picked = chooseOperationalCurrent({ betflag, goldbet });
assert.equal(picked.source, 'BETFLAG_AAMS_DIRECT');
assert.equal(picked.snapshot.price, 2.15);

const opening = {
  status: OPEN_STATUS.TRUE_OPEN_CERTIFIED,
  bookmaker: 'betflag',
  market_key: marketKey,
  price: 2.35,
  fetched_at: now
};
const movement = buildMovementSeries({ opening, current: betflag });
assert.equal(movement.status, 'MOVEMENT_CERTIFIED');
assert.equal(movement.true_open, 2.35);
assert.equal(movement.current, 2.15);

const invalidMixedBook = buildMovementSeries({ opening, current: goldbet });
assert.equal(invalidMixedBook.status, 'MOVEMENT_INCOMPLETE');
assert.equal(invalidMixedBook.reason, 'SAME_BOOK_SAME_MARKET_VIOLATION');

const stale = { ...betflag, fetched_at: '2026-08-28T00:00:00.000Z' };
const stalePick = chooseOperationalCurrent({ betflag: stale, goldbet });
assert.equal(stalePick.source, 'GOLDBET_DIRECT_FALLBACK');

console.log('standard-odds-series tests passed');
