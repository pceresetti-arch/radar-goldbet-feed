import assert from 'node:assert/strict';
import { evaluateDataGate, MARKET_STATUS } from '../src/data-gate.mjs';

const required = ['ANYTIME', 'SCORER_1H', 'SHOTS'];

const recovered = {
  market_key: 'ANYTIME',
  status: MARKET_STATUS.QUOTED_RECOVERED,
  price: 2.8,
  source: 'BETFLAG_AAMS_DIRECT',
  fetched_at: '2026-08-28T19:00:00Z',
  attempts: [{ source: 'BETFLAG_AAMS_DIRECT', result: 'FOUND' }]
};

const notQuoted = {
  market_key: 'SCORER_1H',
  status: MARKET_STATUS.NOT_QUOTED_CONFIRMED,
  event_structure_checked: true,
  attempts: [
    { source: 'PRIMARY_EVENT_MARKET_TREE', result: 'MARKET_ABSENT' },
    { source: 'SECONDARY_EVENT_ENDPOINT', result: 'MARKET_ABSENT' }
  ]
};

const failed = {
  market_key: 'SHOTS',
  status: MARKET_STATUS.ACQUISITION_FAILED,
  attempts: [
    { source: 'BETFLAG_AAMS_DIRECT', result: 'HTTP_429' },
    { source: 'BETFLAG_AAMS_DIRECT_RETRY', result: 'TIMEOUT' }
  ]
};

const blocked = evaluateDataGate(required, [recovered, notQuoted, failed]);
assert.equal(blocked.pass, false);
assert.equal(blocked.status, 'DATA_GATE_BLOCKED');
assert.deepEqual(blocked.confirmed_not_quoted, ['SCORER_1H']);
assert.deepEqual(blocked.blocked, [{ market_key: 'SHOTS', status: 'ACQUISITION_FAILED' }]);

const shotsRecovered = {
  market_key: 'SHOTS',
  status: MARKET_STATUS.QUOTED_RECOVERED,
  price: 1.95,
  source: 'BETFLAG_AAMS_DIRECT',
  fetched_at: '2026-08-28T19:00:02Z',
  attempts: [{ source: 'BETFLAG_AAMS_DIRECT', result: 'FOUND' }]
};

const passed = evaluateDataGate(required, [recovered, notQuoted, shotsRecovered]);
assert.equal(passed.pass, true);
assert.equal(passed.status, 'DATA_GATE_PASS');

console.log('data-gate tests passed');
