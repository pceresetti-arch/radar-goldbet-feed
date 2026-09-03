# RADAR UNICO — DEEP ANALYSIS COMPLETION GATE

Questa regola è **VINCOLANTE** e prevale sulla velocità operativa. Nessun verdetto finale BET / NO BET può essere emesso come analisi conclusa se la Deep Analysis obbligatoria non è stata completata.

Il contratto `RADAR_BETFLAG_PLAYER_VALUE_AND_AUDIT_CONTRACT.md` è parte integrante di questo gate.

## 1. XI E IDENTITÀ
- Verificare fixture corretta, competizione, orario e stato della formazione.
- Distinguere UFFICIALE da PROBABILE.
- Verificare 11v11, modulo e `xi_fingerprint` quando disponibile.
- Se cambia l'XI, invalidare e rifare l'analisi giocatore.

## 2. STATO GIOCATORI, RUOLO E MINUTI
Per ogni giocatore offensivo rilevante verificare:
- ruolo reale;
- forma/stato recente;
- titolarità;
- minuti attesi;
- distribuzione dei minuti, non solo media;
- rischio sostituzione;
- rischio sostituzione condizionato al game state;
- rientri/acciacchi/fatica;
- concorrenza dalla panchina;
- rigori e piazzati.

Campi minimi quando materialmente stimabili:
- `expected_minutes_mean`;
- `p_minutes_le_45`;
- `p_minutes_46_65`;
- `p_minutes_66_80`;
- `p_minutes_gt_80`;
- `substitution_risk_reason`.

Un titolare NON equivale automaticamente a 75–90 minuti. La P player deve incorporare il rischio di sostituzione, specialmente per attaccanti di squadre sfavorite o tatticamente sacrificabili.

## 3. FORMAZIONE CONTRO FORMAZIONE
- Analizzare sistema contro sistema, altezza blocco, pressing, transizioni, ampiezza, mezzi spazi, palle inattive, mismatch e assenze.
- Analizzare zone reali d'attacco e vulnerabilità difensive avversarie.
- Valutare matchup giocatore-zona-difensore/sistema e rischio raddoppio/copertura.
- Confrontare esplicitamente tra loro i principali candidati offensivi: TEAM VOLUME non deve essere assegnato automaticamente al centravanti.

## 4. SVILUPPO PARTITA E MODELLO GOL
- Stimare xG/gol attesi squadra e match.
- Stimare P(squadra segna 1+/2+/3+).
- Modulo 1T obbligatorio: P(>=1 gol 1T), xG 1T e fair odds.
- Valutare game state plausibili e loro impatto sui giocatori/mercati.
- Integrare il rischio che uno svantaggio multiplo precoce cambi minuti, ruolo, volume e sostituzioni.

## 5. BETFLAG TRUE OPEN / MOVIMENTO — OBBLIGATORIO COME STATO, NON COME PREZZO SOSTITUTIVO
Per il Radar operativo il bookmaker di riferimento è **solo BetFlag/AAMS**.

Ogni analisi deve dichiarare lo stato del movimento BetFlag della stessa identità:
`fixture + market + period + line + selection + player` quando applicabile.

Priorità apertura:
1. `TRUE OPEN BETFLAG` solo con prova esplicita BetFlag;
2. `OPEN RADAR CERTIFICATA BETFLAG` solo con osservazione BetFlag continua e sana che dimostri assenza -> comparsa;
3. `FIRST_SEEN` solo diagnostico.

Quando disponibili, conservare:
`TRUE OPEN -> intermedi -> pre-XI -> post-XI -> T-40 -> T-30 -> CURRENT`.

Regole:
- se TRUE OPEN non è certificata: `TRUE OPEN NON CERTIFICATA / MOVIMENTO INCOMPLETO`;
- se T-40/T-30 non sono stati catturati: `NON CATTURATO`;
- distinguere `ACTIVE_DROP`, `REBOUNDED_AFTER_DROP`, `RISING`, `FLAT`;
- prima del FINAL GATE dichiarare se il movimento BetFlag SUPPORTA / CONTRADDICE / è NEUTRO.

GoldBet e altri bookmaker sono ammessi esclusivamente come **contesto/shadow/cross-market research** chiaramente separato. Non possono:
- sostituire CURRENT BetFlag;
- diventare il prezzo del FINAL GATE;
- produrre una BET;
- essere presentati nel board operativo come quote giocabili.

L'assenza di TRUE OPEN BetFlag non impedisce da sola una decisione basata su CURRENT BetFlag fresco e certificato, ma impedisce qualsiasi pretesa di MMS/OPEN forte.

