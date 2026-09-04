# RADAR FULL ANALYSIS GATE V2

## Purpose
This contract is the hard completion gate for every Radar PRE-XI, FULL, POST-XI, WATCH, T-30 and FINAL GATE analysis. A response MUST NOT be labelled `ANALISI TOTALE` when a required block is missing. Missing data must be surfaced as `ATTESA / DATA GAP` rather than silently omitted.

## Mandatory readiness strip
Every FULL/POST-XI output must expose, before the final recommendation:

`Fixture | XI | BetFlag CURRENT | Props | Movement | Tactical | Player context | 1H model | Price gate`

Each item is `OK`, `WARN` or `BLOCK` with a short reason.

## 1. Fixture identity gate
Before any price or player claim, resolve the exact fixture, competition, kickoff and BetFlag identity. A guessed fixture path or fuzzy name match cannot be used as proof that a BetFlag market is absent.

## 2. XI source confidence
`XI_SOURCE_CONFIDENCE` is one of:
- `CERTIFIED_PRIMARY`: full XI explicitly confirmed by an official club or league source.
- `CERTIFIED_CROSSCHECK`: the full XI matches across at least two independent live providers.
- `PROVIDER_ONLY`: one live provider only. It MUST NOT be called official.
- `PREDICTED`: probable/predicted XI.
- `MISSING`.

Compatibility mapping:
- `CROSS_CONFIRMED` -> `CERTIFIED_CROSSCHECK`.
- `SOURCE_CONFIRMED` -> `PROVIDER_ONLY` unless source metadata explicitly identifies a primary official source.
- A provider showing a lineup is not, by itself, an official-source certificate.

For POST-XI/FULL player recommendations that materially depend on role or minutes, `PROVIDER_ONLY`, `PREDICTED` and `MISSING` must be visibly flagged. `MISSING` blocks the final player decision; `PROVIDER_ONLY` cannot be described as an official XI.

## 3. BetFlag exact CURRENT gate
For every priced recommendation use this strict route:
1. branch `betflag-live` -> `feed/betflag-live-status.json`;
2. require fresh healthy standard/player lane as applicable;
3. `feed/betflag-residential-fixtures-index.json` or the canonical live fixture index;
4. resolve exact fixture;
5. read the exact per-fixture file declared by the index;
6. resolve exact bookmaker + fixture + market + selection + period + line + player identity;
7. aggregate truncation or an unreadable aggregate MUST NOT be treated as an empty exact lane;
8. declare acquisition failure only after the exact route is exhausted or unhealthy.

A priced `BET` is blocked when exact fresh BetFlag CURRENT is unavailable.

## 4. BetFlag market completeness
`BETFLAG_MARKET_COMPLETENESS` is:
- `COMPLETE`: standard markets plus the relevant available player-market matrix were scanned for the candidates under analysis;
- `PARTIAL`: standard current is available but the player matrix is absent, incomplete or not applicable;
- `MISSING`: exact current standard markets are unavailable.

For every relevant player candidate, scan the complete BetFlag matrix when quoted: anytime/Marcatore Plus, 1T, 2T, first scorer, Gol o Assist, Assist, substitution-linked scorer/assist markets, shots, SOT, 1T shots/SOT and supported combos. Never infer that a market does not exist after a single failed lookup.

## 5. Movement certification
`MOVEMENT_CERTIFICATION` is one of:
- `TRUE_OPEN_CURRENT_T30`
- `TRUE_OPEN_CURRENT`
- `OPEN_RADAR_CURRENT_T30`
- `OPEN_RADAR_CURRENT`
- `FIRST_SEEN_CURRENT`
- `CURRENT_ONLY`
- `MISSING`

Exact movement identity is bookmaker + fixture + market + selection + period + line + player.

Rules:
- Only explicit BetFlag evidence can be called `TRUE_OPEN`.
- `OPEN_RADAR` requires continuous healthy BetFlag observation proving absent -> appeared.
- `FIRST_SEEN` is diagnostic only.
- Cross-book movement is context only and NEVER substitutes for BetFlag movement.
- Strong same-book movement threshold remains absolute delta >= 0.20.
- `CURRENT_ONLY` can support a price-only value decision if the other gates pass, but movement MUST NOT be cited as evidence.
- `MISSING` means the movement audit was not performed and must be surfaced as `DATA GAP`.

## 6. Tactical and player-context gate
FULL analysis must include, when materially available:
- formation vs formation and real player lanes;
- pressing, block height, width, half-spaces, rest defense, transitions, cross/cut-back and set pieces;
- matchup player-zone-defender/system;
- absences, bench, recent minutes, rest/travel/fatigue and physical availability;
- expected minutes and substitution risk;
- penalties/set pieces;
- xG/xA, shots/SOT and offensive share.

Missing tactical/player context cannot be silently converted into a generic narrative.

## 7. POST-XI DELTA gate
When XI becomes certified, or changes after a first confirmation, recompute:
- players in/out and formation;
- real roles/lanes;
- expected minutes and substitution risk;
- penalties/set pieces;
- xG/xA/shot/SOT share;
- team xG and xG 1T;
- formation-vs-formation matchup;
- every relevant player-prop P/fair/gate;
- exact CURRENT price and post-XI price change.

If this delta is required but not complete, POST-XI/FULL cannot be called complete.

## 8. Mandatory model blocks
A FULL analysis requires:
- fixture/competition/kickoff identity;
- XI source confidence and formations;
- tactical matchup;
- absences/bench/fitness/minutes/rest;
- venue, pitch/weather when relevant, home/away, table and motivation;
- team/opponent underlying data and xG;
- 1H xG, P(>=1 goal 1H), fair odds and relevant 1H player allocation;
- player probability, expected minutes, penalties/set pieces and substitution risk;
- complete relevant BetFlag market matrix;
- exact CURRENT prices and movement certification;
- fair odds, FINAL GATE and edge;
- two scorer rankings: `PIU PROBABILI A SEGNARE` and `MIGLIORI VALUE BET`.

## 9. Decision rules
Hard blocks:
- exact fixture identity missing;
- exact CURRENT BetFlag price missing for a priced recommendation;
- XI missing for a POST-XI/FULL player-role decision;
- required tactical/player context materially incomplete;
- mandatory 1H model omitted;
- required POST-XI delta incomplete;
- market-specific probability/fair/gate absent;
- CURRENT price below FINAL GATE.

Allowed outputs:
- `BET`: all relevant gates pass and exact price is above gate.
- `BET PRICE-ONLY`: the value gate passes but movement is only `CURRENT_ONLY` or `FIRST_SEEN_CURRENT`; no movement claim is allowed.
- `NO BET`: data is sufficient and the model/price fails the gate.
- `ATTESA / DATA GAP`: a required data gate is incomplete.

`FAST` may reduce prose redundancy but MUST NOT be presented as `ANALISI TOTALE` if it skips material analytical blocks.

## 10. Audit rule
Every analysis must persist or expose the status of XI confidence, exact BetFlag current, market completeness, movement certification, tactical/player context, 1H model and final price gate. The absence of evidence must remain visible in the audit trail and must never be upgraded after the event.