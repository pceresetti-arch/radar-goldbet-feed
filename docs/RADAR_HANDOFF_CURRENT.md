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

Fast path introdotto il 30/08/2026:
- `feed/information-move-index.json`
- `feed/information-move-fixtures/<slug>.json`
- i task automatici devono leggere PRIMA l'indice e poi SOLO il file della partita interessata; il feed monolitico è fallback/debug.

Gerarchia movimento operativa:
1. fast lookup GoldBet/mercato storico via Flashscore/Diretta;
2. watcher/movement BetFlag per conferma same-book e snapshot intermedi;
3. CURRENT BetFlag direct per prezzo realmente giocabile e final gate.

Quando GoldBet current e BetFlag current sono sostanzialmente allineati, mostrare operativamente `OPEN DI MERCATO/GOLDBET -> CURRENT BETFLAG` senza appesantire l'output. Segnalare la distinzione solo in caso di divergenza materiale.

## Bug prioritario quote automatiche — diagnosi 30/08/2026
Il bug osservato era: alcune analisi automatiche dichiaravano `quote non recuperate` nonostante il feed BetFlag live fosse sano.

La verifica manuale del percorso ha confermato che il problema NON è l'acquisizione BetFlag:
- `feed/betflag-residential-fixtures-index.json` su branch `betflag-live` è leggibile, `source_healthy=true` e contiene le fixture operative;
- test su `Utrecht - PSV Eindhoven`: fixture trovata nell'indice, file `feed/betflag-residential-fixtures/utrecht-psv-eindhoven.json` leggibile su `betflag-live`, con 41 mercati standard e 232 player props;
- nel test la CURRENT BetFlag 1X2 PSV era `1.50`;
- `feed/information-move-index.json` su `main` è pubblicato e leggibile;
- per Utrecht–PSV il fast path movimento conteneva GoldBet opening `1.63` e GoldBet current `1.50` sulla vittoria PSV.

Conclusione: quando un run automatico continua a dire che non trova le quote, va classificato come problema di LETTURA/PERCORSO DEL TASK, non come problema BetFlag, salvo prova contraria sul feed live.

## Correzione applicata ai task automatici il 30/08/2026
I task attivi `Radar Pre-XI + Watch` e `Radar XI + Final Gate` sono stati irrigiditi con un PRE-FLIGHT obbligatorio:
1. prima di qualsiasi analisi devono usare il connettore GitHub e leggere `feed/betflag-residential-fixtures-index.json` con ref ESPLICITO `betflag-live`;
2. devono conservare `generated_at`, `source_healthy`, `fixture_count`;
3. se la lettura fallisce devono emettere `BETFLAG PATH READ FAILURE — betflag-live/index`, non `quote non recuperate`;
4. se il preflight passa con `source_healthy=true`, i feed legacy su `main` non possono diventare fonte primaria;
5. per ogni partita devono prendere il campo `file` dall'indice e leggere ESATTAMENTE quel file ancora con ref=`betflag-live`;
6. se fixture + file sono sani e contengono quote, lo stato obbligatorio è `CURRENT BETFLAG RECUPERATA`;
7. se manca solo OPEN/movimento, lo stato obbligatorio è `CURRENT BETFLAG RECUPERATA — OPEN/MOVIMENTO INCOMPLETO`;
8. `ACQUISIZIONE BETFLAG FALLITA / QUOTA CURRENT NON RECUPERATA` è consentito solo se index/file non sono realmente leggibili o la fixture non è recuperabile dopo verifica identità.

## Standard obbligatorio di analisi POST-XI — aggiornamento 30/08/2026
Quando entrambe le formazioni ufficiali sono disponibili, ogni analisi automatica deve essere realmente approfondita e completa, sul livello qualitativo dell'analisi manuale Utrecht–PSV del 30/08/2026. Non è sufficiente riportare XI, forma recente, 1-2 note generiche e quote.

