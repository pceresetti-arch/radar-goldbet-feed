# BetFlag ChatGPT Live Read Contract

## Purpose

Prevent stale/empty BetFlag reads caused by querying `main` for operational odds.

## Mandatory live-read route

For every Radar operational analysis that needs CURRENT BetFlag prices, player props, standard markets, fixture-level prices, or source-health status, ChatGPT/callers MUST read the dedicated branch:

`betflag-live`

The `main` branch is source code/configuration and MUST NOT be treated as the live odds branch.

## Required read order

1. Read `feed/betflag-live-status.json` from `betflag-live`.
2. Require fresh `generated_at`, `source_healthy=true`, and the relevant lane health (`player_source_healthy` and/or `standard_source_healthy`).
3. Read `feed/betflag-residential-fixtures-index.json` from `betflag-live`.
4. Resolve the exact fixture and use its declared `file` path.
5. Read that per-fixture file from `betflag-live`.
6. Use only rows with exact fixture + market + period/line + selection + player identity.

## Large aggregate files

Do NOT infer that the player lane is empty merely because a large aggregate file such as `feed/betflag-residential-current.json` returns empty/truncated through a connector/read bridge. The authoritative health check is `feed/betflag-live-status.json`; the preferred operational read surface is the per-fixture file declared by the live fixture index.

If live status reports healthy player rows but the aggregate cannot be rendered, continue through the fixture index/per-fixture files. This is a read-transport limitation, not a BetFlag acquisition failure.

## Failure classification

Only report `ACQUISIZIONE BETFLAG FALLITA / QUOTA NON RECUPERATA` when the fresh `betflag-live` health/status and fixture read actually fail or are unhealthy.

Never classify a stale/empty file on `main` as evidence that BetFlag player acquisition failed.

## Provenance

Odds read from fresh `betflag-live` artifacts retain provenance `BETFLAG_AAMS_DIRECT`; GitHub is only the durable read bridge.
