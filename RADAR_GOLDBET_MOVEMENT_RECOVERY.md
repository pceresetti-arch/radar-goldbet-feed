# Radar Unico — GoldBet movement recovery protocol

## Scopo
Rendere sempre recuperabile, quando tecnicamente esposta dal bookmaker/provider, la sequenza SAME BOOKMAKER GoldBet:

`TRUE OPEN -> snapshot intermedi -> T-40 -> T-30 -> CURRENT/REQUEST`

senza sostituire silenziosamente GoldBet con quote di altri bookmaker.

## Percorsi di acquisizione

### 1. GoldBet direct standard tracker
Resta il percorso primario quando sano. Le serie devono restare etichettate `GOLDBET_DIRECT_STANDARD`.

### 2. GoldBet SAME BOOKMAKER via Diretta/Flashscore — recovery obbligatorio
Se il percorso diretto è stale, in 429, non raggiungibile o non facilmente interrogabile dalla sessione Radar, usare il workflow:

- `.github/workflows/goldbet-movement-resilient.yml`
- request: `radar-movement-request.json`
- output compatto: `feed/radar-movement-diretta-current.json`
- stato/snapshot: `feed/goldbet-diretta-movement-state.json`

Il provider viene interrogato sul bookmaker specifico **GoldBet** risolto dal menu bookmaker (ID osservato 188 nei test del 28/08/2026). Questa serie è SAME BOOKMAKER e NON cross-book; la provenienza deve restare `GOLDBET_SAME_BOOKMAKER_VIA_DIRETTA`.

## TRUE OPEN
Il campo bookmaker-specific `opening` della risposta Diretta/Flashscore viene conservato come `TRUE_OPEN_CERTIFIED` quando presente. Non deve essere confuso con `first_seen`.

Se `opening` manca, il Radar NON inventa la quota iniziale e deve dichiarare:

`TRUE OPEN NON CERTIFICATA — MOVIMENTO INCOMPLETO`

## Snapshot al momento della richiesta
Ogni analisi Radar che richiede movimento deve aggiornare `radar-movement-request.json` con almeno:

- fixture;
- kickoff ISO quando noto;
- opzionalmente market/line/period/selection.

Il push forza una nuova interrogazione bookmaker-specific e salva `request_current` con timestamp. Questo è il punto CURRENT/REQUEST usato nell'analisi, non una vecchia quota di cache.

## T-40 / T-30
Il workflow gira anche ogni 5 minuti sulle fixture attualmente richieste. Inoltre ogni run Radar T-40/T-30 deve forzare il request on-demand: non affidarsi soltanto al cron GitHub.

Per ciascun checkpoint viene mantenuto il campione osservato più vicino al target, entro massimo 7,5 minuti. Un campione più vicino sostituisce automaticamente quello precedente.

Qualità checkpoint:
- `EXACT_NEAR`: distanza <= 1,5 min;
- `GOOD`: <= 3 min;
- `ACCEPTABLE`: <= 5 min;
- `FALLBACK`: <= 7,5 min.

La distanza reale dal target deve sempre essere mostrata. Non chiamare T-40 un punto fuori finestra o un punto ricostruito senza prova.

## SAME BOOKMAKER / SAME IDENTITY
Per dichiarare movimento valido devono coincidere:

- bookmaker GoldBet;
- fixture;
- mercato;
- periodo;
- linea;
- selezione.

Per Over/Under una linea 2.5 non può essere confrontata con 3.5. Per mercati 1T e FT le serie sono separate.

## Ordine di recovery obbligatorio nel Radar
1. Richiedere snapshot CURRENT on-demand.
2. Leggere TRUE OPEN bookmaker-specific.
3. Leggere snapshot intermedi / T-40 / T-30 già persistiti.
4. Se GoldBet direct è sano, usarlo come serie primaria e usare Diretta/Flashscore GoldBet per conferma/apertura.
5. Se GoldBet direct fallisce o è stale, usare `GOLDBET_SAME_BOOKMAKER_VIA_DIRETTA` come recovery same-bookmaker.
6. Solo dopo usare altri bookmaker come cross-check separato.
7. Se anche recovery GoldBet fallisce, dichiarare `TRUE OPEN NON CERTIFICATA — MOVIMENTO INCOMPLETO`.

## Regola per le analisi future
Il Radar NON può più concludere semplicemente “movimento GoldBet non disponibile” senza aver prima tentato il request on-demand e il recovery SAME BOOKMAKER via Diretta/Flashscore.

## Validazione reale iniziale — 28/08/2026
Test su:
- Al Nassr - Al Taawoun;
- Al Khaleej - Al Hilal.

Entrambe le fixture sono state risolte correttamente nel feed Saudi Professional League, GoldBet bookmaker ID 188, con `opening` e `current` per 1X2, Over/Under e Goal/No Goal, senza cross-book. Al momento del test (~T-98) i checkpoint T-40/T-30 erano correttamente ancora null e verranno popolati solo da osservazioni successive valide.
