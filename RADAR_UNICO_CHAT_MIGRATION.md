# Radar Unico — Chat Migration / Deletion Safety

Data consolidamento: 2026-08-25

## Obiettivo
Ridurre la dipendenza del progetto dalle vecchie conversazioni ChatGPT senza pubblicare dati personali/finanziari nel repository pubblico.

## MIGRATO NEL REPOSITORY — non dovrebbe più dipendere dalle vecchie chat
- obiettivo operativo del Radar;
- perimetro campionati, inclusa Saudi Pro League;
- definizione di READY_DEEP_ANALYSIS;
- official XI gate e regola `lineupType=standard`;
- `xi_fingerprint` e invalidazione su cambio XI;
- Deep Matchup Analysis obbligatoria;
- scansione mercati standard/player props;
- player_market_bet_ready;
- minutes/position/shot-origin/concession context;
- heatmap FotMob e mapping Opta→FotMob;
- TRUE OPEN e MMS >=0.20;
- FINAL GATE unico;
- correlazione/esposizione come principio;
- notifiche READY/delta/alert dati incompleti;
- anti-hindsight e validazione prospettica/OOS;
- roadmap tecnica;
- caveat certificazione player props;
- privacy boundary.

Source of truth: `RADAR_UNICO_MASTER.md`.
Machine state: `feed/radar-project-state.json`.

## NON MIGRATO NEL REPOSITORY PUBBLICO PER PRIVACY
Queste categorie non devono essere pubblicate qui senza scelta esplicita di una destinazione privata:
- bankroll personale;
- ricevute GoldBet;
- stake e ritorni personali dettagliati;
- registro completo delle scommesse effettivamente piazzate;
- eventuali dati personali dell’utente;
- copie integrali di vecchie conversazioni.

## STORICO ANALISI
Le future analisi devono essere archiviate prospetticamente in forma strutturata quando tecnicamente disponibile. Per una retro-analisi di performance sono valide soltanto tracce pre-match documentate prima dell’esito.

Le vecchie conversazioni possono contenere analisi storiche non ancora migrate in un ledger privato strutturato. Per questo motivo, fino a quando il backup privato non è stato conservato dall’utente, la scelta più prudente è ARCHIVIARE le vecchie chat anziché eliminarle.

## STATO DI SICUREZZA
- Eliminazione vecchie chat per preservare il MODELLO/ARCHITETTURA: sostanzialmente sicura dopo questo consolidamento.
- Eliminazione vecchie chat per preservare anche TUTTO lo storico personale di giocate/analisi: non considerata sicura finché il backup privato non è stato conservato separatamente.
