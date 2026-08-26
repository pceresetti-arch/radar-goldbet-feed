# Radar Unico — contratto movimenti quota

## Aggiornamento provenienza player — 26/08/2026

Per i nuovi snapshot player, il movimento BetFlag/AAMS diretto resta una serie separata e non deve essere chiamato movimento GoldBet. Ogni punto deve conservare BETFLAG_AAMS_DIRECT, identità esatta, timestamp e freshness. Una prova exact decision-time valida può essere BETFLAG_AAMS_DIRECT_CERTIFIED. GoldBet diretto sulla stessa selezione, quando osservato, resta una serie GOLDBET_DIRECT distinta per cross-check e drift. Le etichette proxy legacy non vanno riscritte.

## Obiettivo
Ricostruire in modo verificabile la traiettoria di prezzo di ciascuna selezione dal primo prezzo osservato fino ai checkpoint pre-kickoff.

## Regola SAME BOOKMAKER / SAME MARKET
Un movimento è valido solo se confronta la stessa partita, lo stesso bookmaker, lo stesso mercato, la stessa linea, lo stesso periodo/scope e la stessa selezione.

## OPEN_RADAR
`OPEN_RADAR` / `FIRST_SEEN` è il primo prezzo realmente osservato dal tracker. Non viene inventato né ricostruito a posteriori. Per i mercati che il Radar monitora prima della loro pubblicazione, il primo prezzo rilevato coincide operativamente con l'apertura osservabile dal sistema.

## Frequenza
Il tracker gira ogni 10 minuti e registra:
- FIRST_SEEN / OPEN_RADAR
- ogni variazione di prezzo
- minimo e massimo osservati
- numero di variazioni
- timestamp dell'ultimo cambio
- checkpoint T-120, T-75, T-60, T-40, T-30 e T-15 quando disponibili

## Sorgenti
- Mercati standard: GoldBet diretto tramite bridge, bookmaker `goldbet`.
- Player props: feed AAMS condiviso fortemente allineato a GoldBet; finché manca certificazione diretta player-by-player, questi movimenti devono essere etichettati come player-proxy GoldBet-aligned e non GoldBet-diretto certificato.

## Lettura del movimento
Per ogni selezione il Radar deve poter confrontare:
- OPEN_RADAR -> corrente
- OPEN_RADAR -> T-40
- OPEN_RADAR -> T-30
- T-60 -> T-40
- T-40 -> T-30
- eventuale accelerazione post-formazione

Il movimento va espresso sia come variazione della quota sia come variazione della probabilità implicita (punti percentuali).

## Formazioni e causalità
Quando una formazione ufficiale viene pubblicata, il timestamp va confrontato con il timestamp dei cambi quota. Il Radar deve distinguere:
- movimento precedente alla formazione
- movimento simultaneo/post-formazione
- movimento tardivo vicino al kickoff

La correlazione temporale non va presentata automaticamente come causalità.

## Player props
Il tracker deve includere, quando presenti, Marcatore/Marc, Marcatore Plus, Marcatore o Sostituto, Marcatore 1T/2T, 1° Marcatore, Assist, Gol e Assist, Tiri Totali, Tiri in Porta e relative versioni Plus.

## Uso decisionale
Il movimento quota è un segnale, non una BET automatica. Entra dopo l'analisi calcistica profonda e contribuisce alla probabilità/fair odds/price gate. Un crollo di quota non sostituisce formazione-vs-formazione, matchup zona-zona e analisi del giocatore.

## Output operativo
Prima della BET il Radar deve mostrare almeno:
- quota OPEN_RADAR
- quota T-40/T-30 se già catturata
- quota corrente
- direzione e ampiezza del movimento
- eventuale timing rispetto alla formazione ufficiale
- quota minima Radar
