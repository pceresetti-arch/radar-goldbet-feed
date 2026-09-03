# Radar Unico — BetFlag Player Value & Scorer Audit Contract

Versione: 2026-09-03
Stato: **VINCOLANTE — OPERATIVO**

## 1. Principio fondamentale
Il Radar può emettere un verdetto operativo `BET`, `NO BET` o `ATTESA QUOTA` su una selezione solo rispetto a un mercato e a una quota **effettivamente disponibili e certificati su BetFlag/AAMS**.

Quote di GoldBet o di altri bookmaker possono essere usate esclusivamente come contesto di mercato, confronto secondario o ricerca storica. Non possono:
- sostituire una quota BetFlag mancante;
- entrare nel FINAL GATE come prezzo giocabile;
- trasformare un candidato in BET;
- essere mostrate nel board operativo come se fossero BetFlag.

Se non esiste una prova fresca e univoca della quota BetFlag: `ATTESA QUOTA / NON VALUTABILE`.

## 2. Provenienza obbligatoria della quota
Ogni quota operativa deve conservare almeno:
- `bookmaker = BETFLAG`;
- `source_provenance = BETFLAG_AAMS_DIRECT`;
- `captured_at`;
- `fixture_id` o mapping fixture univoco;
- etichetta mercato grezza BetFlag;
- mercato normalizzato;
- periodo;
- linea, quando applicabile;
- selezione;
- player identity, quando applicabile;
- stato freshness;
- stato exact-match / unique-match.

Il board finale deve distinguere chiaramente:
- `BETFLAG VERIFIED`;
- `BETFLAG STALE`;
- `BETFLAG ACQUISITION FAILED`;
- `BETFLAG MARKET NOT QUOTED`.

`MARKET NOT QUOTED` richiede prova positiva di assenza da una scansione sana; non può essere dedotto da un errore di acquisizione.

## 3. Identità esatta del mercato e settlement
I mercati player NON devono essere fusi in un generico “marcatore”. Conservare sempre l'identità BetFlag esatta, inclusa la semantica di settlement.

Esempi distinti:
- Marcatore anytime;
- Marcatore Plus;
- Marcatore 1T;
- Marcatore 2T;
- Primo Marcatore;
- Marcatore o Sostituto;
- Marcatore o Sostituto Plus;
- Gol o Assist;
- Assist;
- Assist o Sostituto;
- tiri;
- tiri in porta;
- mercati Plus su tiri/SOT;
- combo player-match.

Il modello deve stimare `P` e fair separatamente per ogni mercato. Non è consentito usare la P(anytime) come sostituto diretto di P(Marc Plus), P(1T), P(Gol o Assist) o di una combo.

In retroanalisi, la selezione deve essere chiusa applicando **la regola di settlement del mercato BetFlag realmente giocato**. Esempio: se un Marc Plus attribuisce esito vincente a un legno, il post-match deve cercare e registrare legni del giocatore; non basta controllare il tabellino marcatori.

## 4. Matrice BetFlag per ogni candidato
Per ogni scorer/player candidate rilevante, dopo XI ufficiali quando disponibili, costruire una matrice dei soli mercati BetFlag effettivamente presenti.

Campi minimi per riga:
- player;
- market;
- BetFlag price;
- P Radar specifica del mercato;
- fair odds;
- FINAL GATE;
- edge assoluto/relativo;
- expected minutes;
- ruolo reale XI;
- rigori/piazzati;
- xG/npxG share stimata;
- shot/SOT share stimata;
- substitution/game-state risk;
- correlation cluster;
- verdict.

Un giocatore può essere `NO BET` come anytime ma `BET` come Marc Plus, Gol o Assist, 1T, tiri o SOT. Il ranking deve essere mercato-specifico.

## 5. Scouting separato dal value
Il Radar deve mantenere due graduatorie distinte:

### A. Scorer / player danger ranking
Ordina i giocatori per probabilità/profilo offensivo indipendentemente dal prezzo.

### B. BetFlag value ranking
Ordina solo selezioni con quota BetFlag certificata in base a edge, robustezza, minuti, ruolo, rischio e correlazione.

Un giocatore può essere un ottimo candidato scouting ma non una BET al prezzo BetFlag disponibile. Il report non deve confondere le due cose.

## 6. Expected Minutes × Game-State Substitution Risk
La probabilità player deve incorporare una distribuzione dei minuti, non un singolo numero ottimistico.

Registrare almeno:
- `expected_minutes_mean`;
- `p_minutes_le_45`;
- `p_minutes_46_65`;
- `p_minutes_66_80`;
- `p_minutes_gt_80`;
- `substitution_risk_reason`.

Aumentare la penalizzazione quando sono presenti uno o più fattori:
- squadra nettamente sfavorita;
- rischio di svantaggio multiplo precoce;
- giocatore tatticamente sacrificabile;
- concorrenza forte dalla panchina;
- rientro da infortunio/fatica;
- congestione calendario;
- storico di sostituzioni anticipate;
- cambio modulo plausibile in svantaggio.

La P(goal/assist/shots) deve essere integrata sui minuti attesi e sui game state plausibili. Un titolare non equivale automaticamente a 75–90 minuti.

## 7. TEAM VOLUME ≠ PLAYER VOLUME
Un incremento di team-xG, Team Total o probabilità vittoria non deve essere assegnato automaticamente al centravanti.

Redistribuire il volume secondo:
- share xG/npxG;
- ruolo e posizione XI;
- tocchi area e zone di conclusione;
- tiri/SOT;
- rigori/piazzati;
- teammate network e assist supply;
- cannibalizzazione con altri finalizzatori;
- matchup individuale/zona;
- minuti e rischio cambio;
- natura del segnale di squadra.

Per ogni partita confrontare esplicitamente almeno i principali candidati offensivi tra loro prima del verdetto.

## 8. Correlation Exposure Gate
Mercati della stessa partita che dipendono dalla stessa tesi latente devono essere raggruppati in un `correlation_cluster`.

Esempi:
- No Goal + Under 2.5 + No Goal/Under combo;
- vittoria squadra + team total + scorer della stessa squadra;
- scorer + scorer 1T + scorer combo fortemente sovrapposti;
- più props dello stesso giocatore guidati dallo stesso volume offensivo.

Per ogni cluster calcolare/registrare:
- selezioni incluse;
- stake nominale totale;
- grado di correlazione qualitativo `LOW/MEDIUM/HIGH/VERY_HIGH`;
- `effective_exposure`;
- scenario comune che fa perdere il cluster;
- cap di esposizione applicato.

Regola: più ticket altamente correlati NON vengono trattati come diversificazione. Il totale del cluster non può superare lo stake massimo previsto per una singola tesi senza edge straordinario, esplicitamente documentato.

## 9. Regime-change protection
In audit e calibrazione distinguere eventi che cambiano materialmente il processo rispetto al pre-match:
- espulsione precoce;
- infortunio/cambio forzato;
- portiere fuori;
- rigore/rosso combinato;
- svantaggio multiplo molto precoce;
- condizioni meteo/campo mutate materialmente.

Marcare `REGIME_CHANGE` con minuto e tipo. Non usare ingenuamente statistiche post-evento per concludere che la P pre-match fosse errata.

## 10. Audit giornaliero obbligatorio
Dopo la conclusione della giornata Radar, l'audit deve includere **tutte** le previsioni archiviate, non soltanto le scommesse piazzate.

Tenere due registri distinti:

### A. Giocate effettive
- mercato BetFlag esatto;
- quota effettivamente presa;
- stake;
- settlement reale;
- ritorno/P&L;
- process grade indipendente dall'esito.

