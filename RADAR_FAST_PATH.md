# Radar Unico — Fast Path operativo

## Obiettivo
Ridurre al minimo il tempo tra disponibilità di formazione/quote e decisione Radar, senza abbassare il livello di certificazione del prezzo.

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
- È ammessa al FINAL PRICE GATE.

### `GOLDBET_DIRECT_ODSS`
- Classe prevista dal Worker Fast Path per una lettura diretta GoldBet attraverso ODSS.
- Per i player props la copertura diretta è attualmente assente: i test restituiscono zero player rows.
- Non dichiarare una quota player GoldBet certificata se la risposta non contiene effettivamente la stessa fixture/mercato/giocatore/selezione.

### `SHARED_AAMS`
- Player props ottenuti dal servizio AAMS condiviso usato per discovery e market sanity.
- `goldbet_direct = false`.
- `price_gate_eligible = false`.
- Non chiamare queste quote “GoldBet attuali” e non usarle per approvare una BET GoldBet.

## Feed rapidi attivi

### Player props imminenti
- `feed/hot/player-props-index.json`
- `feed/hot/player-props/<match_market_id>.json`
- finestra operativa: da T-120 a T+15.
- refresh player props parallelizzato su 8 worker di rete.
- fonte: `SHARED_AAMS`, quindi discovery soltanto.

### Quote standard GoldBet imminenti
- `feed/hot/standard-odds-index.json`
- `feed/hot/standard-odds/<event_id>.json`
- finestra operativa: da T-120 a T+15.
- contiene quote dirette GoldBet e, quando disponibili, TRUE OPEN, T-40, T-30 e current.
- fonte: `GOLDBET_DIRECT_STANDARD`.

## Timing Radar
- T-75/T-60: controllo XI + analisi preliminare; non attendere un readiness perfetto per produrre un report utile.
- Appena XI ufficiali: formazione-vs-formazione e scansione completa player props.
- T-40/T-30: snapshot MMS e FINAL PRICE GATE.
- Entro T-20: se manca il prezzo GoldBet diretto necessario, classificare `ATTESA / NO BET — QUOTA NON CERTIFICATA`; non restare silenziosi e non chiedere all’utente di cercare la quota.

## Regola di velocità
Per una partita imminente il Radar deve leggere prima il file hot specifico, non i grandi file aggregati. I file storici completi servono solo per ricostruzione, audit, backtest o quando il feed hot non contiene la fixture.

## Worker Fast Path
Il codice Worker v6 è presente in `worker/src/index.mjs` e prevede:
- `/live/goldbet`
- `/live/player-props`
- `/live/fixture`
con cache a pochi secondi e fetch concorrenti.

Il deploy v6 resta subordinato alla disponibilità delle credenziali Cloudflare nell'ambiente di deploy. Finché non è pubblicato, i task Radar devono fallire velocemente sul live endpoint e passare immediatamente ai feed `feed/hot/`, senza bloccare l'analisi.

## Player props diretti GoldBet: stato corrente
Le verifiche ODSS/OddsPapi e il bridge GoldBet hanno mostrato mercati standard GoldBet ma zero righe player dirette. Il frontend pubblico GoldBet è inoltre protetto da 403/Akamai negli ambienti server testati.

Conseguenza operativa: il Radar può usare autonomamente i player props condivisi per individuare candidati e mercati, ma una giocata player non supera il FINAL PRICE GATE finché non è disponibile una quota GoldBet diretta certificabile attraverso una sorgente supportata.

## Obiettivo di performance
- discovery player props: pochi secondi per l'intero palinsesto corrente;
- lettura partita imminente: un singolo file hot;
- niente scansioni di JSON multi-megabyte nel percorso decisionale normale;
- notifiche concise, senza duplicare l'intero contratto Radar a ogni esecuzione.
