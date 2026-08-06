---
name: equity_bond_correlation_strategy
description: "Risk-On/Risk-Off dynamics, signal interpretation, Corr90 metric, and allocation strategy for multi-family monitor"
metadata: 
  node_type: memory
  type: project
  originSessionId: 858cce53-2f4c-4185-8369-67ab5f8a8c87
---

# Equity-Bond Correlation Strategy & Risk-On/Risk-Off Dynamics

## Thesis
Azionari e obbligazionari hanno storicamente correlazione inversa: quando l'azionario sale, l'obbligazionario tende a scendere (e viceversa). Tuttavia, questa non è una legge assoluta — il 2022 ha mostrato entrambi crollare insieme. La chiave è riconoscere qual è il regime in corso (Risk-On vs Risk-Off) e leggere i segnali quantitativi dal monitor stesso, non indovinare dalla macroeconomia.

## Dinamiche Fondamentali

### Risk-On Phase (Propensione al rischio)
- Economia cresce, aziende fanno utili
- Investitori vendono bond (rendono meno), comprano azioni (rendono di più)
- **Risultato**: ETF Azionari ⬆️, ETF Obbligazionari ⬇️
- I tassi salgono lentamente (segnale di crescita)

### Risk-Off Phase (Fuga dal rischio)
- Aria di recessione, tensioni geopolitiche, crolli di borsa
- Investitori scappano dalle azioni, si rifugiano nei Titoli di Stato (asset sicuri)
- **Risultato**: ETF Azionari ⬇️, ETF Obbligazionari ⬆️
- I tassi crollano (banche centrali tagliano per stimolare)

### The Critical Factor: Interest Rates
- **Rialzo tassi** → prezzi bond scendono (vecchi coupon meno attraenti) → ETF Obbligazionari ⬇️
- **Taglio tassi** → prezzi bond salgono (vecchi coupon diventano preziosi) → ETF Obbligazionari ⬆️

**Problema 2022**: Sia azionari che obbligazionari crollati insieme perché la Fed alzava i tassi aggressivamente per combattere l'inflazione (entrambi pesati negativamente).

## Segnali Quantitativi da Cogliere nel Monitor

### 🟢 Entrare SOLO su Azionario (Equity-Only Regime)
Perfetto Risk-On. Preferire equity quando:

| Segnale | Logica |
|---------|--------|
| **Regime Azionario = BULL** | Prezzo > EMA20 > SMA50 della famiglia |
| **ADX Azionario > 20–25** | Trend rialzista ha forza e volumi stabili |
| **Regime Obbligazionario = LATERALE o BEAR** | Bond NON stanno salendo |
| **Segnale azione** | Se una famiglia Equity ha 6/6 condizioni L1 e il Regime Bond non è BULL, entrare in Equity |

### 🔵 Entrare SOLO su Obbligazionario (Bond-Only Regime)
Perfetto Risk-Off o inversione tassi. Preferire bond quando:

| Segnale | Logica |
|---------|--------|
| **Regime Azionario = BEAR o LATERALE forte** | Trend azionario collassa o stagna |
| **APRDXM azionario < 4/6** | Score azionario scende drasticamente |
| **Regime Bond Governativi = BULL** | Bond iniziano il rialzo |
| **ADX Bond > 12–15** | Movimento bond sostenuto (è basso per natura) |
| **Segnale azione** | Se Bond ha 6/6 e Azionario è in BEAR, entrare solo in Bond |

### 🟡 Segnale d'Allarme (Correlazione Positiva Anormale)
Se **entrambi** Azionario E Obbligazionario scendono simultaneamente con ADX alto:

- Significa: **Paura d'inflazione + rialzo tassi simultaneo** (come Feb-Mar 2022)
- Nessuno dei due è sicuro
- **Unico porto sicuro**: Monetario / Liquidità (es. XEON, short-term money market)
- Azione: Demote Equity a L3, demote Bond a L3, mantieni L1 solo per Monetario

## Metrica Futura: Corr90 (Correlazione Rolling 90 Giorni)

**Da implementare in risk.py** una volta completato il refactor Phase 4.

```python
corr = rolling_corr(ETF_Azionario_Globale, ETF_Obbligazionario, window=90)
```

Interpreti:

| Corr90 | Regime | Interpretazione | Azione |
|--------|--------|-----------------|--------|
| **−0.5 a −0.8** | Correlazione inversa forte | Portfolio perfettamente diversificato; azionario ⬇️ = bond ⬆️ compensano | OK comprare entrambi se L1 singolarmente |
| **−0.2 a +0.2** | Indipendenti | Due mercati si muovono per ragioni diverse | OK comprare entrambi se L1 singolarmente |
| **+0.5 a +0.8** | Correlazione positiva | Stanno salendo/scendendo insieme — no diversificazione | ⚠️ Attenti: se uno crolla, crolla anche l'altro |

## Strategia Operativa nel Tuo Sistema

**Non scegliere a priori quale famiglia comprare.** Lascia che l'algoritmo lo decida automaticamente:

1. **Ogni famiglia ha regime 3-stati (BULL/LATERALE/BEAR)** e score APRDXM (0–6 condizioni L1)
2. **Il monitor esegue quotidianamente**: calcola regime di Equity, regime di Bond, regime di Commodity
3. **Promozione/demote automatica**:
   - Se Equity → BULL e Bond → BEAR: L1 per Equity, L3 per Bond
   - Se Equity → BEAR e Bond → BULL: L3 per Equity, L1 per Bond
   - Se entrambi → BEAR: L3 per entrambi, L1 solo per Monetario
4. **Diversificazione automatica**: Il portfolio si ribilancia in base ai regimi in tempo reale, non su decisioni manuali

**Vantaggio**: Elimini il rischio di "scegliere male" — è il mercato stesso che te lo dice tramite i tuoi indicatori parametrici.

## Come Memorizzare Domani

Ricorda con: **"Risk-On/Risk-Off e Corr90"** — questa guida contiene tutta la strategia di quando stare su Equity vs Bond.

**Next step** (Phase 4): Implementare Corr90 in `risk.py` e usarla come filtro aggiuntivo nelle decisioni di allocazione multi-famiglia.
