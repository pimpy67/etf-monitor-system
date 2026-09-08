---
name: etf-pac-crypto-metalli-planning-2026-09-05
description: "DEFINITIVE 7-ETF Directa PAC confirmed 2026-09-05 pre-Convalida: VWCE €336+XMAE €328 (equity split), GAGG €52/1lotto+GBSE €50/2lotti (rebalanced bond->gold), DAPP €25 every date; HLT €161+GOAI €147 day-23-only. €3.472/mese max, €3.425 stimato"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f65ec4c-5f2a-4ff6-bd23-925df2bea115
  modified: 2026-09-05T18:01:44.467Z
---

## Working pattern established this session (also see [[etf-financial-advice-boundary]])

User asked to "remember the PAC discussion": going forward, when the user gives a euro
amount, Claude computes the mechanical lot/€ breakdown per ETF per installment date —
but never decides the allocation % or investment timing (personalized financial advice,
declined explicitly several times this session; see the boundary memory).

## FINAL CONFIRMED PLAN — CALCOLATO (analitico, prima della configurazione) vs REALE
(effettivamente digitato su Directa, 2026-09-05) — base €58.000 su 18 mesi (oggi → fine
feb 2028, prima che si liberino i €44k BTP — vedi sezione PATRIMONIO)

**DEFINITIVO v2 — 6 ETF, schermata di conferma Directa vista 2026-09-05.** Scoperta
importante nel processo: **Directa permette un importo diverso per ogni data per lo
stesso ETF nello stesso PAC** — quindi WGLD/GOAI/HLT non sono acquisti manuali separati,
sono DENTRO lo stesso PAC automatico con importo 0 su Giorno 1/8/15 e l'importo pieno
(1 lotto) solo su **Giorno 23**, quindi eseguono **ogni mese** (non ogni 4 mesi —
l'utente ha scelto mensile invece della cadenza trimestrale che gli avevo offerto).

Aggiunto **HLT** (STOXX Europe 600 Healthcare - Acc, LU1834986900, €152,80) come 6°
slot — sanità EUROPEA scelta al posto di un fondo sanità globale/USA (WHCS/HEAL/CURE
ecc., tutti scartati) proprio per il rischio cambio: nessuno dei fondi visti aveva "EUR
Hedged" esplicito nel nome ("(EUR)" da solo, es. su HLTW, NON significa hedged — solo
valuta di quota), ma HLT traccia aziende europee quindi l'esposizione USD e' molto
minore per costruzione del sottostante, non per copertura formale. Stesso schema ISIN
(LU183498xxxx) dei fondi settoriali Amundi già posseduti (TELE.PA, WATC.PA) — quasi
certamente Amundi, idoneo al PAC.

**AGGIORNAMENTO — WGLD sostituito con GBSE (oro hedged)**, su richiesta esplicita
dell'utente dopo la discussione sul rischio cambio ("mi dicevi che c'era un oro senza
esposizione ma in euro" → confermato, sostituito). Struttura diversa: GBSE è €25/data su
**tutte e 4 le date** (non solo giorno 23 come WGLD), quindi lo slot oro scende da
€399/mese a **€100/mese** — riduzione di peso, non solo cambio prodotto.

**AGGIORNAMENTO FINALE v3 (2026-09-05) — VWCE split 50/50 con XMAE (equity globale
hedged)**: utente ha chiesto di poter rimuovere del tutto VWCE a favore di XMAE (Xtrackers
MSCI AC World ESG Screened EUR Hedged, IE000VXC51U5), avvisato della differenza (MSCI ACWI
non FTSE All-World → niente small cap, più filtro ESG, in cambio di copertura EUR) — poi
ha scelto di **dividere lo slot equity-globale a metà** invece di sostituire, €336/data
ciascuno (metà dei precedenti €672 VWCE):
- VWCE: €336/data → 2 quote (€167,84 cad.) = €335,68/data reali
- XMAE: €336/data → 6 quote (€54,64 cad.) = €327,84/data reali

Il totale mensile MASSIMO (importi digitati) **resta invariato a €3.588** — è solo una
redistribuzione dello stesso importo VWCE tra due fondi, non un aumento di budget.

