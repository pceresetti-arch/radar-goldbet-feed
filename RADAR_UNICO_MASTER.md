# Radar Unico Value Bet Calcio — MASTER SOURCE OF TRUTH

Versione iniziale consolidata: 2026-08-25

## 0. Scopo di questo file
Questo documento è il punto di ingresso unico del progetto Radar Unico. Le regole operative distribuite negli altri file restano valide, ma in caso di dubbio il Radar deve leggere prima questo MASTER e poi i contratti specialistici richiamati qui.

Obiettivo finale: intercettare autonomamente una partita del perimetro, aspettare che i dati necessari siano realmente disponibili e freschi, eseguire una Deep Matchup Analysis completa e notificare direttamente una valutazione operativa con BET/NO BET, probabilità, fair odds, FINAL GATE e rischio. Non deve mai esistere una BET generata dal solo prezzo o da un solo segnale.

## 1. Gerarchia delle fonti di verità
Ordine operativo:
1. `RADAR_UNICO_MASTER.md` — regole e architettura globale.
2. `RADAR_FAST_PATH.md` — corsia rapida, provenienza prezzi e proxy BetFlag→GoldBet.
3. `RADAR_UNICO_OPERATIONAL_CONTRACT.md` — contratto completo di Deep Matchup Analysis e mercati.
4. `RADAR_PLAYER_CONTEXT_RULE.md` — ufficialità XI, fingerprint e player-market gate.
5. `RADAR_MMS_PRIMARY_RULE.md` — MMS primario TRUE OPEN GoldBet su 1X2/OVER FT.
6. `TRUE_OPEN_MOVEMENT_POLICY.md` e `RADAR_ODDS_MOVEMENT_CONTRACT.md` — dettagli movimento/TRUE OPEN.
7. `RADAR_UNICO_LINEUP_PIPELINE.md` — pipeline formazioni/tattica.
8. Feed machine-readable correnti in `feed/` — stato operativo live, inclusa `feed/shared-goldbet-proxy-policy.json`.

In caso di conflitto tra vecchie chat e questo repository, va prima verificato se il repository contiene una decisione più recente esplicitamente consolidata. Non ricostruire regole dal risultato ex post.

## 2. Perimetro competizioni
Perimetro operativo consolidato:
- Allsvenskan
- Superettan
- Eliteserien
- Superliga danese
- Eredivisie
- massima serie belga
- Scottish Premiership
- Primeira Liga
- Bundesliga tedesca
- Bundesliga austriaca
- Süper Lig
- La Liga
- Ligue 1
- Premier League
- J1 League
- Saudi Pro League
- UEFA Champions League
- UEFA Europa League
- UEFA Conference League
- più eventuali giocate reali aperte già registrate privatamente.

Il perimetro può essere ampliato, ma una nuova lega non deve essere trattata come equivalente alle altre senza considerare league scoring environment e qualità/copertura dei dati.

## 3. Principio READY, non semplice timer
Il Radar non notifica una partita perché è semplicemente T-40/T-30. Deve notificare quando la partita è realmente pronta per una Deep Matchup Analysis affidabile.

Stato macchina principale: `READY_DEEP_ANALYSIS` da:
- `feed/deep-analysis-readiness-summary.json`
- `feed/deep-analysis-readiness.json`

### READY STANDARD richiede
- XI ufficiale standard fresco;
- layer tattico fresco e sincronizzato allo stesso XI;
- quote GoldBet standard correnti;
- TRUE OPEN GoldBet certificato per tutte le selezioni 1X2 e almeno una linea OVER FT.

I player props NON bloccano la readiness standard se non sono offerti o non sono mappati.

## 4. Definizione rigorosa di formazione ufficiale
Una formazione FotMob può sbloccare il Radar solo se:
- `lineupType = standard`;
- `confirmed = true`;
- 11 contro 11 completi;
- stato `SOURCE_CONFIRMED` o `CROSS_CONFIRMED`.

