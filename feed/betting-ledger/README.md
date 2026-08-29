# Betting Ledger — Registro giocate radar unico

Questo archivio e` ADDITIVO e non sostituisce lo storico precedente. Ogni giornata deve avere un ledger persistente separato e nessun file storico puo` essere sovrascritto o eliminato durante la migrazione.

## Regole vincolanti

1. Una giocata entra nel ledger solo se esplicitamente confermata dall'utente (es. giocato, messo, presa, registra) oppure provata da ricevuta.
2. Ogni giocata riceve un ID univoco `BET-YYYYMMDD-NNN`.
3. Il manifest giornaliero deriva esclusivamente dal ledger della data.
4. Il bankroll non puo` essere aggiornato se il ledger della giornata e` incompleto o non riconciliato.
5. Una nuova chat/progetto non deve ricostruire le giocate dalla memoria: deve leggere il ledger persistente.
6. Le giornate precedenti al 29/08/2026 devono essere migrate retroattivamente dallo storico gia` esistente senza inventare dati mancanti.
7. Le correzioni successive dell'utente prevalgono; una giocata cancellata/non piazzata non va conteggiata.
8. Nessuna migrazione cancella o modifica i vecchi artifact tecnici, snapshot o backtest gia` presenti nel repository.

## Stato migrazione

- 2026-08-29: ledger autorevole creato, 12 giocate riconciliate.
- 2026-08-09..2026-08-28: migrazione storica in corso. Le date incomplete devono essere marcate `RECONCILIATION_REQUIRED` e non usate per calcolare bankroll finche` non chiuse.
