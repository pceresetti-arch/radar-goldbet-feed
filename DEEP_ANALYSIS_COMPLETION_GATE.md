# RADAR UNICO — DEEP ANALYSIS COMPLETION GATE

Questa regola è VINCOLANTE e prevale sulla velocità operativa. Nessun verdetto finale BET / NO BET può essere emesso come analisi conclusa se la Deep Analysis obbligatoria non è stata completata.

## Sequenza obbligatoria prima del verdetto finale

1. XI E IDENTITÀ
- Verificare fixture corretta, competizione, orario e stato della formazione.
- Distinguere UFFICIALE da PROBABILE.
- Verificare 11v11, modulo e xi_fingerprint quando disponibile.
- Se cambia l'XI, invalidare e rifare l'analisi giocatore.

2. STATO GIOCATORI E MINUTI
- Per ogni giocatore offensivo rilevante verificare ruolo reale, forma/stato recente, titolarità, minuti attesi, rischio sostituzione, eventuali rientri/acciacchi, rigori e piazzati.

3. FORMAZIONE CONTRO FORMAZIONE
- Analizzare sistema contro sistema, altezza blocco, pressing, transizioni, ampiezza, mezzi spazi, palle inattive, mismatch e assenze.
- Analizzare zone reali d'attacco e vulnerabilità difensive avversarie.
- Valutare matchup giocatore-zona-difensore/sistema e rischio raddoppio/copertura.

4. SVILUPPO PARTITA E MODELLO GOL
- Stimare xG/gol attesi squadra e match.
- Stimare P(squadra segna 1+/2+/3+).
- Modulo 1T obbligatorio: P(>=1 gol 1T), xG 1T e fair odds.
- Valutare game state plausibili e loro impatto sui giocatori/mercati.

5. TRUE OPEN E MOVIMENTO QUOTE — OBBLIGATORIO
- Ogni analisi deve includere un controllo esplicito del movimento quote a partire dalla TRUE OPEN certificata, non dal FIRST_SEEN.
- Il movimento principale deve essere SAME BOOKMAKER: GoldBet → GoldBet, stessa fixture, stesso mercato, stesso periodo, stessa linea e stessa selezione.
- Sequenza da ricostruire e mostrare quando disponibile: TRUE OPEN → snapshot intermedi → T-40 → T-30 → CURRENT/pre-kickoff. Ogni checkpoint deve avere timestamp/minuti al kickoff quando disponibili.
- `FIRST_SEEN`, `OPEN_RADAR_PROXY`, `OPEN_CAPTURED_NEAR_PUBLICATION`, medie di mercato o quote di altri bookmaker NON possono essere chiamati TRUE OPEN GoldBet.
- Se la TRUE OPEN non è certificata, scrivere chiaramente `TRUE OPEN NON CERTIFICATA / MOVIMENTO INCOMPLETO`; non inventare né retro-ricostruire un'apertura.
- Se T-40 o T-30 non sono stati realmente catturati, dichiararli `NON CATTURATO`; non sostituirli con il CURRENT.
- Segnale MMS forte standard solo se la quota GoldBet scende di almeno 0,20 punti dalla TRUE OPEN certificata sulla stessa selezione/linea.
- Distinguere `ACTIVE_DROP` da `REBOUNDED_AFTER_DROP` quando la quota è scesa e poi risalita.
- Il confronto cross-bookmaker è consentito solo come conferma separata e non sostituisce il movimento GoldBet same-book.
- Per player props BetFlag/AAMS, eventuale movimento va etichettato come movimento BetFlag/AAMS; non deve mai essere chiamato movimento GoldBet senza prezzo GoldBet diretto certificato.
- Prima del FINAL GATE deve essere esplicitamente riportato se il movimento di mercato SUPPORTA, CONTRADDICE o è NEUTRO rispetto alla lettura del modello.

6. MERCATI STANDARD
- Scandagliare 1X2, O/U, Goal/No Goal, team total, 1T/2T e mercati correlati disponibili.
- Integrare il blocco TRUE OPEN/MMS del punto 5 nella valutazione finale, senza sostituire il modello fondamentale con il movimento quota.

7. PLAYER PROPS — SCANSIONE COMPLETA OBBLIGATORIA
Fonte primaria operativa: BetFlag/AAMS, senza attendere GoldBet player diretto. GoldBet player, se disponibile, è cross-check/calibrazione.
Scandagliare SEMPRE, quando disponibili:
- Marcatore anytime
- Marcatore 1° tempo
- Marcatore 2° tempo
- Primo Marcatore
- Primo Marcatore o Sostituto
- Marcatore o Sostituto / Plus
- Gol o Assist PURO
- Gol e Assist
- Assist / Assist o Sostituto
- Assist o Sostituto o Marcatore Plus
- Tiri totali giocatore
- Tiri in porta giocatore
- Tiri/tiro in porta Plus
- Altri player props disponibili

Marcatore 1° tempo e Gol o Assist PURO NON sono opzionali quando il mercato è disponibile.

8. PRICE GATE
- Per ogni candidata calcolare P Radar, fair odds e FINAL GATE.
- BET solo se prezzo operativo corrente >= FINAL GATE.
- Sotto gate = NO BET.
- Se l'utente gioca comunque sotto gate = USER OVERRIDE / SOTTO SOGLIA.
- Il FINAL GATE deve essere applicato solo dopo il controllo del blocco TRUE OPEN/MOVIMENTO QUOTE.

## HARD STOP
Se anche uno dei blocchi 1-8 non è stato eseguito o è materialmente incerto, il Radar NON può presentare il lavoro come analisi finale completa. Deve scrivere chiaramente:
`ANALISI INCOMPLETA — NESSUN VERDETTO FINALE` oppure `ATTESA`, indicando quale blocco manca.

Il blocco movimento si considera eseguito solo se è stata tentata/verificata la TRUE OPEN e il suo stato è dichiarato. Se la fonte non dispone di una TRUE OPEN certificata, il Radar deve mostrare `TRUE OPEN NON CERTIFICATA / MOVIMENTO INCOMPLETO` e non può usare un proxy come segnale MMS.

È vietato sostituire la Deep Analysis con il solo recupero quote, con una shortlist parziale o con un'analisi precedente non riallineata all'XI corrente.

## Storico
Ogni analisi, anche NO BET / ATTESA / ANALISI INCOMPLETA, deve essere conservata per audit retrospettivo con timestamp, fixture, stato XI, fonti prezzo, TRUE OPEN certificata o stato di mancata certificazione, snapshot intermedi/T-40/T-30/CURRENT quando realmente osservati, P/fair/gate, decisione e motivazioni disponibili.