### B. Previsioni non giocate
- BET non eseguite;
- NO BET;
- ATTESA;
- shortlist;
- candidati scartati;
- mercati alternativi analizzati.

Per ogni previsione player verificare, quando disponibili:
- gol;
- assist;
- minuti e minuto sostituzione;
- ruolo reale;
- xG/xA;
- tiri/SOT;
- big chances;
- tocchi area;
- legni;
- rigori/piazzati;
- game state;
- eventi di regime change.

## 11. Metriche scorer obbligatorie
Calcolare su campioni sufficienti e congelati ex ante:

### Scouting Hit Rate
Quanto spesso il marcatore reale o un player ad alta produzione era presente nel top-N del Radar.

### Ranking Hit Rate
Quanto spesso il player/evento migliore era correttamente ordinato rispetto agli altri candidati.

### Value Hit Rate / Calibration
Valuta P, fair e outcome per fascia di probabilità/prezzo; non usa il semplice “ha segnato/non ha segnato” per riscrivere retroattivamente un NO BET.

### Market Selection Efficiency
Confronta, per lo stesso player, quale mercato BetFlag era stato promosso (anytime, Plus, Gol/Assist, SOT ecc.) e se la scelta del mercato era coerente con il tipo di produzione effettiva.

## 12. Anti-result-bias
- Un `NO BET` che vince può essere un buon pass se la quota era sotto fair/gate.
- Una `BET` che perde può avere processo corretto se P e prezzo erano coerenti.
- Nessuna decisione pre-match viene retro-modificata dopo il risultato.
- Classificare gli errori almeno come: `MODEL_ERROR`, `PLAYER_ALLOCATION_ERROR`, `PRICE_ERROR`, `MINUTES_ERROR`, `PORTFOLIO_CORRELATION_ERROR`, `DATA_ERROR`, `SETTLEMENT_ERROR`, `REGIME_CHANGE`, `NORMAL_VARIANCE`.

## 13. Hard stops
È vietato emettere una BET quando:
- non esiste quota BetFlag fresca e univoca;
- il mercato non è identificato esattamente;
- la P usata appartiene a un altro mercato;
- XI/ruolo sono materialmente incerti senza adeguata penalizzazione;
- il correlation gate porta l'esposizione oltre il cap;
- il player identity mapping è ambiguo;
- per una selezione scorer non è stato verificato e dichiarato lo stato rigori/piazzati del giocatore.

Output obbligatorio in questi casi: `ATTESA`, `ATTESA QUOTA`, `NO BET` o `ANALISI INCOMPLETA`, con causa esplicita.

## 14. Obiettivo
Il Radar deve ottimizzare tre capacità separatamente:
1. trovare i giocatori realmente pericolosi;
2. scegliere il mercato BetFlag che remunera meglio quel profilo;
3. comprare solo quando la quota BetFlag reale supera il prezzo minimo richiesto senza concentrare rischio eccessivo sulla stessa tesi.

## 15. Persistent Scorer Watchlist — anti-lost-scorer gate
Un candidato offensivo forte NON viene eliminato definitivamente perché il primo mercato controllato è `NO BET` o perché la quota BetFlag è temporaneamente assente/sotto gate.

### Ingresso watchlist
Entrano almeno:
- i principali giocatori del `PLAYER DANGER / SCOUTING RANKING`;
- rigoristi/piazzati ad alta rilevanza;
- giocatori con ruolo XI offensivo migliore del previsto;
- candidati con forte xG/npxG, SOT, big-chance o tocchi-area share;
- scorer con matchup individuale favorevole;
- candidati per cui un mercato alternativo BetFlag può remunerare meglio del semplice anytime.

La dimensione target è **4–6 candidati offensivi per partita** quando esistono abbastanza profili credibili; non è un obbligo artificiale riempire sei nomi deboli.

