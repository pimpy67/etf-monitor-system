---
name: directa_etf_procedure
description: Procedura corretta per aggiungere ETF Directa al monitor
metadata: 
  node_type: memory
  type: reference
  date: 2026-07-07
  status: ✅ DEFINITO
  originSessionId: c74b19e0-7264-4b9a-a514-edc7242ac1fd
---

# Procedura Aggiunta ETF Directa al Monitor

## ⚠️ REGOLA CRITICA

**QUANDO COMPRI UN ETF IN DIRECTA E LO VUOI AGGIUNGERE AL MONITOR:**

```
❌ NON fare:
   "Aggiungi WAT"

✅ FARE:
   "Aggiungi WAT.MI (o il ticker COMPLETO come appare in Directa)"
```

## Perché?

**Problema**: Ticker abbreviato vs ticker completo
```
Directa mostra: "WAT"  ← abbreviato
Ma su Yahoo Finance ci sono 4 versioni diverse:
  - WAT        = €376.89 ❌ SBAGLIATO (indice generico)
  - WAT.MI     = €70.45  ✅ GIUSTO (Milano - Borsa Italiana)
  - WAT.PA     = €70.29  ✅ GIUSTO (Parigi - Euronext)
  - WAT.DE     = €70.93  ✅ GIUSTO (Francoforte - XETRA)
```

**Soluzione**: Dare il ticker COMPLETO così il sistema sa quale scaricare!

## Procedura Standard

```
1️⃣  Tu: "Voglio aggiungere un ETF Directa: [NOME ETF] (ISIN: [ISIN])"

2️⃣  Io chiedo: "Qual è il ticker COMPLETO come appare in Directa?"
    (Includi il suffisso della borsa: .MI, .PA, .DE, .L, etc.)

3️⃣  Tu: "È [TICKER.SUFFISSO]" (es. "WAT.MI")

4️⃣  Io verifico su Yahoo Finance:
    - ✅ Se esiste [TICKER.SUFFISSO] → Aggiungo al monitor
    - ❌ Se non esiste → Provo altri formati
    - ❌ Se niente funziona → Fallback Investing.com scraping

5️⃣  Monitor scarica il prezzo dal ticker giusto giornalmente
```

## Esempio Pratico

**WAT (Amundi MSCI Water UCITS ETF Dist)**

```
ISIN: FR0010527275

❌ Sbagliato:
   Io aggiungo "WAT"
   Yahoo ritorna €376.89 ← SBAGLIATO

✅ Giusto:
   Tu mi dici "WAT.MI"
   Io aggiungo WAT.MI
   Yahoo ritorna €70.45 ← GIUSTO (Directa)
```

## Borsa Italiana vs Altre Borse

**Quando compri in Directa, di solito è:**
- **Borsa Italiana** → suffisso `.MI`
- Es: `WAT.MI`, `USHYC.MI`, ecc.

Ma verifica sempre in Directa il ticker completo!

## ETF Directa Registrati

| ETF | ISIN | Ticker Directa | Yahoo | Status |
|-----|------|---|---|---|
| Amundi MSCI Water | FR0010527275 | WAT.MI | ✅ WAT.MI | Live |
| Amundi USD HY Corp Bond | LU1435356065 | USHYC | ❌ Yahoo | Investing.com |

## Next Time

**Quando aggiungi un ETF Directa, dammi SEMPRE:**
1. Nome ETF
2. ISIN
3. **Ticker COMPLETO come appare in Directa** (con suffisso borsa)

Così il sistema sa esattamente dove scaricare il prezzo! ✅
