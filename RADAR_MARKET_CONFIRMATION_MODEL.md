# Radar Unico — Cross-Market Movement / Market Confirmation Model

Stato: **RESEARCH + SHADOW MODE**
Data: 2026-08-26

## Obiettivo
Evolvere il modulo MMS da semplice controllo del singolo calo quota a un modello multidimensionale che incrocia il movimento di più mercati della stessa partita per capire **che cosa il mercato sta realmente riprezzando**: forza squadra, gol attesi, gol attesi della singola squadra, tempistica 1T/2T e, quando disponibile, player-specific movement.

Il modello NON sostituisce la Deep Matchup Analysis e NON genera una BET da solo. Finché non supera validazione prospettica/OOS, opera in shadow mode: registra segnali, produce score diagnostici e misura l'incremento informativo senza applicare pesi arbitrari al FINAL GATE.

## 1. Vincolo TRUE OPEN
Ogni movimento operativo deve usare esclusivamente la vera apertura certificata della stessa fonte/bookmaker, stessa fixture, mercato, periodo, linea e selezione.

Per GoldBet:
- `TRUE_OPEN_CERTIFIED` è l'unica apertura ammessa per il movimento principale.
- `FIRST_SEEN`, primo snapshot Radar, `OPEN_RADAR_PROXY`, quote trovate all'inizio dell'analisi, medie di mercato e altri bookmaker NON sono TRUE OPEN.
- se la TRUE OPEN non è certificabile, registrare `TRUE_OPEN_NON_CERTIFIED` e non produrre MMS forte.

Sequenza da conservare quando realmente osservata:
`TRUE OPEN -> intermedi -> pre-XI -> post-XI -> T-40 -> T-30 -> CURRENT -> CLOSE ex post`.

## 2. Normalizzazione: quote -> probabilità de-vigged
Il confronto tra mercati non deve basarsi solo sulla variazione assoluta della quota decimale.

Per ogni checkpoint calcolare:
- quota decimale;
- probabilità implicita grezza;
- overround del mercato;
- probabilità implicita de-vigged;
- delta in punti probabilità rispetto alla TRUE OPEN;
- delta relativo;
- velocità del movimento per unità di tempo.

La variazione assoluta in punti quota (es. -0,20) resta registrata per continuità MMS, ma il modello cross-market usa soprattutto la variazione de-vigged.

## 3. Famiglie di mercato

### A. Team Strength
Mercati principali:
- 1X2 FT;
- handicap / Asian Handicap quando disponibile;
- DNB.

Domanda: il mercato sta aumentando/diminuendo la forza relativa della squadra?

### B. Match Goal Environment
Mercati principali:
- Over/Under FT linea principale;
- linee adiacenti quando liquide;
- Goal/No Goal come conferma separata.

Domanda: il mercato sta aumentando/diminuendo i gol attesi complessivi?

### C. Team Scoring Expectation
Mercati principali:
- Team Total FT;
- squadra segna 1+/2+/3+ quando disponibile.

Domanda: il repricing è specifico sui gol della squadra oppure solo sull'esito?

### D. First-Half / Timing
Mercati principali:
- Over/Under 1T;
- 1X2/handicap 1T;
- Team Total 1T quando disponibile.

Domanda: il vantaggio/gol attesi sono anticipati nei primi 45 minuti?

### E. Player-Specific
Quando è disponibile una serie affidabile e identificata della stessa selezione:
- Marcatore;
- Marcatore 1T/2T;
- Gol o Assist;
- tiri;
- tiri in porta;
- altri props rilevanti.

Il movimento player BetFlag/AAMS deve restare etichettato come BetFlag/AAMS e NON come GoldBet senza prezzo GoldBet diretto certificato.

## 4. Feature da costruire
Per ogni mercato/famiglia salvare almeno:
- true_open_price;
- true_open_time;
- current_price/time;
- de_vig_p_open;
- de_vig_p_current;
- delta_probability_points;
- delta_decimal_price;
- elapsed_minutes;
- movement_velocity;
- pre_XI_delta;
- post_XI_delta;
- T40_delta;
- T30_delta;
- close_delta ex post;
- ACTIVE_DROP / REBOUNDED_AFTER_DROP / RISING / FLAT;
- source/freshness/confidence.

## 5. Coerenza cross-market
Costruire indicatori di convergenza/divergenza fra famiglie.

Esempi da classificare:

### Offensive bullish convergence
- forza squadra sale;
- handicap conferma;
- Over FT sale;
- Team Total sale;
- 1T sale.

Interpretazione: repricing coerente verso più forza offensiva e maggiore produzione gol.

### Strength-only movement
- 1X2/handicap favorevoli;
- Under FT sale / Over scende;
- Team Total poco mosso.

Interpretazione: maggiore probabilità di vittoria, ma non necessariamente più gol/valore marcatori.

### Team-concentrated scoring
- Team Total squadra sale forte;
- totale match poco mosso;
- Goal/No Goal va verso No.

Interpretazione: redistribuzione dei gol verso una sola squadra; potenzialmente molto rilevante per i player props della squadra favorita.

