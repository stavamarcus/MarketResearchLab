# Daily Offline Runner — Design

**Status:** APPROVED WITH REQUIRED DATA-SOURCE ABSTRACTION (architect, 2026-07-15) — changes incorporated below.
**Strategy:** MLE-PAPER-01 (v1.1 frozen)
**Module:** `MarketResearchLab/paper_trading/mle_paper_01/`
**Mode:** `dry_run` only in MVP.

## 0. What changed from the reviewed draft

- **Data source is now abstracted** (`DataSourceProfile` / `--data-source`). The
  runner is **not** hardcoded to DATA-06. MVP default is `DATA06`
  (deterministic dev/tests); operational daily runner after GDU must support
  `MDSM` (MDSM-Lite cache). Pipeline reads: *configured price source* →
  MLE signal → regime → resolver.
- `source_system` is **data-source aware** (§6, OQ-3).
- `business_date` default = **max completed session in the selected data
  source**, not hardcoded to DATA-06 (§6 Q1).
- OQ-1..5 locked (§6, §11).
- **Manual Execution Fallback added** (§13): the runner renders the *same*
  order_plan into a human-readable manual trading report so the strategy is
  tradable by hand when broker integration is unavailable. No new strategy
  logic. Raises OQ-6 (`execution_mode` journal field).

## 1. Position of the runner (what it IS / IS NOT)

A **single-day, production-shaped** process: "given today's close, what would I
plan for the next open." It is **not** the replay engine — Phase-1 replay
(multi-day, simulated fills) exists and is untouched. The runner calls the
**same frozen modules** (`decision_resolver`, `order_planner`, `signal_source`,
`regime_source`, `portfolio_state`) and only wraps them with daily I/O + journal.

**State is read-only in MVP.** The runner applies **no fills** and does **not**
mutate portfolio state from the plan. State advances only later via the
execution / reconciliation layer.

> ⚠️ If `dry_run` is run for several days **without** an execution/reconciliation
> layer, it reuses the same bootstrap / manually-updated state every day. That is
> **not** a multi-day paper simulation (multi-day simulation = the replay engine).
> This is acceptable and intended, but must be understood.

## 2. Data source abstraction (headline requirement)

A `PriceDataSource` interface decouples the runner from where prices live:

```
class PriceDataSource(Protocol):
    profile: DataSourceProfile               # DATA06 | MDSM
    def last_completed_session(self) -> date            # max completed session
    def universe(self, as_of: date) -> list[Symbol]     # frozen 503 universe
    def price_frame(self, as_of: date) -> PriceFrame     # bars needed for rank/regime
```

- `DataSourceProfile = Enum(DATA06, MDSM)`.
- `Data06PriceSource` — reads `mdsm_price_view` (Sharadar split-adjusted OHLCV
  per conid) + `sp500_rank_calendar_universe.csv`. **MVP default.**
- `MdsmPriceSource` — MDSM-Lite cache after GDU. Interface defined now;
  concrete read implemented when GDU cache lands (documented stub until then;
  selecting `MDSM` before it exists → fail-closed with a clear message).

Signal (`rank_10d ≤ 10 → MLE_TOP10`) and `regime200` are computed by the
**existing frozen** `signal_source` / `regime_source`, fed from the selected
`PriceDataSource`. The runner changes **no** signal/regime logic.

## 3. Directory layout

