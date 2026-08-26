# BetFlag Realtime Operational Contract

## Objective

Use BetFlag/AAMS as the primary operational source for football player-prop prices while keeping GoldBet direct as a calibration/cross-check source when available.

## Source of truth for player prices

Primary source: `https://sportservice.betflag.it/api/sport/pregame`.

Source label must remain **BetFlag/AAMS direct**. It must never be relabelled as GoldBet direct.

## Operational paths

### 1. Cloudflare fast path

Target Worker version: `7.0-betflag-operational`.

Exact endpoint: `/live/player-price`.

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
2. request the exact BetFlag/AAMS price at decision time;
3. require exact fixture + player + market + selection/line identity;
4. require a unique healthy proof;
5. compare `current_price >= FINAL_GATE`;
6. classify BET only if all analysis and price conditions pass.

If no unique fresh proof is available, classification is `ATTESA` or `NO BET`, never an inferred BetFlag price.

## Provenance

Allowed labels:

- `BETFLAG_AAMS_DIRECT` — direct BetFlag/AAMS player service;
- `GOLDBET_DIRECT_ODSS` — direct GoldBet filter through the ODSS bridge when fresh and mapped.

Forbidden behaviour:

- substituting an external bookmaker price silently;
- calling a shared or external quote “GoldBet direct”;
- using an old GitHub snapshot as if it were live;
- generating a BET from a non-unique player/market match.

## Deployment state

Cloudflare deployment status is recorded in `feed/cloudflare-deploy-status.json`.

Until Worker v7 is live-verified, the GitHub Actions on-demand proof workflow is the operational fallback for exact BetFlag player prices.
