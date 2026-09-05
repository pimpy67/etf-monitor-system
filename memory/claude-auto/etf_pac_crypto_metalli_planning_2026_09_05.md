---
name: etf-pac-crypto-metalli-planning-2026-09-05
description: "FINAL confirmed 5-ETF PAC plan (VWCE/GAGG/DAPP automated + WGLD/GOAI manual every 4mo), €58k/18mo — supersedes the earlier BTCE.DE/SGLD.MI draft, which turned out ineligible for Directa's automated PAC"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f65ec4c-5f2a-4ff6-bd23-925df2bea115
  modified: 2026-09-05T12:57:55.353Z
---

## Working pattern established this session (also see [[etf-financial-advice-boundary]])

User asked to "remember the PAC discussion": going forward, when the user gives a euro
amount, Claude computes the mechanical lot/€ breakdown per ETF per installment date —
but never decides the allocation % or investment timing (personalized financial advice,
declined explicitly several times this session; see the boundary memory).

## FINAL CONFIRMED PLAN — CALCOLATO (analitico, prima della configurazione) vs REALE
(effettivamente digitato su Directa, 2026-09-05) — base €58.000 su 18 mesi (oggi → fine
feb 2028, prima che si liberino i €44k BTP — vedi sezione PATRIMONIO)

**DEFINITIVO — confermato dall'utente ("questo sarebbe il definitivo"), attivo su Directa
dal 2026-09-05.** Scoperta importante nel processo: **Directa permette un importo diverso
per ogni data per lo stesso ETF nello stesso PAC** — quindi WGLD e GOAI NON sono acquisti
manuali separati come pianificato prima, sono DENTRO lo stesso PAC automatico, ma con
importo 0 su Giorno 1/8/15 e l'importo pieno (1 lotto) solo su **Giorno 23**, quindi
eseguono **ogni mese** (non ogni 4 mesi — l'utente ha scelto di tenerli mensili invece di
tornare a una cadenza trimestrale, opzione che gli avevo offerto).

| ETF | ISIN | Emittente | Giorno 1 | Giorno 8 | Giorno 15 | Giorno 23 | €/mese |
|---|---|---|---:|---:|---:|---:|---:|
| VWCE.MI | IE00BK5BQT80 | Vanguard | €672 (4q) | €672 | €672 | €672 | €2.688 |
| GAGG.MI | LU1437024729 | Amundi | €98 (2q) | €98 | €98 | €98 | €392 |
| DAPP | IE00BMDKNW35 | VanEck | €25 (2q) | €25 | €25 | €25 | €100 |
| WGLD | JE00BN2CJ301 | WisdomTree | 0 | 0 | 0 | €399 (1q) | €399 |
| GOAI | LU1861132840 | Amundi | 0 | 0 | 0 | €147 (1q) | €147 |

**Totale/mese: €3.726 massimo / €3.692 stimato ai prezzi attuali** (confermato da
Directa). Sensibilmente più alto della versione "trimestrale" pianificata prima
(€3.303/mese) perché WGLD+GOAI ora sono mensili.

**Impatto sul capitale €58.000**: a questo ritmo dura **~15,6 mesi**, esaurendosi verso
**metà dicembre 2027** — circa 2,4 mesi PRIMA del target di fine febbraio 2028 (quando
arrivano gli altri €44k dai BTP). L'utente ne è stato informato esplicitamente e ha scelto
comunque questa opzione (accettando di arrivare al 2028 con qualche mese di anticipo sul
capitale, presumibilmente colmabile con la liquidità BancoPosta/altre fonti nel
frattempo, o semplicemente accettando il gap) invece di gestire manualmente uno
spostamento trimestrale dell'importo nel wizard Directa.

Date PAC automatico: 1/8/15/23 di ogni mese. Prossime date manuali WGLD+GOAI (ogni 4
mesi, iniziando ora): set/2026, gen/2027, mag/2027, set/2027, gen/2028.

Prezzi usati per il calcolo (04-05/09/2026): VWCE €167,84 · GAGG €48,695 · DAPP €12,306
(⚠️ NON 12.306 — letto male una volta in sessione, è un prezzo normale ~€12,31) · WGLD
€379,36-379,46 (letto sia come SGLD.MI/Invesco iniziale sia come WGLD/WisdomTree dopo il
cambio ETF, prezzi quasi identici) · GOAI €140,61.

### Come si è arrivati a questo piano (percorso, utile se si rivede la logica)

1. **Percentuali scelte dall'utente**: crypto 2%→poi 3%, metalli preziosi 3%, AI 2%,
   equity 74%→81%→90%, bond 20%→1%→10% — attraverso vari aggiustamenti nella
   conversazione, mai decisi da Claude.
2. **Base capitale**: inizialmente confusa con "2%/3% del patrimonio investibile totale"
   (€201.702,51 — dava cifre mensili enormi, ~€11-12k/mese, incompatibili con qualunque
   PAC reale) — corretto poi a base di un capitale specifico da investire (prima €58k,
   poi verificato anche a €70k) spalmato su un orizzonte di 18 mesi fino a inizio 2028.
3. **Emittenti idonei al PAC automatico Directa**: lista fissa di 13 (iShares, VanEck,
   WisdomTree, DWS Xtrackers, Fidelity, Vanguard, FranklinTempleton, Amundi, L&G, BNP ETF,
   BNP ETF ex-AXA, State Street IM, Leverage Shares) — **né Bitwise né Invesco ci sono**,
   quindi i primi due candidati (BTCE.DE crypto, SGLD.MI oro) NON sono utilizzabili nel
   PAC automatico (restano validi solo come acquisto singolo manuale, che è già come
   l'utente possiede la sua unica posizione crypto attuale, Coinshares Staked Ethereum
   "X.CETH" GB00BLD4ZM24 su Directa).