```
paper_trading/mle_paper_01/
  daily_runner.py            # DailyOfflineRunner + CLI (__main__)
  data_source.py             # PriceDataSource, DataSourceProfile, Data06/Mdsm sources
  runtime_state.py           # state load / save / bootstrap / consistency check
  manual_report.py           # manual_report_<D+1>.md + manual_order_ticket_<D+1>.csv
  calendar_util.py           # XNYS next-session (exchange_calendars)
  runner_config.py           # RunnerConfig + JSON loading (configurable paths)
  # order plan reuses frozen order_planner.write_orders_plan (no new writer)
  # wiring folded into data_source.build_data_source + journal factory
  # UNCHANGED: models.py, decision_resolver.py, portfolio_state.py,
  #   order_planner.py, signal_source.py, regime_source.py
  docs/DAILY-OFFLINE-RUNNER_design.md
  tests/test_runner_*.py
paper_trading/runtime_state/mle_paper_01/dry_run/state.json
paper_trading/order_plans/mle_paper_01/dry_run/orders_plan_<D+1>.csv
paper_trading/order_plans/mle_paper_01/dry_run/manual_order_ticket_<D+1>.csv   # optional fillable ticket
paper_trading/reports/mle_paper_01/dry_run/manual_report_<D+1>.md              # manual trading report
paper_trading/journal_data/dry_run/...                          # journal (audit)
config/runner_config_dry_run.json
```

## 4. Single-run flow

```
1. resolve business_date D          (Q1)  from selected data source
2. resolve target_date D+1          (Q2)  XNYS calendar
3. PREFLIGHT (fail-closed gate)     (Q7)  data / regime / state consistency
4. price_frame(D) from PriceDataSource
5. MLE_TOP10 = signal_source(price_frame, D)          # frozen, rank_10d<=10
6. regime[D] = regime_source(price_frame, D)          # frozen, no D+1 lookahead
7. state = runtime_state.load_or_bootstrap()          (Q3/Q4)  read-only
8. decisions = decision_resolver(MLE_TOP10, regime[D], state, D+1)   # frozen
9. order_plan = order_planner(decisions, state)       # frozen, status=PLANNED
10. journal: daily_state, signals, decisions, order_plans,
    positions snapshot, events; ensure_empty_tables(["fills"])       (Q6)
11. write orders_plan_<D+1>.csv   (Q5, SUCCESS only)
12. render manual_report_<D+1>.md (+ optional manual_order_ticket_<D+1>.csv)  (§13)
13. summary (console + optional .md)
```

## 5. Runner API / CLI

```
DailyOfflineRunner(config, deps).run(business_date=None) -> RunResult

python -m paper_trading.mle_paper_01.daily_runner \
    [--business-date YYYY-MM-DD]    # default: last completed session in source
    [--data-source DATA06|MDSM]     # default DATA06
    [--mode dry_run]                # MVP fixed
    [--config config/runner_config_dry_run.json]
    [--no-order-plan-file]
    [--no-manual-report]            # manual report generated by default
    [--manual-ticket]               # also emit the fillable manual_order_ticket CSV
```

`RunResult`: `business_date, target_date, run_id, status(SUCCESS|STOPPED|FAILED),
data_source, n_buy, n_exit, n_do_nothing, regime_on, cash, equity,
open_positions, warnings, errors, order_plan_path`.

## 6. Answers to the 8 acceptance questions

**Q1 — business_date D:** from `--business-date`; else default =
`PriceDataSource.last_completed_session()` of the **selected** source
(DATA06 → max date in DATA-06; MDSM → max date in MDSM cache after GDU). Not
hardcoded to DATA-06.

**Q2 — target_date D+1:** D is the last session, so D+1 is not in data → resolved
via the **XNYS trading calendar** (`exchangecalendars`, OQ-1). D+1 is only a
label/target on the plan; the runner loads no D+1 data and performs no D+1
computation.

**Q3 — portfolio state location:** `paper_trading/runtime_state/mle_paper_01/
dry_run/state.json`. Schema: `as_of_date, cash, equity, positions[]`
(ticker, conid, shares, entry_date, entry_price, planned_exit_date,
rank_at_entry, regime_at_entry); `free_slots` derived. **Read-only** input in MVP.

**Q4 — bootstrap (first day, no state):** if `state.json` is missing, initialize
from `config/runner_config_dry_run.json` (`cash = starting_equity`,
`positions = []`, slots per strategy), persist it, and journal a
`STATE_BOOTSTRAPPED` event. Bootstrap is **dry_run/replay-like only**; paper/live
runtime must later obtain state via **reconciliation**, never bootstrap.

