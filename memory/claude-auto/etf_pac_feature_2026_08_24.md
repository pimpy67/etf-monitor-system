---
name: etf-pac-feature-2026-08-24
description: "PAC (real DCA) dashboard feature — basket, fee tracking, exited-positions comparison bug fix"
metadata: 
  node_type: memory
  type: project
  originSessionId: a86b83fa-ce9e-444f-aae0-27d1e582e3f3
  modified: 2026-08-29T22:18:12.970Z
---

Built and live: `/pac` page tracking real PAC (Piano di Accumulo Capitale) contributions
on `VWCE.DE` (ISIN `IE00BK5BQT80`, single-ETF basket, user's explicit choice) versus the
real active portfolio, split into three sleeves (PAC/L1/L0) with up/down/neutral arrows
(fires only when spread ≥3pp AND all sleeves have n≥3).

**Execution discipline**: fixed day every month, fixed amount every time — no market
timing (waiting for a dip, varying the amount). User proposed both timing tricks once
each and accepted the "this defeats PAC's purpose" reasoning both times. No order is ever
placed by the system — user buys manually on Directa, then registers the contribution by
hand on the page.

**Real fee correction (2026-08-24)**: first real execution (6 shares `VWCE.DE` on Xetra,
market order) showed a **9.50€** Directa commission — nearly double the 5€ assumed in
every backtest this project has ever run. Added `fee_eur` column
(`migrations/007_add_pac_fee_column.sql`) to `etf_pac_contributions`, folded into invested
capital so % return stays net of real costs. Form defaults to 9.50€.
**Open question, not yet checked**: whether L1/L0 real trades also incur ~9.50€ (foreign
venue) vs the 5€ backtest assumption — user was asked to check but hasn't reported back.
If confirmed, the L1/L0 sleeves in `/api/pac` (and possibly the backtests themselves)
would need the same fee correction — `etf_portfolio_entries` currently has no fee column.

**Real bug found+fixed same day**: the L1/L0 comparison sleeves only read
`etf_portfolio_entries` with `status='active'` — a position that exits (real sale,
registered via the existing "Esci" flow in the Portfolio page) vanished from the PAC
comparison entirely, with its realized gain/loss never counted. Over time this would have
biased the comparison toward whatever happens to be open *right now*, silently dropping
the history of every closed trade (survivorship). Fixed: new
`database.py::get_exited_portfolio_entries()` + `app.py::get_pac()` now sums
`shares × entry_price` / `shares × exit_price` for exited positions into the same sleeve
totals, weighted identically to open positions. No new user action needed — exits are
registered exactly as before via the Portfolio page.

See [[etf_no_auto_exit_real_positions]] — the exit-registration flow this fix depends on
is the same manual "Esci" flow governed by that standing rule.

## Basket vs single ETF — discusso 2026-08-30 (single ETF confermato)

L'utente ha chiesto se un paniere di più ETF sarebbe meglio di 1.000€ su un solo ETF.
Risposta data e accettata: **VWCE è già un paniere** (~3.700 azioni FTSE All-World) —
aggiungere altri ETF azionari globali/USA/Europa aggiunge sovrapposizione, non
diversificazione; fattori (small/value/quality) sono scommesse, non diversificazione.
- L'unica aggiunta con senso reale = un **ETF obbligazionario EUR** (diversifica davvero,
  abbassa drawdown; coerente col 75/25 azioni/bond del portafoglio reale) → al massimo
  **2 strumenti**, alternando i mesi o splittando il versamento. Oltre a quello il PAC
  smette di essere "passivo a decisione zero", che è il suo scopo.
- **Commissioni**: la 9,50€/versamento è il sovrapprezzo Xetra. **VWCE è anche su Borsa
  Italiana come `VWCE.MI`** → commissione Directa standard ~5€. Su un DCA da 1.000€/mese
  fa 0,5% invece di ~1% di attrito. Comprare lì. Con 4 ETF sarebbero ~4 × 9,50 = 38€ =
  3,8% per versamento → insostenibile.
- Se un giorno si aggiunge il bond ETF, valutare anche lì il listino .MI per la
  commissione.
