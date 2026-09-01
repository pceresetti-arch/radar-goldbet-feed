# Radar Unico — contratto operativo mercati e BET

## Aggiornamento fonte player — 26/08/2026

Per i player props, questa sezione prevale sulle formulazioni legacy presenti più avanti:

- BetFlag/AAMS diretto è la fonte operativa primaria.
- Il feed periodico è solo storico/discovery.
- Il prezzo finale deve provenire da una prova exact fresca e univoca del Worker v7 /live/player-price, con source health, timestamp e proof/fingerprint.
- Una prova valida usa la classe BETFLAG_AAMS_DIRECT_CERTIFIED ed entra direttamente nel confronto current_price >= FINAL_GATE.
- GoldBet diretto della stessa selezione resta fonte separata di cross-check/calibrazione.
- Non applicare il precedente PROXY GATE alle nuove decisioni direct; non riclassificare gli esempi legacy SHARED_AAMS o PROXY_BETFLAG_GOLDBET.

## Obiettivo
Il feed player-props automatico entra nel flusso standard del Radar Unico e non viene trattato come sorgente separata.

## Flusso obbligatorio per ogni partita selezionata
1. Identificare la partita e l'orario reale.
2. Controllare la formazione ufficiale da T-75/T-60; appena è ufficiale rifare l'analisi formazione-vs-formazione.
3. Eseguire SEMPRE l'analisi approfondita completa descritta nella sezione "Deep Matchup Analysis" prima di emettere una BET definitiva.
4. Caricare lo snapshot mercati della partita dal feed per-match aggiornato automaticamente.
5. Scandagliare TUTTI i mercati disponibili, non solo i marcatori:
   - Marc / Marcatore
   - Marcatore Plus
   - Marcatore o Sostituto
   - 1° Marcatore e 1° Marcatore o Sostituto
   - Marcatore 1T / 2T
   - Assist / Assist o Sostituto
   - Gol e Assist
   - U/O Tiri Totali Giocatore
   - U/O Tiri In Porta Giocatore
   - versioni Plus
   - altri mercati player presenti nello snapshot
   - Combo marcatori: scorer + 1X2/DC/Over-Under/Goal-No Goal e altre combinazioni disponibili
6. Integrare quote standard GoldBet, movimento OPEN→corrente→T-30, consenso trasversale e contesto lega.
7. Stimare probabilità, fair odds e quota minima per ciascun candidato.
8. Applicare il price gate finale sulla quota corrente più recente.
9. Restituire solo decisioni operative.

## Deep Matchup Analysis — obbligatoria prima di ogni BET
La BET non può essere generata dalla quota da sola. Prima deve essere positiva l'analisi reale della partita e del giocatore.

Per ogni partita il Radar deve valutare, quando i dati sono disponibili:

### 1. Formazione contro formazione
- XI ufficiali e modulo iniziale reale.
- Posizioni effettive, non solo quelle indicate graficamente.
- Cambi rispetto alle ultime partite e impatto delle assenze.
- Qualità della panchina e sostituzioni più probabili.
- Rischio minutaggio ridotto / sostituzione anticipata.
- Rigori, punizioni, corner e altri piazzati assegnati.

### 2. Zona contro zona / chi gioca contro chi
- Terzino/esterno contro ala avversaria.
- Centrale difensivo contro centravanti.
- Mediano contro trequartista / mezzala d'inserimento.
- Fascia forte contro fascia debole.
- Superiorità o inferiorità numerica prevista nelle varie zone.
- Altezza, velocità, forza fisica e gioco aereo nei duelli diretti.
- Piede dominante e lato di gioco.
- Vulnerabilità specifiche del diretto avversario.
- Spazi che possono aprirsi in transizione o contro pressione alta/blocco basso.

### 3. Sviluppo tattico atteso
- Possesso previsto e territorialità.
- Pressing, PPDA / intensità senza palla quando disponibile.
- Linea difensiva alta o bassa.
- Costruzione dal basso, gioco diretto, cross, cut-back, transizioni.
- Dove la squadra crea più occasioni e dove l'avversaria concede di più.
- Probabilità che la partita cambi struttura in caso di gol iniziale.
- Matchup sui calci piazzati offensivi e difensivi.

### 4. Contesto casa/trasferta
- Prestazioni e produzione offensiva/difensiva home vs away.
- Ritmo, xG, tiri e gol casa/trasferta.
- Eventuale vantaggio ambientale, viaggio, superficie e condizioni del campo.
- Fattore pubblico e difficoltà storica della trasferta se statisticamente rilevante.

### 5. Obiettivi e motivazioni reali
- Situazione di classifica.
- Lotta titolo, Europa, playoff, salvezza o eliminazione.
- Andata/ritorno e risultato aggregato nelle coppe.
- Necessità reale di vincere oppure convenienza a gestire.
- Possibile turnover per impegni successivi/priorità di calendario.

