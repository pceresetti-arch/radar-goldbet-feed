# BetFlag Realtime Operational Contract

## Objective

Use BetFlag/AAMS as the primary operational source for football player-prop prices while keeping GoldBet direct as a calibration/cross-check source when available.

## Source of truth for player prices

Primary source: `https://sportservice.betflag.it/api/sport/pregame`.

Source label must remain **BetFlag/AAMS direct**. It must never be relabelled as GoldBet direct.

## Operational paths

### 1. Cloudflare fast path

Canonical Worker: `https://radar-betflag-v7.p-ceresetti.workers.dev`.

Target Worker version: `7.0-betflag-operational`.

Exact endpoint: `/live/player-price`.

Broad discovery endpoint: `/live/player-props`.

For player-prop decisions the canonical Worker above is authoritative. The legacy combined hostname `radar-goldbet.p-ceresetti.workers.dev` and `feed/cloudflare-deploy-status.json` MUST NOT be used to determine BetFlag player-price availability.

Canonical machine health/status file: `feed/betflag-v7-worker-status.json`.

A player quote is eligible for FINAL GATE only when all of the following are true:

- source calls are healthy;
- fixture identity matches;
- player identity matches exactly;
- market identity matches exactly;
- selection and line are unambiguous when required;
- exactly one quote remains after identity filtering;
- the quote is fresh under the Worker freshness policy;
- the response contains a proof fingerprint.

The exact endpoint bypasses the scan cache and requests the relevant BetFlag market directly.

### 2. GitHub Actions on-demand fallback

Workflow: `.github/workflows/betflag-price-proof-on-demand.yml`.

Request file: `betflag-price-proof-request.json`.

Latest result: `feed/betflag-price-proof-latest.json`.

Historical proofs: `feed/price-proofs/`.

This path is operational even when Cloudflare deployment credentials are unavailable. It directly calls BetFlag/AAMS, produces a source timestamp, exact identity check, quote identifiers and SHA-256 fingerprint, and commits the proof to the repository.

If the canonical Worker health check fails, times out, DNS resolution fails, TLS/routing fails, or the current execution environment cannot reach the Worker, trigger/use this fallback immediately. Do not downgrade to historical discovery snapshots and do not consult the legacy combined Worker as a substitute for player prices.

### 3. Transport failure state machine — V2 mandatory

Caller connectivity and BetFlag source health are separate states and MUST NOT be conflated.

Required states:

- `PLAYER_FAST_PATH_OK`: Worker reachable and health/version contract valid.
- `TRANSPORT_PRIMARY_FAILED`: caller cannot reach the Worker because of DNS/network/TLS/routing/timeout; this does **not** prove BetFlag or the Worker is down.
- `BETFLAG_UPSTREAM_FAILED`: Worker/fallback reached but direct BetFlag/AAMS source reports unhealthy/fails.
- `PLAYER_EXACT_FALLBACK_OK`: Worker transport failed but GitHub Actions on-demand direct proof returned a fresh unique healthy exact quote.
- `PLAYER_LANE_UNREACHABLE`: fast path and direct on-demand fallback both failed or could not produce proof.

A `TRANSPORT_PRIMARY_FAILED` event must never degrade the entire Radar run. Calendar, XI, tactical modelling, PRE-XI shortlist and POST-XI rediscovery logic continue independently. Only the unavailable player-price/discovery block is marked incomplete.

The Radar must not convert a caller-side DNS/network failure into `market_not_quoted`, `source_unhealthy`, or global `PIPELINE_DEGRADED` without independent source evidence.

### 4. Discovery behaviour when fast path is unreachable

`/live/player-props` remains the preferred live discovery path.

If the Worker cannot be reached by the caller:

1. keep PRE-XI/XI/context/model lanes active;
2. use any fresh direct BetFlag/AAMS discovery artifact produced by an operational direct-AAMS workflow when available;
3. historical `player-props-current*` files may be used only as discovery hints / market-history context, never as current price proof;
4. exact final price must still be certified through `/live/player-price` or `betflag-price-proof-on-demand.yml`;
5. never infer `mercato non quotato` from a transport or acquisition failure.

## Historical five-minute feed

`feed/player-props-current*.json` remains a broad periodic archive/discovery feed. It is **not** the authoritative final-price endpoint because GitHub scheduled Actions can run late or be skipped.

The historical feed is useful for:

- market discovery;
- OPEN/intermediate movement reconstruction;
- retrospective analysis;
- source health monitoring;
- drift/calibration checks.

A stale GitHub snapshot must never be treated as a current price solely because the file exists.

## Price-gate rule

For player props:

1. perform deep analysis and compute fair odds / FINAL GATE;
2. request the exact BetFlag/AAMS price at decision time from the canonical Worker;
3. if that request is unavailable, immediately invoke/read the on-demand BetFlag proof fallback;
4. require exact fixture + player + market + selection/line identity;
5. require a unique healthy proof;
6. compare `current_price >= FINAL_GATE`;
7. classify BET only if all analysis and price conditions pass.

If no unique fresh proof is available, classification is `ATTESA` or `NO BET`, never an inferred BetFlag price.

## Provenance

Allowed labels:

- `BETFLAG_AAMS_DIRECT` — direct BetFlag/AAMS player service;
- `GOLDBET_DIRECT_ODSS` — direct GoldBet source when fresh/mapped; player props used as cross-check when available.

Forbidden behaviour:

- substituting an external bookmaker price silently;
- calling a shared or external quote “GoldBet direct”;
- using an old GitHub snapshot as if it were live;
- generating a BET from a non-unique player/market match;
- treating `feed/cloudflare-deploy-status.json` as BetFlag player-fast-path health;
- treating one DNS/network failure from the caller as evidence that the canonical Worker is down when the canonical status/fallback can still verify the source;
- treating `not found` as `not quoted` without positive market-availability verification;
- stopping the full PRE-MATCH Radar because only the player transport lane is unavailable.

## Deployment state

Dedicated BetFlag v7 deployment status is recorded in `feed/betflag-v7-worker-status.json` and is authoritative for player-price fast-path health when fresh.

`feed/cloudflare-deploy-status.json` belongs to the legacy/combined `radar-goldbet` Worker and is not authoritative for player props.

When the dedicated Worker is not live-verified, the GitHub Actions on-demand proof workflow is the immediate operational fallback for exact BetFlag player prices.
