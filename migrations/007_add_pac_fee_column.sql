-- Migration: PAC — colonna commissione separata
-- Date: 2026-08-24
-- Motivazione: il primo versamento reale (VWCE.DE su Xetra) ha mostrato una commissione
-- Directa di 9,50EUR, quasi doppia dei 5EUR assunti in tutti i backtest di oggi (probabile
-- sovrapprezzo per mercato estero rispetto a Borsa Italiana, dove sono MEU/PHAG). Senza
-- questa colonna il confronto PAC vs L1/L0 in /api/pac ignorava la commissione, rendendo il
-- PAC otticamente migliore di quanto sia davvero — esattamente l'errore opposto a quello già
-- corretto nei backtest (che includevano sempre i costi). fee_eur si somma ad amount_eur nel
-- calcolo del capitale investito, cosi' il rendimento% resta netto dei costi reali.

ALTER TABLE etf_pac_contributions ADD COLUMN IF NOT EXISTS fee_eur NUMERIC(8, 2) NOT NULL DEFAULT 0;
