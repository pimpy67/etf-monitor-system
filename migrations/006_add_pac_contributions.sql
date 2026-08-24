-- Migration: PAC (Piano di Accumulo Capitale) — tracciamento versamenti reali
-- Date: 2026-08-24
-- Motivazione: confronto diretto, con dati veri (non backtest), tra un PAC passivo
-- (versamento fisso mensile, nessun segnale) e il portafoglio attivo del sistema
-- (etf_portfolio_entries). Stessa filosofia "nessun automatismo" del resto del sistema:
-- l'utente esegue davvero l'acquisto su Directa il giorno fisso di ogni mese, poi lo
-- registra qui a mano — nessun ordine piazzato o simulato dal sistema.
-- Vedi CLAUDE.md sezione "PAC — confronto con portafoglio attivo".

CREATE TABLE IF NOT EXISTS etf_pac_contributions (
  id                SERIAL PRIMARY KEY,
  isin              VARCHAR(20) NOT NULL,
  ticker            VARCHAR(20) NOT NULL,
  fund_name         VARCHAR(200),
  contribution_date DATE NOT NULL,
  amount_eur        NUMERIC(12, 2) NOT NULL,
  price             NUMERIC(12, 4) NOT NULL,
  shares            NUMERIC(16, 6) NOT NULL,
  broker            VARCHAR(20) NOT NULL DEFAULT 'Directa',
  created_at        TIMESTAMP DEFAULT now(),
  UNIQUE (isin, contribution_date)
);

CREATE INDEX IF NOT EXISTS idx_pac_contributions_isin
  ON etf_pac_contributions (isin);