`lastStarting11`, `lastStartingLineups`, predicted, probable, expected o altre formazioni storiche/probabili NON sono ufficiali e non possono sbloccare READY.

Ogni XI ufficiale riceve un `xi_fingerprint`. Se cambia anche un titolare dopo la prima conferma:
- invalidare l’analisi player precedente;
- rigenerare tattica;
- rigenerare player context;
- bloccare la promozione di player props a BET finché tutti i downstream layer non corrispondono al nuovo fingerprint.

## 5. Deep Matchup Analysis obbligatoria
Prima di qualsiasi BET analizzare almeno, quando i dati sono disponibili:
- formazione-vs-formazione;
- modulo reale e ruoli funzionali;
- lato/fascia/half-space/altezza;
- matchup giocatore-zona-sistema;
- assenze, rientri, panchina, rischio sostituzione;
- rigori, punizioni, corner e gerarchie piazzati;
- stato fisico e carico minuti;
- casa/trasferta;
- obiettivi reali e game state competitivo;
- possesso, pressing/PPDA, linea difensiva, costruzione, transizioni, cross/cutback/piazzati;
- xG/npxG, tiri, SOT, big chances, tocchi area;
- league scoring environment;
- sviluppo 1T/2T;
- ambiente esterno se materialmente rilevante;
- mercato e prezzo SOLO dopo l’analisi calcistica.

Dati non verificabili devono ridurre la confidenza, non essere riempiti con supposizioni presentate come fatti.

## 6. Player Context Gate
Per promuovere a BET un mercato giocatore è richiesto `player_market_bet_ready = true` oltre al normale price gate o, per il proxy, oltre al PROXY GATE.

Richiede:
- player props freschi;
- `player-matchup-context` fresco;
- stesso `xi_fingerprint` dell’XI ufficiale.

Se la quota player esiste ma il contesto è stale/missing/mismatched, il mercato può essere solo `WATCH/ATTESA`, non BET, anche se il prezzo diretto o proxy supera il gate.

### Contesto player attualmente disponibile
- starts/appearances;
- minuti medi quando selezionato;
- P60/P75/P90 preliminari;
- posizione iniziale storica;
- shot origin e zone di tiro;
- shot xG e SOT;
- tipo/situazione delle conclusioni;
- opponent concession map;
- heatmap/location-density storica quando offerta.

P60/P75/P90 sono `PRELIMINARY_UNCALIBRATED`: possono modificare rischio/confidenza, non creare edge autonomo.

## 7. Heatmap storiche
Fonte: FotMob location-density su campo 105x68.

Mapping: le heatmap usano Opta player IDs; il Radar deve mapparli ai FotMob player IDs tramite `matchDetails.content.playerStats.optaId`.

Feature consentite quando disponibili e sincronizzate:
- centroid x/y;
- dispersion;
- dominant zone;
- final-third share;
- box share;
- central share.

Queste heatmap NON sono GPS continuo né touch-by-touch. Sono contesto spaziale reale del provider. L’assenza di heatmap non blocca la player analysis: fallback su starting position + shot origin + concession map.

Finché non validate prospetticamente OOS, le heatmap non possono produrre delta numerico autonomo sulla probabilità.

## 8. Mercati da scandagliare
Il Radar deve partire dal mercato/prezzo disponibile e scandagliare sistematicamente tutto ciò che è realmente offerto, non soltanto una shortlist preconcetta.

### Standard
- 1X2
- DNB/handicap quando disponibili
- Over/Under
- Goal/No Goal
- team total
- primo tempo / secondo tempo quando sensato
- combo compatibili con modellazione della probabilità congiunta.

### Player props
- Marcatore anytime
- Marcatore 1T
- Marcatore 2T
- Primo marcatore
- Marcatore Plus
- Marcatore o Sostituto / varianti equivalenti
- Gol o Assist / Gol e Assist quando offerti
- Assist / Assist o Sostituto
- U/O Tiri Totali Giocatore
- U/O Tiri in Porta Giocatore
- versioni Plus
- altri props reali disponibili.

