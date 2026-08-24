# Radar Unico — pipeline autonoma formazioni

## Obiettivo
Ridurre il rischio di perdere le formazioni ufficiali/titolari vicino al calcio d'inizio e alimentare automaticamente la Deep Matchup Analysis.

## Feed operativo
- Workflow: `.github/workflows/refresh-current-lineups.yml`
- Output completo: `feed/lineups-current.json`
- Output sintetico: `feed/lineups-current-summary.json`
- Frequenza: ogni 5 minuti.
- Finestra di polling: T-120 → T+15.

## Sorgente primaria attuale
FotMob tramite endpoint web correnti `/api/data/matches` e `/api/data/matchDetails`, accessibili dal runner GitHub con client HTTP browser-like.

La sorgente espone, quando pubblicati:
- XI titolari casa/trasferta;
- modulo;
- panchina quando disponibile;
- shirt/player id;
- position id / usual position id;
- coordinate di disposizione tattica sul campo (horizontal/vertical layout);
- provider del dato (es. Opta/Opta SD API quando indicato dal payload).

## Stati
- `SOURCE_CONFIRMED`: 11 titolari per entrambe le squadre presenti nella sorgente.
- `LINEUP_PRESENT`: dati formazione presenti ma non abbastanza completi per confermare 11+11.
- `NOT_AVAILABLE`: formazione non pubblicata o partita non risolta nella sorgente.
- `CROSS_CONFIRMED`: riservato alla futura conferma indipendente con una seconda sorgente.

## Regola Radar
1. Da T-120 il feed comincia a sorvegliare la partita.
2. Appena compare `SOURCE_CONFIRMED`, il Radar deve usare quell'XI per la rivalutazione formazione-vs-formazione e matchup zona-contro-zona.
3. Per una BET finale, quando tecnicamente possibile, cercare anche conferma indipendente/ufficiale del club o competizione; in caso di conflitto non assumere che una sola sorgente sia corretta.
4. Se a T-40/T-30 la formazione resta `NOT_AVAILABLE`, ridurre confidenza e intensificare la ricerca web/ufficiale invece di inventare ruoli.
5. Una formazione già confermata viene mantenuta e non richiede polling ridondante.

## Primo test reale
Nel primo test corretto della pipeline (25/08/2026), 9 delle 12 partite comprese nella finestra T-120/T+15 avevano già un XI completo 11+11 riconosciuto dalla sorgente. Tra queste Botafogo RJ–Athletico Paranaense risultava disponibile circa T-34,5.

## Integrazione tattica
Le coordinate di layout devono essere sfruttate come input aggiuntivo per:
- posizione reale del giocatore;
- lato/fascia e mezzo spazio occupati;
- probabili duelli diretti;
- sovrapposizioni/occupazione delle zone;
- matchup ala-terzino, punta-centrale, trequartista-mediano;
- validazione della grafica/posizione dichiarata da altre fonti.

Le coordinate non devono essere interpretate come tracking fisico continuo: descrivono la disposizione/ruolo della formazione fornita dalla sorgente.
