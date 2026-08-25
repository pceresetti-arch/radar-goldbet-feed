# Radar Unico — Fast Path operativo

## Obiettivo
Ridurre al minimo il tempo tra disponibilità di formazione/quote e decisione Radar, senza confondere una quota GoldBet diretta con una quota proxy ad alta correlazione.

## Principio architetturale
GitHub è archivio, audit e fallback. Non deve essere trattato come database live quando esiste una corsia più veloce.

Ordine operativo:
1. fast/live source quando disponibile;
2. feed `feed/hot/` per la partita imminente;
3. feed aggregati/storici solo come fallback o audit.

## Provenienza prezzi
Ogni sorgente deve essere classificata esplicitamente.

### `GOLDBET_DIRECT_STANDARD`
- Quota ottenuta dal bridge diretto GoldBet per i mercati standard.
- `goldbet_direct = true`.
- `price_gate_eligible = true` se fixture, mercato, linea e selezione coincidono e la freshness è adeguata.
- È ammessa direttamente al FINAL PRICE GATE.

### `GOLDBET_DIRECT_ODSS`
- Classe prevista dal Worker Fast Path per una lettura diretta GoldBet attraverso ODSS.
- Per i player props la copertura diretta è attualmente assente: i test restituiscono zero player rows.
- Non dichiarare una quota player GoldBet certificata se la risposta non contiene effettivamente la stessa fixture/mercato/giocatore/selezione.

### `SHARED_AAMS`
- Player props ottenuti dal servizio AAMS/BetFlag condiviso.
- `goldbet_direct = false`.
- Il prezzo grezzo non deve essere chiamato “quota GoldBet”.
- Può però essere promosso operativamente a `GOLDBET_ALIGNED_PROXY` quando la certificazione cross-brand è forte e fresca.

### `GOLDBET_ALIGNED_PROXY`
È una quota BetFlag/AAMS utilizzabile per una decisione player BET con buffer prudenziale, NON una quota GoldBet diretta.

Prerequisiti obbligatori:
1. leggere `feed/shared-goldbet-price-certification.json` o `feed/shared-goldbet-proxy-policy.json`;
2. certificazione non più vecchia di 45 minuti;
3. `verdict` uguale a `STRONG_EXACT_MATCH` o `STRONG_NEAR_MATCH`;
4. almeno 8 fixture simultanee abbinate;
5. nessun segnale di divergenza materiale nella certificazione corrente;
6. stessa fixture, stesso giocatore, stesso mercato, stessa linea/selezione nel feed player;
7. feed player sufficientemente fresco per la finestra pre-match.

La prova corrente è cross-brand sui mercati standard 1X2, non una dimostrazione matematica che ogni player prop sia identico. Per questo il proxy usa un gate più severo.

## Proxy price gate player
Con certificazione `STRONG_EXACT_MATCH` o `STRONG_NEAR_MATCH` fresca:

`PROXY_GATE = max(FINAL_GATE × 1.03, FINAL_GATE + 0.05)`

La quota BetFlag/AAMS player supera il gate soltanto se:

`PROXY_PRICE >= PROXY_GATE`.

Esempi:
- FINAL GATE 2.00 → PROXY GATE 2.06;
- FINAL GATE 3.00 → PROXY GATE 3.09;
- FINAL GATE 5.00 → PROXY GATE 5.15.

Se la certificazione scende a `NEAR_MATCH_ONLY`, usare solo WATCH/ATTESA oppure, se esplicitamente previsto dalla policy macchina, un buffer minimo più severo pari a `max(FINAL_GATE × 1.05, FINAL_GATE + 0.10)`.

Se la certificazione è stale, `UNPROVEN`, `DIVERGENT_OR_INSUFFICIENT` o mancano i prerequisiti, il proxy NON può approvare la BET: `ATTESA / NO BET — PROXY NON CERTIFICATO`.

## Classificazione output
- Prezzo GoldBet diretto sopra gate: `BET`.
- Prezzo player proxy sopra PROXY GATE: `BET (PROXY BETFLAG→GOLDBET)`.
- Proxy sotto PROXY GATE: `NO BET`.
- Proxy non certificato/stale: `ATTESA / NO BET — PROXY NON CERTIFICATO`.

