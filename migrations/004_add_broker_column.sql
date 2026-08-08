-- Migration: Aggiungi colonna broker a etf_portfolio_entries
-- Date: 2026-08-09
-- Motivazione: la guida "come piazzare SL/TP" e' specifica del broker — su Directa
-- (conto cash) non si puo' tenere attivo un ordine Limite (TP) in parallelo allo Stop
-- sulle stesse quote (verificato in produzione 2026-08-08, vedi CLAUDE.md sezione
-- "Esecuzione ordini reali su Directa"), mentre Webank supporta Stop Loss e Take Profit
-- contemporaneamente attivi (verosimilmente OCO). L'utente opera su entrambi — serve
-- sapere quale broker per ogni posizione per mostrare il messaggio giusto in email e
-- dashboard invece di una nota generica valida solo per Directa.

ALTER TABLE etf_portfolio_entries
ADD COLUMN IF NOT EXISTS broker VARCHAR(20) NOT NULL DEFAULT 'Directa';

-- Backfill: unica posizione nota non-Directa al momento della migrazione.
UPDATE etf_portfolio_entries
SET broker = 'Webank'
WHERE isin = 'FR0007056841';

-- Verifica dopo migrazione:
-- SELECT isin, fund_name, broker FROM etf_portfolio_entries WHERE status = 'active';