| ETF | ISIN | Emittente | Giorno 1 | Giorno 8 | Giorno 15 | Giorno 23 | €/mese | % |
|---|---|---|---:|---:|---:|---:|---:|---:|
| VWCE.MI | IE00BK5BQT80 | Vanguard | €336 (2q) | €336 | €336 | €336 | €1.344 | 37,46% |
| **XMAE** (EUR Hedged, ACWI ESG) | IE000VXC51U5 | DWS Xtrackers | €336 (6q) | €336 | €336 | €336 | €1.344 | 37,46% |
| GAGG.MI | LU1437024729 | Amundi | €98 (2q) | €98 | €98 | €98 | €392 | 10,93% |
| GBSE | JE00B8DFY052 | WisdomTree | €25 (1q) | €25 | €25 | €25 | €100 | 2,79% |
| HLT | LU1834986900 | Amundi (probabile) | 0 | 0 | 0 | €161 (1q) | €161 | 4,49% |
| GOAI | LU1861132840 | Amundi | 0 | 0 | 0 | €147 (1q) | €147 | 4,10% |
| DAPP | IE00BMDKNW35 | VanEck | €25 (2q) | €25 | €25 | €25 | €100 | 2,79% |

**AGGIORNAMENTO FINALE v4 (2026-09-05, DEFINITIVO) — GAGG ridotto a 1 lotto, GBSE portato
a 2 lotti**, su richiesta esplicita utente (ribilanciamento bond→oro all'interno dello
stesso budget). Input finali su Directa: GAGG €52/data (1 lotto, era €98/2 lotti), GBSE
€50/data (2 lotti, era €25/1 lotto). Tutto il resto invariato (VWCE €336, XMAE €328, DAPP
€25 su tutte e 4 le date; HLT €161 + GOAI €147 solo giorno 23).

| ETF | ISIN | Emittente | Giorno 1/8/15 | Giorno 23 | €/mese | % (su stimato) |
|---|---|---|---:|---:|---:|---:|
| VWCE.MI | IE00BK5BQT80 | Vanguard | €336 (2q) | €336 | €1.342,72 | 39,20% |
| XMAE | IE000VXC51U5 | DWS Xtrackers | €328 (6q) | €328 | €1.311,36 | 38,29% |
| GAGG.MI | LU1437024729 | Amundi | €52 (1q) | €52 | €194,78 | 5,69% |
| GBSE | JE00B8DFY052 | WisdomTree | €50 (2q) | €50 | €185,28 | 5,41% |
| HLT | LU1834986900 | Amundi (probabile) | 0 | €161 (1q) | €152,80 | 4,46% |
| GOAI | LU1861132840 | Amundi | 0 | €147 (1q) | €139,60 | 4,08% |
| DAPP | IE00BMDKNW35 | VanEck | €25 (2q) | €25 | €98,45 | 2,87% |

**Totale/mese: €3.472 massimo / €3.425 stimato ai prezzi attuali del 2026-09-05**
(~€41.664 massimo / ~€41.100 stimato all'anno). Rispetto alla v3 (GAGG 2 lotti/GBSE 1
lotto): bond scende da 11% a 5,7% del paniere, oro sale da 2,8% a 5,4%.

**CONFIGURAZIONE DEFINITIVA CONFERMATA su Directa (schermata "Importi e frequenze",
2026-09-05, in attesa solo del click su Convalida)** — questa è la tabella e i numeri
da usare per qualunque riferimento futuro al piano PAC, sostituisce le versioni v1/v2/v3
sopra (lasciate per lo storico del percorso decisionale).

**Rischio cambio — stato dopo lo split**: **GBSE** (oro) e **XMAE** (metà dello slot
equity globale) ora hedged EUR. Restano SENZA copertura: l'altra metà di VWCE, DAPP
(crypto/blockchain, USA-heavy), GOAI (robotics/AI, USA-heavy) — mitigato solo
indirettamente sullo slot sanità con HLT (europeo, non hedged ma meno USD-esposto per
costruzione del sottostante). Nessun hedged trovato per DAPP/GOAI tra gli emittenti
verificati (iShares, WisdomTree, VanEck, DWS Xtrackers, Amundi, State Street). Alternativa
hedged trovata ma non adottata per l'intero slot equity globale: iShares MSCI World EUR
Hedged (IWDE-IE00B441G979 — solo mercati sviluppati, non All-World/ACWI).

**Impatto sul capitale €58.000**: a questo ritmo (ora ~€3.887-3.845/mese con 6 ETF) dura
poco meno dei ~15,6 mesi stimati con 5 ETF — esaurimento indicativo entro fine 2027,
qualche mese prima del target di fine febbraio 2028 (quando arrivano gli altri €44k dai
BTP). L'utente ne era già stato informato con 5 ETF e ha scelto comunque la cadenza
mensile; l'aggiunta di HLT stringe leggermente ulteriormente questo margine.

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
