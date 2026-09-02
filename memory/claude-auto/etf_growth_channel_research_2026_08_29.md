---
name: etf_growth_channel_research_2026_08_29
description: "CLOSED (2026-08-30) — research to improve L1 entry timing from the top performers' growth channel. Verdict: NO edge survives real capacity constraints (random selection beat every score). Stay on smart_6_macd + L0. SCRATCH scripts on repo, not deployed, safe to delete."
metadata: 
  node_type: memory
  type: project
  originSessionId: 25f78187-b94a-49d9-ad66-fd0c86929d0e
  modified: 2026-08-29T22:13:41.258Z
---

## 🔴 VERDETTO FINALE (2026-08-30) — FILONE CHIUSO, nessun candidato

Il backtest di portafoglio con **vincolo di capitale reale** (`backtest_portfolio.py`,
8 slot × 10k = 80k, 3,5 anni, core) chiude la questione. P&L netto **realizzato**
(prezzi veri; le curve equity avevano ancora un bug festivi, fix `48439ee` mai rilanciato,
ma non cambia nulla):

| strategia | trade | net/trade | netto totale 3,5 anni |
|---|---|---|---|
| always | 603 | +5€ | +2.715€ |
| score (pullback) | 835 | +5€ | +4.245€ |
| strength | 376 | +41€ | +15.426€ |
| worst | 210 | +74€ | +15.524€ |
| **random** | 375 | +47€ | **+17.768€** |

- **`random` (scelta casuale tra i candidati in uptrend) fa PIÙ soldi di ogni score.**
  L'edge +146€/trade di `worst` nel test *senza vincoli* NON sopravvive: quando devi
  scegliere 8 su 100+ candidati, quale scegli non conta.
- ~+15-18k€ su 80k in 3,5 anni = **~+5,5%/anno**, sotto un DCA passivo su VWCE
  (~+7-8%/anno stesso periodo bull), con molto più lavoro.

**Conclusione**: nessun edge di timing d'ingresso regge alla realtà operativa.
`smart_6_macd` + L0 restano in produzione — edge piccolo, raro, ma **non costoso**
(~24 segnali/anno). Il PAC passivo è genuinamente competitivo, non un'illusione.

**Cleanup da fare (quando l'utente conferma)**: rimuovere dal repo
`research_growth_channels.py`, `backtest_growth_score.py`, `backtest_portfolio.py` +
`data/research_*.csv.gz` + `data/research_traderet_*.csv.gz`. Commit SCRATCH:
`1a8988e`..`48439ee`.

⚠️ Nota su un dato non certo emerso qui: il "+23% PAC su 3 anni" (CLAUDE.md, sezione PAC
del 24/08) è **un backtest** (DCA €1.000/mese simulato), non un risultato reale — il PAC
vero è partito il 24/08/2026. Come ordine di grandezza è valido (equity globale è
davvero salita ~30-40% cumulato 2023-2026), al centesimo no, e la finestra è tutta bull
(2022 escluso).

---
### Storico dell'indagine (tenuto per contesto)

**User's question (2026-08-29)**: partendo dai dati reali (Golden Dataset congelato), si
può caratterizzare il "canale di crescita" degli ETF più performanti ed estrarne una
firma d'ingresso ripetibile/predittiva? Motivato dal fatto che a agosto 2026 **zero
ingressi L0 e zero L1** in tutto il mese, mentre il market regime è BULL 94/100.

**Why**: il gate 7/7 nativo scatta 1-3 volte in 3 anni; `smart_6_macd` (produzione dal
24/08) ~16 trade/anno; il PAC passivo su VWCE.DE batteva il sistema attivo di ~20 punti su
3 anni. Se c'è un modo migliore di cronometrare gli ingressi, va trovato dai dati.

**How to apply**: riprendere da qui se si torna sul tema. Non è deployato niente. Vedi
[[etf_post_lockdown_todo_20260906]] per gli altri 8 candidati già in Shadow Monitor.

## Script (SCRATCH, sul repo — commit `1a8988e`..`f46e15c`, da rimuovere a fine analisi)
- `research_growth_channels.py` — FASE 1 build dataset feature+forward-return dal frozen
  batch `2026-08-07`; FASE 1b leaderboard + episodi di crescita + firma d'ingresso; FASE 2
  Spearman feature→target IN/OUT + quality-score prototipo + tenuta per anno.
  Output: `data/research_growth_dataset.csv.gz` (~158k righe, 221 ticker dopo pulizia,
  2023-02→2026-08). `--families core|equity|all`, `--target fwd_ret_60|fwd_mar_60`.
- `backtest_growth_score.py` — testa lo score come trigger d'ingresso reale (uscita SL/TP
  di L1, costi 5+5€, tasse 26%, split IN<2025-01-01/OUT). Modi: `score` (pullback),
  `always` (nessun timing), `worst` (score al contrario = forza), `strength` (score
  fittato su `fwd_trade_ret` = rendimento reale del trade con SL/TP — target stop-aware,
  versione pulita di `worst`). `--mode all`, `--sweep`.
- Pulizia dati: `clean_ohlc()` scarta 5 ticker corrotti dal frozen batch
  (`0E2B.IL 3LAM.MI 3LFB.MI 3LNV.MI 3SNV.MI` — spike tipo il già-noto 3LAM). Il primo run
  senza pulizia era spazzatura (rvol 10.000%, slope 1e37, fwd_ret medi +300%).

## Cosa si è trovato

