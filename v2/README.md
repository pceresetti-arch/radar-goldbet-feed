# Radar Unico V2 Core

Questa directory introduce la ricostruzione incrementale del Radar senza modificare il runtime V1 su `main`.

## Obiettivo iniziale

Rendere impossibile che il sistema interpreti automaticamente una quota non recuperata come mercato non quotato.

La raccolta dati e l'analisi sono due fasi separate. L'Analysis Engine non parte finché il Data Gate non è soddisfatto.

## Politica quote V2

- `BetFlag/AAMS direct` è la sorgente operativa primaria per le quote e deve essere interrogata per tutte le famiglie di mercato disponibili, standard e player props.
- `GoldBet` non è più una dipendenza critica del Radar: è un cross-check non bloccante quando disponibile.
- L'assenza o il fallimento del recupero GoldBet non deve rallentare né bloccare l'analisi se la quota operativa BetFlag/AAMS è fresca e verificata.
- Se BetFlag/AAMS non restituisce un mercato, il Radar deve distinguere tra mercato realmente non quotato e acquisizione fallita; non può assumere che il mercato non esista.
- Eventuali fonti alternative sono fallback espliciti e devono essere etichettati come tali; nessuna sostituzione silenziosa.

Contratto macchina: `contracts/quote-source-policy.json`.

## Stati obbligatori di ogni mercato

- `QUOTED_RECOVERED`: mercato trovato, prezzo valido, fonte e timestamp presenti.
- `NOT_QUOTED_CONFIRMED`: assenza dimostrata; non equivale a "non trovato".
- `ACQUISITION_FAILED`: il mercato può esistere, ma il recupero tecnico è fallito.
- `UNCERTAIN`: evidenza insufficiente per classificare presenza/assenza.

## Regola Data Gate

Per ogni mercato richiesto dalla checklist della partita:

- `QUOTED_RECOVERED` -> terminale valido;
- `NOT_QUOTED_CONFIRMED` -> terminale valido solo con controllo struttura evento e almeno due prove di assenza;
- `ACQUISITION_FAILED` -> BLOCCA il Data Gate e richiede escalation/retry;
- `UNCERTAIN` -> BLOCCA il Data Gate e richiede ulteriore verifica;
- mercato senza stato -> BLOCCA il Data Gate.

Quindi la velocità non deriva dal saltare mercati: deriva dal parallelizzare acquisizioni, riusare snapshot freschi e rilanciare soltanto i blocchi falliti.

## File iniziali

- `src/data-gate.mjs`: logica eseguibile del gate.
- `src/quote-source-policy.mjs`: seleziona BetFlag/AAMS come quota operativa primaria e tratta GoldBet come cross-check non bloccante.
- `contracts/market-acquisition.schema.json`: contratto macchina per evidenza mercato.
- `contracts/quote-source-policy.json`: gerarchia fonti quote V2.
- `test/data-gate.test.mjs`: test dei casi trovato / non quotato confermato / acquisizione fallita.
- `test/quote-source-policy.test.mjs`: test della gerarchia fonti e della non-dipendenza da GoldBet.

## Prossimi blocchi V2

1. `match-state`: stato persistente unico per fixture e checkpoint PRE-XI / POST-XI / T-40 / T-30.
2. `collector-orchestrator`: acquisizioni concorrenti con retry/backoff e cache, con BetFlag/AAMS come prima sorgente quote.
3. `market-discovery`: determina quali famiglie mercato devono essere presenti/verificate per evento e bookmaker.
4. `analysis-engine`: moduli brevi e strutturati (match, XI, player, scorer allocation, market, risk).
5. `final-judge`: output obbligatorio BET / NO_BET / BORDERLINE / WAITING_DATA / PARTIAL_ANALYSIS.
6. Migrazione dello stato runtime fuori dai grandi JSON mutabili in Git.

## Principio di migrazione

V1 resta operativo finché un blocco V2 non supera test e smoke test end-to-end. Nessun cutover "big bang".