### Divergence / warning
Mercati correlati si muovono in direzioni incompatibili o senza consenso sufficiente.

Il modello deve assegnare un livello di coerenza: `HIGH`, `MEDIUM`, `LOW`, `CONTRADICTORY`.

## 6. Accelerazione e informazione post-XI
Separare il movimento in finestre temporali:
- OPEN -> pre-XI;
- pre-XI -> post-XI;
- post-XI -> T-30;
- T-30 -> close (diagnostico ex post).

Costruire un `POST_XI_ACCELERATION_SCORE` che misuri se la velocità/direzione del movimento cambia materialmente dopo la pubblicazione della formazione ufficiale.

L'accelerazione post-XI può essere più informativa del semplice delta cumulativo, ma va validata OOS prima di diventare un correttore operativo.

## 7. Market Confirmation Index (MCI)
Obiettivo: sintetizzare le famiglie senza perdere interpretabilità.

Output candidato:
- `TEAM_STRENGTH_SCORE`;
- `MATCH_GOALS_SCORE`;
- `TEAM_SCORING_SCORE`;
- `FIRST_HALF_SCORE`;
- `PLAYER_SPECIFIC_SCORE`;
- `COHERENCE_SCORE`;
- `POST_XI_ACCELERATION_SCORE`;
- `MCI_TOTAL` su scala normalizzata, ad es. -100..+100.

### Regola anti-overfitting
NON fissare operativamente pesi tipo 35/25/25/15 per intuizione.

I pesi devono essere:
1. stimati sul development set;
2. congelati;
3. verificati su holdout temporale/OOS;
4. sottoposti a bootstrap, sensitivity e leave-one-league-out;
5. promossi solo se migliorano robustamente il benchmark.

Finché questo non avviene, lo score resta shadow/diagnostico.

## 8. Target di validazione
Validare separatamente la capacità del segnale di migliorare:
- P(squadra segna >=1);
- P(squadra segna >=2);
- P(squadra segna >=3);
- Over/Under FT;
- P(gol 1T);
- team xG calibration;
- player P(gol);
- player P(gol 1T);
- tiri / SOT quando disponibili;
- CLV e ROI/yield solo dove esiste prezzo osservato affidabile.

Metriche:
- Brier score;
- log-loss;
- calibrazione;
- lift vs modello senza movimento;
- AUC solo come diagnostica secondaria quando sensata;
- CLV;
- ROI/yield con intervalli di confidenza;
- stabilità per lega/stagione/mercato/fascia quota.

## 9. Ablation obbligatoria
Confrontare sullo stesso campione:
- modello base senza movement features;
- + singola famiglia (1X2, O/U, Team Total, 1T...);
- + cross-market coherence;
- + post-XI acceleration;
- + MCI completo.

Serve a capire quali famiglie aggiungono vera informazione e quali duplicano segnali già contenuti nel modello o negli altri mercati.

## 10. Repricing del modello — solo dopo promozione OOS
In futuro, se validato, MCI potrà modificare prudentemente team-xG/P Radar.

Vincoli:
- nessun salto arbitrario;
- cap massimo del delta;
- evitare doppio conteggio con mercato già incluso altrove;
- distinguere effetto sulla forza squadra da effetto sui gol;
- la direzione del correttore deve essere interpretabile.

Esempio concettuale (NON ancora operativo): forte convergenza offensiva può aumentare leggermente team-xG; strength-only movement può aumentare P(vittoria) senza aumentare significativamente P(marcatore).

## 11. Redistribuzione ai giocatori
Un eventuale delta team-xG validato NON va assegnato automaticamente al centravanti.

Redistribuire secondo:
- share xG/npxG;
- ruolo XI reale;
- minuti attesi;
- rigori/piazzati;
- tiri e SOT;
- zone di conclusione;
- teammate network;
- cannibalizzazione;
- matchup;
- natura del segnale (FT vs 1T, team total vs strength-only).

## 12. Gate di promozione
Il modulo può passare da `RESEARCH/SHADOW` a `OPERATIONAL_CORRECTOR` solo se:
- migliora OOS Brier/log-loss/calibrazione in modo replicabile;
- non dipende da una singola lega/stagione;
- mantiene direzione sensata nelle sensitivity analysis;
- l'effetto è materialmente utile e non solo statisticamente minimo;
- non peggiora il FINAL GATE tramite overfitting;
- sono documentati failure modes e cap del correttore.

## 13. Priorità di lavoro
1. Costruire dataset TRUE OPEN -> CURRENT/T-30 per 1X2, handicap, O/U FT, Team Total, mercati 1T.
2. De-vigging e normalizzazione temporale.
3. Costruire family scores senza pesi operativi.
4. Coherence/divergence classifier.
5. Post-XI acceleration.
6. Ablation development.
7. Freeze pesi/regole.
8. Holdout/OOS.
9. Solo dopo eventuale promozione, integrazione prudente in team-xG/P Radar/FINAL GATE.

## Regola finale
**Movimento quota = informazione, non decisione.**

Il valore del modulo nasce dall'incrocio coerente di più mercati, dalla vera apertura e dalla validazione prospettica; non dal fatto che una singola quota sia semplicemente scesa.