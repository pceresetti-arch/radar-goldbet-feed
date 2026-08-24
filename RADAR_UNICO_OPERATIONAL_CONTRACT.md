# Radar Unico — contratto operativo mercati e BET

## Obiettivo
Il feed player-props automatico entra nel flusso standard del Radar Unico e non viene trattato come sorgente separata.

## Flusso obbligatorio per ogni partita selezionata
1. Identificare la partita e l'orario reale.
2. Controllare la formazione ufficiale da T-75/T-60; appena è ufficiale rifare l'analisi formazione-vs-formazione.
3. Caricare lo snapshot mercati della partita dal feed per-match aggiornato automaticamente.
4. Scandagliare TUTTI i mercati disponibili, non solo i marcatori:
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
5. Integrare quote standard GoldBet, movimento OPEN→corrente→T-30, consenso trasversale e contesto lega.
6. Stimare probabilità, fair odds e quota minima per ciascun candidato.
7. Applicare il price gate finale sulla quota corrente più recente.
8. Restituire solo decisioni operative.

## Regola decisionale
- BET: quota corrente >= quota minima Radar e analisi completa positiva.
- BET FORTE: edge robusto + formazione/ruolo/minutaggio favorevoli + price gate superato con margine.
- BORDERLINE: edge piccolo; stake ridotto solo se il gate è ancora superato.
- NO BET: nessuna selezione supera il gate o dati insufficienti.

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
