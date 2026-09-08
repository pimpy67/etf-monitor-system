-- 011 — PAC: importo fisso per esecuzione (come funziona davvero Directa)
-- Il piano Directa e' a importo fisso (es. VWCE 336 EUR/data), non a quote fisse.
-- L'auto-tracking del monitor compra floor(amount / prezzo) quote entro il budget.
-- shares_per_exec resta come stima di fallback quando amount_eur_per_exec e' NULL.

ALTER TABLE etf_pac_plan ADD COLUMN IF NOT EXISTS amount_eur_per_exec NUMERIC(12,2);
