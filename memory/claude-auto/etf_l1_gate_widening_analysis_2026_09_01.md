---
name: etf-l1-gate-widening-analysis-2026-09-01
description: "In-progress analysis \"allargare il gate L1 + ripensare L0\" — Run 1 done (no case for widening), Run 2 (IN/OOS) running overnight on VPS, L0 side not started"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8ac1bdd4-8873-403f-82c8-16bc1c375114
  modified: 2026-09-02T09:41:44.744Z
---

User asked (2026-09-01, late night) to prepare an analysis on **whether to widen the L1
entry gate**, plus **"pensiamo anche qualcosa per L0"**. Trigger: shadow-monitor review
showed the native 7/7 gate produced **0 real L1 entries in 4 weeks**, and every closed
shadow trade (L0 + radars) in that month was a stop loss. User is skeptical the whole
shadow-monitor pipeline is earning its keep (see [[etf_post_lockdown_todo_20260906]]).

## Resume mechanics

- VPS SSH: `ssh -i ~/.ssh/id_ed25519_vps root@76.13.37.133` (the plain `root@...` key is
  NOT loaded on this PC — must pass `-i ~/.ssh/id_ed25519_vps` every time).
- **Run 2 result** lands at `/app/data/backtest_l1_fast_result.json` in container
  `etf_monitor_system-app-1` (+ human log `data/bt_l1_fast.log`). Launched 2026-09-02
  ~02:00 UTC, PID 12437, nohup — survives everything. ETA ~06:00-08:00 UTC. Check:
  `ssh -i ~/.ssh/id_ed25519_vps root@76.13.37.133 'docker exec etf_monitor_system-app-1 cat /app/data/bt_l1_fast.log'`
- Scratch tool: `backtest_l1_fast.py` (repo root, **untracked** — fast O(n) engine:
  precompute indicators once/ticker via `optimize_hyperparameters.precompute_ticker`, feed
  to `suggest_level(precomputed=...)`, reuse `backtest_l1.simulate/aggregate`). The plain
  `backtest_l1.py` is O(n²)/ticker → ~4h even core-only on this 1-vCPU VPS.
- **Guarded code change** (reverted in prod container AND local repo, keep reverting):
  `technical_analysis.py::suggest_level()` cond. 6 — added optional
  `p.get('macd_dip_tolerance_pct')` → `macd_ok = macd_positive and (macd_rising or (0 <= dist_ema20 < tol))`.
  Default (param absent) = current behavior exactly. Container backup at
  `/app/technical_analysis.py.bak_bt`. Re-apply + `docker cp` to `/app/` when running a
  backtest that needs the dip variants, then restore prod right after launch (running
  process keeps its in-memory copy). This closes a real doc/code gap: CLAUDE.md documents
  cond. 6 as having an `OR dist_EMA20 < 2%` branch that **never existed in code**.

## Run 2 — DONE 2026-09-02 (core-only, IN/OOS split, 10k€/trade)

| Variant | IN N/WR/PF/net€ | OOS N/WR/PF/net€ | verdict |
|---|---|---|---|
| prod_current (smart_6_macd) | 31 / 54.8% / **1.45** / +3031 | 18 / 55.6% / **1.62** / +2758 | positive both windows — the realistic ceiling; matches CLAUDE.md certified CANDIDATE_MODEL_B numbers exactly → fast engine validated |
| override_6 | 83 / 42.2% / **1.05** / +840 | 52 / 51.9% / 1.81 / +9957 | **FRAGILE confirmed** — IN barely breaks even (PF 1.05, +0.1%/trade). Dead. |
| dip05_prod (dip tol 0.5%) | = prod exactly | = prod exactly | **INERT** — dip branch fires 0 extra entries |
| dip10_prod (dip tol 1.0%) | = prod exactly | = prod exactly | **INERT** |

Per-family both windows (prod_current): **only equity_sviluppati is unambiguously positive**
(IN WR 65% +4.05% / OOS WR 78% +5.46%). mercati_emergenti negative both (IN −0.16%, OOS
−1.96%). settoriali_growth **negative in-sample** (−1.06%, N=4). metalli_industriali
negative (0% WR, −4.15%, N=2).

