# CLAUDE.md — ETF Monitor System

Documento di riferimento tecnico. Caricato automaticamente da Claude Code a ogni sessione.

> ⚠️ **REGOLA PERMANENTE (2026-07-15)**: Vedi sezione **"REGOLA DI SINCRONIZZAZIONE PERMANENTE — PDF Parametri"** — qualsiasi modifica ai parametri deve propagarsi automaticamente a PDF, dashboard, e documentazione. Non è tollerata sincronizzazione manuale.

---

## Infrastruttura VPS

- **Provider**: Hostinger VPS — Ubuntu 24.04 LTS
- **IP**: `76.13.37.133`
- **SSH**: `ssh root@76.13.37.133`
- **SSH key locale**: `~/.ssh/id_ed25519_vps`
- **DNS**: Cloudflare (record A proxied) — SSL deve essere **Full (strict)**
- **Reverse proxy**: Nginx → `/etc/nginx/sites-enabled/etf` → porta 5001

---

## Percorsi

| Risorsa | Percorso |
|---------|----------|
| Sorgente locale (Windows) | `C:\Users\andrea.pavan_allievi\Documents\etf_monitor_system\` |
| Git repo VPS (= deploy dir) | `/root/etf_monitor_system/` |
| Container attivo | `etf_monitor_system-app-1` → porta **5001** |
| Dashboard | `https://etf.andreapavan.tech` |
| Git remote VPS | `git@github-pimpy67:pimpy67/etf-monitor-system.git` |
| Git remote locale | `https://github.com/pimpy67/etf-monitor-system` |

---

## Deploy

```bash
# Da Windows (Git Bash / WSL):
./deploy.sh
```

`deploy.sh` fa in sequenza:
1. `git push origin main` (se ci sono modifiche)
2. SSH VPS: salva `etf_monitoraggio.xlsx` → `git reset --hard origin/main` → ripristina Excel
3. SSH VPS: `docker compose -p etf_monitor_system build app`
4. SSH VPS: `docker compose -p etf_monitor_system up -d --force-recreate app`

> **Perché salvare l'Excel?** Il monitor aggiorna `etf_monitoraggio.xlsx` in-place (livelli ETF). `git reset --hard` lo sovrascriverebbe con la versione del repo. Il backup/ripristino mantiene i livelli aggiornati.

> **Database**: PostgreSQL in Docker volume `etf_monitor_system_etf_postgres_data` — non viene mai toccato dal deploy.

---

## Comandi rapidi VPS

```bash
# Log live container
ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 --tail=30 -f"

# Trigger manuale monitor
ssh root@76.13.37.133 "curl -s -X POST http://localhost:5001/api/trigger-update"

# Query DB
ssh root@76.13.37.133 "docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c '<SQL>'"

# Stato container
ssh root@76.13.37.133 "docker ps --filter name=etf_monitor_system"
```

---

## Database PostgreSQL

- Container: `etf_monitor_system-postgres-1`
- User: `etfmonitor`, DB: `etfs`, password in `.env` → `DB_PASSWORD`
- Volume: `etf_monitor_system_etf_postgres_data`

**Tabelle principali:**
- `etf_price_history` — storico OHLCV (isin, date, open, high, low, close, volume)
- `etf_l1_tracking` — ETF in trend sicuro L1 (entry_date, entry_price)
- `etf_l1_exit_history` — storico uscite L1 (exit_date, exit_rule, pct_gain)
- `etf_l0_tracking` — ETF in deep recovery L0
- `portfolio_entries` — portafoglio personale
- `portfolio_events` — eventi portafoglio (buy/sell parziali)

---

## Variabili d'ambiente `.env`

```
DB_PASSWORD=...
RESEND_API_KEY=...
EMAIL_SENDER=onboarding@resend.dev
EMAIL_RECIPIENT=andreapavan67@gmail.com
MONITOR_HOUR=17
MONITOR_MINUTE=0
MONITOR_DAYS=1-5
RUN_ON_START=false
```

---

## Architettura sistema

