# Radar Unico — Ledger, Bankroll e Retroanalisi Contract

## Regola fondamentale
Il registro delle giocate e il bankroll sono componenti core del Radar e non possono essere trattati come memoria conversazionale opzionale.

## Source of truth
- `data/ledger/bankroll_state.json`: bankroll corrente ufficiale.
- `data/ledger/YYYY-MM-DD.json`: ledger giornaliero completo delle giocate effettivamente piazzate.
- `data/audit/YYYY-MM-DD.json`: audit giornaliero di TUTTE le previsioni Radar (BET giocate/non giocate, NO BET, ATTESA, shortlist, props e alternative).

## Registrazione immediata obbligatoria
Quando l'utente conferma una giocata con formule come `giocato`, `messo`, `presa`, `registra`, `salva`:
1. registrare immediatamente la giocata nel ledger del giorno;
2. non creare duplicati se la stessa giocata era già presente;
3. salvare almeno: data/ora Europe/Rome, partita, competizione, selezione, mercato esatto, quota presa, stake, bookmaker, stato OPEN, ritorno potenziale, profitto potenziale, classificazione Radar pre-bet, P Radar/fair/gate se disponibili, XI/ruolo se disponibili;
4. aggiornare l'esposizione aperta e il bankroll/cash state secondo il modello contabile adottato;
5. non sovrascrivere la storia: le correzioni devono essere tracciabili.

## Settlement obbligatorio
Alla chiusura:
- verificare risultato reale e settlement del mercato esatto;
- distinguere mercati speciali (Plus, Marc o Sost, combo, tiri, SOT, 1T, ecc.);
- salvare status WON/LOST/VOID/PUSH/CANCELLED, ritorno, P/L e fonte di verifica;
- aggiornare il bankroll corrente.

## Fine giornata obbligatoria
Ogni fine giornata deve essere eseguita una riconciliazione con:
- numero totale giocate;
- stake totale;
- vinte/perse/void/pending;
- ritorni;
- P/L giornata;
- ROI giornata;
- hit rate;
- bankroll iniziale e finale;
- esposizione residua;
- controllo che ogni conferma di giocata della giornata sia presente nel ledger.

## Retroanalisi giornaliera obbligatoria
Non riguarda soltanto le giocate effettive. Deve includere TUTTE le previsioni prodotte dal Radar:
- BET giocate e non giocate;
- NO BET;
- ATTESA;
- candidate scartate;
- shortlist;
- mercati alternativi e player props.

Per ogni previsione confrontare decisione pre-match, quota osservata, P Radar, fair, gate, XI/ruolo previsto, risultato reale, sviluppo partita, xG, tiri/SOT, big chances, 1T/2T, game state e — per i player — minuti, ruolo reale, xG/xA, tiri/SOT, tocchi area, rigori/piazzati e sostituzioni. Separare sempre process grade da result grade.

## Storico lungo
Il sistema deve consentire interrogazioni su finestre arbitrarie (giorni, settimane, mesi, 6+ mesi) e produrre:
- dettaglio di tutte le giocate;
- P/L cumulato;
- ROI;
- hit rate;
- andamento bankroll;
- breakdown per campionato, squadra, mercato, bookmaker, quota, fascia di stake, pre/post-XI, grade Radar;
- drawdown, winning/losing streak;
- confronto tra previsioni BET/NO BET/ATTESA e risultati reali;
- calibrazione P Radar vs frequenza osservata.

## Integrità
- Nessun bankroll può essere dichiarato ufficiale se non deriva da `bankroll_state.json` o da una riconciliazione esplicitamente certificata.
- Mai inventare baseline mancanti.
- In caso di discrepanza tra ledger e saldo comunicato dall'utente, il saldo comunicato diventa nuova baseline solo se l'utente lo dichiara esplicitamente; la discrepanza va conservata come reconciliation event.
- Il bankroll ufficiale confermato il 03/09/2026 è 144,20 EUR.
