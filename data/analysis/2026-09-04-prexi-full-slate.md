# Radar Unico — PRE-XI full slate 04/09/2026

Status: PRE-XI, snapshot iniziale serale 03/09/2026. Nessuna giocata registrata come piazzata.

## Fonte quote
BetFlag live branch `betflag-live`, source `BETFLAG_AAMS_DIRECT`, source/player/standard healthy. Live status: 200 fixture gate-eligible, 5.145 standard rows, 5.189 player rows. Fixture index e file esatti letti dal feed residenziale.

## Regola di ranking
A+/A = priorità massima ma non automatica; B+/B restano nella shortlist. La classe finale dipende da XI, ruolo/minuti, prezzo corrente e correlation exposure. Il pattern storico sui mercati protetti viene usato come tie-break, non come garanzia.

## Shortlist PRE-XI operativa
1. Lione–Auxerre — Loïs Openda Marcatore o Sostituto @2.10 — A PRE-XI; stima P 51–53%, fair ~1.89–1.96, gate ~2.05. Candidato A+ solo dopo XI/ruolo/minuti. Alternative: Openda Marc @2.25 B+/A-, O1.5 SOT @1.80 B+, Lyon -1 3-way @2.35 B+/A-. Evitare cumulo correlato.
2. Al Ahli–Al Riyadh — Al Ahli -1 3-way @1.78 — B+/A- PRE-XI; favorita molto forte ma prezzo non largo. Player: Trincão Marc/Sost @2.55 B+, Spertsyan @2.35 B, Galeno @2.90 B; Toney @1.42 protetto NO BET per prezzo.
3. Basaksehir–Galatasaray — Galatasaray -1 3-way @2.35 — B+ PRE-XI. Player: Rafael Leão Marc/Sost @2.10 B+ se titolare/ruolo alto; Osimhen Marc/Sost @1.73 NO BET/prezzo compresso; Osimhen O2.5 SOT @2.15 WATCH B+ subordinato a distribuzione volume e XI.
4. Viborg–Lyngby — Tim Freriks Marcatore Plus @2.10 / Marc o Sost @2.20 — B+ PRE-XI se titolare centravanti. Viborg 1 @1.78 B. Dorian Hanza Plus @2.25 B, Marc/Sost @2.35 B. Nessuna A prima di verifica XI/ruolo.
5. Al Shabab–Al Hilal — Crysencio Summerville Marc/Sost @2.35 — B+ PRE-XI se titolare; Milinkovic-Savic @2.55 B; Meite @1.73 NO BET per prezzo. Al Hilal -1 3-way @1.70 B. Escludere Salem Al-Dawsari/Theo Hernandez finché stato fisico non chiarito.
6. Fredrikstad–Bodø/Glimt — match profile A-/B+ ma selezione finale non certificata in questo snapshot perché il player matrix non è stato estratto integralmente. Bodø è leader con forte produzione recente, ma Fredrikstad arriva in forma; non forzare 1X2 corto. Da riesaminare nel prossimo snapshot live e POST-XI.

## Rejected / price-compressed examples
- Osimhen Marc/Sost @1.73: profilo giocatore fortissimo, prezzo sotto gate operativo.
- Toney Marc/Sost @1.42: NO BET per compressione estrema.
- Al Hilal 1 @1.28: NO BET come singola base.
- Al Ahli 1 @1.30: NO BET come singola base.
- Galatasaray 1 @1.57: troppo corto rispetto alle alternative, non priorità.

## Notes di processo
- Nessuna A+ assegnata PRE-XI: Openda è il candidato più vicino.
- Mercati protetti preferiti all'anytime quando il prezzo resta sopra gate, coerentemente col pattern storico; nessuna promozione automatica basata sul backtest.
- Quote >=4 sui scorer richiedono edge straordinario e gate severo.
- Una sola esposizione principale per macro-tesi/fixture salvo edge indipendente certificato.
- POST-XI deve essere salvato come snapshot separato append-only.
