# Radar Unico — Doppie Value e Doppie Speculative

## Obiettivo
Il Radar può proporre, oltre alle singole, accumulatori da esattamente due selezioni quando la combinazione aumenta l'efficienza rischio/rendimento senza introdurre gambe negative soltanto per alzare la quota.

Le doppie sono un layer aggiuntivo: non sostituiscono le singole e non trasformano NO BET in BET.

## 1. Tipi di doppia

### DOPPIA VALUE
Combinazione preferenziale di due selezioni che superano entrambe il rispettivo FINAL GATE singolo.

Priorità:
- A + A
- A + B
- B + B solo con dati molto solidi e margine sufficiente.

Obiettivo: mantenere value robusto su entrambe le gambe, con correlazione bassa e prezzo combinato sopra il gate combinato.

### DOPPIA SPECULATIVA
Combinazione più aggressiva e a stake ridotto. Può includere:
- A + B
- A + C
- B + C

ma ogni gamba deve comunque essere almeno sopra il proprio FINAL GATE oppure avere una probabilità congiunta esplicitamente modellata che renda positiva la combinazione. Una selezione D / NO BET / sotto gate non può essere usata per costruire una doppia speculativa solo per aumentare la quota.

## 2. Preferenza per partite diverse
Preferire selezioni di due partite differenti. In questo caso, se non emergono dipendenze materiali comuni, la probabilità congiunta preliminare può essere:

`P_doppia = P1 * P2`

Verificare comunque eventuali dipendenze non ovvie: stesso contesto competitivo, rotazioni collegate, mercato/news comune o altra fonte di correlazione.

## 3. Stessa partita
Non moltiplicare ingenuamente probabilità di mercati della stessa partita.

Per una doppia same-game serve una probabilità congiunta modellata esplicitamente considerando la correlazione. Se non è possibile stimarla in modo affidabile, la combinazione è NO BET come doppia anche se le due singole sono interessanti.

## 4. Prezzo e fair combinata
Per eventi indipendenti o sufficientemente indipendenti:
- `P_joint = P1 * P2`
- `fair_joint = 1 / P_joint`
- `quota_combinata_osservata = quota1 * quota2` per una normale multipla senza boost/bonus, usando prezzi correnti realmente osservati.

Il Radar deve mostrare anche il margine rispetto alla fair combinata.

## 5. FINAL GATE della doppia
Una doppia può essere BET soltanto quando:
1. le due gambe sono ammissibili secondo questa policy;
2. i prezzi delle due gambe sono freschi;
3. la probabilità congiunta è stimabile;
4. la quota combinata osservata supera il FINAL GATE combinato.

Per gambe indipendenti, base del gate combinato:
`gate_base = gate1 * gate2`

Applicare un buffer prudenziale aggiuntivo per:
- rischio di errore su due stime;
- data confidence inferiore;
- eventuale correlazione residua;
- player props non direttamente GoldBet-certified.

Quindi il FINAL GATE combinato non deve essere meno prudente del prodotto dei due gate singoli.

## 6. Requisiti minimi DOPPIA VALUE
- entrambe le gambe almeno B, salvo A+A/A+B preferite;
- entrambe sopra FINAL GATE singolo;
- Deep Matchup Analysis completa su entrambe;
- prezzo fresco;
- nessun dato critico stale;
- correlazione bassa o esplicitamente modellata;
- quota combinata sopra FINAL GATE combinato;
- niente duplicazione della stessa tesi di rischio senza dichiararlo.

## 7. Requisiti minimi DOPPIA SPECULATIVA
- nessuna gamba D/NO BET/sotto gate;
- almeno una gamba A o B;
- massimo una gamba C;
- probabilità e fair di entrambe documentate;
- quota combinata sopra FINAL GATE combinato;
- stake sensibilmente inferiore alla DOPPIA VALUE;
- etichetta SPECULATIVA obbligatoria.

## 8. Player props
Se una gamba è un player prop:
- deve rispettare `player_market_bet_ready=true` per essere trattata come BET singola;
- se il prezzo player non è ancora direttamente GoldBet-certified, indicare il caveat;
- il buffer del gate combinato deve aumentare rispetto a due mercati standard direttamente certificati.

## 9. Correlazione ed esposizione
Non proporre una doppia se crea esposizione eccessiva rispetto alle singole già consigliate sulla stessa tesi.

Esempi da trattare con cautela:
- stessa squadra favorita + suo marcatore;
- stesso giocatore marcatore + Over tiri;
- due mercati fortemente dipendenti dallo stesso scenario tattico.

Se la doppia viene suggerita insieme alle singole, mostra l'esposizione come alternativa o stake aggiuntivo ridotto, non come edge completamente indipendente.

## 10. Output obbligatorio
Per ogni doppia mostrare:
- etichetta `DOPPIA VALUE` o `DOPPIA SPECULATIVA`;
- Gamba 1: partita, mercato, selezione, quota, P, fair, FINAL GATE, classe;
- Gamba 2: partita, mercato, selezione, quota, P, fair, FINAL GATE, classe;
- correlazione: BASSA / MEDIA / ALTA e motivo;
- P congiunta;
- fair combinata;
- quota combinata osservata;
- FINAL GATE combinato;
- edge combinato;
- data confidence;
- stake consigliato;
- principali failure modes.

## 11. Volume
Non forzare una doppia ogni giorno. Proporla soltanto quando esistono almeno due gambe compatibili che superano realmente i criteri.

Default di output per una giornata ricca:
- al massimo 1 DOPPIA VALUE principale;
- eventualmente 1 DOPPIA SPECULATIVA separata.

## 12. Validazione
Archiviare prospetticamente ogni doppia proposta con le due gambe, prezzi, probabilità, gate, quota combinata e timestamp. Valutare separatamente performance delle singole e della doppia. Non retro-costruire doppie dopo aver visto gli esiti.