**Q5 — order_plan location:** `paper_trading/order_plans/mle_paper_01/dry_run/
orders_plan_<D+1>.csv` (human-readable handoff for the future execution step) plus
the journal `order_plans` table (audit). CSV columns: `target_date, ticker,
conid, action, target_value, quantity, price_source=next_open, order_type,
status=PLANNED`. CSV written **only on SUCCESS**.

**Q6 — journal usage:** `JournalWriter(mode="dry_run",
strategy_id="MLE-PAPER-01", base_dir=journal_data, source_system=<per record>)`
as a context manager; one run = one business_date. Writes daily_state, signals,
decisions, order_plans, positions snapshot, events;
`ensure_empty_tables(["fills"])`. `write_event` for RUN_START / RUN_COMPLETE /
STOP / warnings. `source_system` is **data-source aware** (OQ-3):
`signals`/`regime` → `DATA06` or `MDSM`; `decisions`/`order_plans` →
`DAILY_RUNNER`; `positions` → `RUNTIME_STATE`; `events` → `DAILY_RUNNER`.

**Q7 — data error:** **fail-closed preflight** before the resolver verifies
(a) selected source has complete data for the universe @ D, (b) regime is
computable, (c) state is consistent. Any failure → **STOP**, terminal
`RUN_FAILED`/`RUN_STOPPED` event (+ reason), **no order_plan CSV**, non-zero exit.
Journal write failure → run = FAILED. No silent fallbacks beyond those the spec
explicitly permits.

**Q8 — proof the runner does not change resolver logic:** (1) the runner
**imports and calls** `decision_resolver`/`order_planner` (via `wiring.py`); it
never reimplements them. (2) **passthrough parity test** — for a fixed
(signals, regime, state, D+1), `runner.decisions == decision_resolver(...)`
field-equal. (3) static test that the runner module defines no resolver logic.
(4) **golden-day determinism** — identical inputs → identical order_plan across
runs.

## 7. Error handling (fail-closed, approved)

| Failure | Behavior |
|---|---|
| missing data (universe / @D) | STOP, event, no order_plan, exit≠0 |
| regime not computable | STOP, event |
| inconsistent portfolio state | STOP, event |
| selected data source unavailable (e.g. MDSM before GDU) | STOP, clear event |
| journal write failure | run = FAILED, event if possible, exit≠0 |

On STOP the order_plan CSV is **not** written; the journal records the failed run.

## 8. Lightweight signal parity (inventory, not a research project)

Runner design must **not** be blocked by parity research.
- If a **DATA06/MDSM** validation already covers TOP10 / `rank_10d` parity →
  just reference it.
- If missing → perform the **minimal delta sanity test** (recompute `rank_10d`
  for a known D from the selected source, assert TOP10 == `signal_source` v1.1
  output).
- This concerns **price-rank parity in the selected source**, not MDSM-Lite SF1
  fundamental reconciliation.

## 9. Test plan

`test_business_date_resolution` (default = last completed session, per source),
`test_target_date_next_session` (XNYS), `test_datasource_profile_selection`
(DATA06 default; MDSM selected-before-GDU → fail-closed),
`test_bootstrap_creates_state`, `test_state_load_roundtrip`,
`test_state_read_only` (runner does not mutate state),
`test_resolver_passthrough_parity`, `test_order_plan_planned_status_success_only`,
`test_journal_all_tables_dry_run` (mode/strategy_id/source_system correct),
`test_fail_closed_missing_data`, `test_fail_closed_regime`,
`test_fail_closed_inconsistent_state`, `test_no_broker_import` (static),
`test_determinism_golden_day`, `test_summary_fields`, plus the manual-layer
tests in §13.7.

