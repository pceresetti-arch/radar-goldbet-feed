# Radar Unico — contratto operativo mercati e BET

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
