---
name: bug_l0_missing_july_16
description: "4 ETF L0 (KRW.PA, CC1.PA, PHAG.MI, INRG.MI) disappeared after deploy — data fetching issue"
metadata: 
  node_type: memory
  type: project
  status: OPEN
  discovered: 2026-07-16
  impact: HIGH
  originSessionId: ae0867eb-de7e-46f3-9b31-3785a4e8b296
---

# BUG: L0 ETF Spariti dopo Deploy (2026-07-16)

## Sintomi
- 4 ETF erano in L0 su 2026-07-15: KRW.PA, CC1.PA, PHAG.MI, INRG.MI
- Dopo deploy ed ricalcolo monitor: L0 count = 0
- Database `etf_l0_tracking` è vuoto

## Root Cause
**I 4 ETF non hanno dati di prezzo per 2026-07-15 nel database.**

```sql
SELECT ticker, date, close FROM etf_price_history 
WHERE date = '2026-07-15' 
AND ticker IN ('KRW.PA', 'CC1.PA', 'PHAG.MI', 'INRG.MI');
-- Result: 0 rows
```

Mentre altri 211 ETF hanno dati per 2026-07-15, questi 4 **non vengono fetchati** da Yahoo Finance:
- **KRW.PA** — Amundi MSCI Korea (potrebbe non essere disponibile)
- **CC1.PA** — China Tech (potrebbe non essere disponibile)
- **PHAG.MI** — WisdomTree Silver (ticker Milano Borsa, non Yahoo)
- **INRG.MI** — iShares Clean Energy (potrebbe avere ISIN mismatch)

## Ipotesi
1. **Ticker non validi su Yahoo Finance** — es. tickers Milano Borsa (.MI, .PA) non sono tutti su Yahoo
2. **Problema data_fetcher.py** — non riesce a recuperare dati per questi ticker specifici
3. **ETF Directa/MTA** — alcuni ETF sono solo su piattaforme italiane, non su Yahoo Finance

## Impatto
- L0 portfolio perde tracking su questi 4 ETF
- Nessuna email di alert per deep recovery
- Profitti potenziali persi se si recuperano

## Fix Richiesto
1. Verificare i ticker corretti su Yahoo Finance (https://query1.finance.yahoo.com/v1/finance/search?q=ISIN)
2. Se ticker non su Yahoo, usare API alternativa (FT Markets, Investing.com)
3. Aggiornare Excel con ticker corretti
4. Ricalcolare L0 al prossimo monitor ciclo
