# Daily Trade Plan — design note

Status: **APPROVED — implemented + small patches applied.** Architect priority A
(2026-07-15). Post-first-render patches (approved): (1) runtime strategy_id →
`MLE-REGIME200-HOLD10-01` (MLE-PAPER-01 kept only as legacy label); (2) `dry_run`
banner "DRY_RUN ONLY — DO NOT PLACE REAL ORDERS" + checklist wording "do not
execute unless mode is paper_manual/live_manual"; (3) fill template + ticket
carry `conid`, `planned_side`, `planned_qty` (+ blank actuals) so reconciliation
does not key on ticker alone. No broker, no order submission, no state mutation,
no launcher, no paper connection. Render-only, from local state + decisions +
feasibility.

## 0. Goal

Evolve the existing `manual_report.py` render into a complete **Daily Trade
Plan** with the architect's 9 sections, so a human can execute manually without
ambiguity: what to buy, how many shares, what not to buy, what to sell, what to
hold, what to record after fills.

## 1. Approach

- **Extend `manual_report.py`** (keep the module + `write_report` / `write_ticket`
  names the runner already calls); retitle output **"Daily Trade Plan"**;
  restructure into the 9 numbered sections. No new wiring beyond a few extra
  arguments the runner already has.
- `manual_report` stays **render-only / calendar-free**. The two calendar-derived
  fields (estimated exit-if-filled, hold days-remaining) are computed in
  `daily_runner` (which already holds the XNYS `next_session_fn` and the hold
  constant) and passed in.

## 2. Section mapping (exists / added)

| # | Section | Status |
|---|---|---|
| 1 | Header: strategy_id, run_id, mode, D, D+1, data_source, portfolio_state source | add run_id + portfolio_state source |
| 2 | Account: equity, cash, open positions, max positions; cash≠equity normal | add max_positions label + cash≠equity note |
| 3 | Regime: ON/OFF; if OFF → no new BUYs, exits/holds still apply | add the OFF note |
| 4 | BUY: ticker/conid, **rank**, target_value, ref_price(D close), indicative_qty, est_debit, feasibility status/reason, DO NOT BUY, **planned_exit_date_if_filled**, estimate note | add rank + planned_exit_date_if_filled |
| 5 | EXIT: ticker, conid, current qty, exit date, "sell full position at planned exit close; no discretionary changes" | add exit date col + instruction |
| 6 | HOLD: ticker, qty, entry_date, planned_exit_date, **days_remaining**, "hold / no action" | add entry_date + days_remaining + instruction |
| 7 | Capital Feasibility: status, min op capital, TOO_EXPENSIVE, INSUFFICIENT_CASH, rounding drag, unused budget, remaining cash, warnings | already present |
| 8 | Manual execution checklist (architect's exact list) | expand current PAPER/LIVE checklist |
| 9 | Fill recording template: ticker, side, quantity, actual_fill_price, timestamp, commission/fees, order_id, status | add template table + align ticket CSV columns |

## 3. Design decisions (proposed)

- **D1 — planned_exit_date_if_filled** (BUY): estimated exit close =
  **10 XNYS sessions after `target_date` (D+1)**, since entry is the D+1 open
  and hold = 10 (`planned_exit = entry_index + 10`). Labelled *"estimated — set
  for real only at fill"* (the frozen rule sets `planned_exit_date` at fill).
- **D2 — rank** (BUY): `SignalCandidate.rank_10d` mapped to the BUY ticker
  (1 = strongest).
- **D3 — days_remaining** (HOLD): number of **XNYS trading sessions** from D
  (exclusive) to `planned_exit_date` (inclusive) — sessions, not calendar days.
- **D4 — calendar logic lives in `daily_runner`**; `manual_report` receives the
  computed values (`estimated_exit_if_filled`, per-hold `days_remaining`) and
  stays render-only.
- **D5 — fill recording**: a template table in the `.md` **and** aligned ticket
  CSV columns: `ticker, side, quantity, actual_fill_price, timestamp,
  commission_fees, order_id, status`. Still no ingestion here — recording only.

## 4. Non-goals (unchanged)

No broker, no order submission, no state mutation, no rank-11 substitution, no
discretionary ticker picking, no launcher, no paper connection. Fill *ingestion*
(reading the filled ticket back into the journal, `execution_mode=MANUAL`,
schema 1.1.0) is a **separate later step**, not part of this task.

## 5. Open questions

- **OQ-1** — confirm planned exit = entry_index + 10 sessions (entry = D+1 open,
  exit on close), i.e. 10 XNYS sessions after D+1.
- **OQ-2** — `days_remaining` counted as **trading sessions** (not calendar
  days)?
- **OQ-3** — extend `manual_report.py` (keep the name; it is the manual-workflow
  renderer) vs. introduce a new `trade_plan.py`. Proposed: **extend**.

## 6. Tests (render-level, no broker)

- All 9 sections present in the rendered plan.
- BUY: qty=0 → DO NOT BUY with reason; rank + planned_exit_date_if_filled shown.
- Account: `cash != equity` supported and rendered (both shown).
- Regime OFF → the "no new BUYs; exits/holds still apply" note appears.
- HOLD: entry_date + days_remaining present.
- Fill recording template columns present; ticket CSV columns aligned.
- No resolver/broker calls (AST scan); render-only (no state mutation).
