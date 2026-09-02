---
name: etf-proactive-status-reminders
description: "User wants periodic, unprompted recaps of everything open/in-progress on the ETF system — don't wait to be asked 'what's pending'"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c23e4e15-4c77-4fcf-a9c0-f0d2dc00b62b
  modified: 2026-08-20T10:30:53.408Z
---

Proactively resurface the list of open/in-progress threads on the ETF system, not only
when the user explicitly asks "cosa c'è in sospeso" — and do it more than once per
session if the session runs long or wraps in stages.

**Why**: said explicitly (2026-08-20) after a session where several backtests, two
Shadow Monitors, a threshold sweep, and a third Shadow Monitor were all launched in
parallel — the user's stated worry is that with this much happening at once, something
gets forgotten ("non vorrei lasciarle nel dimenticatoio"). This is a standing concern
about the pace of work, not a one-off request.

**How to apply**:
- The canonical list lives in [[etf_post_lockdown_todo_20260906]] — keep it current
  every time a new candidate/backtest/Shadow Monitor is started, not just at the end of
  a session. Treat "did I update this file" as part of finishing any such task, the same
  way updating CLAUDE.md is part of finishing a parameter change.
  ⚠️ Filename/date is a snapshot label — the checklist itself stays live and gets
  extended past 2026-09-06 for whatever opens after that date; don't treat the date in
  the name as an expiry.
- At natural checkpoints — a feature just shipped, a background task just finished, the
  conversation seems to be winding down, or a new session opens on this project — give a
  short unprompted recap: what's live/running (Shadow Monitors, background backtests),
  what's waiting on a date (lockdown end 2026-09-06), what's waiting on a user decision.
  Keep it to a few lines, point to the memory file for detail rather than restating it in
  full every time.
- When starting a fresh session on this project, lead with a brief status recap (what's
  running, what's pending) rather than waiting for the user to ask first — same spirit as
  the existing "CHECK FIRST" memory notes, but applied proactively mid-conversation too,
  not just at session start.
