# Radar Unico — regola MMS primaria

## Segnale operativo principale
Il Radar deve dare priorità ai movimenti di quota GoldBet sui mercati standard full-time seguenti:

1. **1X2** — qualsiasi selezione 1 / X / 2.
2. **OVER/UNDER** — linee goal full-time disponibili.

Il modulo **Information Move** estende il controllo anche a Goal/No Goal e Draw No Bet quando la sorgente storica espone correttamente apertura e quota corrente.

## Definizione di crollo forte
Un **crollo forte MMS** esiste quando, sulla stessa selezione e sullo stesso bookmaker GoldBet:

`TRUE OPEN GoldBet - quota osservata >= 0.20`

La soglia assoluta 0,20 resta il trigger storico MMS, ma non è sufficiente da sola per classificare un movimento come informativo: il modulo usa anche variazione di probabilità implicita e consenso degli altri bookmaker.

## Benchmark valido
Per il segnale forte si usa esclusivamente il **TRUE OPEN GoldBet certificato da Diretta/Flashscore**.

- Provenienza: `GOLDBET_VIA_FLASHSCORE_HISTORICAL`.
- `opening` = apertura GoldBet riportata/storicizzata dalla fonte.
- `value` = quota GoldBet corrente nella stessa risposta.
- `FIRST_SEEN` resta solo diagnostico/proxy e non genera segnale forte quando manca il TRUE OPEN.

## Checkpoint
Il confronto va mantenuto su TRUE OPEN → T-40 → T-30 → quota corrente/pre-BET.

Se il crollo >=0,20 era presente a T-40/T-30 ma poi rientra, conservarlo come `REBOUNDED_AFTER_DROP`. Se resta almeno 0,20 sotto il TRUE OPEN, lo stato è `ACTIVE_DROP`.

## Information Move Score
Il Radar non deve assumere che ogni discesa sia denaro informato. Per la stessa partita + mercato + selezione + linea deve confrontare GoldBet con gli altri bookmaker italiani disponibili nella stessa sorgente Diretta/Flashscore.

Lo score considera almeno:

- variazione GoldBet in punti percentuali di probabilità implicita opening→current;
- mediana della variazione degli altri bookmaker;
- numero di bookmaker con opening e current;
- percentuale di bookmaker nella stessa direzione;
- penalità per movimento isolato GoldBet o mercato complessivamente fermo/contrario.

Classi: `INFORMATION_MOVE_A >=80`, `B 65–79.9`, `C 50–64.9`; sotto 50 nessun forte movimento informativo. A/B richiedono almeno 4 bookmaker, consenso direzionale >=65% e movimento mediano nella stessa direzione.

## Uso primario: MARKET-IMPLIED xG SHIFT
Lo scopo principale del movimento non è inseguire il prezzo, ma stimare se il mercato sta modificando la **quantità di gol attesa che una squadra può esprimere**.

Per ogni partita con copertura sufficiente il Radar deve:

1. ricostruire consenso opening e current di 1X2;
2. ricostruire consenso opening e current della linea O/U full-time più informativa, preferendo 2.5;
3. rimuovere il margine bookmaker (de-vig);
4. stimare due coppie Poisson compatibili con quei prezzi: `lambda_home_open / lambda_away_open` e `lambda_home_current / lambda_away_current`;
5. calcolare `market_xg_delta_home`, `market_xg_delta_away`, `market_xg_delta_total`;
6. classificare la capacità realizzativa: `GOAL_CAPACITY_UP_STRONG`, `UP`, `STABLE`, `DOWN`, `DOWN_STRONG`.

Un delta assoluto >=0.10 xG attiva nuova analisi; >=0.20 xG la rende prioritaria.

### Integrazione nel modello Radar
Il market-xG non sostituisce il modello indipendente. Può correggerlo solo con shrinkage:

`xG_adjustment = market_xG_delta × (0.50 × confidence)`

con cap massimo iniziale di `±0.25 xG` per squadra.

Quindi, se il Radar stimava 1.60 xG per una squadra e il mercato mostra `+0.30 xG` con confidence 0.80, la correzione è +0.12 e il nuovo riferimento diventa circa 1.72 xG, non 1.90.

La correzione si applica solo quando il modello base non incorpora già quelle stesse quote correnti, per evitare doppio conteggio.

Il MARKET-IMPLIED xG SHIFT deve poi propagarsi a:

- distribuzione gol squadra 0/1/2/3/4+;
- probabilità di segnare almeno 1/2/3 gol;
- Over/Under e BTTS;
- profilo 1° tempo con quota di xG 1T coerente;
- scorer allocation dei titolari offensivi;
- probabilità marcatore, Gol o Assist, tiri e SOT quando il ruolo individuale è coerente.

## Uso secondario: MOVE-LAG EDGE
Dopo l'aggiornamento market-xG, il Radar può anche cercare un ritardo di repricing BetFlag. Se modello + market-xG sono coerenti con la selezione e BetFlag resta sopra il final gate, la selezione può essere etichettata `MOVE_LAG_EDGE`. Se BetFlag è già scesa sotto il gate: `NO BET`.

Il movimento non crea mai da solo una BET e il final gate BetFlag resta obbligatorio.

Ordine operativo:

`MODELLO RADAR -> TRUE OPEN/MOVIMENTO -> CONSENSO CROSS-BOOK -> MARKET-xG SHIFT -> NEWS/XI RECHECK -> RICALCOLO DISTRIBUZIONE GOL/PLAYER -> BETFLAG CURRENT/EXACT -> FINAL GATE -> BET/NO BET`
