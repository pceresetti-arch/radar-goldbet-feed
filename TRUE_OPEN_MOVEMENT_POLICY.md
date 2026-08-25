# Radar Unico — TRUE OPEN Movement Policy

## Regola principale — VINCOLANTE DAL 25/08/2026
Per qualunque richiesta dell'utente sul movimento di una quota e per qualunque controllo operativo automatico T-40/T-30, il benchmark primario e obbligatorio e' la **vera quota di apertura certificata del bookmaker (`TRUE_OPEN_CERTIFIED`)**.

Sequenza operativa obbligatoria:

`TRUE OPEN CERTIFICATA -> snapshot intermedi -> T-40 -> T-30 -> CURRENT/PRE-BET`

Il semplice `FIRST_SEEN`, `OPEN_RADAR`, una quota attuale di un altro bookmaker o una media mercato NON possono sostituire la vera apertura.

Se la vera apertura non e' certificabile, il Radar deve scrivere esplicitamente:

`TRUE OPEN: NON CERTIFICATA / MOVIMENTO OPEN→CURRENT INCOMPLETO`

e NON deve attribuire un movimento forte, MMS o direzione OPEN→T-40/T-30 usando il FIRST_SEEN come se fosse l'apertura reale.

## Definizioni
- `TRUE_OPEN_CERTIFIED`: prima quota realmente pubblicata dal bookmaker per quella specifica partita + mercato + linea + selezione, certificata da una sorgente affidabile o da una cattura dimostrabile della prima pubblicazione.
- `FIRST_SEEN` / `OPEN_RADAR`: prima quota osservata dal nostro sistema. E' solo diagnostica; non e' la vera apertura salvo certificazione separata.
- `OPEN_CAPTURED_NEAR_PUBLICATION`: quota intercettata molto vicino alla comparsa del mercato. Resta distinta da `TRUE_OPEN_CERTIFIED` e non va chiamata “apertura reale” senza prova della prima pubblicazione.
- `T-40`: snapshot piu vicino possibile a 40 minuti dal calcio d'inizio, separato da T-30.
- `T-30`: snapshot piu vicino possibile a 30 minuti dal calcio d'inizio.
- `CURRENT/PRE-BET`: ultima quota disponibile e fresca prima della raccomandazione/piazzamento.

## Gerarchia di affidabilita dell'apertura
1. `TRUE_OPEN_CERTIFIED`: unica classe ammessa come benchmark operativo “apertura reale”.
2. `OPEN_CAPTURED_NEAR_PUBLICATION`: diagnostica ad alta confidenza, ma NON apertura reale certificata.
3. `OPEN_RADAR_PROXY` / `FIRST_SEEN`: diagnostica tecnica; mai MMS primario.
4. `OPEN_UNKNOWN`: nessuna apertura affidabile.

Per il controllo richiesto dall'utente “da apertura a ora / T-40 / T-30”, solo il livello 1 consente di presentare il confronto come movimento dall'apertura reale.

## Same-bookmaker / same-market rule
Ogni confronto deve usare la stessa identica chiave:
- bookmaker;
- partita/evento;
- mercato;
- periodo (FT, 1T, 2T ecc.);
- linea (es. O/U 2.5, tiri 3.5);
- selezione;
- giocatore, quando applicabile.

Per GoldBet il movimento principale deve essere GoldBet→GoldBet. Il consenso di altri bookmaker e' soltanto un controllo incrociato separato e non puo' modificare la sequenza GoldBet TRUE OPEN→CURRENT.

Non e' valido confrontare quote di bookmaker diversi o linee/mercati diversi per costruire artificialmente un movimento.

## Freschezza della quota corrente
Una quota non deve essere chiamata `CURRENT` se lo snapshot non e' sufficientemente fresco.

Nel report indicare timestamp o eta' della quota quando disponibile. Se la quota e' stale, scrivere `CURRENT STALE` e tentare un refresh prima di concludere.

## Metriche da calcolare
Per TRUE_OPEN→CURRENT, TRUE_OPEN→T-40 e TRUE_OPEN→T-30 calcolare quando disponibili:
- variazione quota assoluta;
- variazione percentuale della quota;
- variazione in punti percentuali della probabilita' implicita;
- direzione del movimento;
- numero di cambi osservati;
- minimo/massimo intermedio;
- eventuale accelerazione dopo la formazione ufficiale;
- stato `ACTIVE_DROP` o `REBOUNDED_AFTER_DROP`;
- consenso trasversale su altri bookmaker, sempre separato dal movimento same-bookmaker.

## Soglia MMS primaria
Per il Radar il segnale forte standard resta:

`TRUE_OPEN_CERTIFIED - quota osservata >= 0.20`

La soglia deve essere misurata sulla stessa selezione GoldBet. Un FIRST_SEEN→CURRENT >=0.20 non e' un MMS primario e deve essere etichettato solo come movimento diagnostico.

## Relazione con le formazioni
Il Radar deve distinguere temporalmente:
- movimento iniziato prima della formazione ufficiale;
- movimento immediatamente successivo alla formazione;
- movimento tardivo fra T-40 e T-30;
- movimento successivo a T-30 prima del price gate finale.

Questo serve a capire se il mercato stava gia' prezzando l'informazione oppure se la formazione ha prodotto una vera rivalutazione.

## Player props e proxy BetFlag/AAMS
Per i player props, il movimento BetFlag/AAMS puo' essere analizzato soltanto come movimento della fonte proxy e deve essere etichettato chiaramente.

Non chiamare mai `movimento GoldBet` una sequenza osservata solo su BetFlag/AAMS.

Se in futuro sara' disponibile la vera apertura GoldBet diretta dello stesso player/mercato/linea/selezione, quella sequenza avra' priorita'.

## Regola decisionale
Il movimento di quota e' un input, non una BET automatica.

Una BET deve comunque passare:
- analisi approfondita formazione-vs-formazione;
- zona-vs-zona e matchup giocatore;
- ruolo/minutaggio;
- contesto tattico, fisico e motivazionale;
- stima probabilita'/fair odds;
- quota minima Radar;
- price gate finale.

## Regola di trasparenza
Nei report operativi il Radar deve mostrare esplicitamente:

`TRUE OPEN GOLDBET: @X.XX [TRUE_OPEN_CERTIFIED]`
`INTERMEDI: ...`
`T-40: @X.XX [timestamp]`
`T-30: @X.XX [timestamp]`
`CURRENT: @X.XX [timestamp/freshness]`

Se manca la certificazione:

`TRUE OPEN GOLDBET: NON CERTIFICATA`
`FIRST_SEEN: @X.XX [SOLO DIAGNOSTICA]`

Mai presentare FIRST_SEEN, BetFlag o una media di mercato come vera apertura GoldBet.

## Obiettivo operativo
Per tutte le partite future il tracker deve acquisire la vera apertura quanto prima, conservarla immutabile e poi accumulare snapshot intermedi distinti fino a T-40, T-30 e CURRENT. La ricostruzione deve essere auditabile ex post e non riscritta dopo il risultato.