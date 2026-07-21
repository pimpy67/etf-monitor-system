# Prompt per Claude Code — Implementazione STEP 3 v4.0 (L0 / L1 / L2)

> Copia tutto il contenuto sotto la riga `---` e incollalo in Claude Code da terminale.

---

Contesto: sto revisionando il sistema "ETF Monitor" (STEP 3 v3.0 → v4.0-v4.3).
File di riferimento: `config/etf_families.yaml` (fonte di verità dei parametri),
`technical_analysis.py` (calcolo indicatori/segnali), `monitor.py` (ciclo di
monitoraggio). Il PDF in `config/` è generato automaticamente dal YAML: non
modificarlo mai a mano.

Prima di scrivere codice: leggi `config/etf_families.yaml`, `technical_analysis.py`
e `monitor.py` per capire la struttura attuale (nomi dei parametri esistenti,
come sono organizzate le famiglie ETF, come vengono valutate le condizioni
di L1 e L0 oggi). Poi implementa le modifiche sotto, in quest'ordine di
priorità:

## PRIORITÀ 1 — L0: Filtro di Regime con doppio percorso

Obiettivo: L0 (Deep Recovery) deve attivarsi solo su una vera fine di bear
market, non su un pullback fisiologico in trend rialzista. Serve un filtro
di regime A MONTE delle 4 condizioni di ingresso già esistenti, con due
percorsi alternativi:

**Percorso LENTO** (bear market conclamato): valido se l'asset è sotto SMA200
da almeno `regime_min_days_below_sma200` giorni consecutivi E il drawdown
è sostenuto per almeno `dd_min_duration_days` giorni (non solo toccato).
Il drawdown soglia va normalizzato sulla volatilità dell'asset:
```
dd_threshold_effettivo = dd_threshold_atr_multiple * ATR(60) / prezzo_medio_periodo
```
Conferma di ripresa: reclaim di `EMA(reclaim_ema_slow_period)`, default 50,
invece del solo micro-breakout attuale. Aggiungi anche, come via
alternativa alla divergenza RSI esistente, un segnale di capitolazione:
volume > `capitulation_volume_multiplier` * media_volume_20gg seguito entro
pochi giorni da inversione di chiusura.

**Percorso RAPIDO** (flash crash): bypassa il countdown del percorso lento se
il drawdown normalizzato su ATR supera `flash_crash_zscore_threshold`
(default 4 deviazioni) entro una finestra di `flash_crash_window_days`
(2-3 giorni). Conferma di ripresa più reattiva: reclaim di
`EMA(reclaim_ema_fast_period)`, default 20.

**Gestione dello stato** (IMPORTANTE — richiede stato persistente per
strumento, non ricalcolo stateless ad ogni ciclo):
- Al momento del trigger (lento o rapido), salva `l0_confirmation_mode`
  (`"fast"` o `"slow"`) e `l0_trigger_low_price` (il minimo che ha generato il
  trigger).
- Se scatta il percorso Rapido, ha SEMPRE priorità sul Lento anche se il
  Lento era già validato in precedenza sullo stesso strumento.
- `l0_confirmation_mode` resta bloccato (lock) per l'intero ciclo di
  recovery finché il trade non si chiude.
- Invalidazione: se il prezzo rompe al ribasso `l0_trigger_low_price`,
  l'intero tentativo di recovery viene invalidato (reset completo dello
  stato, non retrocessione a modalità slow), e la gerarchia va rivalutata
  da zero al prossimo ciclo. Questa regola vale per ENTRAMBI i percorsi,
  non solo per il rapido.

**Nuovi parametri YAML per famiglia** (equity/emerging/growth/defensive/bond_gov/
bond_corp/commodities/gold/industrial_metals/reit/crypto/leva/pe_buffer —
NON su monetario, dove L0 resta disabilitato):

| Parametro | Descrizione |
|---|---|
| `regime_min_days_below_sma200` | Giorni minimi sotto SMA200 per validare il regime bear |
| `dd_min_duration_days` | Giorni minimi di drawdown sostenuto |
| `dd_threshold_atr_multiple` | Multiplo di ATR(60) per drawdown normalizzato |
| `capitulation_volume_multiplier` | Soglia volume per segnale di capitolazione |
| `reclaim_ema_fast_period` | Default 20, per tutte le famiglie |
| `reclaim_ema_slow_period` | Default 50, per tutte le famiglie |
| `flash_crash_zscore_threshold` | Soglia deviazioni standard per il percorso rapido |
| `flash_crash_window_days` | Finestra giorni per il drawdown estremo (2–3) |

Proponimi valori di default ragionevoli per famiglia partendo dai
`dd_threshold`, `RSI Max` e `SL` già presenti nel YAML attuale, poi mostrameli
prima di scriverli nel file.

## PRIORITÀ 2 — L1: Spazio Residuo Minimo + fix squeeze/chattering

Obiettivo: aggiungere una settima condizione di ingresso a L1 che verifichi
lo spazio fisico disponibile prima del trade, senza bloccare i breakout da
compressione di volatilità e senza generare doppia contrazione del target.

**Nuova condizione** (l'ingresso richiede che almeno UNA delle due sia vera):

a) distanza da resistenza tecnica:
```
distanza_resistenza_pct = (max(resistance_lookback_days) - prezzo) / prezzo
```
valida se `>= min_reward_pct`

b) spazio da volatilità:
```
spazio_atr_pct = (ATR(14) / prezzo) * atr_multiplier
```
valida se `>= min_reward_pct`

