import assert from 'node:assert/strict';
import {
  createQuoteTimeline,
  setTrueOpen,
  appendQuoteSnapshot,
  evaluateQuoteMovement
} from '../src/quote-timeline.mjs';

const timeline = createQuoteTimeline({
  bookmaker: 'betflag',
  fixture_id: 'fx-1',
  market: 'OVER_UNDER',
  period: 'FT',
  line: 2.5,
  selection: 'OVER'
});

setTrueOpen(timeline, {
  bookmaker: 'betflag', fixture_id: 'fx-1', market: 'OVER_UNDER', period: 'FT', line: 2.5, selection: 'OVER',
  price: 1.98, captured_at: '2026-08-29T10:00:00Z', source: 'BETFLAG_AAMS_DIRECT', certification: 'TRUE_OPEN_CERTIFIED'
});

setTrueOpen(timeline, {
  bookmaker: 'betflag', fixture_id: 'fx-1', market: 'OVER_UNDER', period: 'FT', line: 2.5, selection: 'OVER',
  price: 2.10, captured_at: '2026-08-29T10:05:00Z', source: 'BETFLAG_AAMS_DIRECT', certification: 'TRUE_OPEN_CERTIFIED'
});
assert.equal(timeline.true_open.price, 1.98, 'true open must be immutable');

appendQuoteSnapshot(timeline, {
  bookmaker: 'betflag', fixture_id: 'fx-1', market: 'OVER_UNDER', period: 'FT', line: 2.5, selection: 'OVER',
  price: 1.84, captured_at: '2026-08-29T17:20:00Z', source: 'BETFLAG_AAMS_DIRECT', minutes_to_kickoff: 40
});
appendQuoteSnapshot(timeline, {
  bookmaker: 'betflag', fixture_id: 'fx-1', market: 'OVER_UNDER', period: 'FT', line: 2.5, selection: 'OVER',
  price: 1.76, captured_at: '2026-08-29T17:59:20Z', source: 'BETFLAG_AAMS_DIRECT', minutes_to_kickoff: 0.67
});

const movement = evaluateQuoteMovement(timeline, '2026-08-29T18:00:00Z', 120);
assert.equal(movement.status, 'MOVEMENT_READY');
assert.equal(movement.current_fresh, true);
assert.equal(movement.T40.price, 1.84);
assert.equal(movement.price_delta, -0.22);

const stale = evaluateQuoteMovement(timeline, '2026-08-29T18:05:00Z', 120);
assert.equal(stale.status, 'CURRENT_STALE');

assert.throws(() => appendQuoteSnapshot(timeline, {
  bookmaker: 'goldbet', fixture_id: 'fx-1', market: 'OVER_UNDER', period: 'FT', line: 2.5, selection: 'OVER',
  price: 1.75, captured_at: '2026-08-29T18:00:10Z', source: 'GOLDBET_DIRECT_STANDARD'
}), /QUOTE_IDENTITY_MISMATCH/);

console.log('quote-timeline tests passed');
