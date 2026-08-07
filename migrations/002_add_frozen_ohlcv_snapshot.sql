-- Migration: Golden Dataset — storico OHLCV congelato per backtest riproducibili
-- Date: 2026-08-07
-- Motivazione: backtest_l1.py rifetchava OHLCV live da Yahoo Finance a ogni run,
-- rendendo i risultati non riproducibili (Yahoo rivede retroattivamente gli adjusted
-- close). Vedi CLAUDE.md sezione "L1 — Come Si Esce" per l'indagine 3 vs 80 vs 1 trade
-- che ha portato a questa migrazione. Tabella separata da etf_price_history (che il
-- monitor live continua ad aggiornare quotidianamente) — questa non viene mai toccata
-- dal monitor, solo dallo script di backfill one-time.

CREATE TABLE IF NOT EXISTS etf_price_history_frozen (
  id           SERIAL PRIMARY KEY,
  freeze_batch VARCHAR(20) NOT NULL,
  ticker       VARCHAR(20) NOT NULL,
  isin         VARCHAR(20),
  date         DATE NOT NULL,
  open         NUMERIC(12, 4),
  high         NUMERIC(12, 4),
  low          NUMERIC(12, 4),
  close        NUMERIC(12, 4) NOT NULL,
  volume       BIGINT,
  created_at   TIMESTAMP DEFAULT now(),
  UNIQUE (freeze_batch, ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_etf_frozen_ticker_date
  ON etf_price_history_frozen (freeze_batch, ticker, date DESC);

-- Verifica dopo backfill:
-- SELECT freeze_batch, COUNT(DISTINCT ticker) AS n_ticker, COUNT(*) AS n_rows,
--        MIN(date) AS from_date, MAX(date) AS to_date
-- FROM etf_price_history_frozen GROUP BY freeze_batch;
