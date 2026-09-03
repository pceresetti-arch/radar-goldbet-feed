# Radar Unico — Archivio Analisi e Retroanalisi Contract

## Obiettivo
Ogni analisi Radar prodotta deve essere persistita in modo interrogabile e collegabile alle eventuali giocate effettive. Lo storico non può dipendere dalla memoria conversazionale.

## Struttura obbligatoria
- `data/analysis/YYYY-MM-DD/<match_slug>/<timestamp>_<phase>.json`: snapshot analisi pre-match, PRE-XI, POST-XI, T-30, aggiornamenti e final gate.
- `data/ledger/YYYY-MM-DD.json`: solo giocate effettivamente piazzate.
- `data/audit/YYYY-MM-DD.json`: retroanalisi giornaliera di TUTTE le previsioni.
- `data/ledger/bankroll_state.json`: bankroll ufficiale corrente.

## Campi minimi per ogni snapshot analisi
- id univoco analisi;
- data/ora Europe/Rome;
- partita, competizione, kickoff;
- fase: PRE_XI / POST_XI / T30 / FINAL / UPDATE;
- stato XI e formazione/ruoli usati;
- fonti/timestamp rilevanti;
- contesto, matchup tattico, assenze, minuti/rischio sostituzione;
- xG e distribuzioni gol incluse 1T/2T;
- player context e penalty status;
- quote BetFlag exact osservate e movement SAME BOOKMAKER quando disponibile;
- per ogni previsione/candidata: mercato, selezione, decisione BET/NO_BET/ATTESA/WATCH, quota osservata, P Radar, fair, gate, edge, grade, motivazioni e rischi;
- identificazione esplicita di mercati alternativi e candidati scartati;
- hash/chiave di collegamento verso eventuale riga del ledger se l'utente piazza la giocata.

## Regola append-only
Le analisi vecchie non vanno sovrascritte. Un nuovo aggiornamento crea un nuovo snapshot con timestamp. Le correzioni devono essere tracciabili.

## Collegamento analisi → giocata
Quando l'utente conferma una giocata, il ledger deve salvare `analysis_id` o `analysis_refs` delle analisi che hanno generato la decisione, inclusi P Radar/fair/gate originari. Questo impedisce hindsight bias.

## Retroanalisi
Per una retroanalisi futura il sistema deve recuperare prima gli snapshot originali pre-match e poi confrontarli con risultato e statistiche reali. Vietato ricostruire a posteriori una previsione che non esiste nello storico.

## Query storiche
Il sistema deve poter rispondere a richieste su finestre arbitrarie, incluse 6+ mesi, restituendo:
- tutte le giocate reali con esiti e P/L;
- tutte le previsioni Radar, incluse non giocate;
- hit rate, ROI, yield, drawdown, streak;
- breakdown per lega, mercato, giocatore, squadra, quota, grade, PRE-XI/POST-XI;
- calibrazione P Radar vs frequenza osservata;
- confronto tra BET / NO BET / ATTESA e risultati reali;
- errori di processo e miglioramenti modello.

## Regola operativa immediata
Da questo commit in avanti, ogni nuova analisi Radar significativa deve essere persistita nello schema sopra. Se il salvataggio fallisce, l'output deve segnalarlo come `ANALYSIS_ARCHIVE_WRITE_FAILED` e non fingere che lo storico sia stato aggiornato.
