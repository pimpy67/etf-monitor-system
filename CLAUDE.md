# CLAUDE.md — ETF Monitor System

Documento di riferimento tecnico. Caricato automaticamente da Claude Code a ogni sessione.

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
       └─ alerts.py → email
```

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

### Profili parametri per tipo ETF
| Parametro | equity_developed | equity_sector | equity_emerging | commodity | bond | thematic |
|-----------|:---:|:---:|:---:|:---:|:---:|:---:|
| RSI entry range | 50–70 | 50–70 | 50–65 | 50–65 | 48–62 | 50–70 |
| Dist max EMA20 | 4% | 5% | 5% | 5% | 2% | 6% |
| ADX min | 20 | 22 | 20 | 22 | 15 | 22 |
| Giorni sopra EMA20 | 3 | 3 | 3 | 3 | 3 | 3 |
| SMA200 filter | Sì | Sì | Sì | Sì | No | Sì |

---

## Note operative

- `docker compose` (senza trattino) su Ubuntu 24.04
- **CRITICO**: dopo `docker cp` su file `.py` → sempre `docker restart etf_monitor_system-app-1`
- Il monitor modifica `etf_monitoraggio.xlsx` in-place → `git reset --hard` lo sovrascrive → il `deploy.sh` gestisce il backup automatico
- Ticker Yahoo Finance: formato `SWDA.L`, `ENRJ.PA`, `XEON.DE` ecc.
- Per trovare ticker dato ISIN: `https://query1.finance.yahoo.com/v1/finance/search?q={ISIN}`
- **214 ETF monitorati** (aggiornato 22/05/2026)