### 6. Stato fisico e disponibilità
- Infortuni, rientri, acciacchi, squalifiche.
- Giocatori appena rientrati o con minutaggio controllato.
- Carico recente di minuti e giorni di riposo.
- Congestione calendario e viaggi.
- Forma atletica osservabile e trend recente.

### 6A. Modulo quantitativo Freschezza/Fatica
Il riposo non può restare una nota descrittiva. Per ogni squadra e candidato player-prop il Radar deve produrre, quando i dati sono disponibili:
- giorni dall'ultima gara, partite e minuti negli ultimi 7/14/21 giorni;
- supplementari, trasferte/viaggi consecutivi, rotazioni e titolari da 80–90 minuti;
- rientro da infortunio, età, ruolo ad alta intensità, rischio cambio e minuti attesi;
- costo fisico del sistema di gioco e aggravanti ambientali;
- Freshness Score 0–100 per squadra e giocatore;
- Freshness Delta = score squadra A − score squadra B.

Il modulo deve correggere direttamente P Radar, fair, FINAL GATE, minuti attesi e probabilità di sostituzione. Per scorer e player props deve correggere separatamente P(evento 1T) e P(evento 2T), perché la fatica non è temporalmente uniforme. Gli input, il punteggio e la correzione applicata devono essere archiviati per retroanalisi.

### 7. Forma e qualità recente, senza overfitting
- xG / npxG prodotti e concessi.
- Tiri, tiri in porta, big chances, tocchi in area.
- Conversione e regressione attesa.
- Prestazioni recenti pesate per forza degli avversari.
- Distinguere risultato finale da qualità reale della prestazione.

### 8. Analisi specifica del giocatore candidato
- Ruolo reale e posizione media prevista.
- Minuti attesi.
- xG, npxG, tiri/90, tiri in porta/90, tocchi area/90.
- Assist/xA, key passes e coinvolgimento creativo quando rilevanti.
- Volume e qualità delle occasioni ricevute.
- Rigori e piazzati.
- Relazione con i compagni che gli creano occasioni.
- Avversario diretto e zona difensiva che dovrà attaccare.
- Probabilità che il suo ruolo cambi durante la partita.

### 8A. Profilo spaziale e ruolo-condizionato del giocatore
Il Radar deve distinguere il rendimento del giocatore in base a DOVE e COME viene utilizzato, non soltanto ai numeri stagionali aggregati.

Quando i dati evento/posizionali sono disponibili, valutare:
- posizione nominale e posizione media reale;
- centravanti, seconda punta, ala destra/sinistra, trequartista, mezzala offensiva e altri ruoli effettivamente occupati;
- produzione di gol, xG, tiri, tiri in porta e tocchi area per ruolo;
- minuti/esposizione giocati in ciascun ruolo, per evitare di sopravvalutare piccoli campioni;
- zone di tiro: area piccola, zona centrale dell'area, mezzi spazi, lato destro/sinistro, fuori area;
- lato dal quale riceve più palloni pericolosi;
- attacchi primo palo, secondo palo, centro area, cut-back e profondità alle spalle della linea;
- frequenza con cui entra nelle zone ad alto xG rispetto alla semplice conversione dei gol;
- piede/testa usati nelle conclusioni e compatibilità col tipo di occasioni che l'avversario concede;
- variazione del profilo quando parte largo ma stringe dentro oppure quando viene schierato più vicino alla porta.

Regola: il Radar non deve usare il semplice conteggio "gol segnati da quella posizione" senza normalizzarlo per minuti, tiri, xG e numero di ingressi/ricezioni in quella zona.

### 8B. Teammate Network — chi gli gioca vicino e chi lo alimenta
Per ogni candidato player-prop, identificare i compagni che aumentano o riducono la sua probabilità di produrre l'evento.

Valutare, quando disponibile:
- quali giocatori occupano le zone immediatamente vicine;
- coppie ricorrenti ala-terzino, punta-trequartista, punta-seconda punta, mezzala-ala;
- passaggi progressivi e passaggi ricevuti fra i due giocatori;
- key pass / xA del compagno verso il candidato;
- assist effettivi del compagno verso il candidato, ma pesati per volume di occasioni create;
- chi gli serve più cross, cut-back, filtranti o palle inattive;
- combinazioni a tre più frequenti che portano il candidato al tiro;
- presenza/assenza del principale creatore di occasioni per quel giocatore;
- variazione di xG/tiri/tocchi area del candidato con e senza determinati compagni in campo;
- compatibilità piede/lato: per esempio ala che rientra + terzino sovrapposto oppure esterno che crossa sul lato forte della punta.

