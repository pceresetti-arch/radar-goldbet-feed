export function quoteIdentity(q = {}) {
  return [
    q.bookmaker,
    q.fixture_id,
    q.market,
    q.period || 'FT',
    q.line ?? '',
    q.selection
  ].map((v) => String(v ?? '').trim()).join('|');
}

export function createQuoteTimeline(meta = {}) {
  const identity = quoteIdentity(meta);
  if (!meta.bookmaker || !meta.fixture_id || !meta.market || !meta.selection) {
    throw new Error('QUOTE_IDENTITY_INCOMPLETE');
  }
  return {
    schema_version: 'radar-v2-quote-timeline-v1',
    identity,
    bookmaker: meta.bookmaker,
    fixture_id: meta.fixture_id,
    market: meta.market,
    period: meta.period || 'FT',
    line: meta.line ?? null,
    selection: meta.selection,
    true_open: null,
    snapshots: [],
    current: null
  };
}

function assertSameIdentity(timeline, quote) {
  if (timeline.identity !== quoteIdentity({
    bookmaker: quote.bookmaker ?? timeline.bookmaker,
    fixture_id: quote.fixture_id ?? timeline.fixture_id,
    market: quote.market ?? timeline.market,
    period: quote.period ?? timeline.period,
    line: quote.line ?? timeline.line,
    selection: quote.selection ?? timeline.selection
  })) {
    throw new Error('QUOTE_IDENTITY_MISMATCH');
  }
}

export function setTrueOpen(timeline, quote) {
  assertSameIdentity(timeline, quote);
  if (timeline.true_open) return timeline;
  if (quote.certification !== 'TRUE_OPEN_CERTIFIED') {
    throw new Error('TRUE_OPEN_NOT_CERTIFIED');
  }
  if (!Number.isFinite(Number(quote.price)) || Number(quote.price) <= 1 || !quote.captured_at || !quote.source) {
    throw new Error('TRUE_OPEN_EVIDENCE_INVALID');
  }
  timeline.true_open = {
    price: Number(quote.price),
    captured_at: quote.captured_at,
    source: quote.source,
    certification: quote.certification,
    proof: quote.proof ?? null
  };
  return timeline;
}

export function appendQuoteSnapshot(timeline, quote) {
  assertSameIdentity(timeline, quote);
  if (!Number.isFinite(Number(quote.price)) || Number(quote.price) <= 1 || !quote.captured_at || !quote.source) {
    throw new Error('SNAPSHOT_EVIDENCE_INVALID');
  }
  const snap = {
    price: Number(quote.price),
    captured_at: quote.captured_at,
    source: quote.source,
    source_class: quote.source_class ?? null,
    minutes_to_kickoff: Number.isFinite(Number(quote.minutes_to_kickoff)) ? Number(quote.minutes_to_kickoff) : null,
    proof: quote.proof ?? null
  };
  timeline.snapshots.push(snap);
  timeline.snapshots.sort((a, b) => new Date(a.captured_at) - new Date(b.captured_at));
  timeline.current = snap;
  return timeline;
}

export function getNearestCheckpoint(timeline, targetMinutes, toleranceMinutes = 5) {
  const candidates = timeline.snapshots
    .filter((s) => Number.isFinite(s.minutes_to_kickoff))
    .map((s) => ({ ...s, distance: Math.abs(s.minutes_to_kickoff - targetMinutes) }))
    .filter((s) => s.distance <= toleranceMinutes)
    .sort((a, b) => a.distance - b.distance);
  return candidates[0] ?? null;
}

export function evaluateQuoteMovement(timeline, nowIso, maxCurrentAgeSeconds = 120) {
  if (!timeline.current) return { status: 'NO_CURRENT_QUOTE' };
  const ageSeconds = Math.max(0, (new Date(nowIso) - new Date(timeline.current.captured_at)) / 1000);
  const currentFresh = ageSeconds <= maxCurrentAgeSeconds;
  const sameBookMovementReady = Boolean(timeline.true_open && currentFresh);
  return {
    status: sameBookMovementReady ? 'MOVEMENT_READY' : (currentFresh ? 'TRUE_OPEN_MISSING' : 'CURRENT_STALE'),
    current_fresh: currentFresh,
    current_age_seconds: Math.round(ageSeconds),
    true_open: timeline.true_open,
    current: timeline.current,
    T40: getNearestCheckpoint(timeline, 40),
    T30: getNearestCheckpoint(timeline, 30),
    price_delta: sameBookMovementReady ? Number((timeline.current.price - timeline.true_open.price).toFixed(3)) : null
  };
}
