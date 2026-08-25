# Radar Unico — Official XI & Player Context Gate

## Purpose
Increase pre-bet precision by ensuring player markets are evaluated on the actual official XI, current tactical role, realistic minutes risk and opponent concession structure.

## 1. Official XI definition
A FotMob lineup can unlock the Radar only when all conditions hold:
- `lineupType = standard`
- `confirmed = true`
- complete 11 v 11
- status `SOURCE_CONFIRMED` or `CROSS_CONFIRMED`

`lastStarting11`, `lastStartingLineups`, predicted, probable and expected lineups are historical/probable references only. They must never be labelled official and must never unlock `READY_DEEP_ANALYSIS`.

## 2. XI fingerprint and revision rule
Each official 11 v 11 receives an `xi_fingerprint` derived from the two teams and starter IDs.

If the fingerprint changes after the first confirmation:
- the previous player-level analysis is invalidated;
- tactical positioning must be regenerated;
- player matchup context must be regenerated;
- player props cannot be promoted to BET until the downstream layers match the new fingerprint.

## 3. Standard deep-analysis readiness
A match may become `READY_DEEP_ANALYSIS` for standard markets only when these are fresh and synchronized:
- official standard XI;
- tactical positioning layer based on that XI;
- current GoldBet standard odds;
- certified GoldBet TRUE OPEN for all 1X2 selections and at least one full-time Over line.

Player props do not block standard analysis if they are not offered.

## 4. Player-market BET gate
A recommendation on any player market requires `player_market_bet_ready = true` in addition to the normal price gate.

This requires:
- current player props feed;
- current `player-matchup-context` feed;
- player context produced for the exact same `xi_fingerprint` as the official XI.

If player prices exist but context is missing/stale/mismatched, the market can only be `WATCH/ATTESA`, never BET.

## 5. Player matchup context
For each official starter, the context layer currently uses recent FotMob match data to derive:
- starts and appearances;
- average minutes when selected;
- preliminary P(60+), P(75+), P(90) estimates;
- historical starting coordinates/role zone;
- shot count, shot xG and shots on target;
- shot-origin coordinates and dominant shot zone;
- shot situation/type;
- opponent concession map by pitch zone and chance situation.

The current default lookback is six recent completed matches per team.

## 6. Calibration restriction
The minutes probabilities are `PRELIMINARY_UNCALIBRATED`.
They may alter confidence, risk and expected exposure time, but cannot create standalone betting edge or justify stake escalation until prospectively/OOS validated.

Historical positional coordinates are lineup-layout proxies and shot-origin coordinates are event-data proxies. They are not GPS tracking or complete in-match heatmaps.

## 7. Price discipline
Even when `player_market_bet_ready = true`, a player bet is valid only if:
- the deep matchup analysis supports the selection;
- `GoldBet current price >= FINAL GATE`;
- the recommendation passes correlation/exposure controls.

The player-context layer improves the probability estimate; it never overrides the price gate.
