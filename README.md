# ETF Monitor System

Sistema automatizzato di monitoraggio ETF a 4 livelli con alert email e dashboard web.

Dashboard: **https://etf.andreapavan.tech**

---

## Infrastruttura

- **VPS**: Hostinger Ubuntu 24.04 LTS — `76.13.37.133`
- **Container Docker**: `etf_monitor_system-app-1` → porta 5001
- **Database**: PostgreSQL in Docker (user: `etfmonitor`, db: `etfs`)
- **Reverse proxy**: Nginx + Cloudflare (SSL Full strict)
- **Email**: Resend API (`onboarding@resend.dev`)
- **Dati prezzi**: Yahoo Finance OHLCV (ticker formato `SWDA.L`, `ENRJ.PA`, ecc.)

---

## Deploy

```bash
./deploy.sh
```

Fa in sequenza: `git push` → SSH backup Excel VPS → git reset → smart_restore livelli → docker build → docker up → trigger monitor.

> `smart_restore.py` preserva la colonna Livello dall'Excel VPS durante il reset git, evitando di perdere i livelli aggiornati dal monitor.

---

## Struttura file

```
├── app.py                  # Flask API + serving dashboard
├── monitor.py              # Logica principale: fetch OHLCV, calcolo livelli
├── technical_analysis.py   # Indicatori: EMA20, SMA50, SMA200, ADX14, RSI14, MACD
├── data_fetcher.py         # Fetch OHLCV da Yahoo Finance
├── database.py             # Wrapper PostgreSQL
├── scheduler.py            # Scheduler: 17:00 CEST principale, 09:00 silenzioso
├── alerts.py               # Email Resend: nuovi L1/L0, uscite, stop loss
├── dashboard.html          # Frontend SPA
├── etf_monitoraggio.xlsx   # Excel master — fonte di verità per lista ETF
├── smart_restore.py        # Preserva colonna Livello durante deploy
├── deploy.sh               # Script deploy completo
├── docker-compose.yml
├── portfolio_analysis.py   # Analisi portafoglio personale (vedi sotto)
├── analisi_portafoglio.sh  # Launcher Mac analisi portafoglio
├── analisi_portafoglio.bat # Launcher Windows analisi portafoglio
└── portafogli/             # XLS banca + report HTML (gitignored)
```

---

## Livelli

| Livello | Nome | Descrizione |
|---------|------|-------------|
| **L3** | Universe | Tutti gli ETF — monitoraggio passivo |
| **L2** | Watchlist | Prezzo sopra EMA20 da ≥3 giorni, o EMA20 > SMA50 |
| **L1** | Core Portfolio | 6 condizioni tecniche tutte soddisfatte — trend confermato |
| **L0** | Deep Recovery | ETF in forte calo (≥8–20% dal picco) con segnali di rimbalzo |

### Condizioni entrata L1 (tutte obbligatorie)
1. **Allineamento**: price > EMA20 > SMA50 (+ price > SMA200 se attivo per asset class)
2. **Persistenza**: days_above_EMA20 ≥ 3 e slope EMA20 > 0
3. **RSI ottimale**: range dipende da asset class (es. equity 50–70, bond 48–62)
4. **Distanza EMA20** ≤ soglia (equity 4%, sector 5%, bond 2%)
5. **ADX** ≥ soglia (equity 20, sector/commodity 22, bond 15)
6. **MACD momentum**: macd_h > 0 e (macd_h > macd_h_prev o dist < 2%)

### Uscita L1 — 6 regole (in ordine di priorità)
| # | Regola | Trigger |
|---|--------|---------|
| F | Kill Switch | Calo giornaliero ≤ −3% |
| A | Stop Loss | Prezzo sotto EMA20 da ≥ 3 giorni |
| B | Trailing Stop | EMA10 < EMA20 |
| C | Stanchezza | RSI_prev ≥ 70 e RSI oggi < 70 (non-bond) |
| E | ADX debole | ADX < 18 e prezzo < EMA20 |
| D | Uscita Parziale | RSI > 78 → vendi 90%, mantieni 10% + acquista XEON |

---

## Analisi portafoglio personale

Script giornaliero indipendente che legge l'estratto XLS dalla banca e genera un report operativo.

### Workflow
1. Scarica XLS dalla banca → copia in `portafogli/`
2. Mac: `./analisi_portafoglio.sh` — Windows: doppio click su `analisi_portafoglio.bat`

### Output
- **Report HTML** aperto automaticamente nel browser
- **Digest email** con P&L totale, segnali ETF, stop loss
- **Grafico storico** valore portafoglio (SVG inline, si accumula giorno per giorno)
- **Watchlist top-5** ETF già in L1 nel monitor, non ancora in portafoglio

### File locali richiesti
`.env` nella cartella `etf_monitor_system/` (gitignored — va creato a mano):
```
RESEND_API_KEY=...
EMAIL_RECIPIENT=andreapavan67@gmail.com
EMAIL_SENDER=onboarding@resend.dev
```

---

## Comandi rapidi

```bash
# Log live
ssh root@76.13.37.133 "docker logs etf_monitor_system-app-1 --tail=50 -f"

# Trigger monitor manuale
ssh root@76.13.37.133 "curl -s -X POST http://localhost:5001/api/trigger-update"

# Query DB
ssh root@76.13.37.133 "docker exec etf_monitor_system-postgres-1 psql -U etfmonitor -d etfs -c '<SQL>'"

# Git pull VPS (il monitor modifica xlsx — scartare prima)
ssh root@76.13.37.133 "cd /root/etf_monitor_system && git checkout -- etf_monitoraggio.xlsx && git pull origin main"
```

---

> I segnali sono informativi, non consulenza finanziaria.
