# Radar Unico — TRUE OPEN Movement Policy

## Regola principale
Per l'analisi dei movimenti quota il benchmark corretto e obbligatorio e' la vera quota di apertura del mercato (`TRUE OPEN`), confrontata con gli snapshot pre-kickoff, in particolare `T-40` e `T-30`.

Sequenza primaria:

`TRUE OPEN -> T-40 -> T-30 -> CURRENT/PRE-BET`

Il semplice `FIRST_SEEN` del tracker NON equivale automaticamente alla vera apertura del bookmaker.

## Definizioni
- `TRUE_OPEN`: prima quota realmente pubblicata dal bookmaker per quella specifica partita + mercato + linea + selezione.
- `FIRST_SEEN` / `OPEN_RADAR`: prima quota osservata dal nostro sistema. E' un fallback tecnico, non deve essere chiamato TRUE OPEN senza prova.
- `T-40`: snapshot piu vicino possibile a 40 minuti dal calcio d'inizio, in finestra separata da T-30.
- `T-30`: snapshot piu vicino possibile a 30 minuti dal calcio d'inizio.
- `CURRENT/PRE-BET`: ultima quota disponibile prima della raccomandazione/piazzamento.

## Gerarchia di affidabilita dell'apertura
1. `TRUE_OPEN_CERTIFIED`: apertura fornita esplicitamente da una sorgente storica/ufficiale affidabile o registrata esattamente al momento della prima pubblicazione del mercato.
2. `OPEN_CAPTURED_NEAR_PUBLICATION`: il Radar era gia' in monitoraggio continuo e ha intercettato la comparsa del mercato nel primo ciclo utile; utilizzabile con confidenza alta ma distinto da TRUE_OPEN_CERTIFIED.
3. `OPEN_RADAR_PROXY`: prima quota che il tracker ha visto senza prova che coincida con la pubblicazione iniziale; utilizzabile solo come fallback e con peso ridotto.
4. `OPEN_UNKNOWN`: nessuna apertura affidabile; il segnale OPEN->T-40/T-30 non deve essere inventato.

## Same-bookmaker / same-market rule
Ogni confronto deve essere sulla stessa identica chiave:
- bookmaker;
- partita/evento;
- mercato;
- periodo (FT, 1T, 2T ecc.);
- linea (es. O/U 2.5, tiri 3.5);
- selezione;
- giocatore, quando applicabile.

Non e' valido confrontare quote di bookmaker diversi o linee/mercati diversi per costruire artificialmente un movimento.

## Metriche da calcolare
Per TRUE_OPEN -> T-40 e TRUE_OPEN -> T-30 calcolare almeno:
- variazione quota assoluta;
- variazione percentuale della quota;
- variazione in punti percentuali della probabilita' implicita;
- direzione del movimento;
- numero di cambi osservati;
- minimo/massimo intermedio;
- eventuale accelerazione del movimento dopo l'uscita delle formazioni;
- consenso trasversale su altri bookmaker, separato dal movimento same-bookmaker.

## Relazione con le formazioni
Il Radar deve distinguere temporalmente:
- movimento iniziato prima della formazione ufficiale;
- movimento immediatamente successivo alla formazione;
- movimento tardivo fra T-40 e T-30;
- movimento successivo a T-30 prima del price gate finale.

Questo serve a capire se il mercato stava gia' prezzando l'informazione oppure se la formazione ha prodotto una vera rivalutazione.

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
Nei report operativi il Radar deve mostrare esplicitamente la qualita' dell'apertura:

`OPEN: @X.XX [TRUE_OPEN_CERTIFIED]`
oppure
`OPEN: @X.XX [CAPTURED_NEAR_PUBLICATION]`
oppure
`FIRST_SEEN: @X.XX [OPEN_RADAR_PROXY]`
oppure
`TRUE OPEN: non disponibile`.

Non deve mai presentare un FIRST_SEEN come vera quota di apertura senza evidenza.

## Obiettivo operativo
Per tutte le partite future il tracker deve essere attivo abbastanza presto da intercettare la pubblicazione dei mercati e conservare la prima quota osservata, continuando poi con snapshot distinti T-40 e T-30. Parallelamente, quando disponibile, una sorgente storica esplicita di opening price deve avere priorita' per certificare il TRUE OPEN.