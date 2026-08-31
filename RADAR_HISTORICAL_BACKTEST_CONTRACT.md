# Radar Unico — Historical Backtest Contract

Versione: 2026-08-31
Stato: VINCOLANTE per il BACKTEST MASTER STORICO; non modifica il Radar operativo.

## 1. Scopo
Costruire un backtest storico multi-stagione incrementale usando esclusivamente informazioni dimostrabilmente conoscibili prima del kickoff. Il backtest storico e l'audit operativo giornaliero sono filoni distinti e non devono contaminarsi.

## 2. Anti-hindsight
È vietato usare per costruire feature o decisioni pre-match:
- risultato finale;
- statistiche post-match;
- XI, news, quote o timestamp pubblicati dopo il kickoff;
- prezzi ricostruiti o interpolati senza snapshot reale;
- FIRST_SEEN come sostituto di TRUE OPEN quando il test richiede OPEN certificato;
- dati di stagioni future nel development set.

Outcome e statistiche post-match possono essere uniti solo dopo il freeze delle feature pre-match e servono esclusivamente alla valutazione.

## 3. Unità minima eleggibile
Una fixture entra nel dataset storico soltanto se sono verificati senza ambiguità almeno:
- competition;
- season;
- fixture_id stabile o chiave di join equivalente;
- kickoff_utc;
- home_team e away_team;
- outcome autorevole, unito ex post;
- bookmaker;
- market/line/selection;
- almeno un prezzo pre-match osservato con timestamp e provenienza;
- source_reliability.

Per OPEN→CLOSE/MMS sono inoltre richiesti OPEN e CLOSE realmente osservati sullo stesso bookmaker, stesso evento, mercato, periodo, linea e selezione.

## 4. TRUE OPEN e movimento
MMS primario storico:
- bookmaker GoldBet;
- TRUE OPEN certificato;
- mercati 1X2 FT e OVER FT;
- drop assoluto >= 0.20 come soglia standard da validare, non da assumere ottimale;
- FIRST_SEEN solo diagnostico;
- preservare ACTIVE_DROP e REBOUNDED_AFTER_DROP quando esistono snapshot intermedi validi.

OPEN→T-30 può essere testato solo se lo snapshot T-30 esiste realmente. Non stimare T-30 dal CLOSE.

## 5. Split temporale
Ogni lega/stagione conserva ordine temporale. Soglie, pesi, feature selection e calibrazione vengono definiti soltanto sul development set e congelati prima del holdout/OOS. Sono vietati random split che mescolano futuro e passato quando possono introdurre leakage temporale.

## 6. Baseline e filoni
Ordine di lavoro:
1. risultati + forza strutturale pre-match/Elo o proxy documentato + forma pre-match + casa/trasferta + qualità avversari;
2. quote same-book OPEN→CLOSE;
3. MMS e soglie movimento per lega/mercato/ampiezza;
4. 1X2, O/U, Goal/No Goal, team total e mercati correlati;
5. player props solo con prezzi e identità pre-match verificabili;
6. XI/xi_fingerprint, ruolo/minuti/matchup solo con pubblicazione pre-kickoff documentabile;
7. PRE-XI vs POST-XI FULL REDISCOVERY soltanto quando esistono entrambi gli snapshot storici pre-kickoff.

## 7. Metriche
Calcolare dove definibili:
- Brier score;
- log-loss;
- calibrazione/reliability;
- CLV solo con prezzo di confronto realmente osservato;
- hit rate;
- ROI/yield soltanto su prezzi realmente osservati e su strategie definite ex ante;
- drawdown;
- robustness per lega/mercato/ruolo;
- leave-one-league-out quando il campione lo consente.

Nessuna metrica economica deve essere prodotta su quote inventate o ricostruite.

## 8. Ablation
Confronti accoppiati sullo stesso campione eleggibile:
- BASE;
- BASE + MOVEMENT;
- BASE + XI;
- BASE + MINUTES;
- BASE + MATCHUP/CONCESSION;
- BASE + HEATMAP;
- combinazioni predefinite.

Un modulo non diventa edge autonomo senza miglioramento prospettico/OOS replicabile. Niente promozione da un singolo campione o da un singolo risultato.

## 9. Data quality
Registrare per ogni source/block:
- missingness;
- duplicati;
- fixture mapping ambiguity;
- timestamp ambiguity;
- stale/last-known-good;
- source failure;
- margine bookmaker/de-vigging quando applicabile;
- anomalie e quarantena.

Campioni non sufficientemente solidi vanno esclusi o quarantinati, non forzati.

## 10. Perimetro e avanzamento
Priorità iniziale: Svezia, poi Norvegia, poi altre leghe Radar con copertura storica sufficiente. Le quattro stagioni richieste devono essere nominate solo quando i label stagione sono presenti o acquisiti da una fonte verificabile; non inferirli dal nulla.

Il ledger persistente `feed/historical-backtest-ledger.json` è il checkpoint di avanzamento. Il manifest fonti `feed/historical-source-manifest.json` descrive cosa manca, cosa è eleggibile e cosa è in quarantena.

## 11. Separazione dall'audit giornaliero
L'audit giornaliero può unire outcome alle previsioni prospettiche concluse, ma non deve retro-modificare snapshot, prezzi, XI, source class o decisioni. P/L e ROI personali appartengono al registro privato delle giocate effettivamente piazzate e non al repository pubblico.
