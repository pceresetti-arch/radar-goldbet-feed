# Radar Unico — Pattern report quantitativo fino al 03/09/2026

## Copertura
Campione quantitativo usato: 87 giocate con quota, stake ed esito identificabili da record recuperati/ledger relativi a 15/08, 19/08, 20/08 (solo blocco recuperabile), 21/08 (solo 6 record finanziariamente completi), 22/08 (11 righe complete su 13 autoritative), 23/08, 30/08, 31/08, 02/09 e 03/09.
Sono escluse le righe mancanti/incoerenti e le giornate non ancora ricostruite integralmente; quindi questo NON è ancora il totale economico definitivo dall'inizio progetto.

Totale campione: 87 giocate; stake 577,00 EUR; ritorni 514,05 EUR; P/L -62,95 EUR; hit 31/87 = 35,63%; ROI -10,91%.

## Per famiglia di mercato
- Marcatore anytime: n=36, W=8, stake 286 EUR, ritorni 163,75 EUR, P/L -122,25 EUR, hit 22,22%, ROI -42,74%.
- Marcatore Plus: n=18, W=11, stake 90 EUR, ritorni 143,50 EUR, P/L +53,50 EUR, hit 61,11%, ROI +59,44%.
- Marc o Sost: n=4, W=2, stake 20 EUR, ritorni 32 EUR, P/L +12 EUR, hit 50%, ROI +60%.
- Assist o Sost o Marc Plus: n=1, W=1, stake 5 EUR, ritorni 11,25 EUR, P/L +6,25 EUR, ROI +125%.
- Mercati protetti aggregati (Plus + Marc o Sost + Assist/Sost/Plus): n=23, W=14, stake 115 EUR, ritorni 186,75 EUR, P/L +71,75 EUR, hit 60,87%, ROI +62,39%. Quota media circa 2,88.
- Marcatore 1T: n=10, W=3, stake 78 EUR, ritorni 75,50 EUR, P/L -2,50 EUR, hit 30%, ROI -3,21%.
- Primo marcatore: n=3, W=1, stake 18 EUR, ritorni 13,80 EUR, P/L -4,20 EUR, ROI -23,33% (campione minuscolo; first-home separato n=1, L).
- Tiri totali: n=3, W=1, stake 15 EUR, P/L -4,25 EUR, ROI -28,33%.
- SOT: n=2, W=1, stake 10 EUR, P/L +3,75 EUR, ROI +37,5% (campione troppo piccolo).
- Gol o Assist: n=2, W=1, stake 15 EUR, P/L +7 EUR, ROI +46,67% (campione troppo piccolo).
- Combo: n=2, W=1, stake 10 EUR, P/L +5,25 EUR, ROI +52,5% (campione troppo piccolo).

## Per fascia quota
- <=2,29: n=22, W=11, stake 160 EUR, P/L -12,50 EUR, hit 50%, ROI -7,81%.
- 2,30–2,99: n=30, W=12, stake 175 EUR, P/L -8,75 EUR, hit 40%, ROI -5,00%.
- 3,00–3,99: n=20, W=5, stake 155 EUR, P/L -16 EUR, hit 25%, ROI -10,32%.
- >=4,00: n=15, W=3, stake 87 EUR, P/L -25,70 EUR, hit 20%, ROI -29,54%.

## Pattern prioritari
1. STRONG SIGNAL — Mercati protetti vs anytime: il contrasto è enorme nel campione corrente. Protetti n=23 ROI +62,39% contro anytime n=36 ROI -42,74%, con quota media protetta non più bassa in modo tale da spiegare da sola la differenza. Non promuovere ancora a legge universale: possibile selection/date bias, ma deve diventare priorità di ricerca e tie-break operativo.
2. STRONG SIGNAL — Scorer allocation: ripetuti casi in cui la squadra/slot offensivo produce ma il singolo anytime fallisce. Il vantaggio dei mercati protetti è coerente con un modello più capace di individuare funzione offensiva/slot che realizzatore individuale esatto.
3. MEDIUM/STRONG — Quote alte: deterioramento monotono del ROI con la fascia quota; >=4,00 è -29,54%. Richiede gate più severo e stake/rischio separato, soprattutto scorer/1T/first scorer.
4. STRONG PROCESS ISSUE — Esposizioni correlate: più giocate sulla stessa macro-tesi possono moltiplicare il drawdown senza moltiplicare l'informazione (es. Paciência positivo ma altamente concentrato; Falkirk-Rangers tripla negativa; Gent-OHL doppia negativa). Serve correlation exposure gate per fixture/tesi.
5. STRONG PROCESS ISSUE — Minuti e sostituzione: il modello deve usare distribuzioni P(<45), P(60+), P(75+), P(90) e non un solo expected-minutes. Cornelius 35' è caso guida; Plus può mitigare alcuni rischi ma non tutti.
6. MEDIUM — 1T non è automaticamente cattivo: 10 giocate, ROI circa -3%, ma forte dispersione. Deve essere sottomodello indipendente da anytime e first scorer, con P/fair/gate propri.
7. MEDIUM — Player volume lines: pochi casi, ma è evidente che il line-step è determinante (1.5/2.5/3.5/4.5). Stimare intera distribuzione tiri/SOT, non solo media attesa.

## Implicazioni operative provvisorie
- Quando esiste una tesi scorer forte, confrontare obbligatoriamente anytime vs Plus vs Marc/Sost vs Gol/Assist/Assist e props volume; non scegliere l'anytime per default.
- Inserire penalità aggiuntiva nel final gate per scorer standard con quota >=4,00 fino a nuova calibrazione.
- Per una stessa fixture/tesi, calcolare esposizione aggregata e limitare duplicazioni altamente correlate.
- Separare modelli: anytime, 1T, first scorer, protected markets, shots, SOT.
- Calibrare scorer allocation partendo da team xG ma usando share individuale xG/tiri/SOT/tocchi area, rigori, minuti, sostituzione e concorrenza interna.

## Limiti
Questo report è quantitativo ma ancora incompleto rispetto a tutte le giocate dall'avvio del 09/08. Mancano alcune giornate e righe non completamente recuperate (in particolare parte del 16, 20, 22, 24, 26, 27, 29 e 01/09 in forme diverse). Non usare il P/L aggregato -62,95 EUR come P/L ufficiale del progetto: è solo il sottocampione con record finanziari completi. Il bankroll ufficiale resta separato in data/ledger/bankroll_state.json.
