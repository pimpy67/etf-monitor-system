# ETF Monitor System

Sistema automatizzato di monitoraggio ETF a 4 livelli con logica di entrata gerarchica (Gate 2/2 + Velocity 2+/4), alert email giornalieri, dashboard web real-time, e tracking portafoglio con stop loss dinamico.

**Dashboard**: https://etf.andreapavan.tech | **ETF monitorati**: 240 | **Monitor**: 18:30 CEST (+ 09:00 silenzioso lun-ven)

---

## 🏗️ Architettura

**Monolithic Flask app** — Backend + Frontend in un'unica app containerizzata.

```
┌─────────────────────────────────────────────────────────────┐
│               ETF MONITOR SYSTEM (Flask)                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  🔵 BACKEND (Python — ~9,500 righe)                         │
│  ├─ app.py (1,186 righe)           Flask API + routing     │
│  ├─ monitor.py (1,333 righe)       Fetch OHLCV + Calcolo L0/L1/L2/L3
│  ├─ technical_analysis.py (1,952)  EMA20, SMA50, ADX, RSI, MACD
│  ├─ database.py (1,143 righe)      PostgreSQL wrapper      │
│  ├─ portfolio_analysis.py (1,740)  SL dinamico, metriche   │
│  ├─ scheduler.py (214 righe)       Job scheduler (cron)    │
│  ├─ data_fetcher.py (241 righe)    Yahoo Finance client    │
│  ├─ alerts.py (595 righe)          Email Resend digest     │
│  ├─ pdf_generator.py (308 righe)   PDF parametri (auto-gen)│
│  └─ risk.py (292 righe)            Risk metrics            │
│                                                               │
│  🟢 FRONTEND (HTML + JavaScript — 2,530 righe)             │
│  └─ dashboard.html (138.6 KB)      SPA completa            │
│     ├─ Tab: L1, L2, L3, L0         Dashboard trading       │
│     ├─ Tab: Portafoglio            Tracking posizioni      │
│     ├─ Tab: Parametri              YAML dinamico           │
│     ├─ Fetch /api/* endpoints      Real-time updates       │
│     └─ Grafici, filtri, export     UI interattiva          │
│                                                               │
│  🟡 CONFIG & DATA                                           │
│  ├─ config/etf_families.yaml       Parametri famiglie ETF  │
│  ├─ etf_monitoraggio.xlsx          Source of truth         │
│  ├─ data/dashboard_data.json       Cache dati (15 min)     │
│  ├─ data/isin_mapping.json         ISIN ↔ Ticker mapping   │
│  └─ docker-compose.yml             PostgreSQL + App        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Flusso Richiesta

```
Browser (https://etf.andreapavan.tech/)
   ↓
Nginx (reverse proxy, port 5001)
   ↓
Flask app.py
   ├─ GET / → Serve dashboard.html (SPA)
   └─ GET /api/* → JSON endpoints
      ├─ /api/etf-data               (L0/L1/L2/L3 counts)
      ├─ /api/l1-tracking            (posizioni portafoglio)
      ├─ /api/parameters             (YAML dinamico)
      ├─ /api/trigger-update         (monitor manuale)
      └─ ...

dashboard.html (JavaScript)
   ├─ Fetch /api/etf-data ogni 60s
   ├─ Render tab dinamici
   └─ Real-time updates
```

---

## 📋 Infrastruttura

| Componente | Dettagli |
|-----------|----------|
| **VPS** | Hostinger Ubuntu 24.04 LTS — `76.13.37.133` |
| **Container** | `etf_monitor_system-app-1` → porta 5001 |
| **Database** | PostgreSQL in Docker (user: `etfmonitor`, db: `etfs`) |
| **Reverse proxy** | Nginx `/etc/nginx/sites-enabled/etf` → port 5001 |
| **SSL** | Let's Encrypt + Cloudflare Full (strict) |
| **Email** | Resend API (`onboarding@resend.dev`) — API key in `.env` |
| **Dati prezzi** | Yahoo Finance OHLCV (formato ticker: `SWDA.L`, `ENRJ.PA`, ecc.) |
| **Scheduling** | 18:30 CEST (principale) + 09:00 CEST lun-ven (silenzioso) |

---

## 📂 Struttura Codice

```
.
├── app.py                      # Flask API server + routing
├── monitor.py                  # Fetch OHLCV + calcolo livelli
├── technical_analysis.py       # Indicatori tecnici (core logic)
├── database.py                 # PostgreSQL wrapper
├── data_fetcher.py             # Yahoo Finance client
├── scheduler.py                # APScheduler (cron jobs)
├── alerts.py                   # Email Resend (digest)
├── pdf_generator.py            # PDF parametri (auto-gen da YAML)
├── portfolio_analysis.py       # Tracking portafoglio + SL dinamico
├── risk.py                     # Risk metrics
├── smart_restore.py            # Preserva livelli durante deploy
│
├── dashboard.html              # SPA frontend (HTML + JS inline)
├── etf_monitoraggio.xlsx       # Master list ETF (source of truth)
│
├── config/
│   └── etf_families.yaml       # Parametri per 15 famiglie ETF
├── data/
│   ├── dashboard_data.json     # Cache dati (aggiornato ogni monitor)
│   └── isin_mapping.json       # ISIN ↔ Ticker mapping
├── portafogli/
│   ├── portfolio_history.json  # Storico portafoglio (7 entries)
│   └── stop_loss_history.json  # Storico SL
│
├── docker-compose.yml          # PostgreSQL + App services
├── Dockerfile                  # Image build
├── .env                        # Secrets (gitignored)
├── requirements.txt            # Python dependencies
└── deploy.sh                   # Deploy script completo
```

---

## 🚀 Deploy

```bash
./deploy.sh
```

**Workflow**:
1. `git add -A && git commit && git push origin main` (se ci sono modifiche)
2. SSH VPS: backup `etf_monitoraggio.xlsx` → `git reset --hard origin/main`
3. SSH VPS: ripristina `etf_monitoraggio.xlsx` (preserva livelli aggiornati)
4. SSH VPS: `docker compose build app`
5. SSH VPS: `docker compose up -d --force-recreate app`
6. Trigger manuale monitor (carica dati iniziali)

> **Smart restore**: `smart_restore.py` preserva la colonna Livello dell'Excel locale durante il reset git, evitando di perdere i livelli aggiornati dal monitor.

---

## 📊 Schema Livelli

| Livello | Nome | Descrizione |
|---------|------|-------------|
| **L3** | Universe | Tutti i 240 ETF — monitoraggio passivo |
| **L2** | Watchlist | ETF con momentum ma non ancora confermati |
| **L1** | Core Portfolio | Trend confermato — logica gerarchia 2+2 |
| **L0** | Deep Recovery | ETF in calo forte (8–20% dal picco) con segnali rimbalzo |

### L1 — Entrata: gate rigido a 7 condizioni (dal 22/07/2026, `min_buy_count: 7` per tutte le famiglie)

| # | Condizione | Logica |
|---|-----------|--------|
| 1 | Allineamento | `price > EMA20 > SMA50` (+ SMA200 se `mm200_filter`) — puramente geometrico |
| 2 | Persistenza | `days_above_EMA20 ≥ N` (per famiglia, oggi 3 per tutte) AND `slope(EMA20) > 0` |
| 3 | RSI ottimale | `rsi_entry_low ≤ RSI ≤ rsi_entry_high` (per famiglia) |
| 4 | Distanza EMA20 | `0% ≤ dist_EMA20 ≤ ema_dist_max` |
| 5 | ADX | `ADX ≥ adx_entry` |
| 6 | MACD momentum | `histogram > 0` AND (rising OR `dist_EMA20 < 2%`) |
| 7 | Spazio residuo | resistenza (max N gg) o ATR×mult ≥ `min_reward_pct` |

Se **una sola** è FALSE → bloccato (L2). Poi le **fondamenta**: regime BULL (`(EMA20−SMA50)/SMA50 > lateral_band`), prezzo>SMA50, no kill switch.

> ⚠️ **"Gerarchia 2+2" (Gate A+M + Velocity P/R/D/X, sizing 60-100%) esiste ancora nel codice** (`check_l1_entry_accelerated()`, STEP 12) ma **non decide il livello reale** — viene solo calcolata e salvata come metadata (`l1_accelerated_entry` in `dashboard_data.json`). Il gate che conta oggi è quello a 7 condizioni sopra. Stesso discorso per il sistema "tiered" (`check_l1_entry_tiered()`, quality score 0-4): calcolato, non collegato a nulla.

### L1 — Uscita: due motori distinti (dashboard vs portafoglio reale)

**Dashboard** (`suggest_level()`, classifica il livello nell'universo monitorato):

| # | Regola | Trigger | Azione |
|---|--------|---------|--------|
| F | Kill Switch | Calo giornaliero ≤ −3% | Totale |
| A | Stop Loss | Prezzo < EMA20 da ≥3 gg | Totale |
| B | Trailing Stop | EMA10 < EMA20 | Totale |
| C | Stanchezza | RSI era ≥70, ora <70 | Totale (non-bond) |
| E | ADX debole | ADX < 18 + price < EMA20 | Totale |
| — | Downgrade score/regime | buy_count<7 o regime≠BULL | L1→L2 |

**Portafoglio reale** (`check_l1_exit()`, le posizioni comprate davvero in `etf_portfolio_entries`): F kill switch → **SL dinamico** → B trailing → C stanchezza → **SG dinamico** (take profit) → E ADX debole. Niente Regola A, niente downgrade per score — usa lo stop loss/gain dinamico al loro posto.

> **Fix 2026-08-04**: prima la Regola E non scattava mai (bug nomi famiglia legacy vs YAML) e il target dello Stop Gain dinamico era di fatto statico (dati mai passati alla funzione). Entrambi corretti — dettagli in `CLAUDE.md`.

**⚠️ Come funziona davvero (nessun automatismo)**: il sistema non compra/vende mai da solo. L'utente acquista manualmente gli ETF che entrano in L1, poi ogni giorno riceve via email SL e TP ricalcolati e li aggiorna manualmente su Directa. La posizione esce solo quando il prezzo tocca uno dei due a mercato. **B, C, E, F non sono vendite** — segnalano solo che l'ETF non è più un candidato per un *nuovo* acquisto, non toccano le posizioni aperte.

---

## 🔗 API Endpoints

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/` | GET | Dashboard HTML (SPA) |
| `/api/etf-data` | GET | L0/L1/L2/L3 counts + summary |
| `/api/l1-tracking` | GET | ETF in L1 (posizioni portafoglio) |
| `/api/l0-tracking` | GET | ETF in L0 (deep recovery) |
| `/api/parameters` | GET | Parametri YAML (dinamici) |
| `/api/parameters-tables-html` | GET | Tabelle parametri HTML formattate |
| `/api/download-parameters-pdf` | GET | PDF scaricabile (auto-gen da YAML) |
| `/api/trigger-update` | POST | Trigger monitor manuale |

---

## 💾 Database

**PostgreSQL** (Container: `etf_monitor_system-postgres-1`)

**Tabelle principali**:
- `etf_price_history` — Storico OHLCV giornaliero (isin, date, open, high, low, close, volume)
- `etf_l1_tracking` — ETF in L1 (entry_date, entry_price, stop_loss, etc.)
- `etf_l1_exit_history` — Storico uscite L1 (exit_date, exit_rule, pct_gain)
- `etf_l0_tracking` — ETF in L0 (entry_date, panic_low, days_in_l0)
- `portfolio_entries` — Portafoglio personale (isin, entry_date, entry_price, entry_mode)

---

## 🔧 Comandi Rapidi

```bash
# Log live container
ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 --tail=50 -f"

# Trigger monitor manuale
ssh root@76.13.37.133 "curl -s -X POST http://localhost:5001/api/trigger-update"

# Query DB
ssh root@76.13.37.133 "docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c '<SQL>'"

# Git pull VPS (scartare Excel modificato prima)
ssh root@76.13.37.133 "cd /root/etf_monitor_system && git checkout -- etf_monitoraggio.xlsx && git pull origin main"

# Stato container
ssh root@76.13.37.133 "docker ps --filter name=etf_monitor_system"
```

---

## ⚙️ Configurazione

`.env` (gitignored — va creato a mano):
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

`config/etf_families.yaml` — Parametri per 15 famiglie ETF (RSI range, ADX threshold, trailing stop, L0 drawdown, ecc.)

---

> I segnali sono informativi, non consulenza finanziaria.
