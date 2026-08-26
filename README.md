# Radar Unico Value Bet Calcio

Repository operativo del progetto Radar Unico.

## Start here
Leggere prima **`RADAR_UNICO_MASTER.md`**. È il source of truth consolidato per obiettivo, readiness, formazione ufficiale, Deep Matchup Analysis, player context, GoldBet, MMS, FINAL GATE, notifiche, validazione OOS, privacy e roadmap.

Stato macchina sintetico: **`feed/radar-project-state.json`**.

## Contratti specialistici
- `RADAR_UNICO_OPERATIONAL_CONTRACT.md` — Deep Matchup Analysis e mercati.
- `RADAR_PLAYER_CONTEXT_RULE.md` — official XI, fingerprint, player-market BET gate.
- `RADAR_MMS_PRIMARY_RULE.md` — MMS primario TRUE OPEN GoldBet.
- `TRUE_OPEN_MOVEMENT_POLICY.md` — policy TRUE OPEN.
- `RADAR_ODDS_MOVEMENT_CONTRACT.md` — tracking quote/checkpoint.
- `RADAR_UNICO_LINEUP_PIPELINE.md` — formazioni e tattica.
- `BETFLAG_REALTIME_CONTRACT.md` — acquisizione BetFlag/AAMS player props, certificazione quota esatta, freshness e fallback on-demand.

## Feed operativi principali
- `feed/deep-analysis-readiness-summary.json`
- `feed/deep-analysis-readiness.json`
- `feed/lineups-current.json`
- `feed/lineups-tactical-current.json`
- `feed/odds-movement-current.json`
- `feed/diretta-goldbet-true-open-index.json`
- `feed/player-props-current.json`
- `feed/betflag-price-proof-latest.json`
- `feed/cloudflare-deploy-status.json`
- `feed/player-matchup-context-current.json`
- `feed/player-heatmap-context-current.json`
- `feed/player-context-validation-ledger.json`
- `feed/radar-mms-primary-signals.json`

## Player props realtime
Per una decisione operativa sui player props, il file periodico `player-props-current.json` è storico/discovery, non il prezzo finale. Il prezzo operativo deve essere certificato a richiesta tramite il Worker v7 `/live/player-price` quando disponibile; in fallback si usa `.github/workflows/betflag-price-proof-on-demand.yml`, che interroga direttamente BetFlag/AAMS e salva prova, timestamp, identificatori quota e SHA-256.

## Regola fondamentale
Nessuna BET può essere generata dal solo prezzo o da un solo segnale. Serve analisi approfondita, dati affidabili, probabilità/fair e FINAL GATE. I moduli preliminari o non calibrati possono modificare rischio/confidenza ma non creare edge autonomo.

## Privacy
Il repository è pubblico. Non usarlo come archivio di bankroll personale, ricevute o storico finanziario dettagliato dell’utente.