Injected fakes stand in for the frozen strategy modules so the orchestration,
fail-closed paths, journal writes, CSV handoff, calendar and bootstrap are all
exercised without a live data source.

## 10. Acceptance criteria

- For a valid D, produces `orders_plan_<D+1>.csv` + full journal; **no orders sent**.
- Data source is configurable (DATA06 now, MDSM interface ready); not hardcoded.
- Fail-closed on every defined failure.
- `decision_resolver`/`order_planner`/MLE/sizing **unchanged** (parity test green).
- All journal rows: mode=`dry_run`, strategy_id=`MLE-PAPER-01`, data-source-aware
  `source_system`.
- Deterministic (golden-day).
- Answers all 8 questions (§6).
- Manual fallback (§13): renders a manual report + optional fillable ticket that
  **exactly mirror** the order_plan (no discretionary drift); PAPER/LIVE safety
  checklist + fill-recording instructions present; manual outputs on SUCCESS
  only; `MANUAL_REPORT_GENERATED` event logged.

## 11. Locked OQ decisions

- **OQ-1:** XNYS via `exchangecalendars` (verify presence; if absent, propose the
  smallest safe dependency — no hand-written static holiday list as the final
  solution).
- **OQ-2:** no `--simulate-fills` in MVP; state read-only.
- **OQ-3:** `source_system` data-source aware (see Q6).
- **OQ-4:** CSV handoff + journal parquet; no standalone parquet handoff.
- **OQ-5:** bootstrap from `config/runner_config_dry_run.json`, `dry_run` only;
  paper/live gets state via reconciliation later.

## 12. Implementation dependency — wiring (DECIDED: A, inventory-first)

**Decision (architect 2026-07-15): option A.** The production runner must call the
**real** frozen modules — `decision_resolver`, `signal_source`, `regime_source`,
`portfolio_state`, `order_planner`, and the `DATA06`/`MDSM` reader — through
**thin adapters** in `wiring.py`. Fakes are permitted **only in unit tests**; no
production fake wiring as a final implementation. If an interface is not clean,
write a thin adapter — never duplicate strategy logic.

**Before coding, a short API inventory** documents the real interfaces:

- how `signal_source` is called (inputs, `MLE_TOP10` return shape)
- how `regime_source` is called (inputs, regime return)
- the object `decision_resolver` expects and returns
- the `portfolio_state` format
- the format `order_planner` returns
- where/how `DATA06` is read (and the `MDSM` reader interface for later)

The runner keeps dependency injection so unit tests exercise orchestration with
fakes, while production wiring binds the real modules.

## 13. Manual Execution Fallback

**Requirement:** the strategy must remain tradable **by hand** when broker
integration is unavailable. This is a **rendering + handoff** layer over the
*same* `order_plan`/DecisionResolver output — it adds **no** strategy logic.

### 13.1 What it is / is not

- It renders the identical `order_plan` (same decisions, same sizing) into a
  human-readable report a person can execute manually in TWS.
- It performs **no** discretionary ticker selection, **no** MLE/resolver change,
  and **no** broker submission. Forbidden items are enforced by the same
  passthrough-parity and no-broker-import tests (§9).

### 13.2 Outputs

- `paper_trading/reports/mle_paper_01/dry_run/manual_report_<D+1>.md` — the
  human-readable manual trading report (generated by default; suppress with
  `--no-manual-report`).
- `paper_trading/order_plans/mle_paper_01/dry_run/manual_order_ticket_<D+1>.csv`
  — optional fillable ticket (`--manual-ticket`). It mirrors the order_plan and
  adds blank columns the user fills after executing:
  `actual_fill_price, actual_quantity, actual_timestamp, execution_mode, notes`.
  The ticket therefore doubles as the **manual fill recording sheet** later
  ingested by the reconciliation step.

Both are written **only on SUCCESS** (same rule as the order_plan CSV).

### 13.3 Manual report contents (all required)

