---
name: etf-post-lockdown-todo-20260906
description: "Master checklist of everything backtested/candidate but NOT yet live, plus the recurring-checkpoint review process that replaced the fixed 2026-09-06 deadline"
metadata: 
  node_type: memory
  type: project
  originSessionId: c23e4e15-4c77-4fcf-a9c0-f0d2dc00b62b
  modified: 2026-09-03T11:17:02.257Z
---

## ⚠️ Aggiornamento 2026-08-23 — processo cambiato da scadenza fissa a checkpoint ricorrente

La scadenza fissa 2026-09-06 sotto (era "il" momento di decisione) è superata come **unico**
momento di decisione, ma resta valida come primo checkpoint. Cosa cambia, deciso esplicitamente
dall'utente il 2026-08-23:

- Gli Shadow Monitor **restano accesi indefinitamente** in background (già così di default,
  non serve "riattivarli" a nessuna data) — continuano a girare finché non decidiamo di
  spegnerli.
- Al posto della data secca, si useranno **checkpoint ricorrenti** (indicativo: mensile, non
  prima del 06/09 per il primo giro) in cui si estrae lo stato con le query sotto e si
  riporta il confronto native_7 vs candidati — senza che questo triggeri automaticamente una
  modifica.
- **Soglia di fiducia per promuovere qualcosa in produzione: N≥30 trade chiusi** (coerente
  con la soglia già usata in tutti gli sweep di questo progetto — non 15-20, cifra proposta
  in una discussione con un'altra AI lo stesso giorno e scartata perché non derivata dai
  nostri backtest). Sotto N≥30 un candidato resta "in osservazione", punto.
- **Nessuna promozione automatica per soglia raggiunta o per tempo passato** — resta sempre
  una decisione esplicita dell'utente al momento del checkpoint. **Due eccezioni concesse
  finora**, entrambe casi singoli su richiesta esplicita e immediata dell'utente, non un
  precedente generale per abbassare la soglia N≥30: item 3 sotto
  (`CANDIDATE_MODEL_L0_SL_20260820`, 2026-08-20) e item 1 sotto
  (`CANDIDATE_MODEL_B_20260807`/`smart_6_macd`, 2026-08-24, promosso con N=1 nello Shadow
  Monitor — motivato da un confronto PAC-vs-attivo fatto la stessa sessione, non dal
  raggiungimento della soglia).
- **Snapshot al primo check intermedio (2026-08-23, 18 giorni dopo l'inizio)** — per
  contesto, non ancora una decisione:
  - Produzione reale (`etf_l1_tracking`/`etf_l0_tracking`/`etf_l1_exit_history`, entry_date
    ≥2026-08-05): **0 nuovi ingressi L1, 0 nuovi ingressi L0, 0 uscite L1**. Il gate 7/7 non
    ha prodotto alcun segnale in tutta la finestra.
  - `candidate_model_b_20260807`: 1 posizione ombra aperta (`LGQM.DE`, 22/08).
  - `candidate_model_l0_20260808`: 8 posizioni ombra (5 aperte, 2 chiuse in SL entrambe
    leggermente negative: `LBRE.DE` -2.42%, `WATC.SW` -2.59%, 1 rientrata).
  - `candidate_breadth_20260820`: 0 posizioni ombra — stato regime `NORMAL`, breadth 58.9%
    (soglia enter 80%), quindi coerente con nessun trigger finora.
  - Nessuno di questi conteggi si avvicina a N≥30 — tutti i candidati restano "in
    osservazione", nessuna decisione da prendere a questo check intermedio.

---

**Lockdown iniziato 2026-08-05, primo checkpoint 2026-09-06** (poi ricorrente, vedi sopra).
Nothing below should be pushed to `config/etf_families.yaml`
or otherwise made live before a checkpoint confirms it, except by explicit user request. This note is the
single checklist to walk through at each checkpoint — user asked explicitly
(2026-08-20) to make sure none of this gets lost.

## 1. CANDIDATE_MODEL_B_20260807 (L1 entry/exit candidate) — ✅ PROMOTED TO PRODUCTION 2026-08-24

- Params: `mm200_distance_max=7.0%` (absolute, replaces per-family value), `adx_entry` =
  family baseline −4, `min_buy_count=6` with `macd_ok` always mandatory (`smart_6_macd`),
  `l1_stop_gain_dynamic.target_max_pct=15%`. Cluster `core` (equity_sviluppati,
  oro_metalli_preziosi, mercati_emergenti, settoriali_growth, metalli_industriali).
- Certified backtest: IN N=31 PF=1.45 WR=54.8% MaxDD=32.5% | OUT N=18 PF=1.62 WR=55.6% MaxDD=19.1%.
- Shadow Monitor was live 2026-08-07→2026-08-24 (`shadow_monitor.py`, STEP 8), only ever
  reached N=1 (LGQM.DE, opened 2026-08-22) — nowhere near N≥30.
- ✅ **PROMOTED ANYWAY, deliberate lockdown exception (2026-08-24)**: user asked directly
  ("passiamo subito a smart_6_macd"), after the same session built a head-to-head PAC
  comparison (same €1,000/month contribution, 3yr window): `native_7` on
  `equity_sviluppati` alone returned only +1.03% (1 trade in the window, capital sat idle)
  vs a passive PAC into VWCE.DE at +23.34%; `smart_6_macd` (13 trades taken) closed the gap
  to +7.02% — still behind PAC but a big enough improvement to motivate going live now
  instead of waiting for 06/09. Given two explicit choices (asked via AskUserQuestion):
  user chose **all 5 core families** (not just equity_sviluppati) and the **full certified
  bundle** (not just the bare flag) — both the more aggressive options.
- **Deployed exactly as certified**: for each of the 5 families,
  `use_smart_6_7_macd: true`, `mm200_distance_max: 7.0` (was 2.0-4.0 per family),
  `adx_entry` = old value −4 (equity_sviluppati 22→18, mercati_emergenti 22→18,
  settoriali_growth 25→21, oro_metalli_preziosi 18→14, metalli_industriali 20→16),
  `l1_stop_gain_dynamic.target_max_pct: 0.15` (was 0.05-0.07 per family).
- ⚠️ **Known, accepted risk**: the same day's 14-family survey had already flagged
  `oro_metalli_preziosi` (0 days ever reaches smart_6_macd in its own history) and
  `mercati_emergenti` ("demoted from driver to fragile/regime-dependent") as weak — the
  certified N=151/31/18 backtest was on the pooled 5-family cluster, never re-segmented
  per family (same "pooled hides a bad segment" risk isolated twice earlier this same
  session, for Bond-Trend and the 8-family L0 test). Not re-segmented before promoting —
  decided to go live anyway on explicit request, watch real per-family results instead of
  delaying further.
- **Cleanup done same day** (production now equals the candidate): `shadow_monitor.py`
  deleted from the repo, its STEP 8 call removed from `monitor.py::run()`, `'L1'` variant
  removed from `alerts.py::_SHADOW_VARIANTS` (fallback moved to `'L0'`). The one shadow
  position (`LGQM.DE`) administratively closed in the DB (`exit_reason='PROMOTED'`).
  Deployed via `./deploy.sh`.
- **To do at next checkpoint**: watch real L1 entries family-by-family (`etf_l1_tracking`)
  — if `oro_metalli_preziosi`/`mercati_emergenti` turn out to fire rarely or badly as
  feared, consider restricting `use_smart_6_7_macd` to only the families that prove
  themselves, same discipline already applied to Bond-Trend the same day.
- See [[etf_session_2026_08_07_golden_dataset_and_sweep]] for the original certification.

## 2. CANDIDATE_MODEL_L0_20260808 (L0 entry candidate)

- Params: `regime_min_days_below_sma200=5` (YAML baseline: 10), `dd_min_duration_days=4`
  (unchanged), `l0_take_profit_pct=16%` (unchanged, already live). Only `equity_sviluppati`
  (the only family reachable through the L0 whitelist gate).
- Certified backtest: IN N=152 PF=3.38 WR=44.1% | OUT N=62 PF=4.84 WR=51.6%.
- **Shadow Monitor live since 2026-08-08** (`shadow_monitor_l0.py`, STEP 8b,
  `model_name='candidate_model_l0_20260808'`). As of 2026-08-19 (12 days): 5 positions
  tracked, 1 closed via SL (−2.42%), 4 open (ENRG.PA, INCI.MI, WATC.SW, LBRE.DE).
- **To do at lockdown end**: same extraction query with the L0 model name, decide whether
  to change `regime_min_days_below_sma200` from 10 to 5 for `equity_sviluppati` in the YAML.
- See [[etf_l0_project_2026_08_07]].

## 3. CANDIDATE_MODEL_L0_SL_20260820 — ✅ PROMOTED TO PRODUCTION SAME DAY (deviation from lockdown)

- Trigger: real whipsaw on BRES/LBRE.DE (LU1834983550) — stopped out for real 2026-08-20
  morning at -2.35% net via the production 2% tier-1 SL, then bounced back to near
  breakeven (140.18 vs 140.58 entry) the same afternoon. User asked "wasn't the stop too
  tight?" — this was a genuinely untested gap (unlike the rejected continuous+ratchet
  variant below, which touched tiers 2/3, not tier 1).
