# Radar V2 — T-30 Readiness Policy

## Regola operativa vincolante
Entro 30 minuti dal kickoff (`T-30`) il Radar deve avere gia' completato il pacchetto operativo necessario alla decisione.

A T-30 NON deve iniziare l'analisi: deve soltanto finalizzare/aggiornare i dati dinamici e produrre il verdetto operativo.

## Pacchetto obbligatorio entro T-30
- partita identificata e kickoff verificato in Europe/Rome;
- XI ufficiale acquisito quando pubblicato e relativo fingerprint;
- dati squadra/giocatori e matchup gia' raccolti;
- analisi formazione-vs-formazione completata;
- modello partita e player model completati;
- scorer allocation completata;
- tutti i mercati attesi verificati con stato terminale valido;
- quote correnti operative fresche per i mercati rilevanti;
- apertura certificata quando realmente disponibile;
- storico snapshot gia' accumulato;
- checkpoint T-40 acquisito quando temporalmente disponibile;
- checkpoint T-30 acquisito;
- fair odds, FINAL GATE, edge e rischio gia' calcolati;
- Final Judge pronto a restituire BET / NO_BET / BORDERLINE / WAITING_DATA.

## Distinzione fondamentale: close vs T-30
La vera closing line di mercato esiste solo a ridosso del kickoff e non puo' essere conosciuta 30 minuti prima.

Entro T-30 il Radar deve quindi avere:
- `TRUE_OPEN_CERTIFIED` quando certificabile;
- sequenza degli snapshot osservati;
- `T-40`;
- `T-30`;
- `CURRENT_T30` / quota attuale operativa fresca.

La `TRUE_CLOSE` viene salvata ex post/pre-kickoff quando realmente osservata e serve a CLV/audit, ma NON e' prerequisito conoscibile a T-30.

## Regola anti-ritardo
Qualunque blocco statico o lento deve essere completato prima di T-30. Dopo T-30 sono consentiti solo aggiornamenti incrementali di:
- quote;
- movimenti;
- eventuali variazioni XI dell'ultimo minuto;
- price gate/final judge conseguenti ai delta.

Non rifare l'intera analisi da zero dopo T-30.

## Stato a T-30
- `T30_READY`: pacchetto completo e quota attuale fresca; decisione operativa consentita.
- `T30_BLOCKED_CRITICAL_DATA`: manca un dato critico; nessuna falsa analisi completa.
- `T30_PARTIAL_NONCRITICAL`: manca solo un dato non decisivo, con confidence haircut esplicito.

## Obiettivo
L'utente deve poter ricevere almeno 30 minuti prima del kickoff un output gia' utilizzabile per decidere se piazzare una scommessa, senza dover aspettare ulteriori ricerche strutturali.
