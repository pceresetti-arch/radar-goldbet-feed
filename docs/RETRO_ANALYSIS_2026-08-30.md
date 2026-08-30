# Radar Unico — Retroanalisi 30/08/2026

## Stato registro giocate
Fonte primaria: ticket BetFlag inviati dall'utente.

- Giocate totali registrate: 21
- Chiuse al momento della riconciliazione: 20
- Vincenti: 12
- Perdenti: 8
- Pending al ticket: 1 (Oihan Sancet Gol o Assist @2,90, 5 EUR)
- Stake totale: 101,00 EUR
- Stake chiuso: 96,00 EUR
- Ritorni chiusi: 157,75 EUR
- P/L netto chiuso: +61,75 EUR

Ledger strutturato: `data/ledger/2026-08-30.json`.

## Analisi per famiglia di mercato — 20 chiuse

### Marcatore Plus puro
11 giocate, 9 vinte, 2 perse. Stake 55 EUR. P/L +63,75 EUR. Hit rate 81,8%. ROI +115,9%.

Vinte: Pjaca @2,35; Jatta @2,85; Lind @2,30; Pedro Neto @4,25; Matanovic @2,20; Sinayoko @2,55; Brobbey @2,40; Trenskow @2,10; Iheanacho @2,75.
Perse: Duville-Parsemain @2,95; Junker @2,75.

### Marcatore standard
6 giocate, 1 vinta, 5 perse. Stake 26 EUR. Ritorni 10 EUR. P/L -16,00 EUR. Hit rate 16,7%. ROI -61,5%.

Vinta: Tabakovic @2,00.
Perse: Ementa @3,25; Skogvold @4,20; Kabia @5,75; Tresoldi @1,95; Nisbet @2,65.

### Mercati Plus/combo diversi
Brunner Assist o Sost o Marc Plus @2,25: VINTA, +6,25 EUR.
Abdullahi Marc o Sost @3,55: VINTA, +12,75 EUR.

### 1X2
St Mirren vincente @2,35: PERSA, -5,00 EUR (3-3 vs Motherwell).

## Lezioni immediate dalle giocate
1. La famiglia Marcatore Plus ha sovraperformato nettamente il marcatore standard nella giornata. Il campione e' piccolo, ma il contrasto 9/11 vs 1/6 e' troppo forte per essere ignorato nel prossimo tuning.
2. I mercati Plus/combo hanno protetto meglio dall'incertezza di ruolo/minutaggio e hanno monetizzato meglio le selezioni offensive.
3. I marcatori standard a quota alta/borderline hanno prodotto dispersione: Kabia @5,75, Skogvold @4,20, Ementa @3,25 e Nisbet @2,65 sono tutti persi. Serve un gate piu' severo su volume individuale, share xG, rigori/piazzati e qualita' dei minuti attesi.
4. Nisbet e' una perdita con processo meno negativo del risultato: Aberdeen-Rangers 0-1, ma Nisbet ha avuto un pareggio annullato dal VAR e una situazione da rigore non concessa. Quindi esito perso, ma tesi offensiva non completamente sbagliata.
5. St Mirren @2,35 e' un errore piu' utile: partita finita 3-3 dopo fortissima volatilita'. Il modello ha letto una possibilita' reale di vittoria, ma il mercato 1X2 era meno robusto di alternative protette.

## Previsioni NON giocate recuperate con traccia pre-match verificabile
Non vengono inventate o ricostruite a posteriori le previsioni senza traccia originaria.

### Aberdeen-Rangers
Pre-match recuperato:
- Aberdeen 1X @1,87 — BET B
- Aberdeen @3,80 — BET C
- Rangers — NO BET
- Over 2,5 — NO BET
- Goal — NO BET
- Nisbet marcatore — ATTESA/NO BET borderline in una prima fase; poi giocato @2,65 con stake basso.
Risultato reale: Aberdeen 0-1 Rangers.
Valutazione:
- Aberdeen 1X: FAIL outcome
- Aberdeen ML: FAIL outcome
- Rangers NO BET: la squadra ha vinto, ma il NO BET resta giudicabile sul prezzo, non solo sull'esito
- Over 2,5 NO BET: corretto
- Goal NO BET: corretto
- Tesi Nisbet: persa formalmente, ma con gol annullato e episodio da rigore, quindi process grade migliore del semplice -1.
Lezione: il movimento pro-Aberdeen e' stato sovrappesato; doppia esposizione alla stessa tesi (1X + ML) da evitare senza edge indipendente.

