-- Migration: Add L0 regime state + L1 space_residuo + L2 watchlist
-- Date: 2026-07-20
-- Version: 4.0

-- ============================================================================
-- TABLE: etf_l1_tracking — Aggiungi colonne per space_residuo check
-- ============================================================================

ALTER TABLE etf_l1_tracking
ADD COLUMN IF NOT EXISTS space_residuo_check_result BOOLEAN DEFAULT NULL,
ADD COLUMN IF NOT EXISTS space_residuo_method VARCHAR(50) DEFAULT NULL;

-- ============================================================================
-- TABLE: etf_l0_tracking — Aggiungi colonne per regime state persistente
-- ============================================================================

ALTER TABLE etf_l0_tracking
ADD COLUMN IF NOT EXISTS l0_confirmation_mode VARCHAR(20) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS l0_trigger_low_price DECIMAL(12, 6) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS l0_trigger_date DATE DEFAULT NULL;

-- ============================================================================
-- TABLE: etf_l2_watchlist — NUOVA tabella per readiness score + isteresi
-- ============================================================================

CREATE TABLE IF NOT EXISTS etf_l2_watchlist (
  isin VARCHAR(20) PRIMARY KEY,
  ticker VARCHAR(20),
  score DECIMAL(5, 2) NOT NULL DEFAULT 0.0,
  entered_date DATE,
  exited_date DATE,
  in_watchlist BOOLEAN DEFAULT FALSE,
  ema_smoothed_value DECIMAL(5, 2) DEFAULT 0.0,
  last_raw_score DECIMAL(5, 2) DEFAULT 0.0,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE INDEX idx_ticker (ticker),
  INDEX idx_in_watchlist (in_watchlist),
  INDEX idx_score (score)
);

-- ============================================================================
-- VIEW: v_l2_watchlist_active — Elenco ETF in L2 watchlist (in_watchlist=true)
-- ============================================================================

CREATE OR REPLACE VIEW v_l2_watchlist_active AS
SELECT
  isin,
  ticker,
  score,
  entered_date,
  ema_smoothed_value,
  updated_at
FROM etf_l2_watchlist
WHERE in_watchlist = TRUE
ORDER BY score DESC, updated_at DESC;

-- ============================================================================
-- Commit markers
-- ============================================================================

-- Verifica integrità dopo migrazione:
-- SELECT COUNT(*) as l0_tracking_records FROM etf_l0_tracking;
-- SELECT COUNT(*) as l2_watchlist_records FROM etf_l2_watchlist;
-- SELECT COUNT(*) as l0_with_confirmation FROM etf_l0_tracking WHERE l0_confirmation_mode IS NOT NULL;