### File principali
| File | Ruolo |
|------|-------|
| `app.py` | Flask API + serving dashboard + auto-recovery |
| `monitor.py` | Logica principale: fetch prezzi, calcolo livelli, aggiorna Excel + DB |
| `technical_analysis.py` | Indicatori: EMA20, SMA50, SMA200, ADX14, RSI14, MACD — logica L0/L1/L2/L3 |
| `data_fetcher.py` | Fetch OHLCV da Yahoo Finance |
| `database.py` | Wrapper PostgreSQL |
| `scheduler.py` | Job scheduler — run principale 17:00 + run silenzioso 09:00 (lun-ven) |
| `dashboard.html` | Frontend SPA (HTML+JS, servito da Flask) |
| `etf_monitoraggio.xlsx` | Excel con lista ETF — fonte di verità per ticker e liste |
| `alerts.py` | Email Resend: digest L1, uscite L1, alert L0 |

### Flusso monitor quotidiano
```
scheduler.py
  └─ monitor.py
       ├─ Legge ETF da etf_monitoraggio.xlsx
       ├─ Fetch OHLCV da Yahoo Finance (yfinance)
       ├─ Salva in PostgreSQL (etf_price_history)
       ├─ Calcola EMA20/SMA50/SMA200/ADX/RSI/MACD
       ├─ Determina L0/L1/L2/L3
       ├─ Aggiorna Excel (livelli)
       ├─ Salva data/dashboard_data.json
       ├─ alerts.py → email
       └─ pdf_generator.py → rigenera PDF (STEP FINALE)
```

---

## 📋 REGOLA DI SINCRONIZZAZIONE PERMANENTE — PDF Parametri (2026-07-15)

> **🔴 REGOLA BINDING PER SEMPRE**: Ogni modifica ai parametri del sistema deve essere automaticamente riflessa nel PDF scaricabile. Non deve essere una responsabilità manuale.

### Principio
- **Fonte di verità unica**: `config/etf_families.yaml` — contiene TUTTI i parametri L0/L1/L2/L3
- **Visualizzazione live in dashboard**: `/api/parameters` carica dinamicamente i parametri dal YAML e li mostra nel tab "Parametri di Riferimento"
- **PDF scaricabile**: generato automaticamente **lato server** da `pdf_generator.py` — sempre sincronizzato al 100%
- **Nessuna gestione manuale**: il PDF non viene mai scritto a mano, non viene mai committato in git

### Workflow Automatico (IMPLEMENTATO 2026-07-15)

#### 1. **Al deploy o all'avvio dell'app** (`app.py`)
```python
# All'avvio di Flask:
generate_parameters_pdf('data/ETF_Monitor_Parametri_Riferimento.pdf')
```
→ PDF generato dai parametri YAML attuali

#### 2. **Dopo ogni ciclo di monitor** (`monitor.py::run()`)
```python
# STEP FINALE di ogni monitor (17:00 + 09:00):
generate_parameters_pdf('data/ETF_Monitor_Parametri_Riferimento.pdf')
add_log("✅ PDF parametri rigenerato (sincronizzato con YAML)")
```
→ PDF sempre aggiornato con gli ultimi parametri, il dashboard mostrerà i dati live e il PDF scaricabile riporterà le stesse informazioni

#### 3. **Quando l'utente scarica il PDF**
```
Dashboard → bottone "📥 PDF"
  → GET /api/download-parameters-pdf
  → serve data/ETF_Monitor_Parametri_Riferimento.pdf
  → (file è garantito sincronizzato con YAML)
```

### File interessati
| File | Ruolo |
|------|-------|
| `config/etf_families.yaml` | **Fonte di verità** — modifiche qui propagano automaticamente |
| `pdf_generator.py` | Generatore PDF server-side — legge YAML e produce PDF vero (non HTML→PDF) |
| `app.py` | Genera PDF all'avvio + expone endpoint `/api/download-parameters-pdf` |
| `monitor.py` | Rigeneraa PDF dopo ogni ciclo (STEP FINALE) |
| `dashboard.html` | Tab "Parametri di Riferimento" mostra dati live + bottone "📥 PDF" per il download |