### Stati
Ogni candidato resta in uno stato esplicito fino al kickoff:
- `BET` — un mercato BetFlag supera tutti i gate;
- `WATCH_PRICE` — player forte ma prezzo corrente sotto gate o vicino al gate;
- `WATCH_MARKET` — anytime non value ma esistono/possono aprirsi mercati alternativi pertinenti;
- `WATCH_XI` — ruolo/titolarità/minuti ancora da confermare;
- `WATCH_MOVE` — nuova informazione o movimento BetFlag può cambiare la valutazione;
- `NO_BET_FINAL` — rivalutato con XI/quote finali e nessun mercato BetFlag supera il gate;
- `DROP_PLAYER` — motivazione calcistica forte: fuori XI, ruolo incompatibile, minuti insufficienti, infortunio o drastico peggioramento del profilo.

`NO BET` su un singolo mercato non equivale a `DROP_PLAYER`.

### Rivalutazioni obbligatorie
I candidati in watchlist devono essere riesaminati almeno quando si verifica uno di questi eventi:
1. pubblicazione XI ufficiali;
2. variazione materiale di ruolo/modulo/minuti attesi;
3. comparsa di nuovi player props BetFlag;
4. variazione materiale della quota BetFlag;
5. checkpoint T-40/T-30 quando disponibile;
6. ultimo snapshot fresco utile prima del kickoff.

Ad ogni rivalutazione, scandagliare di nuovo la matrice BetFlag completa del giocatore; non soltanto il mercato che aveva prodotto il primo NO BET.

### Regola di retention
Un player nel top scouting non può passare direttamente da `WATCH_*` a sparire dal report. Deve terminare in `BET`, `NO_BET_FINAL` o `DROP_PLAYER` con causa registrata.

### Audit della watchlist
Nel post-match misurare anche:
- `watchlist_scorer_hit`: il marcatore reale era stato mantenuto nella watchlist?
- `lost_scorer_rate`: marcatori reali identificati inizialmente ma eliminati prima del final scan;
- `rescued_value_rate`: candidati inizialmente non giocabili diventati BET grazie a XI/mercato/prezzo successivo;
- `alternative_market_rescue`: casi in cui anytime era NO BET ma Plus/1T/Gol-Assist/SOT/altro BetFlag era value.

Obiettivo esplicito: ridurre `lost_scorer_rate` senza abbassare il price discipline e senza trasformare la watchlist in una lista indiscriminata di giocatori da scommettere.

## 16. Penalty-Taker Verification Gate — obbligatorio prima di ogni scorer BET
Per qualsiasi selezione che dipende dal gol del giocatore (anytime, Marc Plus, 1T/2T, primo marcatore, scorer combo e mercati equivalenti), il Radar deve verificare **prima del verdetto** la gerarchia rigori/piazzati della squadra.

Campi minimi da registrare:
- `penalty_status = PRIMARY / SECONDARY / NONE / NOT_CERTIFIED`;
- rigorista principale atteso;
- seconda scelta attesa quando nota;
- ultimi rigori della squadra e chi li ha calciati, quando verificabili;
- presenza in campo del rigorista principale negli episodi recenti;
- eventuali cambi di gerarchia da XI, trasferimenti, infortuni o dichiarazioni tecniche;
- free-kick/set-piece role separato dal ruolo sui rigori.

Regole:
- `PRIMARY`: bonus player allocation esplicito e documentato;
- `SECONDARY`: bonus ridotto/condizionale, non equivalente a rigorista principale;
- `NONE`: nessun bonus rigori;
- `NOT_CERTIFIED`: **HARD STOP scorer**; il candidato può restare in WATCH ma non può essere promosso a BET finché lo stato non è risolto o finché una penalizzazione prudenziale documentata non rende comunque il mercato non dipendente da tale informazione.

La P Radar scorer deve essere ricalcolata dopo la verifica del penalty status. È vietato proporre una BET scorer e controllare solo dopo se il giocatore è rigorista.