### L1 VERDICT — LOCKED

- **No case for widening the gate.** Every widening variant is fragile (override_6, PF 1.05
  IN) or inert/harmful (dip: nothing at 0.5-1.0%, floods with 51.7% WR / 83% SL trades at 2.0%).
- The documented MACD "buy-the-dip" branch is a dead end — closing the doc/code gap either
  does nothing or makes it worse.
- **Refined Decision 1: restrict `use_smart_6_7_macd: true` to `equity_sviluppati` ONLY**
  (remove mercati_emergenti, settoriali_growth, oro_metalli_preziosi, metalli_industriali)
  — this is the conservative option the user was offered and declined on 2026-08-24.
- The real lever is the **EXIT** (78-83% of exits are SL in every variant) — NOT tested
  yet. Candidate next analysis: wider / ATR-based / less-reactive L1 SL vs the current
  EMA20-based `calculate_sl_suggerito_l1`.

## Run 1 — DONE (core-only, single 3yr window 2023-08→2026-08, 10k€/trade, costs+tax)

| Variant | N | WR | PF | net/trade | SL/TP | net P&L |
|---|--:|--:|--:|--:|:--:|--:|
| native_7_pure (7/7, smart off) | 4 | 100% | ∞ | +7.15% | 2/2 | +2,861€ |
| **prod_current** (= live: smart_6_macd on 5 core) | 54 | 57.4% | 1.72 | +1.52% | 42/12 | +8,231€ |
| override_6 (6/7 flat) | 151 | 51.0% | 1.91 | +1.76% | 118/33 | +26,509€ |
| macd_dip 2.0% | 375 | 51.7% | 1.86 | +1.47% | 311/64 | +55,304€ |

- `smart_6_all` / `macd_dip_smart6` came out identical to prod_current (54) — artefacts
  (core already has smart_6_macd; the `require_macd` skip-mask uses the strict formula so it
  defeats the dip branch). Ignore those two labels.
- dip 2.0% is far too loose (turns MACD into "histogram>0" since entries are ~always
  within 2% of EMA20) → Run 2 tests **0.5% and 1.0%**.

**Findings:**
1. Live system is NOT broken — PF 1.72, +8,231€/3yr core.
2. Widening raises absolute P&L only by taking 3-7x more trades at **equal-or-worse
   per-trade** quality (net/trade +1.76%/+1.47% vs +1.52%, WR 57→51%). Not a better edge,
   just more volume at the same risk.
3. native_7 pure = 4 trades/3yr — dead, not an operational option.
4. **The structural problem is the EXIT, not the entry**: 78-83% of exits are stop losses
   in EVERY variant. System only wins via asymmetry. Widening entries adds trades that
   ~80% stop out.
5. Per-family (prod_current): equity_sviluppati WR 68% +4.58%/trade, settoriali_growth 67%
   +3.19%, but **mercati_emergenti 27% −1.14%**, metalli_industriali 33% −0.49%. Only 2 of
   the 5 core families generate value — the 3 weak ones (EM/oro/metalli) are exactly the
   ones the 2026-08-24 survey flagged weak but were promoted to smart_6_macd anyway.

## Decision direction (pre Run 2 — to confirm/revise)

Data does NOT support widening the gate. The opposite is emerging:
1. **Narrow `smart_6_macd`** to the 2 families that work (equity_sviluppati,
   settoriali_growth); remove oro_metalli_preziosi / metalli_industriali / mercati_emergenti.
2. Real intervention = **the exit** (EMA20-based SL too reactive, ~80% stop-out rate) —
   test wider / ATR-based / less-reactive SL.
3. Run 2 (IN/OOS) decides if `override_6` collapses out-of-sample like it did in 2024 —
   if so, "widen" is closed for good.

## L0 side — DONE 2026-09-02 (`backtest_l0_fast.py`, 4 variants IN/OOS, 10k€/trade)

