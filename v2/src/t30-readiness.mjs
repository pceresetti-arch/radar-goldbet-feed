const COMPLETE = 'COMPLETED';

export const T30_STATUS = Object.freeze({
  PREPARING: 'PREPARING',
  CRITICAL_FINISH_WINDOW: 'CRITICAL_FINISH_WINDOW',
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
 * Hard operational gate: by T-30 the fixture must already be decision-ready.
 * This is deliberately stricter than the normal Data Gate.
 */
export function evaluateT30Readiness(state, options = {}) {
  const now = options.now || new Date().toISOString();
  const currentQuoteMaxAgeSeconds = options.currentQuoteMaxAgeSeconds ?? 180;
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

  if (state?.xi?.status !== 'OFFICIAL') {
    pushMissing(missing, 'XI_NOT_OFFICIAL', state?.xi?.status || 'MISSING');
  }

  if (state?.data_gate?.status !== 'DATA_GATE_PASS') {
    pushMissing(missing, 'DATA_GATE_NOT_PASS', state?.data_gate?.status || 'NOT_EVALUATED');
  }

  const modules = state?.modules || {};
  for (const name of requiredAnalysisModules) {
    if (modules?.[name]?.status !== COMPLETE) {
      pushMissing(missing, 'ANALYSIS_MODULE_INCOMPLETE', name);
    }
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
    if (!series.t40 || !Number.isFinite(Number(series.t40.price))) {
      pushMissing(missing, 'T40_SNAPSHOT_MISSING', key);
    }
    if (!series.t30 || !Number.isFinite(Number(series.t30.price))) {
      pushMissing(missing, 'T30_SNAPSHOT_MISSING', key);
    }
  }

  const ready = missing.length === 0;
  let status = T30_STATUS.PREPARING;
  if (ready) status = T30_STATUS.T30_READY;
  else if (minutes !== null && minutes <= 30) status = T30_STATUS.T30_DEADLINE_MISSED;
  else if (minutes !== null && minutes <= 45) status = T30_STATUS.CRITICAL_FINISH_WINDOW;

  const nextActions = [...new Set(missing.map((m) => {
    switch (m.code) {
      case 'XI_NOT_OFFICIAL': return 'REFRESH_XI';
      case 'DATA_GATE_NOT_PASS': return 'RETRY_BLOCKED_DATA_ONLY';
      case 'ANALYSIS_MODULE_INCOMPLETE': return `RUN_MODULE:${m.detail}`;
      case 'STANDARD_SERIES_MISSING': return `START_STANDARD_SERIES:${m.detail}`;
      case 'TRUE_OPEN_NOT_CERTIFIED': return `CERTIFY_TRUE_OPEN:${m.detail}`;
      case 'CURRENT_PRICE_MISSING':
      case 'CURRENT_PRICE_STALE': return `REFRESH_CURRENT_PRICE:${m.detail}`;
      case 'T40_SNAPSHOT_MISSING': return `RECOVER_OR_MARK_T40:${m.detail}`;
      case 'T30_SNAPSHOT_MISSING': return `CAPTURE_T30:${m.detail}`;
      default: return 'FIX_TIME_METADATA';
    }
  }))];

  return {
    status,
    ready,
    minutes_to_kickoff: minutes === null ? null : Math.round(minutes * 10) / 10,
    deadline_minutes: 30,
    missing,
    next_actions: nextActions
  };
}
