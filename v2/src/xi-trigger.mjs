export const XI_TRIGGER_STATUS = Object.freeze({
  WAITING_FOR_XI: 'WAITING_FOR_XI',
  XI_NEW_TRIGGER: 'XI_NEW_TRIGGER',
  XI_UNCHANGED: 'XI_UNCHANGED',
  XI_CHANGED_RETRIGGER: 'XI_CHANGED_RETRIGGER'
});

export function evaluateXiTrigger(state = {}) {
  const xi = state.xi || {};
  const currentFingerprint = xi.status === 'OFFICIAL' ? xi.fingerprint : null;
  const analyzedFingerprint = state.analysis_xi_fingerprint || null;

  if (!currentFingerprint) {
    return {
      status: XI_TRIGGER_STATUS.WAITING_FOR_XI,
      should_run_post_xi_analysis: false,
      invalidate_lineup_sensitive_outputs: false,
      next_actions: ['POLL_XI_SOURCES']
    };
  }

  if (!analyzedFingerprint) {
    return {
      status: XI_TRIGGER_STATUS.XI_NEW_TRIGGER,
      should_run_post_xi_analysis: true,
      invalidate_lineup_sensitive_outputs: false,
      xi_fingerprint: currentFingerprint,
      next_actions: ['RUN_POST_XI_ANALYSIS']
    };
  }

  if (analyzedFingerprint !== currentFingerprint) {
    return {
      status: XI_TRIGGER_STATUS.XI_CHANGED_RETRIGGER,
      should_run_post_xi_analysis: true,
      invalidate_lineup_sensitive_outputs: true,
      xi_fingerprint: currentFingerprint,
      previous_analysis_xi_fingerprint: analyzedFingerprint,
      next_actions: ['INVALIDATE_LINEUP_SENSITIVE_OUTPUTS', 'RUN_POST_XI_ANALYSIS']
    };
  }

  return {
    status: XI_TRIGGER_STATUS.XI_UNCHANGED,
    should_run_post_xi_analysis: false,
    invalidate_lineup_sensitive_outputs: false,
    xi_fingerprint: currentFingerprint,
    next_actions: []
  };
}
