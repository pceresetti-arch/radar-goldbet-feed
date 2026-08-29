# BetFlag Realtime Operational Contract — V3

## Objective

Use **BetFlag/AAMS direct only** for operational football odds. GitHub and Cloudflare are transports/read layers, not alternative bookmakers. No external bookmaker may replace a missing BetFlag CURRENT price.

## Source of truth

Upstream source: `https://sportservice.betflag.it/api/sport/pregame`.

Canonical source label: `BETFLAG_AAMS_DIRECT`.

## Durable acquisition architecture

### A. Residential acquisition — authoritative upstream lane

The authoritative collector runs on the self-hosted Windows runner labelled `betflag-residential`.

Workflow: `.github/workflows/betflag-residential-feed.yml`.

Fresh production artifacts:

- `feed/betflag-residential-current.json` — player props;
- `feed/betflag-standard-current.json` — standard markets;
- `feed/betflag-residential-movement.json` — player movement;
- `feed/betflag-standard-movement.json` — standard movement;
- `feed/betflag-open-close-watch.json` — OPEN/CLOSE watch state;
- `feed/betflag-hot-feed.json` and `feed/betflag-fixtures/` — compact discovery/read layer.

The collector uses normal direct HTTP as the fast acquisition path. If BetFlag/Akamai returns HTTP 401/403/429, it MUST automatically bootstrap a real Chrome/Edge session on the residential runner and retry the BetFlag API inside the browser session. This is still BetFlag/AAMS direct; it is only a transport recovery mechanism.

A browser-recovery failure is `ACQUISIZIONE BETFLAG FALLITA/QUOTA NON RECUPERATA`, never `MERCATO NON QUOTATO`.

### B. Stable ChatGPT/read bridge — GitHub repository

For ChatGPT and other callers, the repository `pceresetti-arch/radar-goldbet-feed` is the durable read bridge for the fresh residential artifacts above.

This avoids making a caller-side `workers.dev` DNS/TLS/routing issue a blocker for the Radar. Reading a fresh GitHub artifact does **not** change the odds source: provenance remains `BETFLAG_AAMS_DIRECT` because the artifact was produced by the residential direct collector.

A snapshot is operational CURRENT only when its own source health is true and its timestamp satisfies the Radar freshness requirement. A stale artifact is discovery/history only.

### C. Cloudflare fast path — optional accelerator

Canonical Worker: `https://radar-betflag-v7.p-ceresetti.workers.dev`.

Endpoints:

- `/live/player-price` — exact player price;
- `/live/player-props` — broad discovery.

The Worker is an accelerator, not a single point of failure. If the caller cannot resolve/reach it, immediately use the fresh residential GitHub artifacts rather than declaring BetFlag unavailable.

### D. Exact price proof — residential on-demand

Workflow: `.github/workflows/betflag-residential-price-proof.yml`.

Trigger file: `betflag-price-proof-request.json`.

Latest proof: `feed/betflag-price-proof-latest.json`.

Archive: `feed/price-proofs/`.

The workflow refreshes the BetFlag residential feed first, resolves exact fixture + player + market + line + selection identity, and sets `price_gate_eligible=true` only when the direct source is healthy and exactly one quote is resolved.

The old cloud-only `.github/workflows/betflag-price-proof-on-demand.yml` is diagnostic/deprecated and MUST NOT be used for operational price proof because cloud/datacenter egress can be rejected by BetFlag/Akamai.

## CURRENT price gate

A quote is eligible for BET/NO BET price comparison only when:

1. provenance is `BETFLAG_AAMS_DIRECT`;
2. source is healthy;
3. observation is fresh under the Radar freshness policy;
4. fixture identity is exact;
5. market/period/line/selection identity is exact;
6. player identity is exact when applicable;
7. exactly one quote matches;
8. the price is compared with the current FINAL GATE.

If these conditions are not satisfied: `ATTESA` or `NO BET`; never invent or substitute a price.

## OPEN / movement policy

Priority:

1. `TRUE OPEN BETFLAG` only when BetFlag itself exposes explicit opening evidence;
2. otherwise `OPEN RADAR CERTIFICATA` only when continuous healthy BetFlag observation proves the exact quote was absent and then appeared;
3. `FIRST_SEEN` remains diagnostic only;
4. GoldBet may be retained only as `TRUE OPEN PROXY — GOLDBET` historical context and never as CURRENT BetFlag price.

Movement identity must remain fixture + market + period + line + selection + player when applicable.

## Health state machine

Required states:

- `BETFLAG_RESIDENTIAL_OK` — fresh direct residential acquisition healthy;
- `BETFLAG_BROWSER_RECOVERY_OK` — raw direct request was blocked but browser-session retry recovered direct BetFlag data;
- `TRANSPORT_WORKER_FAILED` — caller cannot reach the Cloudflare Worker, but this says nothing about BetFlag upstream;
- `BETFLAG_UPSTREAM_PLAYER_FAILED` — player lane remains blocked/failing after browser recovery;
- `BETFLAG_UPSTREAM_STANDARD_FAILED` — standard lane failed;
- `BETFLAG_PARTIAL` — one lane healthy and another failed;
- `BETFLAG_EXACT_PROOF_OK` — fresh unique residential exact proof available;
- `PLAYER_LANE_UNREACHABLE` — no fresh direct player quote can be proven.

Standard-market and player-prop health MUST be tracked separately. A player-prop 403 must not erase healthy standard-market data.

## Mandatory market-availability distinction

`MERCATO NON QUOTATO/NON DISPONIBILE SU BETFLAG` requires positive evidence from a healthy BetFlag fixture/market scan that the requested market is absent.

Any timeout, DNS failure, HTTP block, stale feed, parser failure, ambiguity, or unhealthy acquisition is `ACQUISIZIONE BETFLAG FALLITA/QUOTA NON RECUPERATA`.

## Forbidden behaviour

- using another bookmaker as CURRENT fallback;
- relabelling FIRST_SEEN as TRUE OPEN;
- using stale BetFlag data as fresh CURRENT;
- declaring a market non-quoted because acquisition failed;
- treating a Cloudflare/ChatGPT networking problem as a BetFlag outage;
- making the Worker a single point of failure;
- producing a BET without exact fresh BetFlag price proof.