Mai inventare un mercato o una quota mancante.

## 9. GoldBet, BetFlag/AAMS e certificazione prezzi
GoldBet resta il riferimento operativo primario.

### Standard markets — `GOLDBET_DIRECT_STANDARD`
Le quote standard GoldBet provengono dal bridge diretto e sono trattate come GoldBet reali quando il feed è fresco e correttamente mappato. Queste quote possono passare direttamente il FINAL PRICE GATE.

### Player props diretti
La certificazione diretta GoldBet player-by-player non è ancora disponibile in modo sistematico. Se viene trovata una quota GoldBet diretta della stessa fixture/giocatore/mercato/linea/selezione, essa prevale sempre su qualunque proxy.

### Player props condivisi — `SHARED_AAMS`
I player props correnti provengono dal servizio AAMS/BetFlag. Il prezzo grezzo NON deve essere presentato come GoldBet diretto.

### Proxy operativo — `GOLDBET_ALIGNED_PROXY`
Il Radar può usare il prezzo BetFlag/AAMS come proxy operativo di GoldBet quando la calibrazione cross-brand corrente lo autorizza.

Prima di usarlo deve leggere `feed/shared-goldbet-proxy-policy.json` e verificare:
- freshness <=45 minuti;
- `proxy_player_gate_allowed=true`;
- verdict `STRONG_EXACT_MATCH` oppure `STRONG_NEAR_MATCH`;
- almeno 8 fixture simultanee abbinate;
- nessun segnale di divergenza materiale;
- feed player fresco e mapping esatto fixture/giocatore/mercato/linea/selezione.

La calibrazione cross-brand è costruita su snapshot simultanei di mercati standard 1X2 dove BetFlag/AAMS e GoldBet diretto sono entrambi osservabili. È evidenza forte della condivisione/allineamento del pricing, ma NON prova matematica che ogni singolo player prop sia identico. Per questo il proxy usa un buffer prudenziale.

Con policy forte/fresca:
`PROXY_GATE = max(FINAL_GATE * 1.03, FINAL_GATE + 0.05)`

Il player prop è:
- `BET` se esiste prezzo GoldBet diretto >= FINAL GATE;
- `BET (PROXY BETFLAG→GOLDBET)` se manca il diretto e proxy_price >= PROXY_GATE;
- `NO BET` se il proxy è sotto PROXY_GATE;
- `ATTESA / NO BET — PROXY NON CERTIFICATO` se la policy è stale/debole/non ammessa.

Ogni BET proxy deve mostrare esplicitamente fonte proxy, quota proxy, FINAL GATE, PROXY GATE, buffer e stato/freschezza della calibrazione. Non scrivere mai “quota GoldBet @X” quando X proviene dal proxy.

La pipeline di certificazione salva anche exact-rate, near-rate, mean absolute difference, P95 e max difference. Il buffer potrà essere modificato solo sulla base di evidenza prospettica accumulata, non per adattarsi a una singola giocata.

Priorità tecnica aperta: certificazione diretta GoldBet di ogni player market/prezzo/timestamp. Quando sarà disponibile, il prezzo diretto sostituirà il proxy per il final gate.

## 10. MMS primario
Mercati principali:
- 1X2 FT;
- OVER FT.

Segnale forte:
`TRUE OPEN GoldBet - quota osservata >= 0.20`

Regole:
- stesso bookmaker GoldBet;
- stesso evento/mercato/periodo/linea/selezione;
- TRUE OPEN certificato obbligatorio;
- `FIRST_SEEN` solo diagnostico, mai segnale forte;
- checkpoint TRUE OPEN → T-40 → T-30 → CURRENT;
- `ACTIVE_DROP` se il calo >=0.20 resta attivo;
- `REBOUNDED_AFTER_DROP` se il segnale c’era ma poi è rientrato.

Un crollo è un trigger/prioritizzazione, NON una BET automatica.

