# Radar Unico — TRUE OPEN Movement Policy

## Regola principale — BETFLAG ONLY
Per qualunque richiesta sul movimento di una quota e per qualunque controllo operativo automatico PRE-MATCH, POST-XI, T-40/T-30 e PRE-BET, **BetFlag e' l'unico bookmaker operativo ammesso** per tutti i mercati quotati e per la TRUE OPEN.

La regola vale senza eccezioni per:
- 1X2;
- Goal/No Goal;
- Over/Under;
- handicap e doppia chance;
- team total e combo;
- mercati 1° tempo e altri periodi;
- marcatori, marcatore 1T, primo marcatore;
- Gol o Assist, Assist;
- tiri, tiri in porta, tiri 1T;
- Marc o Sost / Marcatore Plus e mercati equivalenti;
- qualsiasi altro standard market o player prop disponibile su BetFlag.

GoldBet, ODSS/OddsPapi, aggregatori e medie di mercato non possono essere usati come fonte operativa, fallback silenzioso o sostituto di BetFlag.

## Sequenza operativa obbligatoria
`BETFLAG TRUE OPEN CERTIFICATA -> snapshot intermedi BETFLAG -> T-40 BETFLAG -> T-30 BETFLAG -> CURRENT/PRE-BET BETFLAG`

Ogni punto della sequenza deve appartenere alla stessa identica chiave BetFlag: evento + mercato + periodo + linea + selezione + giocatore, quando applicabile.

## Definizioni
- `TRUE_OPEN_CERTIFIED_BETFLAG`: prima quota realmente pubblicata da BetFlag per la specifica chiave evento/mercato/periodo/linea/selezione/giocatore, certificata da un campo opening affidabile o da una cattura dimostrabile della prima pubblicazione.
- `FIRST_SEEN_BETFLAG` / `OPEN_RADAR_BETFLAG`: prima quota BetFlag osservata dal Radar. E' solo diagnostica e non equivale alla TRUE OPEN salvo certificazione separata.
- `OPEN_CAPTURED_NEAR_PUBLICATION_BETFLAG`: quota BetFlag intercettata molto vicino alla comparsa del mercato. Resta distinta dalla TRUE OPEN certificata.
- `T-40`, `T-30`, `CURRENT/PRE-BET`: snapshot BetFlag rispettivamente piu' vicini possibile ai relativi momenti operativi.

Se la vera apertura BetFlag non e' certificabile, il Radar deve scrivere esplicitamente:

`TRUE OPEN BETFLAG: NON CERTIFICATA / MOVIMENTO OPEN→CURRENT INCOMPLETO`

Il FIRST_SEEN non puo' essere promosso ad apertura reale e non puo' generare da solo un MMS primario.

## Gerarchia di affidabilita
1. `TRUE_OPEN_CERTIFIED_BETFLAG`: unico benchmark operativo ammesso come apertura reale.
2. `OPEN_CAPTURED_NEAR_PUBLICATION_BETFLAG`: diagnostica ad alta confidenza, non apertura reale certificata.
3. `FIRST_SEEN_BETFLAG` / `OPEN_RADAR_BETFLAG`: diagnostica tecnica.
4. `OPEN_UNKNOWN`: nessuna apertura affidabile.

## Same-bookmaker / same-market rule
Il movimento principale e' sempre **BetFlag→BetFlag**. Non e' valido costruire un movimento usando quote GoldBet, ODSS/OddsPapi, altri bookmaker, aggregatori o linee/mercati differenti.

Eventuali fonti esterne possono essere consultate esclusivamente per contesto statistico non-quote, mai per sostituire una quota BetFlag mancante e mai per certificare la TRUE OPEN BetFlag.

## Mercato non quotato vs acquisizione fallita
Quando una quota o un player prop BetFlag non viene recuperato, il Radar deve distinguere obbligatoriamente tra:
1. `MERCATO NON QUOTATO / NON DISPONIBILE SU BETFLAG`;
2. `MERCATO PROBABILMENTE DISPONIBILE MA ACQUISIZIONE BETFLAG FALLITA / QUOTA NON RECUPERATA`.

Un semplice “non trovato” non equivale mai automaticamente a “non quotato”.

## Freschezza
Una quota non deve essere chiamata `CURRENT BETFLAG` se lo snapshot non e' sufficientemente fresco. Il report deve indicare timestamp o eta' della quota quando disponibile; se stale, deve tentare un refresh prima della decisione finale.

## Metriche di movimento
Per TRUE_OPEN→CURRENT, TRUE_OPEN→T-40 e TRUE_OPEN→T-30 calcolare quando disponibili:
- variazione assoluta della quota;
- variazione percentuale;
- variazione della probabilita' implicita;
- direzione e numero dei cambi;
- minimo/massimo intermedio;
- accelerazione post formazione;
- stato `ACTIVE_DROP` o `REBOUNDED_AFTER_DROP`.

## Soglia MMS primaria
Il segnale forte standard resta:

`TRUE_OPEN_CERTIFIED_BETFLAG - quota BETFLAG osservata >= 0.20`

La soglia deve essere misurata sulla stessa identica selezione BetFlag. Un FIRST_SEEN→CURRENT >= 0.20 resta diagnostico e non e' MMS primario.

## Relazione con le formazioni
Distinguere temporalmente il movimento BetFlag iniziato prima delle XI ufficiali, quello immediatamente successivo, quello fra T-40 e T-30 e quello successivo a T-30 fino al price gate finale.

## Regola decisionale
Il movimento di quota e' un input e non genera automaticamente una BET. Restano obbligatori analisi formazione-vs-formazione, matchup e zona-vs-zona, ruolo/minutaggio, contesto tattico/fisico/motivazionale, stima probabilita'/fair odds, quota minima Radar e price gate finale.

## Formato di trasparenza
Quando disponibile:

`TRUE OPEN BETFLAG: @X.XX [TRUE_OPEN_CERTIFIED_BETFLAG]`
`INTERMEDI BETFLAG: ...`
`T-40 BETFLAG: @X.XX [timestamp]`
`T-30 BETFLAG: @X.XX [timestamp]`
`CURRENT BETFLAG: @X.XX [timestamp/freshness]`

Se manca la certificazione:

`TRUE OPEN BETFLAG: NON CERTIFICATA`
`FIRST_SEEN BETFLAG: @X.XX [SOLO DIAGNOSTICA]`

## Obiettivo operativo
Per tutte le partite future il tracker deve acquisire quanto prima la TRUE OPEN BetFlag di ogni mercato disponibile, conservarla immutabile e accumulare snapshot BetFlag intermedi fino a T-40, T-30 e CURRENT. La sequenza deve essere auditabile ex post e non riscritta dopo il risultato.