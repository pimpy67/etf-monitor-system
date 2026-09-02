-- seed_pac_plans.sql (2026-09-02) — piani PAC confermati dall'utente.
-- Da eseguire UNA volta dopo la migration 008. Il monitor genera poi i versamenti in
-- automatico (etf_pac_contributions, source='auto') a partire da start_date.

-- Piano 1 — Azionario: 2 quote VWCE.MI, giorni 1/8/15/23, commissione 0, dal 2026-09-01
INSERT INTO etf_pac_plan (isin, ticker, fund_name, shares_per_exec, exec_days, fee_eur, broker, start_date, active)
VALUES ('IE00BK5BQT80', 'VWCE.MI', 'Vanguard FTSE All-World UCITS ETF USD Acc',
        2, '{1,8,15,23}', 0, 'Directa', '2026-09-01', TRUE)
ON CONFLICT (isin) DO UPDATE SET
    ticker = EXCLUDED.ticker, fund_name = EXCLUDED.fund_name,
    shares_per_exec = EXCLUDED.shares_per_exec, exec_days = EXCLUDED.exec_days,
    fee_eur = EXCLUDED.fee_eur, broker = EXCLUDED.broker,
    start_date = EXCLUDED.start_date, active = EXCLUDED.active;

-- Piano 2 — Obbligazionario: 1 quota GAGG.MI, giorni 1/8/15/23, commissione 0, dal 2026-09-01
INSERT INTO etf_pac_plan (isin, ticker, fund_name, shares_per_exec, exec_days, fee_eur, broker, start_date, active)
VALUES ('LU1437024729', 'GAGG.MI', 'Amundi IS Core Global Aggregate Bond UCITS ETF Acc',
        1, '{1,8,15,23}', 0, 'Directa', '2026-09-01', TRUE)
ON CONFLICT (isin) DO UPDATE SET
    ticker = EXCLUDED.ticker, fund_name = EXCLUDED.fund_name,
    shares_per_exec = EXCLUDED.shares_per_exec, exec_days = EXCLUDED.exec_days,
    fee_eur = EXCLUDED.fee_eur, broker = EXCLUDED.broker,
    start_date = EXCLUDED.start_date, active = EXCLUDED.active;

-- Cleanup: riga di prova rimasta dal 2026-08-24 (VWCE.DE, 998.04EUR, 6 quote, fee 9.50,
-- 2026-08-25) — dati sbagliati per il piano reale, inquinerebbe il confronto PAC-vs-attivo.
DELETE FROM etf_pac_contributions
WHERE isin = 'IE00BK5BQT80' AND contribution_date = '2026-08-25' AND ticker = 'VWCE.DE';