### AIK-Hammarby
Pre-match recuperato:
- Hammarby @1,35 — NO BET
- Paulos Abraham marcatore @2,00 — NO BET per prezzo compresso, pur indicato come marcatore piu' probabile
- Lind @2,45 — NO BET
- Besara @2,80 — NO BET
Risultato reale: AIK 3-2 Hammarby; Paulos Abraham ha segnato.
Valutazione:
- Hammarby NO BET: ottimo filtro (favorita persa)
- Abraham NO BET: outcome contrario, ma non e' automaticamente errore se @2,00 era sotto gate. Segnale da ricalibrare: quando il modello identifica chiaramente il miglior finalizzatore in una gara ad alta produzione, il gate non deve diventare eccessivamente conservativo.

### Gent-Club Brugge
Pre-match recuperato:
- Club Brugge @1,62 — NO BET
- Tresoldi @1,95 — NO BET
- Forbs @3,70 — NO BET
- Diakhon @3,55 — NO BET
- Vanaken @3,85 — candidato iniziale, poi NO BET post-XI
- Under 2,5 @2,00 — attenzione/attesa, non BET certificata
Risultato reale: Gent 2-1 Club Brugge. Gol Brugge: Hans Vanaken.
Valutazione:
- Brugge NO BET: corretto e importante
- Tresoldi NO BET: corretto
- Forbs NO BET: corretto
- Diakhon NO BET: corretto
- Vanaken NO BET: outcome contrario, ha segnato; candidato iniziale era ben individuato
- Under 2,5: avrebbe perso (3 gol esatti), quindi bene non promuoverlo a BET.
Lezione: il filtro squadra era forte; sul player layer Vanaken era il nome giusto ma il final gate lo ha escluso.

### Utrecht-PSV
Pre-match recuperato:
- PSV @1,45 — NO BET
- Pepi / Til / Perisic / Van Bommel props — NO BET
- Perisic assist @3,20 — borderline/ATTESA
Risultato reale: Utrecht 1-6 PSV. Marcatori PSV: Van Bommel, Til (2), Mauro Junior, Mijnans, Dest.
Valutazione:
- PSV NO BET: outcome contrario, ma quota molto compressa; non equivale automaticamente a cattiva decisione value
- Van Bommel NO BET: ha segnato
- Til NO BET: ha segnato due volte
- Pepi NO BET: corretto sul gol
- Perisic NO BET: corretto sul gol
Lezione: il modello ha sottostimato la coda alta della superiorita' offensiva PSV. Quando il team projection e' molto forte, bisogna cercare player props con quota sufficiente invece di chiudere tutto come NO BET.

### Monaco-Marsiglia
Pre-match recuperato:
- Brunner Assist o Sost o Marc Plus >=2,20-2,25 — BET (giocato @2,25)
- Brunner marcatore >=2,70; @2,60 borderline
- Gouiri Marc Plus >=2,20
- Gouiri marcatore >=2,60
- Gouiri Over 2,5 tiri >=1,80
- Brunner Over 2,5 tiri >=1,90
- Over 0,5 1T solo >=1,35/1,40
- Over 2,5 @1,55 — NO BET
- Goal @1,45-1,50 — NO BET
- Monaco ~2,20 — NO BET
Risultato reale: Monaco 2-0 Marsiglia, doppietta di Paris Brunner.
Valutazione:
- Brunner Plus: centrata
- Brunner marcatore: avrebbe vinto, ma il prezzo osservato @2,60 era sotto il gate >=2,70; disciplina prezzo corretta anche con esito vincente
- Gouiri scorer/Marc Plus: non centrati
- Over 0,5 1T: centrato (Brunner 13') se disponibile sopra soglia
- Over 2,5 NO BET: corretto (solo 2 gol)
- Goal NO BET: corretto (BTTS No)
- Monaco NO BET: outcome contrario, ma deve essere valutato contro fair/gate, non ex post.
Lezione: player read su Brunner eccellente; il mercato principale e' stato scelto bene. Importante non confondere una selezione vincente sotto gate con una decisione sbagliata: il prezzo resta parte del processo.

## Tuning proposto per il Radar
- Separare scorecard per `Marcatore standard` e `Marcatore Plus`: non devono piu' condividere lo stesso gate implicito.
- Aumentare il requisito per marcatore standard: volume tiri individuale, SOT share, xG/90, penalty share, probabilita' di 75+ minuti e centralita' in area.
- Per i favoriti molto forti ma compressi (es. PSV), se 1X2 e' NO BET cercare automaticamente una seconda passata sui player props con prezzo piu' elastico.
- Evitare doppia esposizione altamente correlata sulla stessa tesi di squadra senza edge separato.
- Conservare la distinzione `process grade` vs `result grade`: Nisbet e' l'esempio della giornata.

## Stato audit
Questa e' una prima retroanalisi certificata: include tutte le 20 giocate chiuse dai ticket e le previsioni non giocate che sono state recuperate con una traccia pre-match verificabile. Le previsioni senza traccia originaria non vengono ricostruite a posteriori, per evitare hindsight bias. La retroanalisi va estesa quando vengono recuperati ulteriori snapshot/shortlist del 30/08.
