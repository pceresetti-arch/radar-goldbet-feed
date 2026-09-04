# RADAR DATA ACQUISITION HARDENING V1

This contract hardens the three failure modes observed in live Radar work: false/weak XI certification, missing BetFlag player prices, and incomplete same-book movement reconstruction.

## 1. XI acquisition ladder
For every fixture inside the XI watch window, sources must be tried in this order and evidence must be preserved:
1. official club / league / federation source;
2. first live lineup provider;
3. second independent live lineup provider;
4. additional provider only when the first two disagree.

A lineup may be labelled `CERTIFIED_PRIMARY` only with explicit primary-source metadata. A lineup may be labelled `CERTIFIED_CROSSCHECK` only when at least two independent named sources agree on the full standard 11v11. `SOURCE_CONFIRMED` from one provider is `PROVIDER_ONLY`, never official.

If providers disagree, keep `XI_CONFLICT` visible and block player-role finalisation until resolved. Never silently prefer a probable XI over a later live XI.

## 2. Exact BetFlag CURRENT acquisition
Before declaring a quote missing, the reader must exhaust the exact live route:
- read `feed/betflag-live-status.json` from `betflag-live`;
- verify the relevant standard/player lane is healthy and fresh;
- read `feed/betflag-residential-fixtures-index.json`;
- resolve exact fixture identity;
- read the per-fixture file from the index;
- match exact market/period/line/selection/player identity;
- retry alternate labels/normalised player name only inside the same exact fixture;
- distinguish `market not quoted` from `acquisition failed`, `stale lane`, `fixture unmapped`, and `aggregate truncated`.

A failed aggregate lookup is never proof that the exact fixture lane is empty.

## 3. BetFlag player-market completeness
For every scorer/player candidate, search the complete available matrix before finalising value:
- anytime / Marcatore Plus;
- 1T / 2T / first scorer;
- Gol o Assist / Assist / Gol e Assist;
- scorer/assist substitution-linked variants;
- shots, SOT, 1T shots/SOT;
- supported player-match combos.

If one market is missing, the rest of the candidate matrix must still be checked. The system must never conclude `no quote` after the first missing market.

## 4. Movement certification
Movement is valid only for the exact identity:
`BetFlag + fixture + market + period + line + selection + player`.

Allowed states:
- `TRUE_OPEN_CURRENT_T30`
- `TRUE_OPEN_CURRENT`
- `OPEN_RADAR_CURRENT_T30`
- `OPEN_RADAR_CURRENT`
- `FIRST_SEEN_CURRENT`
- `CURRENT_ONLY`
- `MISSING`

Only explicit BetFlag evidence can establish TRUE OPEN. Cross-book movement is context only. Strong movement remains absolute same-book delta >= 0.20.

If historical snapshots are unavailable, the Radar may still make a `BET PRICE-ONLY` decision using a fresh exact CURRENT and full model, but must not cite movement as supporting evidence.

## 5. Post-XI mandatory recompute
When a certified XI appears or changes, invalidate all PRE-XI player conclusions and recompute:
- roles and formation;
- expected minutes and substitution risk;
- penalties/set pieces;
- player xG/xA/shot/SOT share;
- team xG and 1H model;
- tactical matchup;
- full BetFlag player matrix;
- P/fair/final gate;
- post-XI price and exact movement state.

## 6. Visible readiness
Every FULL/POST-XI analysis must expose:
`Fixture | XI | BetFlag CURRENT | Props | Movement | Tactical | Player context | 1H model | Price gate`

Missing material data must be shown as `WARN` or `BLOCK`; it must never disappear from the output.

## 7. Hard-stop rules
A priced player `BET` is forbidden when any of the following is true:
- exact fixture unresolved;
- exact fresh BetFlag CURRENT unavailable;
- XI missing for a role/minutes-dependent player decision;
- player market identity ambiguous;
- market-specific P/fair/gate missing;
- required post-XI recompute incomplete;
- CURRENT below gate.

A missing TRUE OPEN alone does not block a price-only value decision, but blocks all claims about opening-line movement.
