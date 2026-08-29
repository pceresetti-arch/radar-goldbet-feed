# Radar Unico — Quote Resolution Rule

## Stato: VINCOLANTE

Questa regola disciplina ogni richiesta del tipo “trova la quota”, “meglio X?”, “quanto paga?”, “dammi BET/NO BET”, screening completo post-XI e qualsiasi FINAL PRICE GATE.

## Fonte operativa primaria

Per BetFlag usare sempre, in questo ordine:

1. Worker v7 live (`radar-betflag-v7.p-ceresetti.workers.dev`) per lookup exact quando la corsia live è disponibile.
2. `feed/betflag-fixtures-index.json` per individuare la fixture corrente.
3. File specifico `feed/betflag-fixtures/<fixture>.json` per leggere tutti i mercati standard e player props della partita.
4. Solo dopo un fallimento verificato della corsia BetFlag usare fonti esterne come benchmark/cross-check, mai sostituendole silenziosamente alla quota BetFlag.

## Regola anti-regressione

Una richiesta quota NON può essere chiusa con ricerca web generica, aggregatori o “quota non trovata” prima di aver verificato il feed BetFlag v7.

Se la fixture è presente e il feed è `source_healthy=true` e fresco:
- il mercato presente nel file = QUOTA BETFLAG RECUPERATA;
- il giocatore presente ma il mercato assente = MERCATO NON QUOTATO per quel giocatore in quello snapshot;
- la fixture ha `player_count=0` = PLAYER PROPS NON ESPOSTI nello snapshot corrente; non chiamarlo errore di acquisizione;
- la fixture contiene player props ma il giocatore cercato non compare = GIOCATORE/MERCATO NON ESPOSTO o naming mismatch da verificare, non “quota inesistente” automaticamente.

Se la fixture manca dal feed oppure freshness/health falliscono:
- classificare `ACQUISIZIONE FALLITA / SNAPSHOT NON AFFIDABILE`;
- tentare immediatamente lookup live exact e refresh del bridge;
- solo se anche il live exact fallisce passare ai fallback.

## Matching obbligatorio

Prima di restituire una quota player devono coincidere:
- fixture univoca;
- giocatore;
- mercato;
- eventuale linea;
- selezione;
- quota > 0;
- fonte `BETFLAG_AAMS_DIRECT`;
- feed healthy/fresh o prova live equivalente.

## Output minimo

Ogni risposta operativa deve distinguere chiaramente uno dei seguenti stati:
- `BETFLAG QUOTA RECUPERATA @X`;
- `MERCATO NON QUOTATO / NON ESPOSTO`;
- `ACQUISIZIONE FALLITA / QUOTA NON RECUPERATA`;
- `MATCH AMBIGUO — NON USARE PER FINAL GATE`.

È vietato trasformare automaticamente “non trovato” in “non quotato”.

## Integrazione con analisi Radar

Quando l’utente chiede se una giocata “è meglio”, il Radar deve recuperare prima la quota reale BetFlag del mercato alternativo richiesto e solo dopo confrontare probabilità, fair odds, edge e gate. Non deve rispondere soltanto in termini teorici se la quota è tecnicamente recuperabile.

Per screening post-XI, se il file fixture contiene player props, devono essere scandagliati sistematicamente tutti i mercati disponibili prima della shortlist: Marcatore, Marcatore 1T, 1° Marcatore, Assist, Gol/Assist, Marcatore o Sostituto, Marcatore Plus, tiri, tiri in porta e relative linee/Plus.

## Obiettivo operativo

La pipeline quote deve diventare deterministica: BetFlag v7 -> fixture exact -> mercato exact -> quota -> FINAL GATE. Il web resta supporto informativo, non il percorso primario per la quota BetFlag.