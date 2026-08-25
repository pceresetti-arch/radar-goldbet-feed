# Radar Unico — regola MMS primaria

## Segnale operativo principale
Il Radar deve dare priorità ai movimenti di quota GoldBet sui mercati standard full-time seguenti:

1. **1X2** — qualsiasi selezione 1 / X / 2.
2. **OVER** — selezioni OVER sulle linee goal full-time disponibili (es. Over 0.5, 1.5, 2.5, 3.5, ecc.).

## Definizione di crollo forte
Un **crollo forte MMS** esiste quando, sulla stessa selezione e sullo stesso bookmaker GoldBet:

`TRUE OPEN GoldBet - quota osservata >= 0.20`

La soglia è quindi una variazione assoluta della quota decimale di almeno **0,20**.

## Benchmark valido
Per il segnale forte si usa esclusivamente il **TRUE OPEN GoldBet certificato da Diretta/Flashscore**.

- `FIRST_SEEN` resta archiviato come dato diagnostico/proxy.
- `FIRST_SEEN` non deve generare un segnale forte MMS quando manca il TRUE OPEN certificato.

## Checkpoint
Il confronto va mantenuto su:

- TRUE OPEN → T-40
- TRUE OPEN → T-30
- TRUE OPEN → quota corrente/pre-BET

Se il crollo >=0,20 era presente a T-40 o T-30 ma successivamente rientra, il Radar deve conservarlo come **REBOUNDED_AFTER_DROP** invece di trattarlo come crollo ancora attivo.

Se la quota corrente è ancora almeno 0,20 sotto il TRUE OPEN, lo stato è **ACTIVE_DROP**.

## Uso nel Radar
Il crollo >=0,20 è un **segnale di mercato**, non una BET automatica. Deve essere incrociato con analisi approfondita, formazione, matchup, probabilità stimata, fair odds e price gate finale.