Ogni output proxy deve mostrare esplicitamente:
- `Fonte prezzo: BetFlag/AAMS proxy`;
- quota proxy;
- FINAL GATE modello;
- PROXY GATE applicato;
- buffer;
- stato/freschezza della certificazione cross-brand.

Non scrivere mai “quota GoldBet @X” quando X proviene dal proxy.

## Certificazione cross-brand continua
La pipeline `certify-shared-vs-goldbet.yml` confronta snapshot simultanei BetFlag/AAMS e GoldBet diretto sui mercati standard dove entrambe le fonti sono disponibili.

Metriche da conservare:
- fixture abbinate;
- triplette 1X2 identiche;
- percentuale selezioni identiche;
- percentuale entro 0.05;
- scarto assoluto medio;
- P95 dello scarto assoluto;
- scarto massimo;
- verdetto;
- timestamp e freshness.

La certificazione deve essere aggiornata automaticamente durante la giornata. È evidenza per la trasferibilità del pricing cross-brand; non sostituisce una futura certificazione diretta player-by-player quando questa diventerà tecnicamente disponibile.

## Feed rapidi attivi

### Player props imminenti
- `feed/hot/player-props-index.json`
- `feed/hot/player-props/<match_market_id>.json`
- finestra operativa: da T-120 a T+15;
- refresh player props parallelizzato su 8 worker di rete;
- fonte grezza: `SHARED_AAMS`;
- uso operativo: `GOLDBET_ALIGNED_PROXY` solo se la policy/certificazione corrente lo consente.

### Quote standard GoldBet imminenti
- `feed/hot/standard-odds-index.json`
- `feed/hot/standard-odds/<event_id>.json`
- finestra operativa: da T-120 a T+15;
- contiene quote dirette GoldBet e, quando disponibili, TRUE OPEN, T-40, T-30 e current;
- fonte: `GOLDBET_DIRECT_STANDARD`.

## Timing Radar
- T-75/T-60: controllo XI + analisi preliminare; non attendere un readiness perfetto per produrre un report utile.
- Appena XI ufficiali: formazione-vs-formazione e scansione completa player props.
- T-40/T-30: snapshot MMS e FINAL PRICE GATE.
- Per player props: tentare prima GoldBet diretto; se non disponibile, applicare immediatamente la corsia `GOLDBET_ALIGNED_PROXY` quando certificata.
- Entro T-20: se né prezzo diretto né proxy certificato superano il rispettivo gate, classificare NO BET/ATTESA; non restare silenziosi e non chiedere all’utente di cercare la quota.

## Regola di velocità
Per una partita imminente il Radar deve leggere prima il file hot specifico e la piccola policy proxy, non i grandi file aggregati. I file storici completi servono solo per ricostruzione, audit, backtest o quando il feed hot non contiene la fixture.

## Worker Fast Path
Il codice Worker v6 è presente in `worker/src/index.mjs` e prevede:
- `/live/goldbet`
- `/live/player-props`
- `/live/fixture`
con cache a pochi secondi e fetch concorrenti.

Il deploy v6 resta subordinato alla disponibilità delle credenziali Cloudflare nell'ambiente di deploy. Finché non è pubblicato, i task Radar devono passare immediatamente ai feed `feed/hot/`, senza bloccare l'analisi.

## Player props diretti GoldBet: stato corrente
Le verifiche ODSS/OddsPapi e il bridge GoldBet hanno mostrato mercati standard GoldBet ma zero righe player dirette. Il frontend pubblico GoldBet è inoltre protetto da 403/Akamai negli ambienti server testati.

Questa limitazione non blocca più automaticamente il Radar: quando la certificazione cross-brand è forte e fresca, il prezzo BetFlag/AAMS può essere usato come proxy prudenziale secondo il PROXY GATE. La ricerca di una fonte GoldBet player diretta resta comunque prioritaria e, quando disponibile, prevale sempre sul proxy.

## Obiettivo di performance
- discovery player props: pochi secondi per l'intero palinsesto corrente;
- lettura partita imminente: un singolo file hot;
- decisione player possibile anche senza frontend GoldBet diretto, ma con proxy calibrato e dichiarato;
- niente scansioni di JSON multi-megabyte nel percorso decisionale normale;
- notifiche concise, senza duplicare l'intero contratto Radar a ogni esecuzione.
