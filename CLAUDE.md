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

### L1 — Core Portfolio — 6 condizioni TUTTE obbligatorie
| # | Condizione | Logica |
|---|-----------|--------|
| 1 | Allineamento | price > EMA20 > SMA50 (+ price > SMA200 se mm200_filter=True) |
| 2 | Persistenza | days_above_EMA20 ≥ 3 AND slope(EMA20) > 0 |
| 3 | RSI ottimale | rsi_entry_low ≤ RSI ≤ rsi_entry_high (per tipo ETF) |
| 4 | Distanza EMA20 | 0% ≤ dist_EMA20 ≤ ema_dist_max |
| 5 | ADX | ADX ≥ adx_entry |
| 6 | MACD momentum | macd_h > 0 AND (macd_h > macd_h_prev OR dist_EMA20 < 2.0%) |

### Uscita L1 — 6 Regole
| Pri | Regola | Trigger |
|:---:|--------|---------|
| 1 | F Kill Switch | Calo giornaliero ≤ −3% |
| 2 | A Stop Loss | Prezzo sotto EMA20 da ≥ 3 giorni |
| 3 | B Trailing Stop | EMA10 < EMA20 |
| 4 | C Stanchezza | RSI_prev ≥ 70 AND RSI_oggi < 70 (non-bond) |
| 5 | E ADX debole | ADX < 18 AND prezzo < EMA20 |
| 6 | D Uscita Parziale | RSI > 78 → vendi 90%, mantieni 10% + acquista XEON |

### Profili parametri FAMIGLIE ETF — 14 Classi (aggiornato 2026-07-14)

> **FONTE AUTOREVOLE**: `config/etf_families.yaml` — questa tabella è sincronizzata al YAML. Qualsiasi modifica ai parametri DEVE essere applicata contemporaneamente qui.

| Famiglia | RSI entry | ADX | days_ema | min_buy | ema_dist_max | l0_dd % | sl_buffer | sg_target | sg_floor | sg_decay | sg_rsi |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **equity_sviluppati** | 45–55 | 22 | 5 | 5 | 4.0% | 15% | 2.0% | 4.0% | 2.0% | 0.002 | 65 |
| **mercati_emergenti** | 40–52 | 22 | 3 | 6 | 5.0% | 20% | 2.5% | 5.0% | 2.5% | 0.002 | 65 |
| **settoriali_growth** | 48–58 | 25 | 5 | 5 | 5.0% | 18% | 3.0% | 7.0% | 3.5% | 0.002 | 65 |
| **settoriali_difensivi** | 42–50 | 18 | 5 | 5 | 2.5% | 15% | 1.5% | 3.0% | 1.5% | 0.002 | 65 |
| **bond_governativi** | 38–48 | 12 | 3 | 5 | 1.5% | 8% | 1.0% | 2.0% | 1.0% | 0.001 | 65 |
| **bond_corp_hy_em** | 42–52 | 15 | 3 | 5 | 2.0% | 10% | 1.5% | 3.0% | 1.5% | 0.001 | 65 |
| **commodities** | 40–55 | 22 | 3 | 6 | 3.0% | 20% | 3.0% | 6.0% | 3.0% | 0.002 | 65 |
| **oro_metalli_preziosi** | 38–52 | 18 | 3 | 5 | 2.5% | 15% | 2.5% | 5.0% | 2.5% | 0.002 | 65 |
| **metalli_industriali** | 38–50 | 20 | 3 | 5 | 3.0% | 18% | 2.5% | 5.0% | 2.5% | 0.002 | 65 |
| **real_estate_reit** | 42–52 | 15 | 3 | 5 | 2.0% | 12% | 2.0% | 4.0% | 2.0% | 0.001 | 65 |
| **crypto_digital_assets** | 35–52 | 28 | 3 | 5 | 6.0% | 25% | 5.0% | 12.0% | 6.0% | 0.003 | 65 |
| **leva_single_stock** | 45–58 | 28 | 3 | 5 | 4.0% | 20% | 4.0% | 15.0% | 7.5% | 0.003 | 65 |
| **private_equity_buffer** | 40–55 | 15 | 3 | 5 | 2.5% | 15% | 1.5% | 3.0% | 1.5% | 0.001 | 65 |
| **monetario_liquidita** | n/a | n/a | 3 | 6 | 0.5% | n/a | 0.5% | 0.5% | 0.2% | 0.0 | 97 |

