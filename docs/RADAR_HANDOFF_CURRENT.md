# Radar Unico Value Bet Calcio — Handoff operativo

Ultimo aggiornamento: 30/08/2026

## Scopo
Sistema di analisi pre-match e post-XI per value bet calcio. GitHub orchestra, macchina Windows residenziale raccoglie BetFlag/AAMS, feed pubblicati su branch `betflag-live`, moduli costruiscono XI/tattica/player context/readiness, quindi il Radar calcola P Radar, fair odds, final gate e decisione BET / NO BET / ATTESA. Nessun autobetting.

## Stato attuale acquisizione quote
- BetFlag CURRENT diretto: operativo e sano tramite feed residenziale/Worker.
- File per-fixture BetFlag sul branch `betflag-live`: fonte operativa per quote correnti standard e player props.
- Regola vincolante: se la CURRENT BetFlag fresca/exact è leggibile, la quota è RECUPERATA. La mancanza della OPEN non deve mai essere descritta come `quota non recuperata`.

## Stato attuale movimenti quota
La pipeline esiste già ed è attiva:
- script: `scripts/build_information_move_feed.py`
- fonte storica: Flashscore/Diretta odds comparison con GoldBet opening + GoldBet current e confronto cross-book
- feed principale: `feed/information-move-current.json`
- workflow: `.github/workflows/build-information-move-feed.yml`

Nuovo fast path introdotto il 30/08/2026:
- `feed/information-move-index.json`
- `feed/information-move-fixtures/<slug>.json`
- i task automatici devono leggere PRIMA l'indice e poi SOLO il file della partita interessata; il feed monolitico è fallback/debug.

Gerarchia movimento operativa:
1. fast lookup GoldBet/mercato storico via Flashscore/Diretta;
2. watcher/movement BetFlag per conferma same-book e snapshot intermedi;
3. CURRENT BetFlag direct per prezzo realmente giocabile e final gate.

Quando GoldBet current e BetFlag current sono sostanzialmente allineati, mostrare operativamente `OPEN DI MERCATO/GOLDBET -> CURRENT BETFLAG` senza appesantire l'output. Segnalare la distinzione solo in caso di divergenza materiale.

## Bug aperto prioritario
Le analisi automatiche continuano talvolta a dichiarare di non trovare le quote anche quando il feed BetFlag live è sano e i file per-fixture contengono quote aggiornate.

Questo va trattato come problema di LETTURA/PERCORSO DEL TASK, non come problema di acquisizione BetFlag, finché il feed live risulta sano.

Diagnosi da completare nella prossima chat:
1. verificare esattamente quali file/branch consulta il task automatico nel run che fallisce;
2. verificare se legge per errore file vecchi/vuoti come `feed/betflag-standard-current.json` o `feed/betflag-residential-hot-feed.json` invece dei file per-fixture su `betflag-live`;
3. verificare che il fast path movimenti appena introdotto sia realmente pubblicato e leggibile;
4. correggere il task perché usi direttamente l'indice fixture BetFlag e il relativo file per-partita;
5. fare test pratico su una partita imminente e confermare: quote CURRENT, OPEN/movimento, player props, P/fair/gate.

## Regole operative quote / errori
Distinguere sempre:
1. `MERCATO BETFLAG NON QUOTATO / NON DISPONIBILE`
2. `ACQUISIZIONE BETFLAG FALLITA / QUOTA CURRENT NON RECUPERATA`
3. `CURRENT BETFLAG RECUPERATA MA OPEN/MOVIMENTO INCOMPLETO`

Non confondere mai il caso 3 con il caso 2.

## Task automatici aggiornati
- `Radar Pre-XI + Watch`
- `Radar XI + Final Gate`

Entrambi sono stati aggiornati per:
- usare BetFlag CURRENT direct per decisione;
- usare fast lookup dei movimenti come prima scelta;
- non aspettare lo storico BetFlag se la OPEN GoldBet/mercato è già disponibile esternamente;
- non dichiarare quote mancanti solo per assenza di OPEN.

## Modifiche recenti rilevanti
- commit fast lookup script: `303dec8c5ee0a0e8286412b045a5f9796d01477f`
- commit workflow fast lookup: `2455e0762cd4c7ff50dbb873e4940a9e3ae264ed`

## Come riprendere in una nuova chat
Prompt consigliato:

`Continua il progetto Radar Unico Value Bet Calcio. Leggi prima docs/RADAR_HANDOFF_CURRENT.md nel repository pceresetti-arch/radar-goldbet-feed e riparti dal bug prioritario: le analisi automatiche continuano a dichiarare di non trovare le quote nonostante il feed BetFlag live sia sano. Verifica il percorso di lettura del task, correggilo e fai un test pratico.`