### Tecnologie usate
- **ReportLab**: generazione PDF lato server (no dipendenze browser, sempre affidabile)
- **YAML** → **Python dict** → **PDF**: pipeline diretta, nessuna intermediazione

### Modifica dei parametri — Procedura Automatica
```
1. Modifica config/etf_families.yaml
   ✅ Automatico: dashboard mostra i nuovi parametri in tempo reale (next refresh)
   ✅ Automatico: prossimo monitor rigenerato PDF con i nuovi valori

2. Fai deploy (./deploy.sh)
   ✅ Automatico: app.py rigenera PDF all'avvio

3. Utente scarica PDF
   ✅ Garantito: riceve il PDF con i parametri aggiornati
```

### Compliance con CLAUDE.md
- **Ogni modifica ai parametri nel codice** (YAML, technical_analysis.py, monitor.py) **genera automaticamente un nuovo PDF**
- **Non modificare il PDF manualmente**
- **La fonte di verità è sempre config/etf_families.yaml**
- **Il PDF è un derivato del YAML**, non una fonte indipendente

### Endpoint Helper per Sincronizzazione Tabelle HTML

**Endpoint** `/api/parameters-tables-html` (NEW 2026-07-15):
- Genera le tabelle HTML parametri **dinamicamente** dal YAML
- Restituisce JSON con HTML già formattato
- Usare via fetch JavaScript nel dashboard per aggiornare le tabelle automaticamente

**Implementazione completa**:
- ✅ PDF scaricabile → **100% automatico** da YAML (`pdf_generator.py`)
- ✅ Sezione "Parametri Dinamici" → **sincronizzata automaticamente** via `/api/parameters`
- ✅ Endpoint `/api/parameters-tables-html` → **100% automatico**, pronto per JavaScript
- ⚠️ Tabelle HTML nel dashboard → Per ora hardcoded, ma possono essere sostituite caricando da `/api/parameters-tables-html`

**Road Map**:
1. (Fatto) PDF + `/api/parameters` + `/api/parameters-tables-html` = tre layer di sincronizzazione
2. (TODO) Aggiornare JavaScript nel dashboard per caricare tabelle da `/api/parameters-tables-html` (fase 2)
3. (TODO) Rimuovere tabelle hardcoded dal dashboard HTML (fase 2)

---

## Schema Livelli ETF

### L1 — Core Portfolio — GERARCHIA 2+2 INTELLIGENTE (2026-07-15)

> **NOTA**: La vecchia logica "6 condizioni tutte obbligatorie" è stata **SOSTITUITA** dalla **gerarchia 2+2** che consente entry più veloci.

#### **GATE STRUTTURALE** — 2/2 OBBLIGATORI (non negoziabili)
| Parametro | Condizione | Significato |
|-----------|-----------|-------------|
| **A** | `price > EMA20` | Il prezzo è sopra la media veloce — il rally è attivo |
| **M** | `MACD_histogram > 0` | Il volume sta spingendo al rialzo — momentum positivo |

**Regola**: Se **A ∧ M** sono entrambi FALSE → **BLOCCO TOTALE**, nessun ingresso possibile.

#### **VELOCITÀ FLESSIBILE** — Almeno 2 su 4 RICHIESTI
| Parametro | Condizione | Significato |
|-----------|-----------|-------------|
| **P** | `price > SMA50` | Allineamento confermato con media media |
| **R** | `rsi_entry_low ≤ RSI ≤ rsi_entry_high` | RSI in range ottimale per famiglia |
| **D** | `ADX ≥ adx_min_threshold` | Forza direzionale confermata |
| **X** | `EMA20 > SMA50` | Allineamento bifase in accelerazione |

**Regola**: Conteggia quanti tra {P, R, D, X} sono TRUE. Se **count ≥ 2** → INGRESSO AUTORIZZATO.

#### **CONFIDENCE MAPPING**
```
Gate 2/2 ✓  +  Velocity 2/4  →  60% confidence (size 60% allocation)
Gate 2/2 ✓  +  Velocity 3/4  →  80% confidence (size 80% allocation)
Gate 2/2 ✓  +  Velocity 4/4  →  100% confidence (size 100% allocation)
```

