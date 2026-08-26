# Analysis work queue consumption

`feed/analysis-work-queue.json` contiene i filoni quantitativi da sviluppare nel Backtest Master + Audit.

Regola: ogni ciclo quantitativo deve leggere anche `feed/radar-project-state.json`; gli item `HIGH` della coda devono essere trattati come lavoro prioritario compatibilmente con disponibilità/qualità dei dati. Il primo item attuale è il modello cross-market movement / Market Confirmation Index definito in `RADAR_MARKET_CONFIRMATION_MODEL.md`.

Nessun modulo in stato `RESEARCH_SHADOW_MODE` può modificare P Radar, stake o FINAL GATE finché non supera il gate di promozione OOS definito nel relativo contratto.
