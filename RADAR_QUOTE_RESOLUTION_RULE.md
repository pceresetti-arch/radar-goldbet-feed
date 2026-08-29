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

## Player Market Optimization — REGOLA VINCOLANTE

Quando l’utente indica un giocatore, il compito del Radar NON è cercare soltanto la quota del mercato nominato. Deve determinare quale sia il modo migliore di giocare quel giocatore tra TUTTI i mercati BetFlag disponibili, usando prima un’analisi calcistica completa e poi il confronto prezzo/probabilità.

Ordine obbligatorio:

1. ANALISI TOTALE DEL GIOCATORE E DEL MATCH
   - XI ufficiale, titolarità, ruolo reale e posizione media prevista;
   - minuti attesi e rischio sostituzione;
   - stato fisico, forma e carico recente;
   - rigori, punizioni, corner e altre palle inattive;
   - xG, xA, tiri, tiri in porta, big chances, tocchi in area e shot share;
   - scorer allocation rispetto ai compagni: quota reale di pericolosità individuale sul totale offensivo della squadra;
   - avversario diretto, lato di campo, matchup, altezza linea, pressing, transizioni e spazi concessi;
   - probabilità e distribuzione gol della squadra e della partita;
   - profilo 1° tempo / 2° tempo;
   - contesto competitivo, necessità di risultato, rotazioni e scenario partita;
   - eventuali movimenti quota rilevanti e consenso di mercato quando disponibili.

2. SCANSIONE COMPLETA DEI MERCATI DEL GIOCATORE
   Devono essere letti e confrontati tutti quelli effettivamente quotati, inclusi quando presenti:
   - Marcatore anytime;
   - Marcatore 1° tempo;
   - Marcatore 2° tempo;
   - 1° Marcatore;
   - 1° Marcatore o Sostituto;
   - Marcatore o Sostituto;
   - Marcatore Plus;
   - Gol o Assist / equivalenti;
   - Assist;
   - Assist o Sostituto;
   - Gol e Assist;
   - Doppietta / Tripletta;
   - tiri totali giocatore, tutte le linee;
   - tiri totali Plus, tutte le linee;
   - tiri in porta, tutte le linee;
   - tiri in porta Plus, tutte le linee;
   - qualunque altro player prop esposto da BetFlag per quella fixture.

3. PROBABILITÀ SEPARATA PER OGNI MERCATO
   Non trasferire automaticamente P(marcatore) a mercati diversi. Stimare separatamente, quando applicabile:
   - P(anytime);
   - P(gol 1T);
   - P(gol 2T);
   - P(primo marcatore);
   - P(assist);
   - P(gol o assist);
   - distribuzione tiri e tiri in porta per ciascuna linea;
   - probabilità degli equivalenti Plus/Sostituto considerando la specifica regola di regolamento del mercato.

4. FAIR ODDS, EDGE E PRICE GATE
   Per ogni mercato candidato calcolare:
   - probabilità stimata;
   - fair odds = 1 / probabilità;
   - quota reale BetFlag;
   - edge rispetto alla fair;
   - gate minimo accettabile;
   - robustezza dell’edge rispetto a incertezza di minuti, ruolo e scenario gara.

5. SCELTA DEL MODO MIGLIORE DI GIOCARE IL PLAYER
   La raccomandazione finale deve essere il mercato con il miglior rapporto tra:
   - edge reale;
   - probabilità di successo;
   - compatibilità con il profilo del giocatore;
   - rischio specifico del mercato;
   - qualità/freschezza della quota.

   La quota più alta NON è automaticamente la migliore giocata. Un mercato più protetto può essere preferibile se offre edge superiore o rischio molto più basso; viceversa un mercato più aggressivo può essere preferibile quando il pricing compensa davvero il rischio.

6. CLASSIFICA FINALE
   Per ogni giocatore analizzato il Radar deve restituire almeno:
   - `MIGLIORE GIOCATA`;
   - eventuale `SECONDA SCELTA`;
   - eventuale `EVITARE` per mercati apparentemente attraenti ma sotto fair/gate;
   - `NO BET SUL GIOCATORE` se nessun mercato quotato offre valore sufficiente.

## Interpretazione delle domande dell’utente

- “Come lo gioco?” = eseguire l’intera Player Market Optimization.
- “È meglio Marcatore Plus?” = NON confrontare solo due etichette: analizzare il giocatore e tutti i suoi mercati disponibili, poi dire se Plus è davvero il migliore.
- “Neanche primo tempo?” = recuperare quota reale 1T, stimare P(1T) separatamente e confrontarla con tutte le alternative sensate.
- “Quanto paga?” = lookup quota exact; se il contesto è decisionale, non fermarsi al numero ma indicare se quella quota è giocabile rispetto alla fair.

## Integrazione con analisi Radar

Quando l’utente chiede se una giocata “è meglio”, il Radar deve recuperare la quota reale BetFlag del mercato richiesto, ma deve anche verificare se esiste un mercato migliore sullo stesso giocatore. Non deve rispondere soltanto in termini teorici se le quote sono tecnicamente recuperabili.

Per screening post-XI, se il file fixture contiene player props, devono essere scandagliati sistematicamente tutti i mercati disponibili prima della shortlist.

## Obiettivo operativo

La pipeline decisionale deve diventare:

BetFlag v7 -> fixture exact -> player exact -> analisi totale player/match -> scansione di tutti i mercati player -> probabilità separate -> fair odds -> quote reali -> edge/gate -> MIGLIORE GIOCATA / NO BET.

Il web resta supporto informativo per dati calcistici, formazione, contesto e cross-check, non il percorso primario per la quota BetFlag.