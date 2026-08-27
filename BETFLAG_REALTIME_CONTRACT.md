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

If the canonical Worker health check fails, times out, or cannot be reached by the current execution environment, trigger/use this fallback immediately. Do not downgrade to historical discovery snapshots and do not consult the legacy combined Worker as a substitute for player prices.

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
- `GOLDBET_DIRECT_ODSS` — direct GoldBet filter through the ODSS bridge when fresh and mapped.

Forbidden behaviour:

- substituting an external bookmaker price silently;
- calling a shared or external quote “GoldBet direct”;
- using an old GitHub snapshot as if it were live;
- generating a BET from a non-unique player/market match;
- treating `feed/cloudflare-deploy-status.json` as BetFlag player-fast-path health;
- treating one DNS/network failure from the caller as evidence that the canonical Worker is down when the canonical status/fallback can still verify the source.

## Deployment state

Dedicated BetFlag v7 deployment status is recorded in `feed/betflag-v7-worker-status.json` and is authoritative for player-price fast-path health.

`feed/cloudflare-deploy-status.json` belongs to the legacy/combined `radar-goldbet` Worker and is not authoritative for player props.

When the dedicated Worker is not live-verified, the GitHub Actions on-demand proof workflow is the immediate operational fallback for exact BetFlag player prices.
