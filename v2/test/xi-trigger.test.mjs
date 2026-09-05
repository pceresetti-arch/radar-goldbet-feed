import assert from 'node:assert/strict';
import { evaluateXiTrigger, XI_TRIGGER_STATUS } from '../src/xi-trigger.mjs';

let r = evaluateXiTrigger({ xi: { status: 'MISSING' } });
assert.equal(r.status, XI_TRIGGER_STATUS.WAITING_FOR_XI);
assert.equal(r.should_run_post_xi_analysis, false);
assert(r.next_actions.includes('POLL_XI_SOURCES'));

r = evaluateXiTrigger({ xi: { status: 'OFFICIAL', fingerprint: 'xi-a' } });
assert.equal(r.status, XI_TRIGGER_STATUS.XI_NEW_TRIGGER);
assert.equal(r.should_run_post_xi_analysis, true);
assert.equal(r.invalidate_lineup_sensitive_outputs, false);

r = evaluateXiTrigger({
  xi: { status: 'OFFICIAL', fingerprint: 'xi-a' },
  analysis_xi_fingerprint: 'xi-a'
});
assert.equal(r.status, XI_TRIGGER_STATUS.XI_UNCHANGED);
assert.equal(r.should_run_post_xi_analysis, false);

r = evaluateXiTrigger({
  xi: { status: 'OFFICIAL', fingerprint: 'xi-b' },
  analysis_xi_fingerprint: 'xi-a'
});
assert.equal(r.status, XI_TRIGGER_STATUS.XI_CHANGED_RETRIGGER);
assert.equal(r.should_run_post_xi_analysis, true);
assert.equal(r.invalidate_lineup_sensitive_outputs, true);
assert(r.next_actions.includes('INVALIDATE_LINEUP_SENSITIVE_OUTPUTS'));

console.log('xi-trigger tests passed');