- `business_date` D and `target_date` D+1
- regime state (ON/OFF) for D
- portfolio state summary (cash, equity, open positions, free slots)
- **BUY** orders: ticker, conid, target_value, order timing (**next session open**)
- **EXIT** orders: ticker, conid, quantity, order timing (per plan)
- **HOLD** positions: ticker, conid, planned_exit_date, days_held
- **DO_NOTHING / skipped** candidates with reason (incl. SKIP_* reasons)
- warnings / errors
- **PAPER vs LIVE account safety checklist** (§13.4)
- **manual fill recording instructions** (§13.5)

Order timing is rendered from the frozen spec using **timing labels**, not a
concrete order type: BUY = **next session open**; EXIT = **planned exit session
close** (per the plan's `price_source`). The concrete `order_type` is **TBD**
until the execution spec — the report shows *when* and *what*, and never
pre-locks MOO/MOC. The report never invents timing.

### 13.4 PAPER vs LIVE safety checklist (in the report)

A checklist the user ticks **before** entering any order manually, e.g.:

- [ ] TWS account matches the intended account (paper `DU…` vs live `U…`)
- [ ] `data_source` and `business_date`/`target_date` are correct for today
- [ ] this is a **dry_run** plan — confirm intended execution account
- [ ] order timing matches the plan (BUY = next session open; concrete order
      type per the eventual execution spec, not pre-locked here)
- [ ] position sizing not manually altered from `target_value`
- [ ] no tickers added/removed vs the plan

The checklist is static text driven by run metadata (account label, mode); it
adds no logic.

### 13.5 Manual execution flow

```
Daily Runner → orders_plan_<D+1>.csv + manual_report_<D+1>.md [+ ticket]
   → user manually enters trades in TWS (optional)
   → user records actual fills on the ticket (fill price / qty / timestamp)
   → reconciliation step later ingests the ticket → journal fills
        with execution_mode = MANUAL
```

The runner itself records **no fills** (state stays read-only, §1). At plan time
the runner emits a journal event `MANUAL_REPORT_GENERATED`. `execution_mode` is
set to `MANUAL` only when fills are recorded later (reconciliation phase).

### 13.6 `execution_mode` in the journal (OQ-6 — DECIDED: B for MVP)

**Decision (architect 2026-07-15): option B for MVP.** Do **not** change the
frozen TRADING-JOURNAL-01 schema now (it is PASS at 1.0.0, and the runner creates
no fills in MVP). Concretely:

- `fills` schema stays **1.0.0**, unchanged.
- The runner writes only the journal event **`MANUAL_REPORT_GENERATED`**.
- The `manual_order_ticket_<D+1>.csv` **may** carry an `execution_mode` column
  (and manual-fill columns) — this is a handoff artifact, **not** the journal
  schema.
- **Later** (manual fill ingestion / reconciliation phase) a nullable
  `execution_mode` column is added to the `fills` table with a
  `SCHEMA_VERSION` bump to **1.1.0**.

### 13.7 Additional tests for the manual layer

`test_manual_report_contains_required_sections`,
`test_manual_report_matches_order_plan` (report BUY/EXIT/HOLD/skip exactly mirror
the order_plan — no discretionary drift), `test_manual_ticket_has_fill_columns`,
`test_manual_outputs_success_only` (nothing written on STOP),
`test_manual_event_logged` (`MANUAL_REPORT_GENERATED` in journal).

## 14. Status

**Verdict (architect 2026-07-15): APPROVED FOR IMPLEMENTATION AFTER API
INVENTORY.**

- OQ-1..5: locked (§11).
- **OQ-6: DECIDED — B for MVP** (events only; journal schema unchanged; fills
  `execution_mode` deferred to 1.1.0 at reconciliation, §13.6).
- Wiring: **A**, inventory-first, thin adapters, fakes-only-in-tests (§12).
- Timing labels only; no MOO/MOC (§13.3–13.4).

Next action: short API inventory of the real frozen modules, then code.
