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

5. MERCATI STANDARD
- Scandagliare 1X2, O/U, Goal/No Goal, team total, 1T/2T e mercati correlati disponibili.
- Per movimento GoldBet usare solo SAME BOOKMAKER e TRUE OPEN certificata quando esiste; FIRST_SEEN solo diagnostico.

6. PLAYER PROPS — SCANSIONE COMPLETA OBBLIGATORIA
Fonte primaria operativa: BetFlag/AAMS, senza attendere GoldBet player diretto. GoldBet player, se disponibile, è cross-check/calibrazione.
Scandagliare SEMPRE, quando disponibili:
- Marcatore anytime
- Marcatore 1° tempo
- Marcatore 2° tempo
- Primo Marcatore
- Primo Marcatore o Sostituto
- Marcatore o Sostituto / Plus
- Gol o Assist / Gol e Assist
- Assist / Assist o Sostituto
- Tiri totali giocatore
- Tiri in porta giocatore
- Tiri/tiro in porta Plus
- Altri player props disponibili

Marcatore 1° tempo NON è opzionale e non può essere saltato.

7. PRICE GATE
- Per ogni candidata calcolare P Radar, fair odds e FINAL GATE.
- BET solo se prezzo operativo corrente >= FINAL GATE.
- Sotto gate = NO BET.
- Se l'utente gioca comunque sotto gate = USER OVERRIDE / SOTTO SOGLIA.

## HARD STOP
Se anche uno dei blocchi 1-7 non è completato o è materialmente incerto, il Radar NON può presentare il lavoro come analisi finale completa. Deve scrivere chiaramente:
`ANALISI INCOMPLETA — NESSUN VERDETTO FINALE` oppure `ATTESA`, indicando quale blocco manca.

È vietato sostituire la Deep Analysis con il solo recupero quote, con una shortlist parziale o con un'analisi precedente non riallineata all'XI corrente.

## Storico
Ogni analisi, anche NO BET / ATTESA / ANALISI INCOMPLETA, deve essere conservata per audit retrospettivo con timestamp, fixture, stato XI, fonti prezzo, P/fair/gate, decisione e motivazioni disponibili.