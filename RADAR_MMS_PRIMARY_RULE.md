# Radar Unico — regola MMS primaria

## Segnale operativo principale
Il Radar deve dare priorità ai movimenti di quota GoldBet sui mercati standard full-time seguenti:

1. **1X2** — qualsiasi selezione 1 / X / 2.
2. **OVER** — selezioni OVER sulle linee goal full-time disponibili (es. Over 0.5, 1.5, 2.5, 3.5, ecc.).

Il modulo **Information Move** estende il controllo anche a Under, Goal/No Goal e Draw No Bet quando la sorgente storica espone correttamente apertura e quota corrente.

## Definizione di crollo forte
Un **crollo forte MMS** esiste quando, sulla stessa selezione e sullo stesso bookmaker GoldBet:

`TRUE OPEN GoldBet - quota osservata >= 0.20`

La soglia assoluta 0,20 resta il trigger storico MMS, ma non è sufficiente da sola per classificare un movimento come informativo: il nuovo modulo usa anche la variazione di probabilità implicita e il consenso degli altri bookmaker.

## Benchmark valido
Per il segnale forte si usa esclusivamente il **TRUE OPEN GoldBet certificato da Diretta/Flashscore**.

- Provenienza operativa: `GOLDBET_VIA_FLASHSCORE_HISTORICAL`.
- `opening` = apertura GoldBet riportata/storicizzata dalla fonte.
- `value` = GoldBet current nella stessa risposta.
- `FIRST_SEEN` resta archiviato come dato diagnostico/proxy.
- `FIRST_SEEN` non deve generare un segnale forte MMS quando manca il TRUE OPEN certificato.

## Checkpoint
Il confronto va mantenuto su:

- TRUE OPEN → T-40
- TRUE OPEN → T-30
- TRUE OPEN → quota corrente/pre-BET

Se il crollo >=0,20 era presente a T-40 o T-30 ma successivamente rientra, il Radar deve conservarlo come **REBOUNDED_AFTER_DROP** invece di trattarlo come crollo ancora attivo.

Se la quota corrente è ancora almeno 0,20 sotto il TRUE OPEN, lo stato è **ACTIVE_DROP**.

## Information Move Score
Il Radar non deve assumere che ogni discesa sia denaro informato. Per ogni stessa combinazione partita + mercato + selezione + linea deve confrontare GoldBet con gli altri bookmaker italiani disponibili nella stessa sorgente Diretta/Flashscore.

Lo score deve considerare almeno:

- variazione GoldBet in **punti percentuali di probabilità implicita** fra opening e current;
- mediana della variazione degli altri bookmaker;
- numero di bookmaker con opening e current disponibili;
- quota di bookmaker che si muove nella stessa direzione di GoldBet;
- penalità per movimento isolato GoldBet o per mercato complessivamente fermo/contrario.

Classi operative:

- `INFORMATION_MOVE_A` = score >= 80;
- `INFORMATION_MOVE_B` = score 65–79.9;
- `INFORMATION_MOVE_C` = score 50–64.9;
- sotto 50 = nessun forte movimento informativo.

A/B richiedono inoltre almeno 4 bookmaker, consenso direzionale >=65% e movimento mediano del mercato nella stessa direzione. A/B attivano `requires_news_xi_recheck=true`.

## Dove nasce il vantaggio: MOVE-LAG EDGE
Il movimento informativo **non modifica automaticamente P Radar, fair odds o final gate** e non crea mai da solo una BET.

Il vantaggio operativo ricercato è un eventuale ritardo di repricing di BetFlag:

1. il modello Radar è già coerente con la selezione;
2. GoldBet mostra TRUE OPEN → CURRENT in forte accorciamento;
3. una maggioranza significativa degli altri bookmaker si muove nella stessa direzione;
4. il Radar ricontrolla immediatamente notizie, XI, ruolo, assenze e contesto;
5. BetFlag viene interrogata con quota CURRENT/exact fresca;
6. se BetFlag è ancora sensibilmente più alta del consenso di mercato **e** la sua quota exact resta >= final gate Radar, la selezione viene etichettata `MOVE_LAG_EDGE` e portata in cima alla shortlist.

Se BetFlag si è già adeguata sotto il gate, il movimento può essere corretto ma non esiste più valore: **NO BET**.

Se il movimento forte va contro il modello Radar, scatta un nuovo controllo analitico; non si forza la BET e non si altera artificialmente la probabilità.

## Uso nel Radar
Il crollo >=0,20 e l'Information Move sono **segnali di mercato**, non BET automatiche. Devono essere incrociati con analisi approfondita, formazione, matchup, probabilità stimata, fair odds e price gate finale.

Ordine operativo:

`MODELLO RADAR -> TRUE OPEN/MOVIMENTO GOLDBET -> CONSENSO CROSS-BOOK -> NEWS/XI RECHECK -> BETFLAG CURRENT/EXACT -> MOVE-LAG TEST -> FINAL GATE -> BET/NO BET`