**Override squeeze** (per non scartare i breakout da compressione pre-esplosione):
```
consolidation_range_pct = (max_N - min_N) / prezzo, con N = 20 giorni
squeeze_percentile = percentile_rank(consolidation_range_pct, ultimi 252gg)
squeeze_valido = (squeeze_percentile <= squeeze_percentile_threshold)
                 OPPURE (consolidation_range_pct <= squeeze_threshold_pct)
```
Se `squeeze_valido` è vero e la rottura è confermata (ADX in salita +
volume in espansione rispetto a media 20gg), bypassa interamente il
requisito `min_reward_pct` per quel trade.

**Vincolo architetturale IMPORTANTE:** lo spazio residuo minimo è SOLO un
filtro booleano di ingresso (accetta/rifiuta). Non deve mai modificare
`SG Target Floor` in ingresso — il floor resta determinato unicamente da
`target_floor_pct` di famiglia, per non sommarsi alla contrazione dinamica
esistente basata sulla pendenza EMA20 (rischio di target chattering /
uscite premature a catena).

**Nuovi parametri YAML per famiglia:**

| Parametro | Descrizione |
|---|---|
| `min_reward_pct` | Margine minimo richiesto per validare L1 |
| `resistance_lookback_days` | Giorni di lookback per la resistenza tecnica |
| `atr_multiplier` | Moltiplicatore ATR per il metodo (b) |
| `squeeze_threshold_pct` | Soglia assoluta di range per lo squeeze |
| `squeeze_percentile_threshold` | Default 20, può essere globale |

## PRIORITÀ 3 — L2: nuovo layer di Readiness Score (pre-screening)

Obiettivo: nuovo layer, NON un livello di trading, che assegna uno score
0-100 agli ETF non ancora in L1, per segnalare quali si stanno avvicinando
a un possibile ingresso. Riusa gli stessi indicatori già calcolati per L1
(EMA20, RSI, ADX, MACD, volume), in versione di prossimità/trend anziché
soglia booleana.

**Componenti dello score** (pesi indicativi, rendili configurabili):

| Componente | Peso | Descrizione |
|---|---|---|
| `dist_ema20_score` | 20 | Prezzo converge verso il range 0-4% da EMA20 |
| `rsi_approach_score` | 20 | RSI in salita, entro `rsi_approach_margin` punti dal bordo inferiore del range L1 |
| `adx_rising_score` | 20 | ADX in salita negli ultimi `adx_trend_days` giorni, anche se sotto soglia |
| `macd_histogram_score` | 20 | Istogramma MACD in aumento verso lo zero |
| `volume_expansion_score` | 10 | Volume relativo > `volume_ratio_threshold` |
| `days_above_ema20_partial` | 10 | Contatore parziale rispetto alla soglia L1 |

**Anti-flickering (mercati laterali):**
- Isteresi: entra in watchlist a `l2_readiness_threshold_enter` (70), esce solo
  sotto `l2_readiness_threshold_exit` (60) — soglie diverse, non la stessa in
  entrata e uscita.
- Smoothing: EMA a `l2_score_smoothing_period` giorni (default 3) sullo score
  grezzo prima del confronto con le soglie.
- Override di salto: se `(raw_score_oggi - raw_score_ieri) > l2_jump_threshold`
  (default 25) E `raw_score_oggi >= l2_readiness_threshold_enter`, il flag
  scatta immediatamente sul valore grezzo, bypassando la EMA per quel giorno.
- Hard-reset: quando scatta l'override di salto, il valore MEMORIZZATO della
  EMA va forzato (hard-set) al valore grezzo del giorno del salto, così il
  decadimento nei giorni successivi riparte da lì e non resta "drogato" dal
  baseline pre-salto. Applica lo stesso hard-reset simmetricamente anche ai
  crolli improvvisi dello score (stesso delta threshold in negativo), per
  evitare l'artefatto opposto.

**Nuovi parametri** (possono essere globali, non serve differenziarli per
famiglia in questa prima versione):

| Parametro | Default |
|---|---|
| `l2_readiness_threshold_enter` | 70 |
| `l2_readiness_threshold_exit` | 60 |
| `l2_score_smoothing_period` | 3 |
| `l2_jump_threshold` | 25 |
| `rsi_approach_margin` | 5 |
| `adx_trend_days` | 5 |
| `volume_ratio_threshold` | 1.2 |

**IMPORTANTE:** non integrare L2 nella dashboard/notifiche finché non hai
scritto un motore di simulazione/backtest che misuri il tasso di falsi
positivi in mercati laterali storici (chop zone) sulla combinazione
isteresi + smoothing rispetto al punteggio grezzo. Fammi vedere i
risultati del backtest prima di esporre il segnale.

## Istruzioni operative

1. Aggiorna prima lo schema YAML (`config/etf_families.yaml`) aggiungendo
   tutti i nuovi parametri per famiglia con i default che proponi,
   mantenendo la piena retrocompatibilità con i parametri esistenti.
2. Implementa la logica in moduli separati o funzioni chiaramente
   isolate (es. `l0_engine`, `l1_engine`, `l2_engine`) dentro
   `technical_analysis.py`, in modo che ogni livello sia testabile in
   isolamento.
3. Per lo stato persistente di L0 (`l0_confirmation_mode`,
   `l0_trigger_low_price`), individua dove `monitor.py` mantiene già lo
   stato per strumento e aggiungi questi campi lì, non ricalcolarli da
   zero ad ogni ciclo.
4. Scrivi unit test per: l'override di squeeze su L1, il doppio percorso
   e l'invalidazione del lock su L0, l'isteresi + hard-reset su L2.
5. Non toccare il PDF in `config/` — si rigenera da solo dal YAML.
6. Prima di eseguire modifiche estese, mostrami il piano (file che
   toccherai, funzioni nuove/modificate) e i valori di default proposti
   per il YAML, e aspetta la mia conferma prima di scrivere il codice.
