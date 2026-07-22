# Daily Paper Manual Runbook v1.1

Status: **APPROVED (v1.0 approved with the required `paper_manual` patch; patch
applied here).** Operator procedure for one end-to-end **paper/manual** trading
day. No automatic orders - the system advises and records; **you** place every
order by hand in TWS Paper. Goal: reduce operational (human) error.

Scope: IBKR **Paper** account `DUQ199078`. All commands run from:

    cd C:\Users\stava\Projects\MarketResearchLab\paper_trading
    conda activate market_research_lab

Timing rule (frozen strategy): **BUY = target_date OPEN; EXIT = planned_exit_date
CLOSE.** Never buy on the close or exit on the open.

## Mode note (resolved)

Two runner modes, two configs:

- **`dry_run`** (`config/runner_config_dry_run.json`) - pure render/test. Trade
  Plan banner: `DRY_RUN ONLY - DO NOT PLACE REAL ORDERS`. Do NOT place orders.
- **`paper_manual`** (`config/runner_config_paper_manual.json`) - manual paper
  execution. Trade Plan banner: `PAPER_MANUAL - PAPER ORDERS ONLY. NO LIVE
  ORDERS. YOU PLACE ORDERS MANUALLY IN TWS PAPER`. This is the mode for the
  cycle below.

`paper_manual` uses its own directories (`...\paper_manual\...`) so paper
artifacts never mix with dry_run test artifacts. `live_manual` does not exist yet
(future, separate guard layer).

---

## 1. Before starting (pre-flight)

- [ ] TWS **Paper** is running and logged in ("Simulated Trading" in the title).
- [ ] Account is **DUQ199078** (Account menu).
- [ ] TWS API on: `Global Configuration -> API -> Settings` - Enable ActiveX and
      Socket Clients = ON, **Read-Only API = ON**, Socket port = 7497, Trusted IP
      127.0.0.1.
- [ ] First run of the day: no unexpected **open orders** and no unexpected
      **positions** in TWS.
- [ ] conda env `market_research_lab` active.

Any of these wrong -> **STOP** (Section 10).

## 2. Broker read-only check (confirm the account)

    python -m mle_paper_01.broker_check --config config/broker_readonly_paper.json --out reports\mle_paper_01\paper_manual

Confirm in `broker_connection_check_<ts>.md`:

- [ ] `result: PASS`, `account=DUQ199078`, `type=paper`
- [ ] all safety checks OK
- [ ] equity / cash as expected (~30086 / 30000)
- [ ] positions / open orders as expected (0 / 0 on a flat day)

Any HARD FAIL (mismatch, live) -> **STOP**.

## 3. State check / seed (paper_manual state)

The `paper_manual` state lives at
`runtime_state\mle_paper_01\paper_manual\state.json`. On the **first** paper cycle
seed it from the account (fresh path, no overwrite needed):

    :: preview (writes nothing)
    python -m mle_paper_01.broker_state_sync --config config/broker_readonly_paper.json --state runtime_state\mle_paper_01\paper_manual\state.json --out reports\mle_paper_01\paper_manual
    :: apply (seeds the paper_manual state)
    python -m mle_paper_01.broker_state_sync --config config/broker_readonly_paper.json --state runtime_state\mle_paper_01\paper_manual\state.json --out reports\mle_paper_01\paper_manual --apply

On later days the state already exists (updated by reconciliation); just verify:

- [ ] local cash / equity match the broker (or a drift you understand)
- [ ] local positions match the broker positions
- [ ] no unexplained drift

Broker positions that do not match local state -> **STOP**.

## 4. Daily Runner -> Daily Trade Plan (paper_manual)

    python -m mle_paper_01.daily_runner --config config/runner_config_paper_manual.json --manual-ticket

Open `reports\mle_paper_01\paper_manual\manual_report_<target_date>.md` and verify:

- [ ] banner reads **PAPER_MANUAL - PAPER ORDERS ONLY. NO LIVE ORDERS.**
- [ ] **business_date (D)** and **target_date (D+1)** are the sessions you expect
- [ ] **Regime** (Section 3): ON/OFF. OFF -> no new BUYs; only EXIT/HOLD
- [ ] **Section 2 Account**: equity/cash reflect the real account
- [ ] **BUY** (Section 4): rank, ref_price, indicative_qty, planned_exit_if_filled;
      note any **DO NOT BUY** rows