- Params: only the first tier of `calculate_sl_suggerito_l0` (profit<5% → entry×0.98)
  widened to **entry×0.96 (4% instead of 2%)**. Tiers 2/3 (breakeven, half-gain
  protection) and TP (16%, unchanged) untouched. Entry gate: identical to production
  (no override on `suggest_level_0()`) — isolates the exit variable only.
- One-shot backtest (Golden Dataset batch 2026-08-07, same IN/OUT split as
  CANDIDATE_MODEL_L0_20260808, baseline production entry params): every buffer 2%→6%
  tested improved WR/PF/net P&L **monotonically**, both IN and OUT — much cleaner signal
  than the rejected continuous+ratchet test. At 4% (chosen — knee of the curve): IN
  N=142 PF=4.68 WR=64.8% P&L=+91,715€ (10k€/trade) vs baseline 2% IN N=146 PF=3.18
  WR=42.5% P&L=+53,602€; OUT N=37 PF=6.18 WR=70.3% P&L=+27,819€ vs baseline OUT N=44
  PF=4.51 WR=50.0% P&L=+22,032€. Trade-off: max theoretical single-trade loss also rises
  (2%→4%), not captured by these aggregate metrics — a real risk trade-off, not a free
  lunch. Scratch sweep script (`optimize_l0_sl_tier1.py`, docker cp'd, run, deleted —
  never entered the repo).
- **Shadow Monitor built, then retired within the hour** (`shadow_monitor_l0_sl.py`,
  STEP 8d in `monitor.py`, `model_name='candidate_model_l0_sl_20260820'`). First live
  cycle: 2 entries — `LBRE.DE` @ 140.18 (SLOW, notably the SAME ETF that whipsawed out
  for real hours earlier — the gate re-qualified it same day) and `DEFS.PA` @ 6.36
  (SLOW). Email fired correctly, confirming the wiring worked.
- ✅ **PROMOTED TO PRODUCTION THE SAME DAY (2026-08-20)** — user explicitly asked to go
  live immediately after seeing the backtest, was told the trade-off (max theoretical
  loss per trade doubles 2%→4%, this breaks the lockdown discipline applied to every
  other candidate this month) and confirmed anyway ("si fallo e memorizza"). Changed
  `technical_analysis.py::calculate_sl_suggerito_l0()` tier-1 buffer `entry×0.98` →
  `entry×0.96` directly (not YAML — the formula is hardcoded, not per-family
  parametrized). Deployed via `./deploy.sh`, syntax-checked in-container first.
  **This is a deliberate one-off exception, not a new precedent** — don't use this as
  grounds to fast-track other candidates (L1 `smart_6_macd`, L0-regime, Breadth) without
  an equally explicit user request.
- **Cleanup done**: `shadow_monitor_l0_sl.py` deleted (repo + STEP 8d call removed from
  `monitor.py` — no longer meaningful once production equals the candidate), `'L0_SL'`
  entry removed from `alerts.py::_SHADOW_VARIANTS`. The 2 shadow positions above were
  administratively closed in the DB (`exit_reason='PROMOTED'`, exit_price=entry_price,
  same day) rather than left open forever with no further tracking.
- **Nothing left to do at lockdown end for this one** — it's live now, not waiting for
  06/09. If real L0 trades under the new 4% buffer start looking wrong, that's a live
  incident, not a backtest revisit — check `etf_portfolio_entries` for real L0 positions
  and their actual SL touches going forward.

## 4. Market Breadth / "Super-Bull Market" gate (2026-08-20, brand new this session)

- Idea: when % of the whole tradable universe (13 families, ~226 tickers) with
  EMA20>SMA50 ("breadth") crosses a high threshold, temporarily relax the L1 gate
  (native 7/7 stays always-on; ALSO allow 6/7+MACD-mandatory entries, but only on
  SUPER_BULL days) and/or scale position size up (10k→15k).
