# Radar Unico — Handoff 2026-09-03 — BetFlag-only + Scorer Audit

Stato: **NUOVO OVERRIDE OPERATIVO** rispetto alle parti precedenti dell'handoff che consentivano a GoldBet/movimenti esterni di entrare troppo vicino al verdetto.

## Regole operative da applicare subito

1. **Prezzo giocabile = BetFlag soltanto.**
   - `BET`, `NO BET` e `FINAL GATE` usano esclusivamente CURRENT BetFlag/AAMS fresco, exact e univoco.
   - GoldBet/altri bookmaker sono solo contesto/shadow/research.
   - Se manca CURRENT BetFlag certificato: `ATTESA QUOTA / NON VALUTABILE`.

2. **Mercato esatto, non categoria generica.**
   - Marc, Marcatore Plus, 1T, Gol o Assist, Marc o Sost, tiri, SOT e combo restano identità distinte.
   - Ogni mercato ha P/fair/gate propri.
   - Il settlement post-match deve seguire la regola BetFlag esatta del ticket.

3. **Matrice BetFlag per candidato.**
   - Dopo XI, per ogni scorer/player candidate scandagliare tutti e soli i props BetFlag realmente presenti.
   - Separare `PLAYER DANGER RANKING` da `BETFLAG VALUE RANKING`.

4. **Expected minutes + game-state substitution risk.**
   - Non assumere 75–90 minuti perché un player è titolare.
   - Registrare distribuzione dei minuti e penalizzare rischio cambio anticipato, soprattutto negli underdog e nei game state estremi.

5. **TEAM VOLUME != PLAYER VOLUME.**
   - Non riversare automaticamente team-xG/team-strength sul centravanti.
   - Confrontare scorer-share, xG/npxG, tiri/SOT, tocchi area, rigori, teammate network, cannibalizzazione e matchup.

6. **Correlation Exposure Gate.**
   - Più ticket della stessa partita e stessa tesi latente vanno trattati come un cluster.
   - No Goal + Under + combo No Goal/Under non sono tre idee indipendenti.
   - HIGH/VERY_HIGH cluster non può superare lo stake massimo di una singola tesi salvo edge straordinario documentato.

7. **Audit giornaliero completo.**
   - Separare giocate effettive da previsioni non giocate.
   - Auditare BET non giocate, NO BET, ATTESA, shortlist e candidati scartati.
   - Per scorer: rank pre-match, gol, assist, minuti, xG/xA, tiri/SOT, big chances, tocchi area, legni, sostituzione, game state.
   - Metriche separate: Scouting Hit Rate, Ranking Hit Rate, Value Calibration, Market Selection Efficiency.

8. **Anti-result-bias.**
   - NO BET vincente non è automaticamente errore.
   - BET perdente non è automaticamente cattivo processo.
   - Classificare `MODEL_ERROR`, `PLAYER_ALLOCATION_ERROR`, `PRICE_ERROR`, `MINUTES_ERROR`, `PORTFOLIO_CORRELATION_ERROR`, `DATA_ERROR`, `SETTLEMENT_ERROR`, `REGIME_CHANGE`, `NORMAL_VARIANCE`.

## Modifiche repository

- Nuovo contratto: `RADAR_BETFLAG_PLAYER_VALUE_AND_AUDIT_CONTRACT.md`.
- `DEEP_ANALYSIS_COMPLETION_GATE.md` aggiornato a BetFlag-only per il verdetto operativo.
- `scripts/validate_radar_quote_consumer.py` passa a schema health v2 e rifiuta source class diverse da `BETFLAG_AAMS_DIRECT`.
- `scripts/radar_player_value_gates.py` introduce funzioni riusabili per:
  - BetFlag-only price gate;
  - probabilità corretta per distribuzione minuti;
  - effective correlated exposure;
  - scorer scouting hit.
- Test aggiunti/aggiornati:
  - `tests/test_validate_radar_quote_consumer.py`;
  - `tests/test_radar_player_value_gates.py`.

## Regola di precedenza
In caso di conflitto tra documenti storici e questo handoff, per il Radar operativo corrente prevalgono nell'ordine:
1. `BETFLAG_REALTIME_CONTRACT.md`;
2. `RADAR_BETFLAG_PLAYER_VALUE_AND_AUDIT_CONTRACT.md`;
3. `DEEP_ANALYSIS_COMPLETION_GATE.md`;
4. questo handoff;
5. documenti storici/research/shadow.

Il backtest storico GoldBet e i modelli di movement research possono continuare come filoni separati, ma non possono contaminare il prezzo operativo BetFlag.