**Legenda colonne**:
- **RSI entry**: range RSI per triggering L1
- **ADX**: soglia ADX minima per L1 (null = non applicabile)
- **days_ema**: giorni consecutivi sopra EMA20 richiesti
- **min_buy**: numero minimo condizioni 6/6 da soddisfare (non usato, sempre 6)
- **ema_dist_max**: distanza massima da EMA20 in percentuale
- **l0_dd %**: drawdown minimo per attivare L0 (null = no L0)
- **sl_buffer**: distanza buffer stop-loss iniziale (STEP 2 — ibrido)
- **sg_target**: stop-gain target (STEP 2)
- **sg_floor**: stop-gain floor minimo (STEP 2)
- **sg_decay**: decadimento giornaliero SG (STEP 2)
- **sg_rsi**: RSI exit per stop-gain (STEP 2)

### Struttura L0 Entry — Parametri per famiglia (Nuovi 2026-07-14)

Ogni famiglia ETF ha parametri specifici per triggerare l'entrata in L0 (deep recovery):

| Famiglia | enabled | dd_threshold | rsi_max | lookback_days | recovery_min % | Note |
|----------|:---:|:---:|:---:|:---:|:---:|------|
| **equity_sviluppati** | ✓ | 6.5% | 45 | 3 | 1.5% | Deep value — trigger conservativo |
| **mercati_emergenti** | ✓ | 8.5% | 42 | 3 | 2.0% | Volatilità moderata |
| **settoriali_growth** | ✓ | 10.0% | 42 | 2 | 2.5% | Tech/AI — drawdown ampio |
| **settoriali_difensivi** | ✓ | 5.0% | 48 | 3 | 1.0% | Defensive — trigger stretto |
| **bond_governativi** | ✓ | 4.0% | 42 | 5 | 0.8% | Gov bonds — protezione massima |
| **bond_corp_hy_em** | ✓ | 5.5% | 44 | 3 | 1.2% | Corp bonds — moderato |
| **commodities** | ✓ | 10.0% | 40 | 3 | 2.5% | Commodity — drawdown ampio |
| **oro_metalli_preziosi** | ✓ | 8.0% | 42 | 3 | 2.0% | PM — volatilità commodity |
| **metalli_industriali** | ✓ | 8.0% | 42 | 3 | 2.0% | Battery metals — moderato |
| **real_estate_reit** | ✓ | 7.0% | 44 | 3 | 1.5% | REIT — dividend safe |
| **crypto_digital_assets** | ✓ | 25.0% | 38 | 2 | 5.0% | Crypto — drawdown estremo |
| **leva_single_stock** | ✗ | n/a | n/a | n/a | n/a | Disabilitato — troppo rischioso per deep recovery |
| **private_equity_buffer** | ✓ | 7.0% | 42 | 3 | 1.5% | Listed PE — conservative |
| **monetario_liquidita** | ✗ | n/a | n/a | n/a | n/a | Disabilitato — no logica recovery |

**Legenda L0 entry**:
- **enabled**: se true, l'ETF è candidato per L0; false disabilita completamente
- **dd_threshold**: drawdown minimo (% sotto picco storico) per attivare L0
- **rsi_max**: soglia RSI massima per ipervenduto (triggering L0)
- **lookback_days**: giorni di lookback per verificare il divergenza rialzista
- **recovery_min %**: minimo recupero richiesto per confermare ingresso L0

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

## Note operative

- `docker compose` (senza trattino) su Ubuntu 24.04
- **CRITICO**: dopo `docker cp` su file `.py` → sempre `docker restart etf_monitor_system-app-1`
- Il monitor modifica `etf_monitoraggio.xlsx` in-place → `git reset --hard` lo sovrascrive → il `deploy.sh` gestisce il backup automatico
- Ticker Yahoo Finance: formato `SWDA.L`, `ENRJ.PA`, `XEON.DE` ecc.
- Per trovare ticker dato ISIN: `https://query1.finance.yahoo.com/v1/finance/search?q={ISIN}`
- **214 ETF monitorati** (aggiornato 22/05/2026)
