import assert from 'node:assert/strict';
import { evaluateT30Readiness, T30_STATUS } from '../src/t30-readiness.mjs';

const now = '2026-08-29T18:00:00Z';
const base = {
  kickoff_at: '2026-08-29T18:40:00Z',
  xi: { status: 'OFFICIAL' },
  data_gate: { status: 'DATA_GATE_PASS' },
  modules: {
    match_model: { status: 'COMPLETED' },
    lineup_model: { status: 'COMPLETED' },
    goal_model: { status: 'COMPLETED' },
    player_model: { status: 'COMPLETED' },
    scorer_allocation: { status: 'COMPLETED' },
    market_model: { status: 'COMPLETED' },
    movement_model: { status: 'COMPLETED' },
    risk_model: { status: 'COMPLETED' },
    final_judge: { status: 'COMPLETED' }
  },
  standard_odds_series: [
    {
      market_key: '1X2_HOME',
      opening_quality: 'TRUE_OPEN_CERTIFIED',
      true_open_price: 2.1,
      current_price: 1.92,
      current_fetched_at: '2026-08-29T17:59:00Z',
      t40: { price: 1.96 },
      t30: { price: 1.92 }
    },
    {
      market_key: 'OU25_OVER',
      opening_quality: 'TRUE_OPEN_CERTIFIED',
      true_open_price: 1.98,
      current_price: 1.8,
      current_fetched_at: '2026-08-29T17:59:30Z',
      t40: { price: 1.84 },
      t30: { price: 1.8 }
    }
  ]
};

const req = { now, requiredStandardSeries: ['1X2_HOME', 'OU25_OVER'] };
let r = evaluateT30Readiness(base, req);
assert.equal(r.ready, true);
assert.equal(r.status, T30_STATUS.T30_READY);

const missingOpen = structuredClone(base);
missingOpen.standard_odds_series[1].opening_quality = 'OPEN_RADAR_PROXY';
r = evaluateT30Readiness(missingOpen, req);
assert.equal(r.ready, false);
assert.equal(r.status, T30_STATUS.CRITICAL_FINISH_WINDOW);
assert(r.missing.some((x) => x.code === 'TRUE_OPEN_NOT_CERTIFIED' && x.detail === 'OU25_OVER'));

const staleAtDeadline = structuredClone(base);
staleAtDeadline.kickoff_at = '2026-08-29T18:29:00Z';
staleAtDeadline.standard_odds_series[0].current_fetched_at = '2026-08-29T17:50:00Z';
r = evaluateT30Readiness(staleAtDeadline, req);
assert.equal(r.ready, false);
assert.equal(r.status, T30_STATUS.T30_DEADLINE_MISSED);
assert(r.next_actions.includes('REFRESH_CURRENT_PRICE:1X2_HOME'));

const incompleteModule = structuredClone(base);
incompleteModule.modules.player_model.status = 'FAILED';
r = evaluateT30Readiness(incompleteModule, req);
assert.equal(r.ready, false);
assert(r.next_actions.includes('RUN_MODULE:player_model'));

console.log('t30-readiness tests passed');
