# Radar Unico — TRUE OPEN Movement Policy

## Principio operativo
Per la decisione pre-match la quota `CURRENT` deve essere una quota BetFlag reale, fresca e riferita alla stessa identica chiave evento + mercato + periodo + linea + selezione + giocatore, quando applicabile.

La disponibilita' della `CURRENT` e la disponibilita' della `OPEN` sono due fatti separati.

**Regola vincolante:** se una `CURRENT BETFLAG` fresca e' presente, la quota E' RECUPERATA e deve essere usata normalmente per P Radar, fair odds, FINAL GATE e decisione. La mancanza della OPEN, di T-30 o di altri checkpoint storici limita soltanto il giudizio sul movimento/MMS e non deve mai essere descritta come `quota non recuperata` o `acquisizione fallita`.

## GoldBet e BetFlag — uso operativo pragmatico
GoldBet e BetFlag vengono trattati come riferimenti dello stesso mercato quando:
- fixture, mercato, periodo, linea e selezione coincidono esattamente;
- la fonte storica della OPEN e' verificabile;
- i prezzi correnti GoldBet/BetFlag, quando entrambi osservabili, sono sufficientemente coerenti da non indicare due mercati materialmente diversi.

In questo caso una OPEN storica GoldBet puo' essere usata come riferimento operativo del movimento BetFlag con etichetta esplicita:

`TRUE OPEN PROXY — GOLDBET/MERCATO`

La provenienza resta auditabile dietro le quinte, ma l'analisi operativa non deve bloccarsi per il solo fatto che la OPEN storica e la CURRENT provengano da due bookmaker molto allineati.

La proxy non deve essere riscritta come `TRUE OPEN BETFLAG UFFICIALE`.

## Gerarchia OPEN
1. `TRUE_OPEN_CERTIFIED_BETFLAG`: apertura BetFlag certificata da campo opening affidabile o prova storica BetFlag verificabile.
2. `OPEN_RADAR_CERTIFICATA_BETFLAG`: apertura catturata dal watcher continuo con prova di comparsa del mercato.
3. `TRUE_OPEN_PROXY_GOLDBET_MARKET`: apertura GoldBet/mercato verificata e coerente con la stessa identica selezione; valida per lettura operativa del movimento, non come certificazione BetFlag ufficiale.
4. `FIRST_SEEN_BETFLAG`: prima osservazione tecnica non certificata.
5. `OPEN_UNKNOWN`: nessuna apertura affidabile disponibile.

Se manca una apertura utilizzabile ma la quota corrente esiste, il formato corretto e':

`CURRENT BETFLAG DISPONIBILE — OPEN STORICA NON ANCORA RICOSTRUITA / MOVIMENTO INCOMPLETO`

## Sequenza di movimento
Ordine preferito:

`OPEN certificata/proxy -> snapshot intermedi -> T-40 -> T-30 -> T-15 -> CURRENT/PRE-BET`

Usare soltanto checkpoint realmente osservati. Non ricostruire retroattivamente snapshot mancanti come se fossero osservati.

Quando la OPEN e la CURRENT sono entrambe BetFlag, il movimento e' `SAME-BOOK CERTIFIED`.

Quando la OPEN e' GoldBet/mercato e la CURRENT e' BetFlag, il movimento e' `MARKET/PROXY MOVEMENT`.

Entrambi possono essere mostrati e usati nell'analisi; solo il primo va chiamato movimento BetFlag same-book certificato.

## CURRENT e FINAL GATE
La quota operativa per la decisione resta `CURRENT BETFLAG` fresca/exact quando disponibile.

Per ogni candidata:
- stima P Radar;
- calcola fair odds;
- calcola un solo FINAL GATE;
- BET solo se `CURRENT BETFLAG >= FINAL GATE` e tutti gli altri blocchi dell'analisi sono completi;
- sotto gate = NO BET, salvo USER OVERRIDE esplicito.

La OPEN serve a interpretare il mercato, non a determinare se la quota corrente esiste.

## Mercato non quotato vs acquisizione fallita vs storico incompleto
Quando manca un dato, distinguere sempre tre casi:
1. `MERCATO NON QUOTATO / NON DISPONIBILE SU BETFLAG`;
2. `ACQUISIZIONE BETFLAG FALLITA / QUOTA CURRENT NON RECUPERATA`;
3. `QUOTA CURRENT BETFLAG RECUPERATA MA OPEN/MOVIMENTO INCOMPLETO`.

Il caso 3 non deve mai essere descritto come caso 2.

Un semplice `non trovato` non equivale automaticamente a `non quotato`.

## Coerenza GoldBet/BetFlag
La OPEN GoldBet/mercato puo' essere usata come proxy solo quando non emergono divergenze correnti materiali tra GoldBet e BetFlag.

Se i prezzi correnti divergono in modo significativo, separare le due fonti e non usare automaticamente la OPEN GoldBet come proxy BetFlag.

La soglia di coerenza puo' essere implementata dal software con una regola documentata e auditabile; il Radar deve conservare sia quota assoluta sia probabilita' implicita per misurare il drift.

## Metriche di movimento
Quando disponibili, calcolare:
- variazione assoluta quota;
- variazione percentuale;
- variazione probabilita' implicita;
- direzione e numero cambi;
- minimo/massimo intermedio;
- accelerazione post-XI;
- `ACTIVE_DROP` / `REBOUNDED_AFTER_DROP`;
- tipo di movimento: `SAME_BOOK_CERTIFIED` oppure `MARKET_PROXY`.

## MMS
Il segnale MMS same-book piu' forte resta basato su BetFlag OPEN -> BetFlag CURRENT/T-40/T-30 sulla stessa chiave.

Una OPEN GoldBet/mercato verificata -> CURRENT BetFlag puo' produrre un segnale di movimento operativo `MARKET_PROXY`, utile come conferma e contesto. Non va chiamato same-book e non deve da solo generare una BET.

## Freschezza
Una quota non deve essere chiamata `CURRENT BETFLAG` se lo snapshot e' stale. Il report deve usare timestamp/freshness quando disponibile e tentare refresh prima della decisione finale.

## Formato operativo
Esempio con OPEN BetFlag:

`OPEN @2.70 [BETFLAG CERTIFICATA] -> T-30 @2.48 -> CURRENT @2.38 [BETFLAG]`

Esempio con OPEN GoldBet/mercato:

`OPEN @2.70 [PROXY GOLDBET/MERCATO] -> CURRENT BETFLAG @2.38`

Se manca la OPEN:

`CURRENT BETFLAG @2.38 — OPEN STORICA NON ANCORA RICOSTRUITA`

## Regola decisionale
Il movimento e' un input, non una BET automatica. Restano obbligatori analisi profonda, XI/ruoli/minuti, matchup, scorer allocation, contesto, P Radar, fair odds e FINAL GATE.

## Obiettivo
Il Radar deve massimizzare velocita' e utilita' operativa senza perdere tracciabilita': recuperare la CURRENT BetFlag direttamente, usare la migliore OPEN storica verificabile disponibile — BetFlag se certificata, altrimenti GoldBet/mercato come proxy coerente — e conservare la provenienza separatamente per audit e retroanalisi.