- **First single-config backtest** (`backtest_market_breadth.py`, enter=80%/exit=65%
  hysteresis, cluster `core` only for entries, whole universe for the breadth signal
  itself): IS (33.8% of days SUPER_BULL) N=7 WR=71.4% PF=1.54 P&L=+641€ (flat 10k) /
  +991€ (dynamic 15k sizing). OOS (65.1% of days SUPER_BULL) N=10 WR=80.0% PF=3.82
  P&L=+2,644€ (flat) / +4,006€ (dynamic sizing). PF *improved* IS→OOS (not overfitting
  signature), but N is tiny — smaller than CANDIDATE_MODEL_B's already-marginal sample.
  Nearly ALL volume comes from the breadth-gated 6/7 branch (native_7 alone: 0 trades IS,
  1 trade OOS) — so this is really testing "smart_6_macd restricted to broad-breadth
  days only" against the already-known unconditional smart_6_macd (151 trades, WR 54.4%,
  much lower than the 71-80% seen here) — suggestive the breadth filter acts as an
  implicit quality filter, NOT proven with N this small.
- **Threshold sensitivity sweep launched same session** (`backtest_market_breadth_sweep.py`,
  13 enter/exit combos, fast re-simulation via precomputed per-day flags instead of
  rerunning `suggest_level()` per combo) — running in background on the VPS as of
  2026-08-20 ~10:02 UTC, result lands in `data/backtest_market_breadth_sweep_result.json`.
  **Check this result before trusting the single-config numbers above** — if the sweep
  shows the 80%/65% pair was a lucky pick (nearby thresholds much worse), the whole idea
  weakens considerably.
- **Sweep result (2026-08-20, `backtest_market_breadth_sweep_result.json`, 13 enter/exit
  combos, fast re-simulation ~5min total)**: robust in the sense that ALL 13 combos are
  profitable on both IS and OOS (PF 1.54-9.55, WR 71-89%), not a lucky single point — the
  70-80% enter range is particularly stable (OOS≥IS pattern, not overfitting). The 85%
  enter zone shows the classic IS-improves-OOS-doesn't overfitting signature already seen
  and rejected elsewhere in this project — avoid pushing enter that high.
  **But a real concern surfaced**: SUPER_BULL was active 46-89% of OOS days in EVERY
  combo tested — never a small minority. This undercuts the original "rare aggressive
  window" framing; in this historical window, "broad breadth" was closer to the default
  state than an exception. What's actually being measured looks more like "smart_6_macd
  plus an extra quality condition that happens to be true most of the time" than a true
  rare regime-switch. Worth checking, before building a Shadow Monitor, whether the dates
  breadth was OFF correspond to sensible macro moments (a real correction/consolidation)
  or are just noise — not yet done.