Prima di qualsiasi verdetto finale BET / NO BET devono essere completati tutti questi blocchi:
1. FORMAZIONE CONTRO FORMAZIONE: confronto XI vs XI ruolo per ruolo e linea per linea, moduli in possesso/non possesso, altezza, ampiezza, mezzi spazi, costruzione, pressing, trigger di pressione, transizioni, cross/cut-back, palle inattive e vulnerabilità specifiche;
2. ZONE E MATCHUP CHIAVE: duelli individuali e di zona per centravanti, esterni, trequartisti, mezzali offensive, terzini/quinti e altri profili rilevanti;
3. ASSENZE / PANCHINA / MINUTI / CONDIZIONE: indisponibili, rientri, acciacchi, rotazioni, congestione calendario, riposo, viaggio, rischio sostituzione e qualità delle alternative;
4. CONTESTO PARTITA: classifica, obiettivi, andata/ritorno se coppa, game state plausibile, incentivi a ritmo alto/basso e possibilità di gestione;
5. MODELLO GOL/XG: xG squadra e match, distribuzione 0/1/2/3/4+ gol, BTTS, Over/Under, team total, profilo 1T/2T e P(almeno 1 gol 1T);
6. PLAYER CONTEXT COMPLETO: scorer allocation e assist allocation, xG/xA, tiri/SOT, big chances, tocchi area, ruolo reale, piazzati/rigori, minuti e concorrenza interna;
7. SCANSIONE PLAYER PROPS: Marcatore anytime, Marcatore 1T/2T, Primo Marcatore, Gol o Assist, Assist, Marcatore Plus / Marc o Sostituto e altri props disponibili, confrontando i mercati collegati della stessa tesi;
8. MERCATI STANDARD E CORRELATI: 1X2, DNB/handicap, doppia chance, Goal/No Goal, O/U, team total, 1T/2T e combo quando disponibili;
9. QUOTE E MOVIMENTI: CURRENT BetFlag exact dal file per-fixture, OPEN/movimento separato, eventuale divergenza GoldBet/BetFlag;
10. PRICE GATE: solo alla fine calcolare P Radar, fair odds, FINAL GATE e verdetto.

Regola anti-scorciatoia: con XI ufficiali la sezione `FORMAZIONE CONTRO FORMAZIONE` deve contenere almeno 3-6 osservazioni concrete e i matchup devono incidere esplicitamente su P Radar / fair / gate. Se un blocco essenziale non è completabile, l'output obbligatorio è `ANALISI POST-XI INCOMPLETA — NESSUN VERDETTO FINALE`, non una BET/NO BET abbreviata.

Il task `Radar Pre-XI + Watch`, se incontra entrambe le formazioni ufficiali, deve cessare il PRE-XI per quella gara e trasformarsi immediatamente nella stessa analisi POST-XI completa.

## Percorso quote vincolante per ogni run
CURRENT BetFlag:
1. repository `pceresetti-arch/radar-goldbet-feed`;
2. branch `betflag-live`;
3. leggere `feed/betflag-residential-fixtures-index.json`;
4. trovare partita + orario;
5. prendere il campo `file`;
6. leggere quel file ancora da `betflag-live`;
7. validare `source_healthy`, `identity_consistent`, `price_gate_fixture_eligible`;
8. usare standard + player props del file per P Radar / fair / gate.

Movimenti:
1. branch `main`;
2. leggere `feed/information-move-index.json`;
3. trovare la partita;
4. leggere SOLO il campo `file` relativo alla fixture;
5. usare GoldBet opening/current, implied probability shift e consensus;
6. confrontare con CURRENT BetFlag.

Vietato usare come fonte primaria per la CURRENT:
- `feed/betflag-standard-current.json` se vuoto/stale;
- `feed/betflag-residential-hot-feed.json` se vuoto/stale;
- file per-fixture cercati erroneamente su `main`;
- feed monolitici quando è disponibile il file per-partita.

## Regole operative quote / errori
Distinguere sempre:
1. `MERCATO BETFLAG NON QUOTATO / NON DISPONIBILE`
2. `ACQUISIZIONE BETFLAG FALLITA / QUOTA CURRENT NON RECUPERATA`
3. `CURRENT BETFLAG RECUPERATA MA OPEN/MOVIMENTO INCOMPLETO`
4. `BETFLAG PATH READ FAILURE — betflag-live/index` o file specifico, quando il problema è tecnico di lettura del task.

Non confondere mai il caso 3 o 4 con il caso 2.

## Task automatici attivi
- `Radar Pre-XI + Watch`
- `Radar XI + Final Gate`

Entrambi ora:
- eseguono preflight GitHub branch-aware;
- usano BetFlag CURRENT direct per decisione;
- usano fast lookup dei movimenti come prima scelta;
- non aspettano lo storico BetFlag se la OPEN GoldBet/mercato è già disponibile esternamente;
- non dichiarano quote mancanti solo per assenza di OPEN;
- devono mostrare un errore di percorso esplicito se il connettore/branch non è leggibile;
- con XI ufficiali devono eseguire il POST-XI completo prima di qualsiasi verdetto finale.

