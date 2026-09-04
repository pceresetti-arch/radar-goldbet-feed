# BetFlag ChatGPT Live Read Contract

## Purpose

Prevent stale/empty BetFlag reads caused by querying `main` for operational odds and prevent false movement claims caused by mixing books, fixtures, markets or snapshots.

This contract is subordinate to and must be read together with `RADAR_FULL_ANALYSIS_GATE_V2.md`.

## Mandatory live-read route

For every Radar operational analysis that needs CURRENT BetFlag prices, player props, standard markets, fixture-level prices, or source-health status, ChatGPT/callers MUST read the dedicated branch:

`betflag-live`

The `main` branch is source code/configuration and MUST NOT be treated as the live odds branch.

## Required read order

1. Read `feed/betflag-live-status.json` from `betflag-live`.
2. Require fresh `generated_at`, `source_healthy=true`, and the relevant lane health (`player_source_healthy` and/or `standard_source_healthy`).
3. Read `feed/betflag-residential-fixtures-index.json` from `betflag-live`.
4. Resolve the exact fixture from the index. Never guess a fixture file path.
5. Use the exact `file` path declared by that fixture record and read it from `betflag-live`.
6. Resolve the exact identity: bookmaker + fixture + market + selection + period + line + player when applicable.
7. For every priced FINAL GATE recommendation, re-read/certify the exact BetFlag CURRENT price at decision time.

A failed guessed path is NOT evidence that a fixture or market is absent.

## Market completeness protocol

For player candidates, one lookup is not sufficient. Search the complete available BetFlag matrix for the exact player/fixture when quoted, including:
- anytime / Marcatore Plus;
- scorer 1T / 2T / first scorer;
- Gol o Assist / Assist;
- substitution-linked scorer/assist markets;
- shots / SOT / 1T shots or SOT;
- supported player-match combos.

The result must be labelled `COMPLETE`, `PARTIAL` or `MISSING`. Do not say “BetFlag non quota questo mercato” unless the exact fixture/player path has been exhausted while the lane is fresh and healthy.

## Large aggregate files

Do NOT infer that the player lane is empty merely because a large aggregate file such as `feed/betflag-residential-current.json` returns empty/truncated through a connector/read bridge. The authoritative health check is `feed/betflag-live-status.json`; the preferred operational read surface is the per-fixture file declared by the live fixture index.

If live status reports healthy player rows but the aggregate cannot be rendered, continue through the fixture index/per-fixture files. This is a read-transport limitation, not a BetFlag acquisition failure.

## Movement certification

Movement is valid only for the exact same identity:

`BetFlag + fixture + market + selection + period + line + player`

Allowed movement certificates:
- `TRUE_OPEN_CURRENT_T30`
- `TRUE_OPEN_CURRENT`
- `OPEN_RADAR_CURRENT_T30`
- `OPEN_RADAR_CURRENT`
- `FIRST_SEEN_CURRENT`
- `CURRENT_ONLY`
- `MISSING`

Rules:
- `TRUE_OPEN` requires explicit BetFlag open evidence.
- `OPEN_RADAR` requires continuous healthy BetFlag observation proving absent -> appeared.
- `FIRST_SEEN` is diagnostic only and must never be described as a true opening price.
- `CURRENT_ONLY` means the price can be used for a price-only value decision, but no movement signal may be claimed.
- Cross-book movement may be shown as context, but can NEVER certify BetFlag movement.
- The strong same-book movement threshold remains absolute delta >= 0.20 on the same exact identity.

When a movement certificate is not available, state it explicitly instead of reconstructing or guessing an opening price.

## Failure classification

Only report `ACQUISIZIONE BETFLAG FALLITA / QUOTA NON RECUPERATA` when the fresh `betflag-live` health/status and exact fixture read actually fail or are unhealthy.

Never classify a stale/empty file on `main`, a truncated aggregate, or a guessed path 404 as evidence that BetFlag player acquisition failed.

## Final gate

A priced `BET` requires a fresh, exact, unambiguous BetFlag CURRENT price. If CURRENT is missing, output `ATTESA QUOTA / DATA GAP`.

If the CURRENT price is certified but movement is only `CURRENT_ONLY` or `FIRST_SEEN_CURRENT`, a value recommendation may be labelled `BET PRICE-ONLY` only when every other analytical gate passes. The movement must not be used to justify that recommendation.

## Provenance

Odds read from fresh `betflag-live` artifacts retain provenance `BETFLAG_AAMS_DIRECT`; GitHub is only the durable read bridge.
