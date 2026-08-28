const COMPLETE = 'COMPLETED';

export const T30_STATUS = Object.freeze({
  PREPARING: 'PREPARING',
  XI_TRIGGERED_ANALYSIS: 'XI_TRIGGERED_ANALYSIS',
  AWAITING_FINAL_PRICE_CHECK: 'AWAITING_FINAL_PRICE_CHECK',
  FINAL_PRICE_WINDOW: 'FINAL_PRICE_WINDOW',
  T30_READY: 'T30_READY',
  T30_DEADLINE_MISSED: 'T30_DEADLINE_MISSED'
});

function finiteDate(value) {
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

function minutesToKickoff(kickoffAt, now) {
  const kickoffMs = finiteDate(kickoffAt);
  const nowMs = finiteDate(now);
  if (kickoffMs === null || nowMs === null) return null;
  return (kickoffMs - nowMs) / 60000;
}

function freshEnough(timestamp, now, maxAgeSeconds) {
  const t = finiteDate(timestamp);
  const n = finiteDate(now);
  if (t === null || n === null) return false;
  const age = (n - t) / 1000;
  return age >= 0 && age <= maxAgeSeconds;
}

function pushMissing(list, code, detail = null) {
  list.push(detail ? { code, detail } : { code });
}

/**
 * XI publication is the main analysis trigger.
 * T-30 is only the final price refresh/certification deadline.
 * T-40 is optional historical telemetry and never blocks readiness.
 */
export function evaluateT30Readiness(state, options = {}) {
  const now = options.now || new Date().toISOString();
  const currentQuoteMaxAgeSeconds = options.currentQuoteMaxAgeSeconds ?? 180;
  const finalPriceWindowMinutes = options.finalPriceWindowMinutes ?? 35;
  const requiredAnalysisModules = options.requiredAnalysisModules || [
    'match_model',
    'lineup_model',
    'goal_model',
    'player_model',
    'scorer_allocation',
    'market_model',
    'movement_model',
    'risk_model',
    'final_judge'
  ];
  const requiredStandardSeries = options.requiredStandardSeries || [];

  const missing = [];
  const minutes = minutesToKickoff(state?.kickoff_at, now);
  if (minutes === null) pushMissing(missing, 'INVALID_KICKOFF_OR_NOW');

  const xiOfficial = state?.xi?.status === 'OFFICIAL' && Boolean(state?.xi?.fingerprint);
  if (!xiOfficial) pushMissing(missing, 'XI_NOT_OFFICIAL', state?.xi?.status || 'MISSING');

  if (state?.data_gate?.status !== 'DATA_GATE_PASS') {
    pushMissing(missing, 'DATA_GATE_NOT_PASS', state?.data_gate?.status || 'NOT_EVALUATED');
  }

  const modules = state?.modules || {};
  for (const name of requiredAnalysisModules) {
    if (modules?.[name]?.status !== COMPLETE) pushMissing(missing, 'ANALYSIS_MODULE_INCOMPLETE', name);
  }

  const seriesByKey = new Map((state?.standard_odds_series || []).map((s) => [s.market_key, s]));
  for (const key of requiredStandardSeries) {
    const series = seriesByKey.get(key);
    if (!series) {
      pushMissing(missing, 'STANDARD_SERIES_MISSING', key);
      continue;
    }
    if (series.opening_quality !== 'TRUE_OPEN_CERTIFIED' || !Number.isFinite(Number(series.true_open_price))) {
      pushMissing(missing, 'TRUE_OPEN_NOT_CERTIFIED', key);
    }
    if (!Number.isFinite(Number(series.current_price)) || Number(series.current_price) <= 1) {
      pushMissing(missing, 'CURRENT_PRICE_MISSING', key);
    } else if (!freshEnough(series.current_fetched_at, now, currentQuoteMaxAgeSeconds)) {
      pushMissing(missing, 'CURRENT_PRICE_STALE', key);
    }

    // T-40 is intentionally NOT required.
    // At/inside T-30 the fresh current quote must be frozen as the final operational T-30 snapshot.
    if (minutes !== null && minutes <= 30 && (!series.t30 || !Number.isFinite(Number(series.t30.price)))) {
      pushMissing(missing, 'T30_SNAPSHOT_MISSING', key);
    }
  }

  const analysisComplete = missing.length === 0 || (
    minutes !== null && minutes > 30 &&
    missing.every((m) => m.code === 'T30_SNAPSHOT_MISSING')
  );
  const finalReady = missing.length === 0 && minutes !== null && minutes <= 30;

  let status = T30_STATUS.PREPARING;
  if (finalReady) status = T30_STATUS.T30_READY;
  else if (minutes !== null && minutes <= 30) status = T30_STATUS.T30_DEADLINE_MISSED;
  else if (analysisComplete && minutes !== null && minutes > finalPriceWindowMinutes) status = T30_STATUS.AWAITING_FINAL_PRICE_CHECK;
  else if (analysisComplete && minutes !== null && minutes <= finalPriceWindowMinutes) status = T30_STATUS.FINAL_PRICE_WINDOW;
  else if (xiOfficial) status = T30_STATUS.XI_TRIGGERED_ANALYSIS;

  const nextActions = [...new Set(missing.map((m) => {
    switch (m.code) {
      case 'XI_NOT_OFFICIAL': return 'POLL_XI_SOURCES';
      case 'DATA_GATE_NOT_PASS': return 'RETRY_BLOCKED_DATA_ONLY';
      case 'ANALYSIS_MODULE_INCOMPLETE': return `RUN_POST_XI_MODULE:${m.detail}`;
      case 'STANDARD_SERIES_MISSING': return `START_STANDARD_SERIES:${m.detail}`;
      case 'TRUE_OPEN_NOT_CERTIFIED': return `CERTIFY_TRUE_OPEN:${m.detail}`;
      case 'CURRENT_PRICE_MISSING':
      case 'CURRENT_PRICE_STALE': return `REFRESH_FINAL_PRICE:${m.detail}`;
      case 'T30_SNAPSHOT_MISSING': return `CAPTURE_T30_FROM_FRESH_CURRENT:${m.detail}`;
      default: return 'FIX_TIME_METADATA';
    }
  }))];
  if (analysisComplete && minutes !== null && minutes > 30) nextActions.push('WAIT_FOR_T30_FINAL_PRICE_CHECK');

  return {
    status,
    ready: finalReady,
    analysis_complete: analysisComplete,
    minutes_to_kickoff: minutes === null ? null : Math.round(minutes * 10) / 10,
    deadline_minutes: 30,
    missing,
    next_actions: [...new Set(nextActions)]
  };
}