- ✅ **Shadow Monitor BUILT AND DEPLOYED (2026-08-20, same session)** — user explicitly
  asked to build it despite the "SUPER_BULL almost never rare" concern above (wants to
  observe it live rather than wait). `shadow_monitor_breadth.py` (new module,
  `model_name='candidate_breadth_20260820'`), wired as STEP 8c in `monitor.py::run()`,
  same try/except non-blocking pattern as the other two. Deliberately tracks ONLY the
  incremental trades (buy_count==6+MACD+fondamenta, only when today's live-computed
  breadth crosses into SUPER_BULL) — native_7 trades are NOT duplicated here, they're
  already the real system. NO other override (no mm200/adx/TP changes) — isolates the
  breadth effect alone, unlike CANDIDATE_MODEL_B which bundles several changes together.
  - New DB state needed (unlike the other two Shadow Monitors): hysteresis requires
    yesterday's regime to decide today's — added `etf_breadth_regime_state` table
    (`migrations/005_add_breadth_regime_state.sql`, applied manually via psql, one row
    per model_name) + `database.py::get_breadth_regime_state()`/`set_breadth_regime_state()`.
    Shadow *positions* reuse the existing generic `etf_shadow_positions` table (already
    keyed by `model_name`, no schema change needed there).
  - Thresholds: enter=80%/exit=65%, chosen because they sit in the stable, well-behaved
    middle of the 2026-08-20 sweep grid (see above), not the highest-backtest-score point.
  - `alerts.py::send_shadow_entries()` refactored from an `is_l0` boolean to a
    `_SHADOW_VARIANTS` dict so a third variant (`'BREADTH'`) could be added cleanly —
    same email mechanism as the other two, teal color (#1ABC9C) to distinguish it.
  - Deployed via `./deploy.sh` after the migration. **Verify next session** that STEP 8c
    ran cleanly on the first live cycle (log line `Breadth oggi: X% (N ETF) — regime
    Y`) — was mid-verification when this note was written.
  - **Extraction query at lockdown end** (same pattern as the other two):
    ```sql
    SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
    FROM etf_shadow_positions WHERE model_name = 'candidate_breadth_20260820'
    ORDER BY entry_date;
    ```
    Also worth checking `etf_breadth_regime_state` to see how much of the live
    observation window was actually spent in SUPER_BULL — this is the open question from
    the sweep (was 46-89% of days in every backtested config), now observable live.
- **To do at lockdown end**: review sweep result; if still promising, build a Shadow
  Monitor for it (same non-invasive pattern) and let it run through a SECOND validation
  window before ever touching the live YAML — this is two backtest sessions old, several
  steps earlier in the pipeline than items 1-2 which already have a full lockdown of live
  shadow data behind them.
- See [[etf_session_2026_08_20_l2_radar_and_breadth_idea]] for the full session narrative.

## 5. "4 pilastri quant avanzati" — ideas tested, mostly not promising as tested

From `backtest_advanced_pillars.py` (2026-08-19/20), pasted by the user from an external
source:
- ✅ **Risk-parity position sizing — RE-RUN 2026-08-24, now a fair comparison**: the
  original test only compared absolute P&L, but risk-parity structurally deploys more
  total capital than flat sizing (sizes up to 3x on low-risk trades) — a higher raw P&L
  didn't prove it was actually a better use of capital. Fixed `backtest_advanced_pillars.
  py::experiment_1_position_sizing()` to also report **ROI% (net P&L / capital
  committed)**, which normalizes for scale. Result: **risk-parity wins on ROI too**, in
  all 6 cells tested (native_7, smart_6_macd, CANDIDATE_MODEL_L0 × 1%/2% risk budget) —
  margin is real but modest, not the dramatic gap the raw P&L numbers suggested:
  - native_7: flat 3.77% vs risk-parity 3.82% (N=1, not conclusive on its own)
  - smart_6_macd: flat 1.52% vs risk-parity 1.74% (1% budget) / 1.58% (2% budget), N=54
  - CANDIDATE_MODEL_L0: flat 6.07% vs risk-parity 6.12% (both budgets), N=128
  **Conclusion: risk-parity sizing is confirmed genuinely more capital-efficient**, not
  just bigger — small but consistent edge across every trade set tested. Not yet wired
  into any real position-sizing logic (still theoretical/backtest-only, same as before)
  — this closes the "was it a fair test" question, doesn't itself promote anything to
  production.
- **Macro-regime veto (ACWI.PA benchmark)**: tested, **hurts** `smart_6_macd` OOS
  (PF 1.45→1.07, avg net +1.2%→+0.21%), roughly neutral on `candidate_l0`. **Don't
  pursue this one** unless new data changes the picture.
- **Relative-momentum ranking on multi-signal days**: only N=8 usable dates — genuinely
  inconclusive, not enough data in this universe/period to test the idea at all.
- **Volume/RVOL data-quality filter**: not a trading idea, a data-quality finding — 75.4%
  of universe has good (>90%) volume coverage in the frozen dataset; Milano (35/51) and
  Swiss (2/6) exchanges notably worse than Parigi (80/97). If ever building an RVOL-based
  filter, it's only viable on a subset of the universe, not comprehensively.

## 6. Rejected — do not re-propose without new evidence

- **L0 SL formula (continuous+ratchet variant, tiers 2/3)**: tested 2026-08-19,
  REJECTED — costs ~7% P&L in-sample despite a better win rate/PF on paper. See
  [[etf_session_2026_08_19_directa_ratchet_and_terminology]]. Distinct from section 3
  above (tier 1) — that one is NOT rejected, still an open candidate.
- **ADX filter on `min_buy_count=6`** (2026-08-05): tested and rejected — `adx_ok` is not
  the dominant missing condition (7.2% of 6/7 trades) and isn't even overrepresented in
  the bad year 2024. See CLAUDE.md "Fase 2 — Ipotesi filtro ADX".
- **`min_buy_count=6` unconditional** (no MACD requirement): tested at 3-year scale,
  fragile/regime-dependent (positive 2025, negative 2024) — not a "ready alternative" on
  its own merits, only the MACD-gated smart_6_macd or the breadth-gated variant above
  showed anything more convincing.

## 7. NEW IDEA (2026-08-23) — dedicated mechanism for oro_metalli_preziosi (and possibly other cyclical/macro families)

Not a candidate yet, not backtested as a real system — just diagnosed and flagged. Confirmed
via Golden Dataset walk: `oro_metalli_preziosi` has **0 days in 3 years** (2023-08-05→today,
4 tickers, ~2955 ticker-days) reaching even smart_6_macd, let alone native 7/7. Root cause:
in 84% of near-miss cases EMA20 is still below SMA50 when everything else would align — the
medium-term trend genuinely hasn't turned yet. A counterfactual forcing Allineamento true
gave a noisy, unconvincing result (N=31, +1.40%/61.3%WR at 30gg, range -16%/+22%) — **not
worth pursuing as a parameter relaxation**, it would mean removing trend confirmation
entirely (same risk L0's whitelist was built to avoid).

**Direction discussed with the user, not yet built or backtested**: gold's actual behavior
(sharp macro-driven bursts, often after a quiet/oversold period, more mean-reverting than
trend-following) may fit the **existing L0 mechanism far better than L1**. L0 is currently
whitelisted to `equity_sviluppati` only (see [[etf_l0_project_2026_08_07]]) — but that
restriction was motivated by failures on structurally-*declining* speculative sectors
(INRG clean energy, BATE battery, BTCN crypto during bear markets), **not** by any
documented gold-specific failure. Worth backtesting L0 (dd_threshold/rsi_max/
l0_take_profit_pct calibrated for gold's volatility) on `oro_metalli_preziosi` specifically
via the Golden Dataset, same rigor as every other candidate this month, before considering
adding it to the L0 whitelist. Nothing built yet — this is a research direction to pick up
post-lockdown, not an active Shadow Monitor.

## 9. CANDIDATE_BOND_TREND_20260824 (new 3rd mechanism) — Shadow live, restricted to bond_corp_hy_em only

- Origin: full 14-family survey (2026-08-24) showed 5 bond/defensive families
  (`bond_governativi`, `bond_corp_hy_em`, `settoriali_difensivi`, `real_estate_reit`,
  `private_equity_buffer`) fire native_7 only 4 times in 3yr, all losses → blocked from L1
  (`min_buy_count: 8`, live). L0 then tested on all 8 "dead" families: 0 trades, 78
  tickers, 3yr — L0 doesn't fit them either. User asked explicitly to build a third
  mechanism.
- Diagnosed first: native_7's 7 conditions walked day-by-day over 40,711 ticker-days —
  7/7 never happens, 6/7 only 0.21% of days. `allineamento_ok` (EMA20>SMA50, 19.1% true)
  and `rsi_ok` (24.8%) are the dominant blockers — equity-calibrated momentum filters
  don't fit rate-driven bond price action.
- New mechanism: `ETFTechnicalAnalyzer.suggest_bond_trend_entry()` — price>EMA20 +
  persistence+slope>0 + tight distance cap + kill switch. No RSI/ADX/MACD/SMA50 at all.
  Exit reuses real `calculate_sl_suggerito_l1`/`calculate_stop_gain_dynamic` unmodified,
  with a bond-appropriate TP target (3% vs equity's 15%).
- First backtest was POOLED across all 5 families (61 tickers): IN N=191 PF=1.71 | OUT
  N=76 PF=1.68 — looked fine. **Same-day correction**: user asked whether parameters
  should differ per family (like equity does) — re-running segmented by family revealed
  the pooled number was hiding a broken family: `bond_governativi` looks OK in-sample
  (PF 1.5-2.2) but **collapses to near-zero out-of-sample** (WR 7-13%, PF 0.01-0.18),
  masked by `bond_corp_hy_em`'s excellent performance in the average. The other 3
  families have too few tickers (2-4) to trust or lose outright.
  - `bond_corp_hy_em` alone: strong and consistent on EVERY parameter combo tested, OOS
    PF systematically BETTER than IN (cleanest anti-overfitting signature in this
    project) — IN N=83 WR=72.6% PF=3.43 | OUT N=45 WR=77.3% PF=**5.89**.
  - **Model restricted to `bond_corp_hy_em` only**, params re-tuned for that family
    (persistence 20→12gg, dist_max 0.5%→0.3%). Deployed same day.
- **Shadow Monitor live**: `shadow_monitor_bond_trend.py`, STEP 8f,
  `model_name='candidate_bond_trend_20260824'`, params in
  `global_params.bond_trend_model` YAML block (now `families: [bond_corp_hy_em]` only —
  never touches `min_buy_count`/native_7). First real cycle: 4 entries (AFRN.PA,
  EFRN.DE, ECR3.DE, AFLT.PA), 0 errors — all already `bond_corp_hy_em`, nothing to clean
  up after the restriction.
- **Lesson for future pooled-cluster candidates**: always check the per-family/per-
  segment breakdown before trusting a pooled aggregate — same pattern as the
  `min_buy_count=6` 2024-vs-other-years issue, but at the family level.
- **To do at next checkpoint**: same N≥30-and-explicit-decision discipline as items 1-2 —
  no promotion without forward confirmation.
  ```sql
  SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
  FROM etf_shadow_positions WHERE model_name = 'candidate_bond_trend_20260824'
  ORDER BY entry_date;
  ```
- See [[etf_family_viability_survey_2026_08_24]] for the full diagnostic and grid search.

## 10. CANDIDATE_TIGHTEN_RSI_20260825 (L1 entry refinement) — Shadow live

- Origin: user noticed `smart_6_macd` entries (e.g. LGQM.DE) firing already extended from
  EMA20 with RSI over range — traced to the specific sub-case where `rsi_ok` is the ONLY
  missing native condition (MACD-confirmed boost still fires, but RSI-overbought entries are
  structurally already-extended moves).
- Fix tested: when only `rsi_ok` is missing, additionally require `dist_ema20<=3.0%` before
  accepting — otherwise skip. An alternative "wait for pullback" mechanism gave numerically
  identical results at every threshold (daily rescan already reproduces the wait), so the
  simpler "tighten" was kept.
- ⚠️ Backtest script had a real bug initially (double-applying the now-baked-in
  `CANDIDATE_MODEL_B` overrides on top of a baseline that already contains them, silently
  halving the effective ADX threshold) — fixed and validated against the certified
  CANDIDATE_MODEL_B numbers before trusting the new result. See
  [[etf_session_2026_08_25_rsi_gate_pac_fixes_radar]] for the full story.
- Certified: baseline IN N=31 PF=1.45 WR=54.8% | OUT N=18 PF=1.62 WR=55.6% vs tighten cap=3%
  IN N=24 PF=2.21 WR=62.5% | OUT N=14 PF=1.69 WR=57.1% — beats baseline on every metric,
  both windows. N<30 both sides — NOT promoted.
- **Shadow Monitor live**: `shadow_monitor_tighten_rsi.py`, STEP 8g,
  `model_name='candidate_tighten_rsi_20260825'`. Reuses production `suggest_level()`
  entirely, only adds the extra distance gate on the RSI-only sub-case.
- **To do at next checkpoint**:
  ```sql
  SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
  FROM etf_shadow_positions WHERE model_name = 'candidate_tighten_rsi_20260825'
  ORDER BY entry_date;
  ```

## 11. CANDIDATE_RADAR_APPROACH_20260825 / CANDIDATE_RADAR_BOUNCE_20260825 — Shadow live

- Origin: user asked whether the two informational dashboard radars (Radar Anticipato,
  Radar Rimbalzo EMA20) made sense as real entry triggers, not just informational display.
- Backtest (`backtest_radars.py`, new script, Golden Dataset batch 2026-08-07, same IN/OUT
  split as every other candidate, L1 reference re-simulated in the same run for a true
  apples-to-apples comparison — not old certified numbers): both radars' PF **improves**
  out-of-sample (approach 1.54→1.93, bounce 1.38→1.56 — after excluding `3LAM.MI`, the same
  corrupted-data ticker already flagged in [[etf_family_viability_survey_2026_08_24]], which
  first inflated bounce's PF to a fake 5.88 via a single +11,960% trade) and near-zero
  overlap with real L1 entries (0.0%/1.2% within ±10 days, same ticker) — genuinely
  different opportunities, not noise. Trade volume ~25-30x L1's but WR/PF per trade lower —
  "more quantity, lower quality" rather than a replacement.
- Certified (10k€/trade): L1 ref IN N=37 WR=59.5% PF=1.90 / OUT N=17 WR=52.9% PF=1.45 |
  approach IN N=932 WR=43.1% PF=1.54 / OUT N=381 WR=49.1% PF=1.93 | bounce IN N=1085
  WR=52.5% PF=1.38 / OUT N=435 WR=54.9% PF=1.56. MaxDD metric NOT meaningful here (raw
  cumulative-% over 1000+ trades, not comparable to the ~30-150-trade candidates it was
  designed for) — ignore it for these two.
- **Shadow Monitor live 2026-08-25**: `shadow_monitor_radars.py`, STEP 8h/8i in
  `monitor.py::run()`. Candidate universe mirrors the live `/api/approach-radar` (levels
  2/3) and `/api/bounce-radar` (levels 1/2/3) endpoints. Exit reuses real L1
  SL/TP functions unmodified. First live cycle: 4 approach entries + 19 bounce entries,
  0 errors.
- **To do at next checkpoint**, same N≥30-and-explicit-decision discipline as every other
  candidate:
  ```sql
  SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
  FROM etf_shadow_positions WHERE model_name IN
    ('candidate_radar_approach_20260825', 'candidate_radar_bounce_20260825')
  ORDER BY model_name, entry_date;
  ```
- See [[etf_session_2026_08_25_rsi_gate_pac_fixes_radar]] for the full backtest + Shadow
  Monitor build narrative.

## 12. Open data-quality issue (found 2026-08-25, NOT fixed) — UST.PA shared by two funds

`LU1829221024` (Amundi Core Nasdaq-100 Swap UCITS ETF Acc, unhedged — confirmed correct
owner of ticker `UST.PA`) and `LU1954152853` (the EUR-Hedged share class of the same fund)
both have `Ticker=UST.PA` in `etf_monitoraggio.xlsx` — identical price/technical-analysis
output for two genuinely different NAVs. A first fix (retagging `LU1954152853` to
`LU1954152853.SG`, found via Yahoo ISIN search, raw chart API confirmed real distinct EUR
data ~20.50) was **reverted same session**: `yfinance.Ticker('LU1954152853.SG').history()`
returns empty ("possibly delisted") despite the raw Yahoo REST API and `.info` metadata
both resolving fine — a real yfinance-specific gap, not a typo. `.F`/`.DE` suffixes also
fail on yfinance. Reverted to `UST.PA` (status quo) rather than leave the ETF frozen on
stale cached data with no error surfaced (`get_etf_history()`'s DB-fallback silently masks
fetch failures). **Still open** — needs the fund provider's own factsheet (Amundi site) to
find a ticker yfinance can actually fetch, not another automated ISIN search. Low priority:
L3, low buy_count, no real position affected.

## 13. CANDIDATE_L0_COOLDOWN_20260827 — Shadow live

- Origin: deepened a "re-entry a conferma" idea from external consulting. Found
  `suggest_level_0()` is level-triggered — the entry signal stays 'True' for many
  consecutive days, so a SL stop taken while the signal is still true produces an
  immediate re-entry the next trading day, with zero memory of the stop just taken. Real
  case verified: `LBRE.DE`/`LU1834983550`, entry=True continuously 2026-08-13→08-20, SL
  hit 08-14, re-entry 08-15 — in that specific case the re-entry helped (lower cost basis
  right before the real recovery to +7.19%), but the underlying mechanism has zero
  protection against the opposite whipsaw (immediate re-entry into a still-weak leg).
- Backtested two variants (`backtest_l0_cooldown.py`, scratch, deleted after use) on the
  real `equity_sviluppati` universe (105 tickers, Golden Dataset batch 2026-08-07, split
  IN 2023-08-05→2025-08-05 / OOS 2025-08-05→2026-08-05, real SL/TP functions unchanged):
  - **'reclaim' (block re-entry until price closes above the stopped trade's entry
    price)**: REJECTED — IN improves (PF 4.23→5.18, WR 62.1%→67.0%) but OOS collapses
    (PF 2.02→1.42, WR 45.5%→36.4%) — classic overfitting signature already seen elsewhere
    in this project.
  - **'cooldown N trading days' (block re-entry on the same ticker for N days after a SL
    stop, nothing else changed)**: 10 days beats baseline on EVERY OOS metric with no
    overfitting signature — IN N=97 PF=4.38 WR=62.9% | OOS N=12 PF=2.41 WR=50.0%
    P&L=+4,404€/10k, vs baseline OOS N=11 PF=2.02 WR=45.5% P&L=+3,179€/10k. Cooldown 3gg
    nearly identical (OOS N=12 PF=2.39 WR=50.0%). First re-entry-gate candidate in this
    project that beats baseline consistently IN+OOS.
  - `cooldown 3gg + reclaim` combo: numerically IDENTICAL to reclaim alone (N=88 both) —
    reclaim is always the more restrictive constraint of the two when both are active, so
    the combo adds nothing (expected, not a bug).
- **Shadow Monitor live 2026-08-27**: `shadow_monitor_l0_cooldown.py`, STEP 8j in
  `monitor.py::run()`, `model_name='candidate_l0_cooldown_20260827'`. New DB helper
  `database.py::get_last_shadow_sl_exit(model_name, ticker)` (most recent closed SL exit
  for that ticker/model). Cooldown counted in TRADING days via the ticker's own OHLC
  index (`_trading_days_since`), same unit of measure as the backtest — not calendar
  days. Only equity_sviluppati (only L0-reachable family). Verified end-to-end same day:
  syntax-checked in-container, deployed, triggered a full manual cycle — completed clean,
  0 errors in STEP 8j (0 opened/0 closed is expected on a brand-new candidate with no
  prior SL-exit history yet, and matches equity_sviluppati currently having 0 real L0/L1
  positions). Email wiring added: `alerts.py::_SHADOW_VARIANTS['L0_COOLDOWN']`.
- **To do at next checkpoint**, same N≥30-and-explicit-decision discipline as every other
  candidate:
  ```sql
  SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
  FROM etf_shadow_positions WHERE model_name = 'candidate_l0_cooldown_20260827'
  ORDER BY entry_date;
  ```

## 14. CANDIDATE_L0_SL_TIER1_20260828 (wider L0 initial stop) — Shadow live, 2 variants

- **Origin**: user asked whether a *support-zone / structural* stop (place SL below each
  ETF's recent support) could be backtested instead of picking a fixed %. Built
  `optimize_l0_sl_structural.py` (scratch, removed after run): 11 candidates on
  equity_sviluppati L0 — `fixed 4/5/6%`, `swinglow` (10/20/30d ± buffer), `atr` (2/2.5/3×),
  `hybrid`. Golden Dataset batch `2026-08-07`, 105 tickers, split IN→2025-08-05/OUT→2026-08-05.
- **Result**: **structural stops do NOT beat a wider fixed %.** `atr_*` whipsaws (OOS WR
  22-31%). `swinglow` raw is mediocre. The 3 that look great (`swinglow_20_1%`, `_30_1%`,
  `hybrid`) give *identical* numbers — artefact: their level falls below the −8% floor for
  almost every trade → they collapse into "fixed −8% stop", N=7 OOS. The clean signal (3rd
  time, after `CANDIDATE_MODEL_L0_SL_20260820`): **wider is better.**
  - `fixed_4%` (production): IN WR 63.1% PF 4.39 | OUT N=11 WR 45.5% PF 2.02
  - `fixed_5%`: IN WR 71.7% PF 5.29 | OUT N=11 WR 54.5% PF 2.70
  - `fixed_6%`: IN WR 74.2% PF 5.05 | OUT N=10 WR 60.0% PF 2.94
  - Monotonic on IN and OUT.
- **NOT promoted** (unlike the 2026-08-20 one): OUT N=10-11 too small, no real triggering
  event. Shadow first.
- **Built**: `shadow_monitor_l0_sl_tier1.py`, STEP 8k in `monitor.py::run()`. Two model
  names in parallel — `candidate_l0_sl_tier1_5pct_20260828` (buffer 0.05),
  `candidate_l0_sl_tier1_6pct_20260828` (0.06). Changes ONLY `l0_sl_tier1_buffer_pct` via a
  local copy of `analyzer.p`; entry (`suggest_level_0`), TP, tier2/3 all native. Email:
  `alerts.py::_SHADOW_VARIANTS['L0_SL_5PCT'/'L0_SL_6PCT']`. Production baseline is
  `l0_sl_tier1_buffer_pct: 0.04` explicit in the YAML for equity_sviluppati.
  `optimize_l0_sl_structural.py` + `optimize_l0_sl_tier1_em.py` removed from repo.
- ⏳ **PENDING VERIFICATION (user to do 2026-08-29)**: deployed 2026-08-28 evening, `import`
  check passed, but the manual `trigger-update` cycle was still running (on the bond ETFs)
  when the session ended — STEP 8k end-to-end not yet confirmed. User will check:
  `docker logs etf_monitor_system-app-1 2>&1 | grep -i "non bloccante" | tail` — if no
  `Errore Shadow Monitor L0-SL` line, STEP 8k ran clean (0 entries = silent = expected, no
  real equity_sviluppati L0 positions right now). The scheduled 09:00 cycle also re-runs it.
- **EM note**: same-day `optimize_l0_sl_tier1_em.py` on `mercati_emergenti` (whitelist+
  blacklist bypassed) — buffer 2%: IN N=86 WR 20.9% PF 1.23 | **OUT N=19 WR 0.0% −4.730€**.
  L0-on-EM has no edge (confirmed again) — no stop fixes it. No EM candidate.
- **To do at next checkpoint**, N≥30-and-explicit-decision:
  ```sql
  SELECT model_name, ticker, entry_date, exit_date, exit_reason, gross_pct_gain, status
  FROM etf_shadow_positions
  WHERE model_name IN ('candidate_l0_sl_tier1_5pct_20260828','candidate_l0_sl_tier1_6pct_20260828')
  ORDER BY model_name, entry_date;
  ```

## 15. Directa-faithful exit model — QUEUED for right after this checkpoint (2026-09-03)

User wants shadow monitors + backtests to model real Directa execution (one active sell
order; Stop ratchets toward price near TP via `order_pricing.compute_order_prices`)
instead of the current clean "SL-or-TP-first-touched, exact fill". This is the **next
project after the 06/09 checkpoint**, ahead of the wider-L1-SL analysis (item in
[[etf-l1-gate-widening-analysis-2026-09-01]]) which would otherwise run on the wrong
exit model. Plan (shared `simulate_directa_exit()` helper → wire into `backtest_l0_v2.py`
+ all 11 live shadow monitors → re-certify baselines → same-day cutover, "ride the
tightened Stop" not "perfect manual Limit at TP"). Read the current shadow data at THIS
checkpoint first for a clean old-model snapshot. Full detail:
[[etf-directa-faithful-exit-model-todo]].

## 18. Decision 3 (06/09 checkpoint) — the L1 low-ADX-grind gap

Discussed 2026-09-03. Live regime check: market is BULL/Risk-ON but `equity_adx: 12.1` — a
weak choppy grind. L1 correctly sits it out (needs ADX ≥ 18). The system covers "strong
trend" (L1) and "deep dip bounce" (L0) but has **NO mechanism for a weak persistent
uptrend** — which is how equity moves most of the time and what the passive VWCE PAC
captures while the active system holds cash. This is the mechanical reason passive beats
active in the current regime. At 06/09: decide (a) accept the split (slow grind → passive
PAC sleeve, active system works only the extremes, size capital to match) or (b) design a
third mechanism for the low-ADX persistent climb. Full reasoning in
[[etf-l1-gate-widening-analysis-2026-09-01]] ("The L1 gap" section).

**2026-09-03 exploratory backtests done** (both scratch, deleted): (1) **momentum/breakout**
for the parabola — concept works (caught silver +57.7% Jan 2026) but marginal system, OOS
PF ~1.1-1.2, tail-dependent, brutal worst-case on leverage; only settoriali_growth
consistent. (2) **grind/slow-climb** — decisively NEGATIVE: any selective "calm channel"
entry is in the market only 24% of the time and underperforms plain buy-and-hold by
18-29pp. **Then tested the regime-gated hold too (3rd grind test same day): −58 to −67pp vs
buy-and-hold** over 2022-06→2026-08 (captures ~15% of B&H return, saves only ~7pp
drawdown). Grind now tested 3 ways, all fail decisively. → **Decision 3 grind side is
SETTLED: no active mechanism beats buy-and-hold for the slow grind; the PAC IS the correct
answer (not a fallback), and the real decision is how big to size the PAC sleeve.** For
drawdown, the lever is asset allocation (bonds, the 75/25 the regime API suggests), not
timing. Only the momentum/parabola mechanism stays open as a "could we add it" (marginal,
tail-risky). Full data in [[etf-l1-gate-widening-analysis-2026-09-01]].

### 18b — DECIDE at 06/09: add a momentum/breakout mechanism for the parabolas? (user asked 2026-09-03 to put this on the agenda)

What the 2026-09-03 exploratory backtest showed: Donchian breakout + ATR chandelier trail
DOES catch the moves L1 structurally rejects (`PHAG.MI` silver +57.7% Jan 2026, one trade).
But as a system it's **marginal** — pooled OOS PF only ~1.10-1.23 (barely above break-even
after costs), 440-770 trades, WR 40-48%, decays IN→OOS (overfit signature). Per-family
wildly inconsistent: `oro_metalli_preziosi` "works" OOS only because of the ONE silver
trade (IN-sample it lost money); `crypto` collapses to 0% WR OOS; `leva_single_stock` worst
trade −83 to −87%. **Only `settoriali_growth` is consistent** (already an L1 driver).

**Options for 06/09:**
- (a) **Don't build it.** The edge is too thin and tail-dependent; same pattern as most
  rejected candidates. Accept that the parabola is not systematically capturable and the
  active system stays L1+L0.
- (b) **Build a narrow, guarded version + Shadow Monitor first** (NOT straight to
  production): restrict to `settoriali_growth` + maybe `oro_metalli_preziosi`; HARD % stop
  that actually holds (leverage products gap through ATR trails); small position size;
  exclude `leva_single_stock`/`crypto`/`commodities` where it collapses OOS. Then N≥30
  forward before any promotion, same discipline as every other candidate. This is real
  work (new entry logic, new exit logic, new shadow monitor) — not a config tweak.
- (c) **Targeted, accept-the-risk manual play** — no system, but a documented rule: "when a
  precious-metals ETF breaks a 20-day high with ADX rising, the user MAY take a discretionary
  position with a −8% hard stop, sized small." Removes the backtest-validation burden by
  making it explicitly discretionary.

Recommendation leaning (b) as a Shadow-only experiment IF the user wants parabola exposure
at all — but (a) is defensible and simpler given the pipeline is already being pruned
(item 16). Do NOT let this become a straight-to-production exception.

**DECISION (user, 2026-09-03): option (b)** — build the narrow guarded momentum mechanism
as a Shadow Monitor. Concrete plan, in order:

1. **Proper narrow backtest first** (`backtest_momentum_narrow.py`, scratch): restrict to
   `settoriali_growth` + `oro_metalli_preziosi` ONLY. Sweep: Donchian N ∈ {20,55}, entry
   ADX_min ∈ {20,25}, and crucially a **HARD % stop** ∈ {−6,−8,−10,−12%} that overrides the
   ATR chandelier (the leverage-gap problem — a hard stop that actually holds). Small
   position size baked into the P&L model (e.g. 5k not 10k). Frozen batch, IN/OOS split,
   per-family breakdown (never pooled — the 2026-09-03 run showed oro's "edge" was ONE
   silver trade). Bar to clear: OOS PF ≥ ~1.3 on BOTH families independently, no IN→OOS
   collapse. If it doesn't clear → fall back to option (a), tell the user.
2. **If it clears**: build `shadow_monitor_momentum.py` (new STEP in `monitor.py::run()`,
   same non-invasive try/except pattern as the other shadows), `model_name =
   `candidate_momentum_YYYYMMDD``, log to `etf_shadow_positions`, email via a new
   `_SHADOW_VARIANTS` entry. NO production entry-logic change, NO YAML change.
3. **N≥30 closed forward + explicit user decision** before any promotion — same discipline
   as every other candidate. NOT a straight-to-production exception.

**Priority: LOWEST of the queued work** — behind 06/09 checkpoint, the Directa-faithful
exit helper (item 15), and the L1 exit analysis (item 17). It's the weakest candidate
(marginal edge) and the user is already concerned about shadow-monitor sprawl (item 16). Do
step 1 (the backtest) around the same time as / just after item 17; only build the shadow
(step 2) if step 1 clears the bar.

## 16. Shadow-monitor PRUNING — scheduled for the 2026-10-06 checkpoint

User asked (2026-09-03) to prune the shadow pipeline at the **October checkpoint** (give
them one more month of data first, don't prune at 06/09). Context: as of 2026-09-03 there
are **11 active shadow monitor modules tracking 13 model_names** (STEPs 8b–8k in
`monitor.py::run()`), none near N≥30 closed after ~1 month, and many are minor variations
on the same theme (3 models just on L0 tier-1 SL width 4/5/6%, 2 on L0 entry timing, 2 on
L0 in extra families). User's own words: "ma quanti modelli stiamo testando???" — the
pipeline has sprawled (each session added one without retiring others).

**At 2026-10-06**: don't just read the numbers — **cut**. Retire any shadow that after
~2 months has 0–1 closed trades and no signal; keep only the 3–4 with enough forward
volume to say something by year-end. Removing a shadow = delete its `shadow_monitor_*.py`
+ its STEP call in `monitor.py` + its `_SHADOW_VARIANTS` entry in `alerts.py` (same
cleanup pattern used when `candidate_model_b`/`candidate_model_l0_sl` were promoted). Keep
the `etf_shadow_positions` rows (historical record), just stop generating new ones.

Snapshot to compare against at that checkpoint (2026-09-03): candidate_radar_approach 14
closed (most), candidate_l0_oro 5, candidate_model_l0_20260808 3 (all 3 losses, 0% WR —
below its certified 44-52% backtest WR), candidate_radar_bounce 4, everything else 0–2.

### Sub-item: `monetario_liquidita` exclusion from the radar shadows (found 2026-09-03)

`shadow_monitor_radars.py` filters the candidate universe by LEVEL only (`suggested_level`
in {1,2,3} for bounce, {2,3} for approach) — **no family filter**. Result: on 2026-09-03
the bounce shadow opened positions on `XEON.DE`/`LU0290358497` (EUR overnight rate — grinds
up ~linearly, no real V-bottom) and `C3M.PA`/`FR0010754200` (0-6M govt bond, near-cash).
A "rebound" trade on a money-market instrument is meaningless. **Also 2026-09-03**: the
approach radar shadow opened on `LVO.MI` (Amundi S&P 500 VIX Futures Enhanced Roll —
reclassified `leva_single_stock` on 07/08, structurally decays -82%/4yr by contango,
blocked from L1 via `min_buy_count:8` and from L0 via blacklist) — yet still slips into
the radar shadows because they filter by LEVEL only. At 06/10: add a family exclusion to
`shadow_monitor_radars.py` (both approach + bounce) covering at least
`monetario_liquidita` + `leva_single_stock`, probably the whole speculative cluster
(`crypto_digital_assets`, `commodities` too). **Also check the live dashboard**: if
`/api/approach-radar` / `/api/bounce-radar` in `app.py` show XEON/C3M/LVO too, fix it
there (the shadow just mirrors those endpoints) — the endpoint fix is the real one, the
shadow filter follows.

**Related, same batch (found 2026-09-03)**: `0E2B.IL` (LYXOR Smart Overnight,
`monetario_liquidita`) throws a caught-but-logged error EVERY monitor run —
`'<=' not supported between 'NoneType' and 'float'` in `check_l1_entry_tiered` /
`check_l1_entry_accelerated` / `l1_check_7_conditions`, and `- 'NoneType' and 'int'` in
`l2_calculate_readiness_score` — because `monetario_liquidita` has `adx_entry`/`rsi_entry_*`
= n/a (None) and those informational motors compare against them unguarded. Non-fatal (ETF
still classified L3). Fix: in `monitor.py::analyze_etf()` skip those 4 blocks for
`monetario_liquidita` (STEP 10/12/14/15, lines ~285-408), OR guard the None params inside
the `technical_analysis.py` methods. Deferred to here (not worth a lockdown deploy for log
noise) — batch with the radar family-exclusion, one deploy.

## 17. L1 EXIT analysis — queued AFTER item 15 (Directa-faithful helper)

Fixed order: 06/09 checkpoint → item 15 (Directa-faithful exit model) → this.
The 2026-09-01 analysis concluded the EXIT is the real problem (78-83% of L1 exits are
stop losses in every variant), not the entry gate. Test wider / ATR-based / 2-day-confirm /
weekly-recompute SL variants vs the current EMA20-based `calculate_sl_suggerito_l1`, on a
LARGE entry pool (every L1/L2 crossing or the ~1000+ radar entries) for statistical power,
decoupled from the entry gate. Full detail + variant list in
[[etf-l1-gate-widening-analysis-2026-09-01]].

## 8. Known gaps, not yet built (lower priority, not blocking)

- ✅ **CLOSED 2026-08-24**: `calculate_sl_suggerito_l0` now reads all 3 tiers from YAML per
  family (`l0_sl_tier1_threshold_pct`/`l0_sl_tier1_buffer_pct`/`l0_sl_tier2_threshold_pct`/
  `l0_sl_tier2_markup_pct`/`l0_sl_tier3_giveback_pct`), defaults = the old hardcoded values
  (5%/4%/15%/1%/8%), zero behavior change verified. Explicit values added for
  `equity_sviluppati`/`oro_metalli_preziosi`/`metalli_industriali` (the only families with
  real or Shadow L0 activity). Relevant now for the L0-oro/metalli Shadow Monitors, which
  bypass the whitelist for testing but previously still used these "one-size" params.
- `smart_6_7_macd` gate exclusion for `leva_single_stock` only covers `suggest_level()` —
  the parallel tiered/accelerated entry motors (`check_l1_entry_tiered()`/
  `check_l1_entry_accelerated()`) don't read `min_buy_count` at all, so if those ever get
  wired into a real decision path, the exclusion needs to be re-applied there explicitly.
