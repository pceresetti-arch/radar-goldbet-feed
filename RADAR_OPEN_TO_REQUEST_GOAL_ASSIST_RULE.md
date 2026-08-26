# Radar Unico — OPEN→REQUEST + GOAL/ASSIST FULL SCAN

Stato: OPERATIVO E VINCOLANTE
Data consolidamento: 2026-08-26

## 1. Movimento quota fino al momento esatto della richiesta
Ogni volta che Paolo chiede una pre-analisi, analisi approfondita, controllo quote, screening player props o verifica di value, il Radar deve ricostruire il movimento prezzo dalla prima apertura realmente certificabile fino allo snapshot disponibile nel momento della richiesta.

Sequenza obbligatoria, per la stessa partita + stesso bookmaker/fonte + stesso mercato + stessa linea + stessa selezione:
- TRUE OPEN certificato, se disponibile;
- altrimenti earliest/first real observed, chiaramente etichettato e MAI spacciato per TRUE OPEN;
- tutti gli snapshot intermedi realmente osservati utili;
- snapshot corrente acquisito il più vicino possibile al timestamp della richiesta utente (`REQUEST_SNAPSHOT`);
- se già temporalmente disponibili: T-40 e T-30;
- close soltanto ex post.

`CURRENT` in una risposta on-demand significa il prezzo osservato al momento della richiesta dell'utente, non l'ultimo valore generico memorizzato ore prima. Se il feed non è abbastanza fresco, il Radar deve tentare un refresh/recupero corrente; se non riesce, deve indicare timestamp/age e dichiarare STALE o NON VERIFICABILE.

Il movimento deve essere quantitativo: quota iniziale → quota alla richiesta, delta assoluto, variazione della probabilità implicita quando utile, numero/timing degli step, eventuale accelerazione/rimbalzo. Deve entrare nel repricing di P Radar, fair odds e FINAL GATE; non è solo descrittivo.

### Fonti
- Mercati standard: GoldBet SAME BOOKMAKER quando direttamente verificabile; TRUE OPEN GoldBet è il riferimento MMS principale.
- Player props: BetFlag/AAMS/ADM come fonte operativa prioritaria. Il relativo movimento resta etichettato BetFlag/AAMS e non va chiamato movimento GoldBet salvo osservazione GoldBet diretta della stessa selezione.
- Cross-bookmaker/aggregatori: soltanto controllo secondario e separato.

Se manca un punto della sequenza, non interpolare e non inventare: scrivere INCOMPLETO/NON VERIFICABILE.

## 2. Scansione completa mercati Goal/Assist
Per ogni partita e soprattutto dopo XI ufficiale, il Radar deve cercare e confrontare TUTTI i mercati realmente disponibili che esprimono una tesi Goal e/o Assist, non soltanto Marcatore anytime.

Includere quando offerti:
- Marcatore anytime;
- Marcatore 1T;
- Marcatore 2T;
- Primo Marcatore;
- Marcatore o Sostituto;
- Primo Marcatore o Sostituto;
- Marcatore Plus e varianti equivalenti;
- Gol o Assist PURO;
- Gol e Assist;
- Assist;
- Assist o Sostituto;
- eventuali combinazioni/Plus che includono goal e/o assist;
- eventuali mercati Goal/Assist 1T o 2T se realmente presenti;
- tiri e tiri in porta come mercati correlati per verificare coerenza della tesi offensiva.

Per ogni giocatore candidato confrontare i mercati correlati e scegliere quello con miglior rapporto probabilità/prezzo/varianza. Ogni mercato deve avere P Radar, fair odds e gate propri: non trasferire automaticamente la probabilità di Marcatore a Gol o Assist o ad Assist.

Non inventare mercati mancanti. Se un mercato Goal/Assist non è disponibile o il feed dedicato è stale, dichiararlo esplicitamente.

## 3. Output minimo obbligatorio nelle analisi richieste dall'utente
Per ogni candidata concreta mostrare almeno:
- mercato e selezione;
- fonte prezzo;
- OPEN/earliest osservabile con timestamp;
- REQUEST_SNAPSHOT corrente con timestamp/age;
- movimento OPEN→REQUEST e stato ACTIVE_DROP / REBOUNDED / RISING / FLAT quando classificabile;
- quota corrente;
- P Radar;
- fair odds;
- FINAL GATE o PROXY GATE applicabile;
- confronto con gli altri mercati Goal/Assist dello stesso giocatore;
- verdetto BET / WATCH / NO BET / DATI INCOMPLETI.

Questa regola si applica a PRE-LINE, PRE-XI, POST-XI, FINAL GATE e alle analisi on-demand richieste direttamente da Paolo.