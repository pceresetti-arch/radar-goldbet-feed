import assert from 'node:assert/strict';
import {
  MODULE_STATUS,
  MODULE_CRITICALITY,
  evaluateModuleProgress,
  nextRetryState
} from '../src/module-state.mjs';

{
  const result = evaluateModuleProgress([
    { key: 'xi', criticality: MODULE_CRITICALITY.CRITICAL, status: MODULE_STATUS.COMPLETED },
    { key: 'player-props', criticality: MODULE_CRITICALITY.CRITICAL, status: MODULE_STATUS.RETRYING },
    { key: 'heatmap', criticality: MODULE_CRITICALITY.NONCRITICAL, status: MODULE_STATUS.FAILED }
  ]);
  assert.equal(result.final_analysis_allowed, false);
  assert.deepEqual(result.completed, ['xi']);
  assert.deepEqual(result.critical_blocked, ['player-props']);
  assert.deepEqual(result.noncritical_failures, ['heatmap']);
}

{
  const result = evaluateModuleProgress([
    { key: 'xi', criticality: MODULE_CRITICALITY.CRITICAL, status: MODULE_STATUS.COMPLETED },
    { key: 'player-props', criticality: MODULE_CRITICALITY.CRITICAL, status: MODULE_STATUS.COMPLETED },
    { key: 'heatmap', criticality: MODULE_CRITICALITY.NONCRITICAL, status: MODULE_STATUS.FAILED }
  ]);
  assert.equal(result.final_analysis_allowed, true);
  assert.equal(result.status, 'READY_FOR_FINAL_ANALYSIS');
}

{
  const retry = nextRetryState({ key: 'quotes', attempts: 1, max_attempts: 4, base_delay_seconds: 5 }, new Date('2026-08-28T20:00:00Z'));
  assert.equal(retry.status, MODULE_STATUS.RETRYING);
  assert.equal(retry.attempts, 2);
  assert.equal(retry.next_retry_at, '2026-08-28T20:00:10.000Z');
}

{
  const failed = nextRetryState({ key: 'quotes', attempts: 3, max_attempts: 4, base_delay_seconds: 5 });
  assert.equal(failed.status, MODULE_STATUS.FAILED);
  assert.equal(failed.next_retry_at, null);
}

console.log('module-state tests passed');