## 6. MERCATI STANDARD — BETFLAG ONLY PER IL VERDETTO
Scandagliare su BetFlag, quando disponibili:
- 1X2;
- O/U;
- Goal/No Goal;
- team total;
- 1T/2T;
- handicap/DNB;
- combo e mercati correlati.

Per ogni mercato operativo servono identità esatta, prezzo BetFlag fresco e FINAL GATE.

## 7. PLAYER PROPS — MATRICE BETFLAG COMPLETA OBBLIGATORIA
Fonte primaria e unica per il prezzo operativo: **BetFlag/AAMS**.

Per ogni candidato rilevante scandagliare i soli mercati effettivamente disponibili su BetFlag, inclusi quando presenti:
- Marcatore anytime;
- Marcatore Plus;
- Marcatore 1T;
- Marcatore 2T;
- Primo Marcatore;
- Primo Marcatore o Sostituto;
- Marcatore o Sostituto / Plus;
- Gol o Assist PURO;
- Gol e Assist;
- Assist / Assist o Sostituto;
- Assist o Sostituto o Marcatore Plus;
- Tiri totali;
- Tiri in porta;
- Tiri / SOT Plus;
- combo player-match;
- altri player props BetFlag disponibili.

Per ogni riga calcolare una P specifica del mercato. È vietato usare la P(anytime) come sostituto meccanico per Plus, 1T, Gol/Assist, SOT o combo.

Se una quota BetFlag non è fresca/certificata: `ATTESA QUOTA / NON VALUTABILE`; non usare prezzi esterni.

## 8. SCOUTING RANKING E VALUE RANKING
Produrre due ranking separati:

1. **PLAYER DANGER / SCOUTING RANKING** — probabilità/profilo offensivo indipendente dal prezzo;
2. **BETFLAG VALUE RANKING** — solo mercati BetFlag certificati, ordinati per edge, robustezza, minuti, ruolo e rischio.

Un giocatore forte non è automaticamente una BET. Un giocatore può essere NO BET anytime ma BET su Marc Plus, Gol/Assist, tiri o SOT.

## 9. PRICE GATE BETFLAG
Per ogni candidata:
- P Radar specifica del mercato;
- fair odds;
- FINAL GATE;
- CURRENT BetFlag certificato;
- edge.

Regole:
- BET solo se `BetFlag CURRENT >= FINAL GATE` e tutti gli altri gate sono superati;
- sotto gate = NO BET;
- quota BetFlag non certificata = ATTESA QUOTA;
- se l'utente gioca sotto gate = USER OVERRIDE / SOTTO SOGLIA.

Nessun bookmaker esterno può colmare il CURRENT BetFlag mancante.

## 10. CORRELATION EXPOSURE GATE
Prima di finalizzare più giocate della stessa partita, raggruppare le selezioni che condividono la stessa tesi latente.

Registrare:
- `correlation_cluster`;
- stake nominale totale;
- correlazione `LOW/MEDIUM/HIGH/VERY_HIGH`;
- `effective_exposure`;
- scenario comune di perdita;
- cap applicato.

Più ticket altamente correlati NON sono diversificazione. Un cluster HIGH/VERY_HIGH non deve superare lo stake massimo previsto per una singola tesi salvo edge straordinario esplicitamente documentato.

## 11. HARD STOP
Se anche uno dei blocchi 1-10 è materialmente incompleto, il Radar non può presentare il lavoro come analisi finale completa.

Output consentiti:
- `ANALISI INCOMPLETA — NESSUN VERDETTO FINALE`;
- `ATTESA`;
- `ATTESA QUOTA`;
- `NO BET`.

Una BET è vietata se manca:
- quota BetFlag fresca/univoca;
- identità esatta del mercato;
- player mapping esatto;
- P specifica del mercato;
- controllo minuti/game-state;
- correlation gate quando esistono esposizioni multiple.

## 12. STORICO E AUDIT
Ogni analisi, anche NO BET / ATTESA / ANALISI INCOMPLETA, deve essere conservata con:
- timestamp;
- fixture;
- stato XI;
- scouting rank;
- BetFlag value rank;
- fonte/provenienza prezzo;
- identità mercato esatta;
- TRUE OPEN BetFlag o stato di mancata certificazione;
- snapshot realmente osservati;
- P/fair/gate;
- expected minutes e substitution risk;
- correlation cluster;
- decisione e motivazioni.

La retroanalisi deve seguire `RADAR_BETFLAG_PLAYER_VALUE_AND_AUDIT_CONTRACT.md` e non deve retro-modificare le decisioni pre-match.
