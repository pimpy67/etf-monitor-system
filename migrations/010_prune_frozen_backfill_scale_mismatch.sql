-- 010_prune_frozen_backfill_scale_mismatch.sql
-- Rimuove il backfill 009 per gli ISIN in cui frozen e live sono su scale di
-- prezzo diverse -> lo splice creava un "gradino" verticale nel grafico Max.
--
-- Diagnosi: ~36 ISIN cambiano scala esattamente al 2025-05-07/08 (data in cui
-- inizia il fetch live 'yfinance' per quegli ETF). Il frozen dataset e il primo
-- tratto live usano quotazioni di listini/valute diversi (ratio 0,39x .. 2,63x).
-- Sugli ETF non colpiti frozen e live coincidono al centesimo (ratio ~1,000).
--
-- Scelta: eliminare il backfill per gli ISIN discordanti (tornano al loro storico
-- live ~15 mesi, corretto ma corto) e tenerlo per i ~178 ETF con splice pulito
-- (grafico ~4,5 anni). Il problema di scala nello storico live di quei 36 e'
-- preesistente e fuori scope qui.
--
-- Soglia: |ratio - 1| > ~0,16 (un singolo giorno non muove un ETF cosi' tanto).
-- Rieseguibile.

WITH bf AS (
    SELECT DISTINCT ON (isin) isin, close AS bf_close
    FROM etf_price_history
    WHERE source = 'frozen_backfill_20260807'
    ORDER BY isin, date DESC
),
lv AS (
    SELECT DISTINCT ON (isin) isin, close AS lv_close
    FROM etf_price_history
    WHERE source <> 'frozen_backfill_20260807'
    ORDER BY isin, date ASC
),
bad AS (
    SELECT bf.isin
    FROM bf JOIN lv USING (isin)
    WHERE (lv.lv_close / NULLIF(bf.bf_close, 0)) NOT BETWEEN 0.85 AND 1.18
)
DELETE FROM etf_price_history p
USING bad
WHERE p.isin = bad.isin
  AND p.source = 'frozen_backfill_20260807';

-- Verifica:
--   SELECT source, COUNT(*), COUNT(DISTINCT isin), MIN(date)
--   FROM etf_price_history GROUP BY source;
