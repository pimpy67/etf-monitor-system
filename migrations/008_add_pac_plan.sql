-- 008_add_pac_plan.sql (2026-09-02)
-- Auto-tracking dei versamenti PAC da un piano salvato, invece dell'inserimento manuale
-- ad ogni esecuzione. Il monitor genera le righe in etf_pac_contributions leggendo questo
-- piano (giorni del mese + quote fisse per esecuzione), usando la chiusura del giorno.

ALTER TABLE etf_pac_contributions
    ADD COLUMN IF NOT EXISTS source VARCHAR(10) NOT NULL DEFAULT 'manual';
-- 'manual' = inserito a mano dall'utente ; 'auto' = generato dal monitor da un piano

CREATE TABLE IF NOT EXISTS etf_pac_plan (
    id               SERIAL PRIMARY KEY,
    isin             VARCHAR(20)  NOT NULL UNIQUE,
    ticker           VARCHAR(20)  NOT NULL,
    fund_name        VARCHAR(200),
    shares_per_exec  NUMERIC(16,6) NOT NULL,           -- quote fisse per esecuzione ("2 lotti")
    exec_days        INTEGER[]     NOT NULL,            -- giorni del mese, es. {1,8,15,23}
    fee_eur          NUMERIC(8,2)  NOT NULL DEFAULT 0,  -- commissione per esecuzione (Directa PAC = 0)
    broker           VARCHAR(20)   NOT NULL DEFAULT 'Directa',
    start_date       DATE          NOT NULL,
    active           BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMP     DEFAULT now()
);