## Modifiche recenti rilevanti
- commit fast lookup script: `303dec8c5ee0a0e8286412b045a5f9796d01477f`
- commit workflow fast lookup: `2455e0762cd4c7ff50dbb873e4940a9e3ae264ed`
- task preflight quote-path: aggiornato 30/08/2026 su entrambi i task automatici attivi;
- hard gate di deep analysis POST-XI: aggiornato 30/08/2026 su entrambi i task automatici attivi.

## Correzione consumer quote — 01/09/2026
Il test reale su Wolfsberger–LASK ha dimostrato che produzione e pubblicazione erano sane, mentre l'analisi manuale aveva saltato il repository ed era ricaduta sul web pubblico. Al momento del test:
- `main/feed/betflag-fixtures-index.json` era fresco e conteneva Wolfsberger–LASK;
- il file esatto `main/feed/betflag-fixtures/wolfsberger-lask-linz.json` conteneva 41 mercati standard e 276 quote player aggregate;
- il fallback residenziale `betflag-live/feed/betflag-residential-fixtures/wolfsberger-lask-linz.json` conteneva 41 mercati standard e 138 righe player;
- la quota CURRENT BetFlag di Giacomo Vrioni marcatore era 3.10.

È stato aggiunto un guardiano lato consumo:
- script: `scripts/validate_radar_quote_consumer.py`;
- test: `tests/test_validate_radar_quote_consumer.py`;
- health output: `feed/radar-quote-consumer-health.json`;
- il workflow `radar-betflag-v7-live-bridge.yml` ora fallisce se indice e file per-fixture non sono realmente leggibili, hanno identità incoerente o non contengono prezzi CURRENT.

Percorso vincolante aggiornato per run automatici e analisi manuali/chat:
1. leggere su `main` `feed/betflag-fixtures-index.json` e usare ESATTAMENTE il campo `file` della partita;
2. validare `source_healthy`, freschezza, identità e presenza quote nel file;
3. usare il CURRENT del file prima di qualsiasi ricerca web;
4. se il percorso Worker/main è assente o degradato, usare il fallback residenziale su ref esplicito `betflag-live`;
5. la ricerca web pubblica è soltanto ultimo fallback e non può giustificare “quota non recuperata” se uno dei due percorsi repository è sano.

Distinzione directory/branch:
- `feed/betflag-fixtures/*` è il percorso Worker-backed pubblicato su `main`;
- `feed/betflag-residential-fixtures/*` è il percorso residenziale pubblicato su `betflag-live`;
- non cercare mai la directory residenziale su `main`.

## Freschezza/Fatica e Combo marcatori — regola operativa 01/09/2026
Ogni FULL Radar deve includere un modulo quantitativo Freschezza/Fatica per squadra e giocatori, con Freshness Score, Freshness Delta e correzione esplicita di minuti attesi, P Radar, fair, gate e distribuzione 1T/2T quando il carico è materiale.

Per ogni candidato scorer deve inoltre essere costruita la matrice dei mercati collegati e delle Combo marcatori disponibili. Le combo devono usare probabilità congiunte e correlazioni, non il prodotto cieco delle probabilità. Se una combo è modellabile ma non presente nel file BetFlag, lo stato corretto è `COMBO MODELLATA — QUOTA BETFLAG NON PRESENTE NEL FEED`; non inventare né sostituire una quota esterna.

## Prossimo controllo consigliato
Osservare il prossimo run automatico su una partita imminente e verificare che l'output riporti:
- `CURRENT BETFLAG RECUPERATA` con quota exact;
- OPEN/movimento separato;
- player props letti dal file per-fixture;
- formazione contro formazione realmente sviluppata;
- zone e matchup chiave;
- xG/gol/1T e player allocation;
- P Radar / fair / final gate;
- nessun falso `quote non recuperate` se il preflight ha passato.

Se compare ancora un falso negativo o una analisi troppo superficiale, il run deve fornire il punto preciso di failure e non una diagnosi generica.

## Come riprendere in una nuova chat
Prompt consigliato:

`Continua il progetto Radar Unico Value Bet Calcio. Leggi prima docs/RADAR_HANDOFF_CURRENT.md nel repository pceresetti-arch/radar-goldbet-feed. Il feed BetFlag live, il fast path movimenti e l'hard gate di deep analysis POST-XI sono già attivi; riparti dal monitoraggio del prossimo run automatico e correggi solo eventuali path read failure o scorciatoie di analisi residue, senza ricominciare l'architettura.`