Per i mercati Assist, il Radar deve fare anche il percorso inverso: identificare quali compagni sono i destinatari più probabili delle occasioni create dal candidato.

### 8C. Assist–Finisher Pair Model
Costruire, quando i dati lo consentono, una rete creatore→finalizzatore.

Per ogni coppia rilevante stimare:
- passaggi che generano tiro;
- xA creato verso quel finalizzatore;
- big chances create;
- assist reali, senza attribuire eccessivo peso alla conversione casuale;
- frequenza di presenza contemporanea in campo;
- lato/zona in cui nasce la connessione;
- tipo di servizio: cross, cut-back, filtrante, piazzato, transizione;
- compatibilità con la struttura difensiva avversaria.

Questo modulo deve alimentare sia mercati Assist sia Gol/Assist e può aumentare o diminuire la probabilità marcatore del finalizzatore.

### 8D. Opponent Concession Map — cosa concede l'avversario e dove
Non basta sapere quanti gol concede una squadra. Il Radar deve cercare COME li concede.

Quando disponibile:
- tiri/xG concessi per zona;
- percentuale di occasioni concesse centralmente, da fascia destra/sinistra, primo/secondo palo;
- cross e cut-back concessi;
- passaggi filtranti e transizioni concesse;
- occasioni da palla inattiva;
- vulnerabilità sui duelli aerei;
- tiri concessi al centravanti, alle ali, ai trequartisti e ai centrocampisti d'inserimento;
- lato difensivo maggiormente attaccabile;
- difensore/terzino specifico responsabile della zona;
- portiere: rendimento sui tipi di tiro rilevanti, senza sovrappesare campioni piccoli.

Il profilo del candidato deve essere confrontato direttamente con la mappa delle concessioni avversarie.

### 8E. Occupazione delle zone e cannibalizzazione fra compagni
Il Radar deve controllare se un compagno favorisce il candidato oppure gli sottrae volume.

Valutare:
- sovrapposizione delle zone di tiro;
- chi attacca il primo palo / secondo palo / centro area;
- chi prende rigori e piazzati;
- chi assorbe più tiri quando entrambi sono in campo;
- se la presenza di una seconda punta libera spazio o sottrae conclusioni;
- se un'ala larga aumenta i cross oppure un'ala invertita entra nella stessa zona del centravanti;
- variazione di share di tiri, xG e tocchi area nelle diverse combinazioni di XI.

### 8F. Tipo di occasione attesa
Il Radar deve prevedere non solo QUANTE occasioni, ma QUALI occasioni il giocatore potrebbe ricevere.

Classificare quando possibile:
- attacco posizionale;
- transizione;
- recupero alto;
- cross;
- cut-back;
- filtrante/profondità;
- seconda palla;
- corner/punizione;
- rigore.

Confrontare il tipo di occasione più probabile nella partita con i tipi di occasione nei quali il giocatore produce più xG/tiri/assist.

### 8G. Game-state profile
Valutare come cambia il candidato in base al punteggio:
- 0-0;
- squadra avanti;
- squadra sotto;
- ultimi 20-30 minuti;
- necessità di rimonta;
- possibile gestione del vantaggio.

Questo influenza soprattutto tiri, assist, mercati 1T/2T e rischio sostituzione.

### 8H. Chemistry / lineup continuity
Quando rilevante, valutare:
- minuti giocati insieme dal reparto offensivo;
- stabilità della catena laterale e delle coppie offensive;
- cambi recenti di allenatore/modulo;
- nuovi acquisti o giocatori rientrati che possono alterare automatismi;
- continuità dell'XI nelle ultime partite.

La chimica non va trattata come narrativa: deve essere supportata, quando possibile, da minuti condivisi, sequenze/passaggi e produzione offensiva.

### 8I. Archetype Matchup
Se non esiste un campione sufficiente contro lo specifico difensore, evitare H2H rumorosi e confrontare invece archetipi simili.

Esempi:
- punta fisica contro centrali deboli nel gioco aereo;
- attaccante rapido contro linea alta/lenta;
- ala 1v1 contro terzino frequentemente isolato;
- trequartista tra le linee contro mediana che concede ricezioni centrali;
- incursore contro difesa che perde marcature sul lato debole.

Il confronto per archetipi deve avere più peso di pochi precedenti testa-a-testa.

### 8J. Sample-size, regressione e affidabilità del segnale
Ogni split posizionale, coppia di giocatori o matchup deve essere pesato per qualità e quantità del campione.

Il Radar deve:
- evitare conclusioni forti da pochi minuti/pochi tiri;
- usare xG/xA e volume come base più stabile dei soli gol/assist;
- applicare regressione verso medie di giocatore/ruolo/lega quando il campione è piccolo;
- pesare maggiormente dati recenti solo quando c'è una reale variazione di ruolo/tattica;
- distinguere pattern persistenti da conversione anomala;
- assegnare internamente un livello di affidabilità al modulo: ALTO / MEDIO / BASSO.

