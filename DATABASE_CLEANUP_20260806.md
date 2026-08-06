# Database Cleanup — 2026-08-06

## Problema
Dopo il deploy di L0 regime filter (regime = BULL obbligatorio), il database conteneva ancora 24 record L0 entrati il 2026-07-30 (PRIMA del fix). Il regime filter blocca i NUOVI ingressi, ma non rimuove i record PRE-ESISTENTI.

## Soluzione Applicata
```sql
DELETE FROM etf_l0_tracking WHERE entry_date < '2026-08-06';
```

**Risultato:** 24 record eliminati
- Erano ETF entrati in L0 durante regime BEAR (7-30)
- Bloccati dall'odierno regime filter
- Rimossi dal tracking database

## Verifica Post-Cleanup
- ✅ L0 count: 24 → 0
- ✅ Regime filter blocca nuovi ingressi: "⛔ L0 BLOCCATO: regime NON suitable"
- ✅ L1 entries: 0 (mercato in BEAR, no nuovi ingressi L1 attesi)

## Implicazioni
1. **Regime filter è ATTIVO e FUNZIONANTE**
2. **Dashboard cleanup manual** è necessario una volta per rimuovere i legacy L0
3. **Recommendation:** aggiungere logica nel monitor per auto-pulire L0 quando regime cambia (future enhancement)

## Timeline
- 2026-07-30: 24 L0 entry during BEAR regime (BUG: no regime filter yet)
- 2026-08-06: Deploy regime filter + whitelist
- 2026-08-06 14:44: Manual cleanup via SQL DELETE

---
**Status:** ✅ RESOLVED
**Files Modified:** None (DB cleanup only)
**Deploy Required:** No (manual SQL cleanup, no code change)