| Variant | IN N/WR/PF/net€ | OOS N/WR/PF/net€ |
|---|---|---|
| **l0_prod** (wl=equity_sviluppati, regime BULL) | 50 / 28% / **0.96** / **−755** | 32 / 72% / 6.63 / +25118 |
| l0_regime_BL (+ LATERALE) | 121 / 41% / **1.69** / +24679 | 56 / 73% / 7.21 / +45060 |
| **l0_regime_all** (no regime gate) | 246 / 44% / **1.72** / +56292 | 73 / 77% / **8.57** / +62858 |
| l0_wl5_BL (5 core + BULL/LAT) | 259 / 33% / 1.23 / +20715 | 91 / 59% / 3.87 / +53263 |

### L0 VERDICT — opposite of L1: the current gate is TOO TIGHT

- **The regime BULL gate on L0 is demonstrably counterproductive.** `l0_prod` (current
  config) is a **net loss in-sample** (PF 0.96, −755€). Relaxing the gate fixes it:
  `l0_regime_BL` PF 1.69, `l0_regime_all` PF 1.72 — and OOS improves too.
- Mechanistically sound (hypothesis confirmed): a real deep drawdown breaks EMA20>SMA50 →
  regime ≠ BULL → today L0 blocks exactly the setups it exists for.
- `l0_regime_all` (drop the gate entirely) is best on nearly every metric, IN + OOS, largest
  N (246/73).
- **Widening the whitelist (`l0_wl5_BL`) is worse** than equity-only — per-family OOS: only
  equity_sviluppati works (WR 73%), EM 26%, growth 38%. Keep whitelist = equity_sviluppati.
- **Decision 2: relax the L0 regime gate** (remove entirely, or at least allow LATERALE).
  Strong backtest case IN+OOS.

### L0 — CODE BUILT 2026-09-02, deploy scheduled 03:00 via VPS cron