### 9. Primo tempo / secondo tempo
- P(>=1 gol 1T), xG 1T e ritmo iniziale previsto.
- Tendenza delle squadre a partire forte o lentamente.
- Distribuzione temporale di gol, tiri e occasioni.
- Impatto tattico delle sostituzioni sul 2T.

### 10. Ambiente esterno
Quando materialmente rilevante:
- Meteo, vento, pioggia e temperatura.
- Condizioni/superficie del terreno.
- Arbitro: rigori, cartellini, stile di gestione, solo con campione adeguato.

### 11. Mercato e prezzo
Solo DOPO l'analisi calcistica:
- Quote OPEN → corrente → T-30 sullo stesso bookmaker.
- Consenso trasversale fra bookmaker.
- Movimenti anomali e cross-market.
- Fair odds del modello.
- Quota minima Radar.
- Edge reale alla quota disponibile.
- Ultimo ricontrollo della quota immediatamente prima della raccomandazione.

### Regola di completezza
Se un parametro importante non è verificabile, il Radar deve segnalarlo internamente come dato mancante e ridurre la confidenza; non deve riempire il vuoto con supposizioni presentate come fatti.

## Modulo Combo marcatori
Per ogni scorer candidato il Radar deve costruire anche la matrice delle combinazioni pertinenti disponibili, almeno:
- giocatore segna + squadra vince / doppia chance;
- giocatore segna + Over/Under rilevante;
- giocatore segna + Goal/No Goal;
- eventuali combo 1T/2T esposte dal bookmaker.

La probabilità della combo deve essere congiunta e condizionata al game state: è vietato moltiplicare meccanicamente probabilità trattate come indipendenti. Per ogni combo servono P congiunta, fair e FINAL GATE propri.

Stati quota obbligatori:
- `COMBO BETFLAG RECUPERATA`: prezzo fresh/exact presente nel feed;
- `COMBO MODELLATA — QUOTA BETFLAG NON PRESENTE NEL FEED`: il modello esiste ma il feed sano non espone la quota;
- `ACQUISIZIONE COMBO FALLITA`: errore tecnico o copertura non verificabile;
- `COMBO NON QUOTATA SU BETFLAG`: solo dopo prova positiva di assenza da scansione sana e completa.

## Regola decisionale
- BET: quota corrente >= quota minima Radar e analisi completa positiva.
- BET FORTE: edge robusto + formazione/ruolo/minutaggio favorevoli + matchup zona-contro-zona favorevole + price gate superato con margine.
- BORDERLINE: edge piccolo; stake ridotto solo se il gate è ancora superato.
- NO BET: nessuna selezione supera il gate, matchup non sufficientemente positivo o dati insufficienti.

Il Radar NON deve inventare una giocata per forza. Se non c'è value reale, la risposta operativa è NO BET.

## Output che l'utente deve ricevere
Per ogni BET:
- Partita
- Giocatore/selezione
- Mercato esatto
- Quota corrente
- Quota minima Radar (gate)
- Fair odds / probabilità stimata
- Edge stimato
- Stake consigliato
- Classe A/B/C
- 1-3 motivi decisivi
- Sintesi del matchup diretto / zona di campo che genera il vantaggio
- Eventuale compagno/connessione offensiva decisiva
- Tipo di occasione attesa che sostiene la giocata

Per NO BET: una riga sintetica con il motivo principale.

## Sorgenti quote player
Il feed automatico corrente è materializzato in:
- `feed/player-props-live-index.json`
- `feed/player-props-matches/<match_market_id>.json`

Il feed è aggiornato automaticamente e lega ogni riga player alla partita reale tramite `mi`.

## Stato di certificazione GoldBet
Le quote standard del backend condiviso hanno mostrato forte allineamento con GoldBet: 8/10 partite confrontate identiche al centesimo su tutto il 1X2 e 10/10 entro 0,05. I player props vengono quindi usati come sorgente operativa ad alta confidenza, ma NON vanno descritti come "GoldBet diretto certificato" finché non esiste una verifica player-per-player indipendente.

## Regola di freschezza
Prima di una raccomandazione BET il Radar deve usare lo snapshot player più recente disponibile. Se la quota è cambiata, prevale sempre la quota corrente e il gate va ricalcolato prima del piazzamento.

## Regola formazioni
Nessuna BET player-prop definitiva deve essere emessa senza considerare la formazione ufficiale quando questa è attesa/disponibile, salvo esplicita classificazione PRE-LINEUP e successiva rivalutazione obbligatoria.
