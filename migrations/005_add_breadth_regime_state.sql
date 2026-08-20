-- Migration: stato persistente del regime di Market Breadth (isteresi giorno-su-giorno)
-- Date: 2026-08-20
-- Motivazione: Shadow Monitor per la "terza via" Market Breadth/Super-Bull (vedi CLAUDE.md
-- e memory/etf_post_lockdown_todo_20260906.md, sezione 3) — l'isteresi a doppia soglia
-- (enter>=80%/exit<65%) ha bisogno di sapere lo stato di IERI per decidere quello di OGGI,
-- altrimenti flipperebbe ogni giorno vicino al bordo. Una sola riga per modello, aggiornata
-- ogni ciclo di monitor. Riusa etf_shadow_positions (gia' generica per model_name) per le
-- posizioni ombra — questa tabella serve solo per il regime, non per i trade.

CREATE TABLE IF NOT EXISTS etf_breadth_regime_state (
  id            SERIAL PRIMARY KEY,
  model_name    VARCHAR(50) NOT NULL UNIQUE,
  current_state VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
  breadth_pct   NUMERIC(6, 4),
  updated_at    TIMESTAMP DEFAULT now()
);
