export const MODULE_STATUS = Object.freeze({
  PENDING: 'PENDING',
  RUNNING: 'RUNNING',
  COMPLETED: 'COMPLETED',
  RETRYING: 'RETRYING',
  FAILED: 'FAILED',
  SKIPPED_NONCRITICAL: 'SKIPPED_NONCRITICAL'
});

export const MODULE_CRITICALITY = Object.freeze({
  CRITICAL: 'CRITICAL',
  NONCRITICAL: 'NONCRITICAL'
});

export function evaluateModuleProgress(modules = []) {
  const criticalBlocked = [];
  const retryable = [];
  const completed = [];
  const noncriticalFailures = [];

  for (const module of modules) {
    if (!module?.key) continue;
    const status = module.status || MODULE_STATUS.PENDING;
    const criticality = module.criticality || MODULE_CRITICALITY.CRITICAL;

    if (status === MODULE_STATUS.COMPLETED) {
      completed.push(module.key);
      continue;
    }

    if ([MODULE_STATUS.PENDING, MODULE_STATUS.RUNNING, MODULE_STATUS.RETRYING].includes(status)) {
      retryable.push(module.key);
      if (criticality === MODULE_CRITICALITY.CRITICAL) criticalBlocked.push(module.key);
      continue;
    }

    if (status === MODULE_STATUS.FAILED) {
      if (criticality === MODULE_CRITICALITY.CRITICAL) criticalBlocked.push(module.key);
      else noncriticalFailures.push(module.key);
    }
  }

  return {
    final_analysis_allowed: criticalBlocked.length === 0,
    status: criticalBlocked.length === 0 ? 'READY_FOR_FINAL_ANALYSIS' : 'WAITING_FOR_CRITICAL_DATA',
    completed,
    critical_blocked: criticalBlocked,
    retryable,
    noncritical_failures: noncriticalFailures
  };
}

export function nextRetryState(module, now = new Date()) {
  const attempts = Number(module?.attempts || 0) + 1;
  const maxAttempts = Number(module?.max_attempts || 4);
  const baseDelaySeconds = Number(module?.base_delay_seconds || 5);

  if (attempts >= maxAttempts) {
    return {
      ...module,
      attempts,
      status: MODULE_STATUS.FAILED,
      next_retry_at: null
    };
  }

  const delaySeconds = Math.min(baseDelaySeconds * (2 ** (attempts - 1)), 60);
  return {
    ...module,
    attempts,
    status: MODULE_STATUS.RETRYING,
    next_retry_at: new Date(now.getTime() + delaySeconds * 1000).toISOString()
  };
}