- [ ] **EXIT** (Section 5): which positions to sell, on which close
- [ ] **HOLD** (Section 6): days_remaining
- [ ] **Capital Feasibility** (Section 7): EXECUTABLE / PARTIAL / NOT_EXECUTABLE

PARTIAL / NOT_EXECUTABLE and you do not understand why -> **STOP**.

## 5. Manual paper order entry (in TWS)

Follow the Trade Plan exactly. Do not improvise.

- [ ] Enter **only executable BUY** names (rows **without** DO NOT BUY)
- [ ] Do **not** enter qty=0 / DO NOT BUY names
- [ ] **No rank-11 substitutions**
- [ ] **No manual ticker picking** - trade only what the plan lists
- [ ] **BUY** at **target_date OPEN**, plan's indicative_qty (whole shares)
- [ ] **EXIT** the planned exits near the **CLOSE**; sell the **full** position
- [ ] Double-check symbol, side, quantity on every ticket before submitting

## 6. Fill the ticket (record actuals)

Open `order_plans\mle_paper_01\paper_manual\manual_order_ticket_<target_date>.csv`
and for each executed order fill the blank actual columns:

- [ ] `actual_quantity`, `actual_fill_price`
- [ ] `timestamp` (must be the **target_date** session)
- [ ] `commission_fees`, `order_id`
- [ ] `status` = `filled` / `partial` / `cancelled`

Leave un-executed rows blank (skipped as "no fill recorded"). Do **not** edit
planned columns.

## 7. Reconciliation - VALIDATE (read-only first)

    python -m mle_paper_01.reconcile --ticket order_plans\mle_paper_01\paper_manual\manual_order_ticket_<target_date>.csv --plan order_plans\mle_paper_01\paper_manual\orders_plan_<target_date>.csv --state runtime_state\mle_paper_01\paper_manual\state.json --mode paper_manual --out reports\mle_paper_01\paper_manual

Check `reconciliation_report_<target_date>.md`:

- [ ] **result: PASS** (validate-only writes nothing)
- [ ] Applied rows are the fills you intend to book
- [ ] no unexpected FAILED rows / Skipped duplicates
- [ ] deviations / warnings understood

**FAIL** -> fix the ticket, re-run validate. Do **not** apply on FAIL.

## 8. Reconciliation - APPLY (write state + journal)

Only after a PASS validate:

    python -m mle_paper_01.reconcile --ticket order_plans\mle_paper_01\paper_manual\manual_order_ticket_<target_date>.csv --plan order_plans\mle_paper_01\paper_manual\orders_plan_<target_date>.csv --state runtime_state\mle_paper_01\paper_manual\state.json --journal-dir journal_data --mode paper_manual --out reports\mle_paper_01\paper_manual --apply

- [ ] report shows **APPLIED** + a **state backup** path
- [ ] journal `fills` written (`execution_mode = MANUAL`) + RECONCILIATION event
- [ ] equity flagged **provisional** (next runner re-marks to close)

## 9. After the run

- [ ] Inspect updated `state.json`: cash, positions, entry/planned_exit dates
- [ ] Cash decreased by real BUY debits / increased by EXIT proceeds
- [ ] Any **PARTIAL EXIT** flag noted for tomorrow (remainder still open)
- [ ] Keep the day's reports (broker check, trade plan, reconciliation)
- [ ] Journal note: date, what was traded, anything unusual

## 10. Stop conditions (halt; do not trade)

- **Account mismatch** - detected account != `DUQ199078`.
- **Live account** - a `U...` (non-paper) account detected.
- **Unexpected open orders** in TWS you did not place / expect.
- **Broker positions do not match local PortfolioState** - reconcile/flatten first.
- **Someone would buy qty=0 / a DO NOT BUY name** - never.
- **Reconciliation FAIL** - never `--apply` on a FAIL.
- **Trade Plan PARTIAL / NOT_EXECUTABLE and you do not understand why**.

When stopped: place no orders, apply no state change, capture the report(s),
resolve the cause before resuming.

---

## Appendix - one-line cycle summary

    pre-flight -> broker_check (PASS) -> state check/seed -> daily_runner
    (paper_manual Trade Plan) -> manual paper orders in TWS -> fill ticket
    -> reconcile VALIDATE (PASS) -> reconcile APPLY -> post-run state check
