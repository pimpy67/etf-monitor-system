-- 009_backfill_frozen_history.sql
-- Backfill di etf_price_history con lo storico del Golden Dataset congelato
-- (etf_price_history_frozen, batch 2026-08-07, dati Yahoo reali 2022-02 -> 2026-08).
--
-- Motivo: la tabella live tiene solo ~12-18 mesi per l'intero universo, quindi il
-- grafico "Max" della modal ETF non poteva andare oltre ~1 anno. Il frozen dataset
-- ha ~4,5 anni per 214 dei 236 ETF. Frozen e live coincidono al centesimo su ogni
-- data sovrapposta (verificato) -> lo splice e' continuo.
--
-- Sicurezza:
--   * inserisce SOLO date anteriori al primo giorno gia' presente in live per quell'ISIN
--   * match per ISIN, ticker preso da live (gestisce i ticker rinominati da agosto)
--   * esclude LU1954152853 (UST hedged, storico frozen potenzialmente contaminato
--     dal doppio listing, gia' ripulito e ribackfillato a parte il 2026-09-03)
--   * ON CONFLICT DO NOTHING -> rieseguibile, non tocca nulla di esistente
--   * source = 'frozen_backfill_20260807' per poter distinguere/annullare

WITH cur AS (
    SELECT DISTINCT ON (isin) isin, ticker
    FROM etf_price_history
    WHERE isin IS NOT NULL AND isin <> ''
    ORDER BY isin, date DESC
)
INSERT INTO etf_price_history (ticker, isin, date, open, high, low, close, volume, source)
SELECT cur.ticker, f.isin, f.date, f.open, f.high, f.low, f.close, f.volume,
       'frozen_backfill_20260807'
FROM etf_price_history_frozen f
JOIN cur ON cur.isin = f.isin
WHERE f.freeze_batch = '2026-08-07'
  AND f.isin <> 'LU1954152853'
  AND f.close > 0
  AND f.date < (SELECT MIN(date) FROM etf_price_history l WHERE l.isin = f.isin)
ON CONFLICT DO NOTHING;

-- Verifica:
--   SELECT source, COUNT(*), MIN(date), MAX(date) FROM etf_price_history GROUP BY source;
-- Rollback (se serve):
--   DELETE FROM etf_price_history WHERE source = 'frozen_backfill_20260807';
