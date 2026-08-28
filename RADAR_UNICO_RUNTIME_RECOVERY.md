# Radar Unico — Runtime recovery contract

## Scopo
Eliminare due single point of failure operativi: risoluzione DNS del Worker BetFlag dal runtime ChatGPT e feed XI stale/bloccato da discovery fixture BetFlag.

## BetFlag/AAMS — ordine obbligatorio
1. Primario: `https://radar-betflag-v7.p-ceresetti.workers.dev`.
2. Se il runtime client non risolve/raggiunge il dominio, NON dichiarare subito BetFlag indisponibile.
3. Attivare il bridge GitHub aggiornando `radar-betflag-v7-live-request.json`.
4. Discovery: `mode=player_index` o `mode=player_props`; leggere il response/feed generato dal workflow `radar-betflag-v7-live-bridge.yml`.
5. Exact FINAL GATE: usare `mode=player_price` con identità precisa della selezione oppure il proof on-demand già presente nel repository.
6. Una quota è operativa solo se la risposta exact è fresca e `price_gate_eligible=true`.
7. Distinguere sempre `worker_health_ok` da `source_healthy`: HTTP 200 del Worker non implica che il servizio BetFlag a monte sia sano in quell'istante.

## Formazioni — ordine obbligatorio
1. Prima fonte automatica: `feed/lineups-current.json` / `feed/lineups-current-summary.json`.
2. Se il feed ha più di 7 minuti o manca una gara T-120/T+15, forzare `refresh-current-lineups-trigger.json` o aggiornare `radar-runtime-request.json`.
3. Il refresh resiliente usa `scripts/refresh_current_lineups_resilient.py` e NON dipende da una chiamata BetFlag live per scoprire le fixture.
4. Target fixture ammessi, in ordine: feed BetFlag upcoming cached, fixture esplicite in `radar-runtime-request.json`, continuità dal feed XI precedente.
5. FotMob serve a risolvere match e XI; soltanto `lineupType=standard` completo 11+11 abilita `SOURCE_CONFIRMED`.
6. `lastStarting11`, predicted/probable/expected restano riferimenti storici/probabili e non diventano XI ufficiali.
7. Se manca ancora XI, intensificare ricerca ufficiale club/lega/UEFA e fonti live indipendenti; non inventare ruoli.

## Gateway unificato
- Trigger: `radar-runtime-request.json`.
- Workflow: `.github/workflows/radar-runtime-gateway.yml`.
- Output: `feed/radar-runtime-current.json`.
- Il gateway verifica Worker, player index, exact player-price richiesti e freschezza XI.

## Regola di errore
Il Radar può scrivere “BetFlag non disponibile” solo dopo avere distinto e verificato: (a) errore client/runtime, (b) Worker health, (c) upstream BetFlag `source_healthy`, (d) bridge GitHub. Il Radar può scrivere “XI non disponibile” solo dopo avere verificato un feed XI fresco o avere forzato il refresh e cercato le fonti ufficiali/live.
