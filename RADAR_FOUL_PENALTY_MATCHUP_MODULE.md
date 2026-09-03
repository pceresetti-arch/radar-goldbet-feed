# Radar Unico — Foul & Penalty Matchup Module

Versione: 2026-09-03
Stato: VINCOLANTE — OPERATIVO

## Scopo
Integrare nella formazione-vs-formazione una stima esplicita del rischio falli, piazzati pericolosi e rigori, senza trattare eventi rari come certezze.

## 1. Output minimo per partita
Ogni analisi POST-XI deve produrre, quando i dati sono verificabili:
- `foul_environment = LOW / MEDIUM / HIGH`;
- `dangerous_foul_risk_home/away`;
- `penalty_risk_home/away = LOW / MEDIUM / HIGH`;
- una stima probabilistica numerica di rigore assegnato alla squadra solo quando il campione e le fonti sono sufficienti;
- `set_piece_pressure_home/away`;
- principali zone/duelli che possono generare fallo;
- giocatori offensivi che attirano più falli in zone pericolose;
- difensori/terzini/centrali avversari più esposti a duelli, ritardi, 1v1 e interventi in area;
- arbitro e VAR solo quando materialmente verificabili e con peso prudente;
- gerarchia rigoristi separata dal semplice rischio di ottenere un rigore.

## 2. Feature di squadra e matchup
Considerare almeno:
- falli commessi e subiti per 90 e trend regredito;
- tocchi/palloni ricevuti in area e ingressi in area;
- dribbling tentati/completati e falli subiti da dribbling;
- cross/cut-back, corse alle spalle e attacchi del mezzo spazio;
- transizioni e duelli difensivi in recupero;
- pressione alta che può generare falli tattici;
- difensori ammoniti/propensi al fallo e mismatch di velocità/agilità;
- rigori ottenuti/concessi con regressione forte verso baseline di lega;
- frequenza di falli in area e mani/interventi tardivi quando documentabile;
- game state atteso: squadra costretta a difendere bassa o ad affrontare molti 1v1 in area.

## 3. Arbitro e VAR
L'arbitro non deve diventare un segnale dominante. Usare, quando disponibile:
- falli fischiati;
- cartellini;
- rigori assegnati;
- storico recente e baseline di lega;
- eventuale tendenza VAR/competizione.

Applicare forte regressione: campioni piccoli o arbitri con pochi match non devono produrre correzioni aggressive.

## 4. Penalty probability
La probabilità di rigore non va ricavata semplicemente dalla media storica della squadra. Deve combinare:
- baseline di lega/competizione;
- capacità offensiva di entrare e ricevere in area;
- profilo dei dribblatori e dei giocatori che attirano contatti;
- vulnerabilità dei difensori avversari nei duelli in area;
- ritmo e game state atteso;
- arbitro/VAR solo come correttore prudente;
- stato XI reale.

Se i dati non bastano, usare solo una classe qualitativa `LOW/MEDIUM/HIGH` e NON inventare una percentuale.

## 5. Impatto sui player props
La P(gol) del giocatore deve essere scomposta concettualmente in:
- contributo da open play / set pieces non-penalty;
- contributo da rigori condizionato a `penalty_status` e alla probabilità che la squadra ottenga un rigore.

Regole:
- `PRIMARY`: riceve la quota principale del penalty-xG atteso;
- `SECONDARY`: riceve solo una quota condizionale legata all'assenza/uscita del PRIMARY;
- `NONE`: nessun bonus penalty, ma nessun hard stop alla BET;
- `NOT_CERTIFIED`: il contributo rigori non può essere usato nel modello; scorer BET sospesa finché la gerarchia non è chiarita se il contributo potrebbe essere materiale.

Non sovrastimare un rigorista in una partita con bassa pressione area/penalty risk; non sottostimare un non-rigorista con forte npxG/shot/SOT/box-touch profile.

## 6. Impatto su mercati squadra e partita
Il modulo può correggere prudentemente:
- team xG;
- distribuzione 0/1/2/3+ gol;
- BTTS/O-U;
- team total;
- scorer allocation;
- primo tempo quando il matchup produce pressione area precoce;
- mercati cartellini/falli solo se BetFlag li quota e il modello dedicato è sufficientemente robusto.

Nessuna correzione deve duplicare informazione già inclusa in xG o market movement.

## 7. Audit
Nel post-match registrare:
- falli totali;
- falli subiti dai principali candidati;
- falli in zona pericolosa quando disponibile;
- rigori assegnati/non assegnati;
- minuto e giocatore che ha subito/commesso il fallo da rigore;
- rigorista e risultato del tiro;
- eventuale VAR;
- se il rischio pre-match era ben classificato indipendentemente dall'evento finale.

Metriche da costruire nel tempo:
- calibrazione `P(penalty)` quando numerica;
- hit rate LOW/MEDIUM/HIGH;
- lift sulla calibrazione scorer rispetto al modello senza penalty-matchup;
- falsi positivi da arbitro/team-history overfit;
- contributo marginale OOS.

## 8. Hard rule
La presenza di un rigorista NON crea da sola una BET. La probabilità di rigore deve dipendere dal matchup e dalla pressione prevista in area. Allo stesso modo, un giocatore NON rigorista può essere la miglior BET scorer se il suo profilo npxG/volume/minuti/matchup e il prezzo BetFlag lo giustificano.
