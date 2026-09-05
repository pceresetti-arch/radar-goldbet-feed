# Radar V2 — XI Event + Final Price T-30 Policy

## Regola operativa vincolante
Il Radar NON deve trattare T-40 e T-30 come due analisi separate.

Il trigger principale e' la pubblicazione dell'XI ufficiale. Appena un XI ufficiale nuovo viene acquisito, parte immediatamente la Deep Analysis post-XI completa.

T-30 resta una sola deadline/finestra di finalizzazione: serve al refresh finale delle quote e alla certificazione del verdetto operativo.

## Flusso corretto
1. Prima del match: partita identificata, TRUE OPEN certificata quando disponibile, dati statici e PRE-XI gia' raccolti.
2. Da circa T-90: polling aggressivo delle fonti XI.
3. Appena `XI_OFFICIAL` compare: scatta `RUN_POST_XI_ANALYSIS`.
4. Se cambia il fingerprint XI: invalidare solo gli output lineup-sensitive e rieseguire il POST-XI.
5. Dopo il POST-XI: la partita resta `AWAITING_FINAL_PRICE_CHECK`.
6. Intorno a T-30: refresh live dei prezzi rilevanti, cattura snapshot T-30, rivalutazione price gate/final judge.
7. Solo dopo questo passaggio la partita puo' diventare `T30_READY`.

## T-40
T-40 e' soltanto telemetria/storico utile per lo studio del movimento.

- non e' un gate operativo;
- non e' obbligatorio per il verdetto;
- la sua assenza non blocca l'analisi;
- se disponibile viene conservato per audit/ricerca.

## Pacchetto obbligatorio per il POST-XI
- XI ufficiale + fingerprint;
- formazione-vs-formazione;
- ruolo reale, minuti, rischio sostituzione;
- dati squadra e giocatori;
- matchup e scorer allocation;
- modello partita, goal model, player model;
- tutti i mercati attesi verificati;
- TRUE OPEN certificata per le serie standard richieste quando realmente recuperabile;
- storico quote gia' osservato;
- fair odds, gate, rischio e Final Judge preliminare.

## Pacchetto obbligatorio al final price check T-30
- tutto il POST-XI gia' completato;
- quota attuale live e fresca per ogni selezione decisionale;
- snapshot T-30 congelato dalla quota fresca;
- ricalcolo solo delle componenti dipendenti dal prezzo/delta;
- verdetto finale BET / NO_BET / BORDERLINE / WAITING_DATA.

A T-30 NON si rifanno da zero match model, player model o scorer allocation salvo cambio XI materiale.

## TRUE OPEN e TRUE CLOSE
La TRUE OPEN, una volta certificata, e' immutabile salvo correzione esplicita e auditabile.

La vera closing line si osserva vicino al kickoff e serve a CLV/audit. Non e' un prerequisito conoscibile a T-30.

## Stati principali
- `WAITING_FOR_XI`: XI non ancora acquisito; continuare polling delle fonti.
- `XI_NEW_TRIGGER`: nuovo XI ufficiale; partire subito con POST-XI.
- `XI_CHANGED_RETRIGGER`: XI cambiato; invalidare output lineup-sensitive e rivalutare.
- `AWAITING_FINAL_PRICE_CHECK`: POST-XI completo, in attesa del controllo prezzo T-30.
- `FINAL_PRICE_WINDOW`: si entra nella finestra di refresh finale.
- `T30_READY`: final price check completato con dati validi.
- `T30_DEADLINE_MISSED`: a T-30 manca ancora un blocco critico.

## Obiettivo
L'utente deve ricevere il risultato completo con anticipo utile. Il Radar reagisce alla formazione ufficiale, non a rituali temporali ridondanti; T-30 serve solo a chiudere prezzo e decisione.
