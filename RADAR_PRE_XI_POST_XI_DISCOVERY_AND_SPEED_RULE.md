# Radar Unico — PRE-XI → POST-XI Discovery + Speed Budget

Stato: **OPERATIVO E VINCOLANTE**
Data: 2026-08-26

## 1. Principio
La pre-analisi deve anticipare il lavoro, ma non può diventare un filtro chiuso. Dopo l'XI ufficiale il Radar deve fare nello stesso ciclo:
1. rivalutazione di tutte le candidate PRE-XI;
2. nuova discovery completa sull'XI reale per trovare value non visibili prima.

La regola è: **la pre-analisi accelera il Radar ma non restringe il Radar**.

## 2. PRE-XI obbligatorio
Prima delle formazioni ufficiali il Radar deve già cercare candidate potenzialmente forti usando, quando disponibili:
- probabili XI e affidabilità delle fonti;
- conferenze stampa, convocati, report allenamenti e fonti locali affidabili;
- infortuni, rientri, acciacchi, turnover e concorrenza interna;
- probabilità di titolarità;
- ruolo/posizione prevista e possibili cambi modulo;
- minuti attesi P60/P75/P90 con affidabilità dichiarata;
- rigoristi e gerarchie piazzati;
- xG/npxG, tiri, SOT, tocchi area, big chances e quota xG squadra;
- compagni creatori e concorrenti che cannibalizzano tiri/xG;
- matchup giocatore-zona-sistema;
- qualità offensiva/difensiva, casa/trasferta, pressing, ritmo, transizioni, piazzati e League Scoring Environment;
- team xG, P(0/1/2/3+ gol) e modulo 1T prima di distribuire probabilità sui giocatori.

Classificazioni PRE-XI:
- `PRE_LINEUP_BET_A/B/C` solo se l'edge è robusto all'incertezza XI;
- `CONDITIONAL_BET` se dipende da titolarità/ruolo/minuti;
- `WATCH_FORTE`;
- `WAIT/NO_BET_PRE_XI`.

Ogni candidata conserva baseline PRE-XI con timestamp, ruolo previsto, minuti previsti, P Radar, fair, gate preliminare, motivazione e fonte prezzo.

## 3. Shortlist persistente ma non esclusiva
La shortlist PRE-XI deve essere riutilizzata quando esce la formazione per evitare lavoro duplicato. Però non può limitare la scansione successiva.

È vietato trattare le candidate PRE-XI come unico universo di giocatori/mercati da controllare POST-XI.

## 4. XI ufficiale — dual lane
Appena compare un XI ufficiale completo e verificato, eseguire entrambe le corsie.

### A. PRE-XI REVALIDATION
Per ogni candidata preliminare:
- confermare/smentire titolarità;
- confrontare ruolo previsto e ruolo reale;
- aggiornare minuti e rischio sostituzione;
- aggiornare creatori, concorrenza/cannibalizzazione e piazzati;
- aggiornare matchup;
- aggiornare team xG, P Radar, fair e FINAL GATE;
- aggiornare prezzo e movimento;
- promuovere, declassare o eliminare la candidata.

### B. POST-XI FULL REDISCOVERY
Rieseguire una scansione completa dell'XI reale anche su giocatori e mercati non presenti nella shortlist PRE-XI.

Cercare esplicitamente nuove value generate da:
- cambio ruolo inatteso;
- esterno schierato punta / punta spostata;
- assenza di un finalizzatore importante;
- nuovo rigorista/piazzato;
- nuovo creatore titolare;
- lato difensivo avversario più debole del previsto;
- cambio modulo;
- diversa occupazione dell'area;
- variazione dei minuti attesi;
- nuova combinazione creatore-finisher;
- mercato player diverso che monetizza meglio la tesi (es. SOT, Gol o Assist, Marcatore 1T).

La scansione POST-XI deve includere tutti i mercati realmente offerti.

## 5. Etichette storico
Ogni candidata deve essere marcata:
- `PRE_XI_IDENTIFIED` se già individuata prima;
- `POST_XI_DISCOVERY` se nasce solo dopo l'XI ufficiale;
- `PRE_XI_PROMOTED_POST_XI` se era WATCH/CONDITIONAL e diventa BET;
- `PRE_XI_INVALIDATED_POST_XI` se l'XI reale distrugge la tesi.