Per i player props proxy non attribuire a GoldBet un movimento osservato soltanto sul feed BetFlag/AAMS: il movimento proxy deve restare etichettato separatamente.

## 11. FINAL GATE unico e vincolante
Per ogni candidata:
1. stimare P Radar;
2. calcolare fair odds;
3. fissare un unico FINAL GATE del modello;
4. confrontare con il prezzo operativo ammesso.

Con prezzo GoldBet diretto:
`BET solo se quota GoldBet corrente >= FINAL GATE`.

Con player price proxy certificato:
`BET (PROXY BETFLAG→GOLDBET) solo se proxy_price >= PROXY_GATE`, dove il PROXY GATE è derivato dal FINAL GATE secondo la policy corrente.

Sotto il rispettivo gate = NO BET.

Classificazione operativa:
- A: forte value / alta qualità dati;
- B: value moderato;
- C: borderline ma ancora sopra gate;
- D / ATTESA / NO BET: gate non superato o dati insufficienti.

La provenienza del prezzo è separata dalla classe A/B/C: una A può essere `DIRECT` o `PROXY`, ma il proxy deve essere dichiarato.

Una decisione utente sotto soglia deve essere distinta come USER OVERRIDE e non retro-etichettata come BET del modello.

## 12. Correlazione ed esposizione
Non trattare giocate correlate come edge indipendenti.

Esempio: Marcatore giocatore + Over tiri dello stesso giocatore + team total della stessa squadra condividono parte della stessa tesi.

Il Radar deve:
- segnalare correlazione;
- preferire il mercato che monetizza meglio la tesi;
- limitare esposizione aggregata per tesi/evento;
- non sommare superficialmente confidence/edge di mercati dipendenti.

## 13. Readiness e notifiche
I sensori ChatGPT attivi devono notificare quando:
1. una gara entra nella finestra operativa e c’è già un’analisi preliminare utile;
2. una gara diventa READY e l’analisi approfondita è stata completata;
3. avviene un delta materiale dopo la prima valutazione;
4. entro circa 20 minuti dal kickoff un input critico rimane stale/guasto e impedisce una valutazione affidabile (`ALERT DATI INCOMPLETI`).

Il Radar non deve restare silenzioso soltanto perché manca un layer non essenziale: deve distinguere PRELIMINARY, READY, WATCH e DATA INCOMPLETE.

Delta materiale include:
- cambio XI/fingerprint;
- cambio ruolo/posizionamento;
- nuovo/rientrato crollo >=0.20;
- quota diretta che attraversa il FINAL GATE;
- quota proxy che attraversa il PROXY GATE;
- variazione della policy BetFlag→GoldBet (proxy abilitato/disabilitato o buffer cambiato);
- player context che promuove/declassa una candidata.

Evitare notifiche rumorose e duplicati.

## 14. Frequenza sensori e limite notifiche ChatGPT
Acquisizione repository:
- lineups: circa ogni 5 min;
- tactical: dopo lineup e aggiornamenti regolari;
- odds movement: circa ogni 5 min;
- player props: circa ogni 5 min;
- TRUE OPEN: circa ogni 10 min;
- readiness: circa ogni 5 min e/o trigger downstream;
- calibrazione BetFlag/AAMS→GoldBet: circa ogni 30 min, con policy valida al massimo 45 min.

I task ChatGPT hanno una frequenza pratica inferiore rispetto ai sensori GitHub. Il progetto usa due task sfalsati circa ogni 30 minuti (`:05` e `:35`). Questo introduce possibile latenza di notifica fino al passaggio successivo del task; non esiste al momento un webhook GitHub→ChatGPT event-driven affidabile disponibile nel progetto.

## 15. Validazione prospettica e anti-hindsight
Tutte le analisi, incluse BET, NO BET, ATTESA e nessuna giocata, devono essere archiviate quando possibile come storico strutturato per successive retro-analisi.