**All code written, smoke-tested, committed. A VPS cron runs `scripts/deploy_l0_3am.sh` at
03:00** (VPS idle then → fast build; the daytime PAC deploy's build took 48 min under load).
No migration (L0 change adds no tables). Files:
- `config/etf_families.yaml`: `global_params.l0_regime_allowed: [BULL, LATERALE, BEAR]`
- `technical_analysis.py::suggest_level_0()`: guarded `_l0_regime_allowed` block — verified
  in smoke test (VWCE.MI in LATERALE regime → `regime_ok_for_l0: True`, was False).
- `shadow_monitor_l0_regime_baseline.py` (NEW): reverse shadow, `model_name=
  'baseline_l0_regime_bull'` — enters only when `suggest_level_0().l0_entry AND regime_str
  == 'BULL'` (replicates the OLD gate). Wired as STEP 8b2 in monitor.py, email variant
  `L0_REGIME_BASELINE`.
- `alerts.py::send_shadow_monthly_digest()` (NEW) + `database.py::get_shadow_digest_stats()`
  / `get_real_l0_digest_stats()` (NEW). Monthly digest: fires from monitor.py STEP 8L when
  `date.today().day == 1` and `send_daily_report`. One row per shadow model + real L0, with
  N/WR/PF/avg%/SL-TP/verdict (CONFERMA ≥1.5PF+≥45%WR / CONTRADDICE ≤1.0PF / dati
  insufficienti <10 closed). Smoke-tested → email sent OK (a real test digest hit the
  user's inbox 2026-09-02).
- `etf_monitoraggio.xlsx` committed with VWCE.MI/GAGG.MI (so `smart_restore` in the deploy
  keeps them; git version previously still had .DE/.PA).
- `scripts/deploy_l0_3am.sh`: git sync → verify code present → build (timeout 40m, proceeds
  if image is recent even on hang) → recreate → health check (fail = leave as-is, log
  loudly) → trigger monitor. Logs to `data/deploy_l0_3am.log`.

**Morning check**: read `data/deploy_l0_3am.log`; confirm STEP 8b2 (Shadow L0-baseline)
ran without error; confirm `l0_regime_allowed` is in the container YAML. Remove the cron:
`crontab -l | grep -v deploy_l0_3am | crontab -`.

### ~~L0 — DECIDED 2026-09-02~~ (superseded above — code built)

User chose option (b): deploy the relaxed L0 gate straight to production (like `smart_6_macd`
24/08 and L0-SL 20/08 — motivated exception), with continued live monitoring. **This is a
SECOND deploy, to do AFTER the PAC feature deploy is verified.** Three parts:
1. **Deploy `l0_regime_all`**: `config/etf_families.yaml` → `global_params.l0_regime_allowed:
   [BULL, LATERALE, BEAR]` (= no regime gate); make the guarded `suggest_level_0()` change
   (`_l0_regime_allowed` list, reads `global_params.l0_regime_allowed`) permanent. Whitelist
   stays `equity_sviluppati` only (widening it was worse — `l0_wl5_BL`).
2. **Reverse shadow monitor** `shadow_l0_strict_baseline` (new): tracks what the OLD
   BULL-only gate WOULD have done, so each report shows live whether relaxing helped/hurt vs
   the old behavior. Logs to `etf_shadow_positions`, `model_name='baseline_l0_regime_bull'`.
3. **Monthly shadow digest email** (NEW — this capability doesn't exist yet). Fires on the
   1st of each month. For every shadow candidate + the L0 baseline: N trades, WR, PF, P&L
   delta vs production, one-line verdict (CONFERMA / CONTRADDICE / dati insufficienti).
   Currently shadow monitors only email on new entries (`send_shadow_entries`), no periodic
   digest — the "checkpoint" is manual SQL. This digest replaces that. Cadence = monthly
   (user's explicit choice over weekly — L0 holds positions weeks/months, weekly = noise).

Caveats: many trades still open at window end (L0 holds 68-168 days — long-hold, ties up
capital); immediate re-entry after stop inflates N (the 2026-08-27 L0-cooldown candidate
would fix); my patched engine counts ~3x the trades documented elsewhere — the *relative*
prod-vs-relaxed comparison holds, absolute values need caution.

Guarded code change for the test: `suggest_level_0()` reads `global_params.l0_regime_allowed`
(list) — if present, `regime_ok = regime_str in allowed`; absent (YAML default) → unchanged.
Reverted in prod + local repo. Backup `/app/technical_analysis.py.bak_bt`.

## ~~L0 side — RUNNING~~ (superseded above)

Scratch tool: `backtest_l0_fast.py` (repo root, **untracked**). Result →
`/app/data/backtest_l0_fast_result.json` + log `data/bt_l0_fast.log`. Poll task ba4cxc66c.
**4 variants** × IN/OOS:
- `l0_prod` (wl=[equity_sviluppati], regime BULL) — baseline
- `l0_regime_BL` (+ LATERALE allowed)
- `l0_regime_all` (no regime gate at all)
- `l0_wl5_BL` (wl = 5 core, + LATERALE)

Perf note: `suggest_level_0` = 142ms/call (52% in `_calculate_atr` recompute every day).
First L0 run (PID 12844) killed after 45min — would've been ~20h. `backtest_l0_fast.py` now
precomputes RSI/ATR/EMA/SMA once per ticker and monkeypatches the analyzer instance methods
to slice them (causal → identical values). 4x faster (142→20ms). ~1.5-2h expected.

Guarded code change for this: `suggest_level_0()` now reads
`global_params.l0_regime_allowed` (list) — if present, `regime_ok = regime_str in allowed`;
absent (YAML default) → unchanged `== 'BULL'`. Reverted in prod container + local repo
after launch (process keeps in-memory copy). Backup `/app/technical_analysis.py.bak_bt`.

Structural hypothesis: the regime BULL gate on all 3 L0 paths means a real deep drawdown
(which breaks EMA20>SMA50 → not BULL) blocks L0, so today L0 only fires on shallow
pullbacks inside an uptrend — contradicts "Deep Recovery".

## Decision framing given to user (full tree in the chat)

Decision 1 (L1 gate): widen / narrow / leave + fix exit. Decision 2 (L0): relax regime /
keep. Decision 3 (meta): if neither produces a credible OOS edge, stop building shadow
monitors and re-discuss active-vs-passive allocation (passive VWCE PAC already beats the
active system in the comparisons). As always: user decides explicitly, no auto-promotion.