Queste etichette entrano nello storico per misurare quanta value viene anticipata PRE-XI e quanta nasce solo con la formazione.

## 6. Quote player — scan ampio, certificazione stretta
Workflow player:
1. scansione massiva BetFlag/AAMS per discovery;
2. filtro per fixture e confronto dei mercati;
3. modello e shortlist;
4. certificazione esatta realtime solo sulle candidate finali che possono superare il gate.

Percorso finale:
`Radar → https://radar-betflag-v7.p-ceresetti.workers.dev/live/player-price → BetFlag/AAMS direct → exact fixture+player+market+selection/line → proof/fingerprint → FINAL GATE`.

Richiedere match univoco, fonte sana, freshness valida e `price_gate_eligible=true`. Se matching ambiguo/assente, nessun prezzo operativo e nessuna BET.

## 7. Test velocità certificato
Riferimento: `feed/quote-realtime-test-latest.json` del 2026-08-26.

Risultati:
- 3 casi positivi tutti HTTP 200;
- tutti unique exact match e `price_gate_eligible=true`;
- controllo negativo player inesistente correttamente rifiutato;
- repeat identity e repeat price stabili;
- latenza media end-to-end circa 2,326 s;
- mediana circa 2,633 s;
- massimo positivo circa 2,738 s;
- mean upstream circa 2172 ms.

Non serializzare una chiamata esatta per ogni giocatore/mercato: usare batch scan e certificare solo i finalisti.

## 8. Speed Budget / fail-fast
Target operativo, non garanzia assoluta:
- 1 partita con XI e fonti normali: obiettivo circa `45–90 s` dalla richiesta alla shortlist finale;
- 3 partite: obiettivo circa `~2 min`;
- 5 partite: obiettivo circa `~3 min`.

Regole per evitare blocchi:
- parallelizzare recuperi indipendenti;
- usare batch scan per quote/mercati;
- non interrogare serialmente ogni prop;
- limitare verifiche esatte alle candidate finali;
- se una fonte secondaria è lenta/fallisce, passare al fallback o dichiarare `NON VERIFICABILE`;
- non ritardare il verdetto per dati ornamentali non materialmente decisivi;
- se manca un blocco obbligatorio, restituire `ANALISI INCOMPLETA / ATTESA` indicando cosa manca invece di restare appesi;
- vicino al kickoff usare la corsia rapida: `XI → matchup/modello → TRUE OPEN/movement → props → exact price → FINAL GATE`.

## 9. Output prioritario
Mostrare prima:
- partita;
- mercato/selezione;
- origine `PRE_XI_IDENTIFIED` o `POST_XI_DISCOVERY`;
- quota operativa e fonte;
- P Radar;
- fair;
- FINAL GATE;
- edge;
- classe A/B/C oppure NO BET/ATTESA;
- 2-4 motivi principali;
- rischio principale;
- movimento quote rilevante.

Il testo descrittivo può seguire, ma non deve ritardare inutilmente il verdetto operativo.

## 10. Cross-market movement
Il modello incrociato resta governato da `RADAR_MARKET_CONFIRMATION_MODEL.md` e rimane in `RESEARCH_SHADOW_MODE` finché non supera validazione OOS. Raccoglie TRUE OPEN/checkpoint, probabilità de-vigged, family scores, coerenza e accelerazione post-XI, ma non applica pesi arbitrari al FINAL GATE.

## 11. Audit
Archiviare, quando disponibili:
- baseline e shortlist PRE-XI;
- XI ufficiale + fingerprint;
- delta probabile→ufficiale;
- candidate rivalutate;
- nuove `POST_XI_DISCOVERY`;
- prezzi discovery vs exact finali;
- latenza pipeline e principali source failures;
- decisione finale e motivazioni.

Il Backtest deve misurare separatamente performance PRE-XI vs POST-XI discovery, valore incrementale della rediscovery, tempo medio/P50/P95 della pipeline e quota di analisi incomplete dovute a timeout/failure.