1. **Classifica per famiglia (MAR = CAGR/maxDD, 3 anni)**: equity_sviluppati 1.05 e
   settoriali_growth 0.97 sono i motori equity; commodities/oro alto rendimento ma DD
   -17/-34%; bond_corp_hy_em MAR alto solo per denominatore (FRN quasi-liquidità);
   leva_single_stock -0.17, crypto/difensivi 0.3. → conferma le 5 core e i blocchi L1.
   Veri compounder: ENRG.PA (+107% in 280gg, maxDD -5,5%), BNK.PA, CEC.PA (+191% tot),
   BNKE.PA (+266%), GRE.PA (+176%), CHIP.MI (+399% tot).

2. **L'idea "compra il pullback" è MORTA.** Lo score che predice alto `fwd_ret_60`
   (RSI basso, sotto EMA20, MACD<0, in drawdown) come trigger d'ingresso reale:
   **durata mediana 1 giorno**, 917/984 uscite = stop loss immediato. Motivo meccanico:
   lo stop L1 (`EMA20 − buffer`) sta *sopra* l'ingresso se entri sotto l'EMA20 → fuori
   al primo tick. La correlazione statistica col rendimento a 60gg era vera ma
   **irrilevante col trading** (che ha gli stop). `score` OUT: +42-53€/trade, PF 1.8.

3. **`worst` mode (= compra la forza) è un edge vero e robusto.** Score al contrario =
   setup di forza/continuazione (sopra EMA20, RSI ~55, MACD>0, basso drawdown). Con
   l'uscita L1: **CORE OUT N=534 (~150/anno), WR 53%, PF 2.27, +146€/trade netto (10k),
   durata 30gg**. Equity OUT: PF 2.28, +137€/trade. IN più debole di OUT (non
   overfitting). Sweep pct 0.70→0.92: +107..+131€/trade, PF 2.0-2.2 sempre
   (parameter-robust). Contro `always` (+58-61€, PF 1.80) e `smart_6_macd` produzione
   (~16 trade/anno, PF ~1.5 documentato) → un ordine di grandezza più operativo a
   qualità più alta.

4. **Questo NON è un meccanismo nuovo** — è una versione **più permissiva** della
   direzione che il gate L1 già segue (compra forza confermata). Il gate non è
   sbagliato, è solo troppo stretto. (Nei messaggi della sessione avevo prima detto
   "L1 compra il momento sbagliato" — **era una sovra-interpretazione, corretta dal
   backtest**.) `smart_6_macd` è già la versione rilassata *validata*; la domanda è se
   un rilassamento ancora più forte (~10x volume) regge.

5. **`score→fwd_mar_60` ("strength" primo tentativo) FALLISCE** — +3€/trade CORE OUT.
   Il target mar non risolve il problema meccanico dello stop.

## `STRENGTH` pulito ESEGUITO (2026-08-29) — DELUDENTE, filone in stand-by

`--mode strength` (score fittato su `fwd_trade_ret` stop-aware), CORE OUT:
N=529, WR 50%, PF 2.08, **+65€/trade** (10k), durata 10gg. EQUITY OUT: **+58€/trade** =
**identico ad `always`** (+58€). Sweep pct 0.70→0.92: +52..+68€/trade, PF 1.9-2.1
(parameter-robust ma a livello mediocre). **Nessun edge reale sopra il baseline `always`.**

`worst (ret)` resta l'unico numero forte (CORE OUT +146€/trade, PF 2.27) MA:
- è uno score fittato su `fwd_ret_60` e preso al contrario — non riproducibile con un
  target onesto.
- **Sospetto artefatto del cap `MAX_FWD_TRADE=90`**: i trade vincenti di `worst` hanno
  durata mediana 30gg ma coda lunghissima (ENRG 280gg). `fwd_trade_ret` tronca a 90gg →
  il target stop-aware penalizza proprio i trend lunghi che rendono `worst` profittevole.
  Se si riprende: rialzare il cap a 180gg e rifare `STRENGTH`.
- `worst (trade)` (bottom decile dello score onesto) fa +85€/trade CORE OUT — un'altra
  lieve inversione → lo score `fwd_trade_ret` non è predittivo in nessuna direzione.

**Verdetto onesto**: nessun miglioramento di timing d'ingresso pulito, robusto e ben
fondato è emerso. Il baseline `always` (+61€/trade, PF 1.80, "stai in un uptrend core con
SL/TP") è la cosa che nulla batte in modo convincente. Takeaway laterale: il costo del
gate attuale è la sua **restrittività**, non la sua logica — coerente con la promozione
di `smart_6_macd`.

## Pending (se si riprende)
- Rialzare `MAX_FWD_TRADE` a 180 in `backtest_growth_score.py`, rifare `STRENGTH` +
  `worst (ret)` → capire se `worst` era artefatto del cap o segnale vero.
- `backtest_l1.py --start 2023-08-05 --compare-min-buy 6` — confronto vs 7/7 mai eseguito.
- Solo se un candidato regge con target onesto → Shadow Monitor. Per ora: **niente da
  proporre**, si resta su `smart_6_macd`.
- Caveat noti: survivorship (frozen = 221 sopravvissuti); concorrenza/capitale non
  modellati (~30-40 posizioni aperte insieme, irrealistico — conta il per-trade);
  researcher DOF (l'ipotesi "forza" è emersa post-hoc, `worst` era un controllo previsto).
- Cleanup: rimuovere gli script SCRATCH + i `data/research_*.csv.gz` dal repo quando si
  chiude il filone.