4. **Nessun emittente idoneo (verificati iShares, WisdomTree, VanEck) offre un vero
   tracker crypto diretto nel catalogo PAC** — solo fondi azionari tematici "Blockchain/
   Crypto Innovators" (iShares BLTH, WisdomTree WBLK, VanEck DAPP) che investono in
   AZIENDE del settore, non nel prezzo della criptovaluta stessa. L'utente ha scelto
   comunque **DAPP** (VanEck) sapendo che è un'esposizione strutturalmente diversa.
   Oro sostituito da SGLD.MI → **WGLD** (WisdomTree Core Physical Gold, JE00BN2CJ301,
   oro fisico vero, idoneo).
5. **Problema lotto minimo**: WGLD (€379/quota) e GOAI (€140/quota) non comprano
   nemmeno 1 quota se spalmati su 4 date/mese con una fetta piccola di budget — risolto
   spostandoli fuori dal PAC automatico, acquisto manuale di 1 lotto ogni 4 mesi (non 6+4,
   semplificato a 4+4 su richiesta utente) — questo li avvicina molto di più al target %
   (dividere per 4 mesi invece che per 1 riduce il loro peso mensile equivalente di 4x).
6. **Emittenti da NON ripetere la ricerca** (verificato, nessun tracker crypto diretto):
   iShares, WisdomTree, VanEck. Se serve ancora cercare, provare Fidelity o DWS Xtrackers.

**Prossimo step quando l'utente conferma di aver configurato tutto su Directa**: aggiungere
le 5 righe (o 3, per la sola parte automatica) in `etf_pac_plan` (vedi
[[etf_pac_plan_autotracking_2026_09_02]] per il meccanismo) — nota che quella tabella ha
`shares_per_exec` FISSO per ogni esecuzione, quindi WGLD/GOAI (manuali, non su ogni data)
NON vanno inseriti lì con la stessa logica delle altre 3 — andrebbero registrati a mano
via `add_pac_contribution` ogni volta che l'utente esegue l'acquisto trimestrale, non come
riga ricorrente automatica.

## PATRIMONIO snapshot — 2026-09-05 (fresh exports, read via PowerShell+Excel COM,
see [[vps-tooling-notes]] for the .xls-binary-file technique)

Total patrimonio ~€212.802,64 across 4 accounts (all fresh exports the same day):
- **Directa** (S7997): €26.092,25 posizioni + €10.946 liquidità = €37.038,25 totale — 8
  posizioni incl. crypto singola (Coinshares Staked Ethereum "X.CETH" GB00BLD4ZM24, 50u,
  ~€3.208), il PAC esistente (VWCE.MI+GAGG.MI), e 4 posizioni reali L1/L0 (TELE.PA,
  TUR.PA, WATC.PA, LTAM.MI).
- **WeBank**: €160.723,90 — ETF già liquidati e spostati su Directa (confermato
  dall'utente); restano 6 BTP, che RESTANO lì (non liquidati): BTP 22/28 3.40% €24k
  (scad. 01/04/2028), BTP Italia 2023-2028 FOI-linked €20k (14/03/2028) — insieme **€44k
  che si liberano a inizio 2028**, punto di riferimento per l'orizzonte dei 18 mesi sopra
  — poi BTP 22/29 3.85% €33k (15/12/2029), BTP 23/30 3.70% €34k (15/06/2030), BTP 0.90%
  2020-2031 €27k (01/04/2031), BTP 0.95% 2021-2032 €28k (01/06/2032). Cedole fisse
  ≈€3.853/anno (esclusa BTP Italia, inflation-linked).
- **Online SIM**: €14.886,36 — 2 fondi residui (Fidelity Latin America, Schroder
  Emerging Europe A), in liquidazione verso Directa.
- **BancoPosta**: €11.100,13 liquidità — riserva per eventuali L1/L0 (coerente con la
  decisione già presa nel progetto: mai vendere il PAC per finanziare L1/L0).

Directa liquidità (€10.946) + Online SIM (€14.886,36) = **€25.832,36** liquidità/liquidabile
subito, distinta dai €44k BTP che arrivano nel 2028 e dai €69.832,61 se si sommano entrambi.
Nessuno di questi coincide esattamente con gli "€58.000"/"€70.000" usati come base del
piano sopra — sono cifre indicative scelte dall'utente per il test dei calcoli, non
necessariamente legate 1:1 a un sotto-insieme preciso del patrimonio.

## Separate project: PATRIMONIO (`APPLICAZIONI _ APP/PATRIMONIO/`)

Standalone client-side-only dashboard (single `dashboard.html`, SheetJS + Chart.js, no
server, data lives only in browser localStorage per its own README) — NOT part of
etf_monitor_system, no shared DB/API. To read current figures, the user must save fresh
bank Excel exports into `PATRIMONIO/export/` (any filename is fine — actual files seen:
`P_TOTALE_S7997_<date>.xlsx` Directa, `Portafoglio-<acct>-<ts>.xls` WeBank,
`elencoFondi (N).xls` Online SIM, `ListaMovimenti (N).xlsx` BancoPosta) — Claude then
reads them via PowerShell+Excel COM (`.xls`/.xlsx binary, the Read tool rejects them
directly). The `/riconciliazione` page inside etf_monitor_system is a DIFFERENT, unrelated
upload — it parses the Directa file in-memory per-request and never persists it, so it
can't be used as a source for PATRIMONIO data either.
