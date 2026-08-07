-- Migration: Shadow Monitor — tracking posizioni ipotetiche di CANDIDATE_MODEL_B_20260807
-- Date: 2026-08-07
-- Motivazione: durante il lockdown parametri (fino al 06/09/2026) il sistema live continua
-- a operare solo con native_7 (min_buy_count=7). Questa tabella traccia in parallelo, senza
-- toccare nessuna decisione reale, cosa avrebbe fatto CANDIDATE_MODEL_B_20260807
-- (mm200_distance_max=7.0%, adx_entry baseline-4, smart_6_macd, TP target 15%) sulle 5
-- famiglie del cluster 'core' — per un confronto native_7 vs candidato su dati forward
-- reali al termine del lockdown. Vedi CLAUDE.md sezione CANDIDATE_MODEL_B_20260807.

CREATE TABLE IF NOT EXISTS etf_shadow_positions (
  id           SERIAL PRIMARY KEY,
  model_name   VARCHAR(50) NOT NULL DEFAULT 'candidate_model_b_20260807',
  ticker       VARCHAR(20) NOT NULL,
  isin         VARCHAR(20),
  famiglia     VARCHAR(50) NOT NULL,
  entry_date   DATE NOT NULL,
  entry_price  NUMERIC(12, 4) NOT NULL,
  exit_date    DATE,
  exit_price   NUMERIC(12, 4),
  exit_reason  VARCHAR(10),
  status       VARCHAR(10) NOT NULL DEFAULT 'open',
  gross_pct_gain NUMERIC(8, 3),
  created_at   TIMESTAMP DEFAULT now(),
  updated_at   TIMESTAMP DEFAULT now(),
  UNIQUE (model_name, ticker, entry_date)
);

CREATE INDEX IF NOT EXISTS idx_shadow_positions_status
  ON etf_shadow_positions (model_name, status);

-- Confronto a fine lockdown (06/09/2026):
-- SELECT ticker, entry_date, exit_date, exit_reason, gross_pct_gain
-- FROM etf_shadow_positions WHERE model_name = 'candidate_model_b_20260807'
-- ORDER BY entry_date;
