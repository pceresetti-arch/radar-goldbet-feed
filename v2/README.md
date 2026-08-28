# Radar Unico V2 Core

Questa directory introduce la ricostruzione incrementale del Radar senza modificare il runtime V1 su `main`.

## Obiettivo iniziale

Rendere impossibile che il sistema interpreti automaticamente una quota non recuperata come mercato non quotato.

La raccolta dati e l'analisi sono due fasi separate. L'Analysis Engine non parte finché il Data Gate non è soddisfatto.

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
- `contracts/market-acquisition.schema.json`: contratto macchina per evidenza mercato.
- `test/data-gate.test.mjs`: test dei casi trovato / non quotato confermato / acquisizione fallita.

## Prossimi blocchi V2

1. `match-state`: stato persistente unico per fixture e checkpoint PRE-XI / POST-XI / T-40 / T-30.
2. `collector-orchestrator`: acquisizioni concorrenti con retry/backoff e cache.
3. `market-discovery`: determina quali famiglie mercato devono essere presenti/verificate per evento e bookmaker.
4. `analysis-engine`: moduli brevi e strutturati (match, XI, player, scorer allocation, market, risk).
5. `final-judge`: output obbligatorio BET / NO_BET / BORDERLINE / WAITING_DATA / PARTIAL_ANALYSIS.
6. Migrazione dello stato runtime fuori dai grandi JSON mutabili in Git.

## Principio di migrazione

V1 resta operativo finché un blocco V2 non supera test e smoke test end-to-end. Nessun cutover "big bang".
