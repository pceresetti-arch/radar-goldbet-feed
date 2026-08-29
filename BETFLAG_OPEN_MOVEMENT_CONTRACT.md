# BetFlag Opening & Movement Contract

## Scope

This contract applies to BetFlag/AAMS odds used by Radar Unico, with exact identity by fixture, market, period, line, selection and player where applicable.

## 1. Opening price is immutable

A real BetFlag opening price is a fixed historical fact. Once certified, it MUST NEVER be replaced by a later quote, a first-seen quote, an external bookmaker quote, or an inferred value.

Canonical label when explicit BetFlag source evidence exists:

`TRUE_OPEN_BETFLAG_SOURCE_CERTIFIED`

Stored fields:
- `true_open_odd`
- `true_open_at`
- `true_open_source_field`

If a later source response disagrees with an already certified opening, the existing opening remains unchanged and the discrepancy is recorded as an opening conflict.

## 2. First BetFlag availability captured by continuous residential monitoring

The current BetFlag player payload does not presently expose an explicit opening-odd field. Therefore FIRST_SEEN must not be silently called TRUE OPEN.

Once at least one healthy residential scan has already been completed, if an exact quote was absent from the previous healthy monitored state and then appears, Radar freezes that first observed BetFlag availability price as:

`OPEN_CAPTURED_AT_FIRST_BETFLAG_AVAILABILITY`

Stored fields:
- `captured_open_odd`
- `captured_open_at`
- `captured_open_basis = ABSENT_FROM_PREVIOUS_HEALTHY_RESIDENTIAL_SCAN`
- `previous_healthy_scan_at`

This captured opening is immutable and is the operational movement reference for future monitoring, but it is NOT relabelled as source-certified TRUE OPEN.

If monitoring began only after a market was already available and BetFlag exposes no explicit opening field, the required status remains:

`TRUE OPEN BETFLAG NON CERTIFICATA — MOVIMENTO INCOMPLETO`

## 3. Movement sequence

For every exact quote the residential tracker preserves:

- certified TRUE OPEN when available;
- otherwise captured first BetFlag availability when valid;
- FIRST_SEEN diagnostic;
- every detected price change with timestamp and delta;
- T-40 checkpoint;
- T-30 checkpoint;
- current exact quote at analysis/decision time.

Canonical sequence:

`TRUE OPEN / CAPTURED OPEN → intermediate snapshots → T-40 → T-30 → CURRENT`

The opening reference never moves. Only the current price and intermediate snapshots change.

## 4. T-40 and T-30

The residential feed normally runs every five minutes. The tracker keeps the closest healthy observation around 40 and 30 minutes before kickoff, with the exact timestamp and actual minutes-to-kickoff recorded. Schedule jitter must not silently create a fake exact timestamp.

## 5. Current price on demand

When the user asks for the current BetFlag price, the residential exact-price workflow MUST perform a fresh direct acquisition from the self-hosted residential runner, resolve exactly one matching fixture/player/market/selection/line, and return a proof containing:

- direct BetFlag source;
- source health;
- fetched timestamp;
- exact identity fields;
- current quote;
- proof fingerprint;
- opening reference and status;
- T-40/T-30 checkpoints when available;
- recent movement history;
- `price_gate_eligible`.

A stale historical snapshot is not a current-price proof.

## 6. No bookmaker substitution

The opening, movement and current quote displayed as BetFlag MUST come from BetFlag/AAMS. No GoldBet, aggregator or external bookmaker quote may be inserted into the BetFlag movement series.

## 7. Failure semantics

`not found` is not automatically `not quoted`.

If acquisition fails, report acquisition failure. If an exact BetFlag market is positively shown unavailable, report market unavailable. If true opening cannot be certified, report the incomplete true-open status without inventing an opening price.

## 8. Residential availability condition

Direct acquisition requires the Windows self-hosted runner labelled `betflag-residential` to be online on a normal permitted network. If the PC or runner is offline, previously stored opening/history remains valid historical evidence, but a new current quote cannot be certified through the residential lane until the runner returns.