Una vera retro-analisi di performance può usare come pre-bet evidence solo dati documentati PRIMA dell’esito:
- classificazione;
- P stimata;
- fair;
- FINAL GATE;
- PROXY GATE quando applicabile;
- quota osservata/presa;
- fonte prezzo `DIRECT` o `PROXY`;
- stato/timestamp della calibrazione proxy quando applicabile;
- motivazione;
- XI/ruolo;
- timestamp/snapshot.

Mai ricostruire retroattivamente una previsione e presentarla come se fosse esistita pre-match.

Le performance delle BET proxy devono essere auditabili separatamente dalle BET con quota GoldBet diretta, così da poter verificare se l’ipotesi di trasferibilità del pricing player regge davvero nel tempo.

### OOS player context
`feed/player-context-validation-ledger.json` conserva snapshot prospettici legati all’esatto `xi_fingerprint`.

Obiettivo: confrontare base model vs base+modulo tramite ablation/OOS e misurare almeno:
- Brier score;
- log-loss;
- calibrazione;
- CLV;
- ROI/yield quando esiste prezzo realmente osservato;
- robustezza per lega/mercato/ruolo.

Nessun nuovo modulo deve diventare edge autonomo prima di miglioramento OOS replicabile.

## 16. Roadmap prioritaria consolidata
Ordine attuale di sviluppo:
1. certificazione diretta GoldBet player props e validazione prospettica del proxy BetFlag/AAMS;
2. modello minuti/sostituzioni calibrato;
3. ablation/OOS automatico dei moduli;
4. delta quantitativo della formazione/lineup impact;
5. creator→finisher network più strutturata;
6. market-movement quality score (velocità, sincronizzazione, post-XI, cross-market);
7. TRUE OPEN dei mercati primo tempo quando tecnicamente disponibile;
8. data-confidence score;
9. correlation/exposure engine;
10. model drift monitoring.

## 17. Cose che il Radar NON deve fare
- inventare quote, formazioni o dati mancanti;
- chiamare ufficiale una probabile/lastStarting11;
- chiamare GoldBet diretto un prezzo BetFlag/AAMS proxy;
- usare il proxy se la policy è stale/debole/non ammessa;
- usare il proxy senza applicare il PROXY GATE;
- trasformare un crollo quota in BET automatica;
- trasformare heatmap/minutes model non calibrati in bonus percentuali arbitrari;
- forzare un numero minimo di giocate;
- modificare soglie sul holdout/OOS dopo aver visto i risultati;
- confondere raccomandazioni con scommesse effettivamente piazzate;
- piazzare scommesse automaticamente.

## 18. Output minimo di una notifica READY
- partita e orario;
- freshness/stato input;
- analysis_scope;
- XI ufficiale + fingerprint;
- sintesi tattica e matchup;
- player minutes/position/heatmap/concession context quando disponibile;
- TRUE OPEN/T-40/T-30/current per i segnali standard rilevanti;
- shortlist BET A/B/C con mercato, selezione, fonte prezzo, prezzo, P, fair, FINAL GATE, eventuale PROXY GATE, edge, rischio e stake suggerito;
- etichetta esplicita `BET (PROXY BETFLAG→GOLDBET)` quando applicabile;
- WATCH/ATTESA se player context o proxy policy non sono sufficienti;
- NO BET importanti.

## 19. Privacy e separazione dati personali
Questo repository è pubblico. Non deve diventare archivio di informazioni personali/finanziarie non necessarie al funzionamento tecnico del modello.

Quindi bankroll personale, ricevute, storico finanziario dettagliato e altri dati user-specific devono restare in un archivio privato/ChatGPT finché non esiste una destinazione privata esplicitamente scelta. Il MASTER conserva metodologia e architettura, non dati finanziari personali.

## 20. Regola di manutenzione
Ogni modifica metodologica materialmente importante deve:
- aggiornare questo MASTER oppure un contratto specialistico richiamato qui;
- essere versionata in Git;
- indicare se è operativa, sperimentale o non calibrata;
- non cancellare retroattivamente risultati/limitazioni precedenti.