#### **VANTAGGI vs VECCHIO 6/6**
| Aspetto | Vecchio 6/6 | Nuovo 2+2 |
|---------|:---:|:---:|
| Entry timing | Day 5-7 | Day 1 |
| Profit captured | +2-3% (coda) | +4-6% (intero move) |

### Uscita L1 — 6 Regole
| Pri | Regola | Trigger |
|:---:|--------|---------|
| 1 | F Kill Switch | Calo giornaliero ≤ −3% |
| 2 | A Stop Loss | Prezzo sotto EMA20 da ≥ 3 giorni |
| 3 | B Trailing Stop | EMA10 < EMA20 |
| 4 | C Stanchezza | RSI_prev ≥ 70 AND RSI_oggi < 70 (non-bond) |
| 5 | E ADX debole | ADX < 18 AND prezzo < EMA20 |
| 6 | D Uscita Parziale | RSI > 78 → vendi 90%, mantieni 10% + acquista XEON |

### Profili parametri FAMIGLIE ETF — 15 Classi (aggiornato 2026-07-16)

> **FONTE AUTOREVOLE**: `config/etf_families.yaml` — **NON modificare manualmente, leggere solo dal YAML**

#### TABELLA PARAMETRI VELOCITÀ GERARCHIA 2+2
Questi parametri sono usati per valutare le 4 condizioni di Velocity (P, R, D, X):

| Famiglia | RSI Range | ADX Min | ema_dist_max | l0_enabled |
|----------|:---:|:---:|:---:|:---:|
| **equity_sviluppati** | 45–55 | 22 | 4.0% | ✓ |
| **mercati_emergenti** | 40–52 | 22 | 5.0% | ✓ |
| **settoriali_growth** | 48–58 | 25 | 5.0% | ✓ |
| **settoriali_difensivi** | 42–50 | 18 | 2.5% | ✓ |
| **bond_governativi** | 38–48 | 12 | 1.5% | ✓ |
| **bond_corp_hy_em** | 42–52 | 15 | 2.0% | ✓ |
| **commodities** | 40–55 | 22 | 3.0% | ✓ |
| **oro_metalli_preziosi** | 38–52 | 18 | 2.5% | ✓ |
| **metalli_industriali** | 38–50 | 20 | 3.0% | ✓ |
| **real_estate_reit** | 42–52 | 15 | 2.0% | ✓ |
| **crypto_digital_assets** | 35–52 | 28 | 6.0% | ✓ |
| **leva_single_stock** | 45–58 | 28 | 4.0% | ✗ |
| **private_equity_buffer** | 40–55 | 15 | 2.5% | ✓ |
| **monetario_liquidita** | n/a | n/a | 0.5% | ✗ |

**Legenda**:
- **RSI Range**: Range per condizione R (Velocity) — per rilevare ipercomprato/ipervenduto
- **ADX Min**: Soglia per condizione D (Velocity) — forza direzionale minima
- **ema_dist_max**: Distanza massima da EMA20 in % (filtro velocità P)
- **l0_enabled**: Se ✗, L0 è disabilitato per questa famiglia (leva, monetario)

**Nota**: I parametri completi (stop loss, trailing, stop gain, L0 drawdown) sono in `config/etf_families.yaml` e auto-sincronizzati nel PDF via `pdf_generator.py`

### L0 — Deep Recovery (indipendente da gerarchia 2+2)

**Parametri L0** (per famiglia in `config/etf_families.yaml`):
- `l0_entry.enabled`: se true, la famiglia è candidata per L0
- `l0_entry.dd_threshold`: drawdown minimo (% sotto picco storico)
- `l0_entry.rsi_max`: RSI max per ipervenduto
- `l0_entry.lookback_high_days`: giorni per divergenza rialzista
- `l0_entry.recovery_min_pct`: minimo recupero richiesto

**Entrata L0** — tutte 4 condizioni obbligatorie:
1. Prezzo almeno `dd_threshold`% sotto il picco (vedi tabella)
2. RSI < `rsi_max` (ipervenduto)
3. Divergenza rialzista (prezzo minimo più basso, RSI minimo più alto negli ultimi `lookback_days`)
4. Segnale recupero: RSI > 32 OPPURE micro-breakout ≥ 0.3% su 5 giorni

