# Radar Unico — pipeline autonoma formazioni e posizionamento tattico

## Obiettivo
Ridurre il rischio di perdere le formazioni ufficiali/titolari vicino al calcio d'inizio e alimentare automaticamente la Deep Matchup Analysis non solo con i nomi degli XI, ma con la loro disposizione sul campo, ruolo funzionale, zona occupata e matchup diretto.

## Feed formazione operativo
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
- coordinate di disposizione tattica sul campo (`horizontalLayout` / `verticalLayout`);
- provider del dato (es. Opta/Opta SD API quando indicato dal payload).

## Stati formazione
- `SOURCE_CONFIRMED`: 11 titolari per entrambe le squadre presenti nella sorgente.
- `LINEUP_PRESENT`: dati formazione presenti ma non abbastanza completi per confermare 11+11.
- `NOT_AVAILABLE`: formazione non pubblicata o partita non risolta nella sorgente.
- `CROSS_CONFIRMED`: riservato alla futura conferma indipendente con una seconda sorgente.

## Layer tattico automatico
Dopo ogni refresh formazione completato con successo parte automaticamente:
- Workflow: `.github/workflows/enrich-current-lineups-tactical.yml`
- Motore: `scripts/enrich_lineups_tactical.py`
- Output completo: `feed/lineups-tactical-current.json`
- Output sintetico: `feed/lineups-tactical-current-summary.json`
- Versione metodo iniziale: `tactical-position-v1`.

### Coordinate e zone
Per ogni titolare vengono prodotti, quando la sorgente espone il layout:
- `tactical_x`: posizione laterale normalizzata 0→1;
- `tactical_y`: profondità normalizzata dalla propria porta verso la porta avversaria;
- `tactical_side`: LEFT / CENTRE / RIGHT;
- `tactical_lane`: LEFT_WIDE / LEFT_HALFSPACE / CENTRAL / RIGHT_HALFSPACE / RIGHT_WIDE;
- `tactical_depth`: GOALKEEPER / DEFENSIVE_LINE / MIDFIELD_LINE / ATTACKING_LINE;
- `formation_line`, `line_size`, `line_slot`;
- `role_code` e `role_family`;
- `role_inference_confidence` e `role_source`.

Per la squadra ospite le coordinate vengono specchiate in un riferimento fisico comune (`common_pitch_x`, `common_pitch_y`). In questo modo le due formazioni sono confrontabili sullo stesso campo e non come due grafiche indipendenti orientate entrambe verso l'alto.

### Ruoli funzionali
Il layer inferisce il ruolo iniziale combinando geometria della formazione e modulo dichiarato. Esempi:
- GK;
- LB/RB, LCB/CB/RCB, LWB/RWB;
- LDM/RDM, LCM/CM/RCM;
- LM/RM, LAM/AM/RAM;
- LW/RW, ST, LST/RST.

Il ruolo inferito non sostituisce il dato reale osservato durante la partita: descrive la disposizione iniziale pubblicata dal provider. Se la geometria e il modulo dichiarato non coincidono, la confidenza viene ridotta automaticamente.

### Matchup diretti
Per ogni titolare non-portiere vengono identificati i due avversari geometricamente più vicini nel riferimento comune del campo. Il calcolo dà maggiore peso alla distanza laterale, così da privilegiare i duelli nella stessa fascia/mezzo spazio.

Questo consente al Radar di costruire automaticamente candidati per:
- ala ↔ terzino/esterno;
- punta ↔ centrale/i;
- trequartista ↔ mediano/centrale;
- esterno ↔ esterno in sistemi a tre;
- sovraccarichi e isolamento su una fascia;
- zone potenzialmente favorevoli per tiro, gol o assist.

## Gate di qualità del posizionamento
Il Radar NON deve trattare qualunque grafica come verità tattica.

Stati del layer tattico:
- `PROVIDER_TACTICAL_CONFIRMED`: 11+11, coordinate quasi complete e forma geometrica coerente col modulo dichiarato;
- `PROVIDER_TACTICAL_AVAILABLE`: 11+11 e buona copertura coordinate, ma almeno una verifica strutturale non è pienamente soddisfatta;
- `XI_WITH_PARTIAL_POSITIONING`: XI completo ma posizionamento incompleto;
- `PARTIAL_XI_POSITIONING`: anche l'XI è incompleto;
- `NO_POSITION_DATA`: nessuna geometria utilizzabile.

Per una conclusione tattica forte, preferire `PROVIDER_TACTICAL_CONFIRMED`. Gli altri stati devono abbassare la confidenza o richiedere verifica indipendente.

## Regola Radar obbligatoria
1. Da T-120 il feed comincia a sorvegliare la partita.
2. Appena compare `SOURCE_CONFIRMED`, il Radar deve usare quell'XI per la rivalutazione formazione-vs-formazione.
3. Se sono disponibili le coordinate, deve leggere `feed/lineups-tactical-current.json` e fare anche il confronto zona-contro-zona prima della raccomandazione finale.
4. Per ogni candidato player prop deve verificare almeno: ruolo funzionale, lato/mezzo spazio, altezza, avversario diretto probabile e compatibilità con il mercato considerato.
5. Per una BET finale, quando tecnicamente possibile, cercare anche conferma indipendente/ufficiale del club o competizione; in caso di conflitto non assumere che una sola sorgente sia corretta.
6. Se a T-40/T-30 la formazione resta `NOT_AVAILABLE`, ridurre confidenza e intensificare la ricerca web/ufficiale invece di inventare ruoli.
7. Se la formazione è completa ma il posizionamento è parziale/non coerente, usare l'XI ma non formulare una conclusione forte sul matchup spaziale senza ulteriore riscontro.
8. Una formazione già confermata viene mantenuta e non richiede polling ridondante.

## Validazione iniziale
Il parser tattico è stato validato automaticamente sul campione reale storico della prima prova completa della pipeline:
- 12 partite nel campione;
- 9 con posizionamento tattico disponibile/confermato, in linea con le 9 formazioni complete già acquisite;
- sul caso Athletic Club, il provider dichiarava 3-4-3 e il rilevamento geometrico ha ricostruito 3-4-3 con copertura coordinate 100%; ruoli ricostruiti: GK, LCB, CB, RCB, LWB, LCM, RCM, RWB, LW, ST, RW.

Report macchina: `feed/tactical-parser-validation.json`.

## Primo test reale formazioni
Nel primo test corretto della pipeline (25/08/2026), 9 delle 12 partite comprese nella finestra T-120/T+15 avevano già un XI completo 11+11 riconosciuto dalla sorgente. Tra queste Botafogo RJ–Athletico Paranaense risultava disponibile circa T-34,5.

## Limiti da rispettare
- Le coordinate descrivono la disposizione iniziale della formazione fornita dal provider: NON sono tracking fisico continuo né posizione media calcolata dagli eventi della partita.
- Il ruolo funzionale è un'inferenza deterministica basata su modulo + geometria e deve restare etichettato come tale.
- La seconda sorgente indipendente non è ancora garantita per tutte le competizioni: `CROSS_CONFIRMED` resta distinto da `SOURCE_CONFIRMED`.
- In caso di conflitto tra modulo dichiarato, coordinate e fonte ufficiale, il Radar deve abbassare la confidenza e non forzare il matchup.