**Uscita L0** — basta 1:
- γ: Prezzo > EMA20 → promozione a L2
- β: RSI < 25 dopo ingresso → trappola ribassista
- α: Prezzo < panic_low (minimo 30gg all'ingresso) → stop assoluto
- ε: Nessun recupero dopo 30 giorni → exit in monitor.py

---

## Trailing Stop Dinamico Continuo (STEP 2 — 2026-07-10)

Il trailing stop per L1 segue una **formula lineare continua** che protegge i profitti senza salti rigidi.

**Formula**:
```
excess_gain = max(0, current_gain_pct - trailing_gain_threshold)
distance = max(trailing_base_pct - (excess_gain × trailing_sensitivity), trailing_min_pct)
SL_percent = 1.0 - distance
SL_price = entry_price × SL_percent
```

**Parametri per famiglia** (dal YAML):

| Famiglia | trailing_base | trailing_sens | trailing_gain_th | trailing_min | Profilo |
|----------|:---:|:---:|:---:|:---:|-----------|
| **equity_sviluppati** | 8.0% | 0.005 | 3.0% | 94% | Moderato |
| **mercati_emergenti** | 9.0% | 0.004 | 3.0% | 92% | Ampio |
| **settoriali_growth** | 9.0% | 0.0045 | 3.0% | 92% | Ampio |
| **settoriali_difensivi** | 6.0% | 0.005 | 2.0% | 95% | Stretto |
| **bond_governativi** | 3.5% | 0.008 | 1.5% | 97% | Molto stretto |
| **bond_corp_hy_em** | 5.0% | 0.007 | 2.0% | 96% | Stretto |
| **commodities** | 11.0% | 0.003 | 3.5% | 90% | Molto ampio |
| **oro_metalli_preziosi** | 8.0% | 0.005 | 3.0% | 93% | Ampio |
| **metalli_industriali** | 9.0% | 0.004 | 3.0% | 92% | Ampio |
| **real_estate_reit** | 5.5% | 0.006 | 2.5% | 95% | Stretto |
| **crypto_digital_assets** | 18.0% | 0.002 | 5.0% | 84% | Massimamente ampio |
| **leva_single_stock** | 11.0% | 0.005 | 2.5% | 91% | Molto ampio |
| **private_equity_buffer** | 5.5% | 0.006 | 2.5% | 95% | Stretto |
| **monetario_liquidita** | 2.0% | 0.02 | 0.5% | 98.5% | Ultra-conservativo |

**Esempi pratici** (Entry €100, usando equity_sviluppati):

| Guadagno | excess_gain | distance | SL_percent | SL_price |
|:---:|:---:|:---:|:---:|:---:|
| 0% | 0% | 8.0% (base) | 92% | €92.00 |
| +3% | 0% | 8.0% (base) | 92% | €92.00 |
| +5% | +2% | 7.9% (8.0 - 2×0.5%) | 92.1% | €92.10 |
| +8% | +5% | 7.75% (8.0 - 5×0.5%) | 92.25% | €92.25 |
| +15% | +12% | 7.4% (8.0 - 12×0.5%) | 92.6% | €92.60 |
| +25% | +22% | 6.9% → **94%** floor | **94%** | **€94.00** |

**Vantaggi formula continua**:
- Nessun salto rigido — il SL si muove fluidamente con il prezzo
- Immune al noise di mercato (±0.1% non attiva/disattiva)
- Protect base per CDA e monetario (trailing_min_pct garantito)
- Ogni giorno il monitor recalcola con il prezzo attuale

---

## Stop Loss L1 Ibrido — Formula Parametrizzata (STEP 2 — 2026-07-09)

Alla entry di una posizione L1, il stop loss iniziale segue una **logica ibrida** che distingue tra phase di accumulazione e take-profit.

**Regola ibrida**:

1. **Se profitto corrente < 2%** (accumulation phase):
   ```
   SL = EMA20 × (1 − sl_buffer_wide)
   ```
   Mantiene il SL più largo per evitare uscite premature.
   
2. **Se profitto corrente ≥ 2%** (profit protection phase):
   ```
   SL = EMA20 × 0.99  (tight 1%)
   ```
   Stringe il SL per proteggere i guadagni già accumulati.

**Parametro `sl_buffer_wide` per famiglia** (vedi tabella profili colonna "sl_buffer"):

| Famiglia | sl_buffer_wide | Entry €100 / Gain 0% | Entry €100 / Gain +3% |
|----------|:---:|:---:|:---:|
| **bond_governativi** | 1.0% | SL €99.00 | SL €99.00 (tight) |
| **settoriali_difensivi** | 1.5% | SL €98.50 | SL €99.00 (tight) |
| **real_estate_reit** | 2.0% | SL €98.00 | SL €99.00 (tight) |
| **equity_sviluppati** | 2.0% | SL €98.00 | SL €99.00 (tight) |
| **bond_corp_hy_em** | 1.5% | SL €98.50 | SL €99.00 (tight) |
| **oro_metalli_preziosi** | 2.5% | SL €97.50 | SL €99.00 (tight) |
| **metalli_industriali** | 2.5% | SL €97.50 | SL €99.00 (tight) |
| **mercati_emergenti** | 2.5% | SL €97.50 | SL €99.00 (tight) |
| **settoriali_growth** | 3.0% | SL €97.00 | SL €99.00 (tight) |
| **commodities** | 3.0% | SL €97.00 | SL €99.00 (tight) |
| **leva_single_stock** | 4.0% | SL €96.00 | SL €99.00 (tight) |
| **crypto_digital_assets** | 5.0% | SL €95.00 | SL €99.00 (tight) |
| **private_equity_buffer** | 1.5% | SL €98.50 | SL €99.00 (tight) |
| **monetario_liquidita** | 0.5% | SL €99.50 | SL €99.00 (tight) |

**Implementazione nel codice**:
- `technical_analysis.py::calculate_stop_loss()` legge `sl_buffer_wide` dal profilo famiglia
- Calcola il profitto corrente: `current_gain_pct = (current_price - entry_price) / entry_price`
- Se `current_gain_pct < 0.02`: applica formula wide (buffer)
- Se `current_gain_pct >= 0.02`: applica formula tight (1%)
- Risultato salvato in DB come `stop_loss_suggested` per il portafoglio

---

## EMAIL GIORNALIERA (19:30 CEST)

**Struttura** (separazione Portafoglio vs Nuovi Segnali):

```
📊 ETF Monitor | Portafoglio Giornaliero | DD/MM/AAAA

── PORTAFOGLIO L1 (In Posizione) ──────────────────
[Tabella: ETF in portafoglio, entry_price, current_price, perf%, entry_mode]

── NUOVI SEGNALI L1 (Valuta Acquisto) ─────────────
[Tabella: ETF con gerarchia 2+2, gate A∧M, velocity, size confidence]

── L0 DEEP RECOVERY (In Posizione) ────────────────
[Elenco ETF con drawdown, RSI, giorni dalla entry]
```

**entry_mode** (per ogni posizione):
- `ACCELERATED`: gerarchia 2+2 (gate 2/2 + velocity 2-4/4)
- `TIERED`: logica precedente (solo riferimento, deprecated)
- `NONE`: non eligibile

---

## Note operative

- `docker compose` (senza trattino) su Ubuntu 24.04
- **CRITICO**: dopo `docker cp` su file `.py` → sempre `docker restart etf_monitor_system-app-1`
- Il monitor modifica `etf_monitoraggio.xlsx` in-place → `git reset --hard` lo sovrascrive → il `deploy.sh` gestisce il backup automatico
- Ticker Yahoo Finance: formato `SWDA.L`, `ENRJ.PA`, `XEON.DE` ecc.
- Per trovare ticker dato ISIN: `https://query1.finance.yahoo.com/v1/finance/search?q={ISIN}`
- **240 ETF monitorati** (aggiornato 2026-07-15)
