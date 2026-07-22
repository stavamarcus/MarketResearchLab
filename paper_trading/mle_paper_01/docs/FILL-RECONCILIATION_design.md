# Fill Recording / Manual Reconciliation — design specification

Status: **APPROVED WITH REQUIRED PATCHES — patches incorporated below; ready for
implementation.** Architect (2026-07-15): close the manual loop. Broker read-only
/ IBKR paper connection deferred (paper account unavailable) — this step is fully
local. OQ-1..7 answered; five required spec patches applied (§ marked
[PATCH]). Code only after this patched spec is signed off.

## 0. Purpose

Complete the manual workflow: after the human enters the Daily Trade Plan's
orders in TWS and fills the ticket with real results, this component ingests the
filled ticket, validates it against the original plan, and — only after a passing
validation and explicit approval — updates the local `PortfolioState` and the
journal so the **next** Daily Trade Plan starts from what was actually traded.

## 1. Scope / non-goals

- **No broker, no IBKR API, no order submission, no auto-execution.**
- Input is a **local filled ticket** (the `manual_order_ticket_<target_date>.csv`
  the Trade Plan produced, with the actual-fill columns filled by the human).
- No strategy change: reconciliation never re-runs the resolver, never picks
  tickers, never substitutes rank 11.
- State is mutated **only** in the explicit apply phase, after validation passes.

## 2. Inputs & authority (OQ-7 — strengthened)

- **Filled ticket** — carries the **actual fill data only**: `actual_quantity,
  actual_fill_price, timestamp, commission_fees, order_id, status`
  (+ `override_reason`, §5). It is human-editable, so its **planned_* fields are
  NOT trusted as authority**.
- **Order plan** `orders_plan_<target_date>.csv` (frozen resolver output) —
  **authority for ticker / side / planned quantity context**.
- **Executability authority** — the **original generated ticket** or the journal
  **`CAPITAL_FEASIBILITY`** event for that `target_date` decides which BUYs were
  executable vs DO NOT BUY. The edited filled ticket is never trusted for this.
- **Current `PortfolioState`** (state.json) — the state to be updated.

Every planned field the reconciliation relies on is re-derived from the plan /
feasibility event, not read from the editable ticket.

## 3. Real fills vs the backtest cost model (OQ-1 = YES)

The frozen `portfolio_state.apply_buy_fill` derives quantity from `target_value`
and models cost as `COST_HALF` (7.5 bps): it is the **backtest / replay** fill,
**not** a real fill. Manual reconciliation has the **actual** integer quantity,
actual fill price and **actual commission/fees**, so it must NOT reuse the
backtest fill. Reconciliation uses a **reconciliation-specific state update** that
reuses the `Position` dataclass + `validate_state` invariant check, but computes
cash from real values:

- BUY: `cash -= actual_quantity * actual_fill_price + commission_fees`
- EXIT: `cash += actual_quantity * actual_fill_price - commission_fees`

(No `COST_HALF` in reconciliation — fees are the real, reported fees.)

## 4. Two-phase safety

1. **Validate (default, read-only)** → produces the mandatory validation report
   (§10); **no state change**.
2. **Apply (explicit `--apply`, only if validation PASSED)** → state backup →
   update state → journal fills + event → reconciliation summary.

If validation FAILS, apply is refused and nothing is written.

## 5. Validation rules (against the plan)

- `ticker` + `conid` must exist in the order plan (no extra / rank-11 tickers).
- `side` must match the planned action for that ticker (BUY vs EXIT).
- **BUY** accepted only if the name was **executable** (per generated ticket /
  `CAPITAL_FEASIBILITY`, §2); a DO NOT BUY / qty=0 name recorded as bought → FAIL.
- **[PATCH 1] BUY on an already-held ticker → FAIL (MVP).** The frozen strategy
  does not re-buy a held name; no automatic extend / average-price in MVP (a
  later, explicit exception may relax this).
- **EXIT** must reference an **existing open position**.
- **[PATCH]** **EXIT `actual_quantity > held_quantity` → hard FAIL** (never create
  a short / negative shares) — not overridable.
- **BUY `actual_quantity > planned_quantity`** → accepted **only** with an
  explicit `override_reason`, a **strong warning**, and an audit
  **`STRATEGY_DEVIATION`** record (OQ-5).
- **[PATCH — OQ-4] Fill session must be `target_date`.** If the fill `timestamp`
  falls on a **different trading session**, validation **FAILs by default**;
  accepted only via explicit `override_reason`. When overridden, the position is
  dated by the **actual fill session**, never falsely by `target_date`.
- Duplicate `order_id` / `fill_id` already applied → skipped (idempotence, §9).

## 6. Status semantics (OQ + [PATCH 2] strict)

- **`filled`** — requires `actual_quantity > 0`, `actual_fill_price > 0`,
  `timestamp` present. Apply the full quantity.
- **`partial`** — same field requirements as `filled`. Apply the actual filled
  quantity.
- **`cancelled`** — `actual_quantity` must be `0` or blank; **no cash/state
  change**. A cancelled row carrying a quantity or price → warning (or FAIL if
  inconsistent).

## 7. State update

- **BUY** → create a `Position`: `shares = actual_quantity`, `entry_price =
  actual_fill_price`, `entry_date = target_date` (normal case; on an accepted
  §5 override, the actual fill session), `planned_exit_date =
  add_sessions(entry_date, 10)` (XNYS, frozen hold10), `signal_rank` from the
  plan; `cash -= actual_quantity*actual_fill_price + commission_fees`. Already
  held → FAIL (PATCH 1), never extend.
- **EXIT** → reduce/close the matching position; `cash +=
  actual_quantity*actual_fill_price - commission_fees`; record realized result.
  **[PATCH 3] Partial EXIT** leaves the **remaining shares open with the original
  `planned_exit_date`**, and the report must flag
  **`PARTIAL EXIT — remaining shares still open, exit-required`** so the next day
  does not forget to sell the remainder.
- **[PATCH 4] Equity** = `cash + mark-to-market of open positions` at the last
  known close. If the current day's close is not yet available, equity is marked
  **`provisional (not marked to close)`**; the next Daily Runner re-marks it to
  close. `cash`, `positions`, `shares`, `entry_price`, `planned_exit_date` are
  authoritative; equity may be provisional.
- Reuses `Position` + `validate_state`; does **not** reuse the backtest
  `apply_buy_fill/apply_exit_fill` (§3).

## 8. Journal (OQ-2 = YES — schema bump 1.0.0 → 1.1.0)

- Populate the `fills` table (schema-only until now) via a **new writer method**
  `write_fill(...)`. `_FILLS` already carries `fill_id, order_id, timestamp,
  ticker, conid, action, quantity, expected_price, fill_price, slippage_bps,
  commission, fees, total_cost_bps, account_id, broker_order_id, status`.
- Add a **nullable `execution_mode`** field to `_FILLS`, set `MANUAL` for
  reconciled fills. Bump `SCHEMA_VERSION` to `1.1.0`. The change is additive
  (nullable column) — **old 1.0.0 journal data stays readable** (reader tolerates
  missing `execution_mode` as NULL).
- Write a `RECONCILIATION` event (target_date, source ticket, applied / skipped /
  failed counts) and, when applicable, `STRATEGY_DEVIATION` records.
- `expected_price` = the plan's `ref_price` (D close estimate); `slippage_bps` /
  `total_cost_bps` derivable from expected vs actual + fees.

## 9. Safety

- Dry **validation report** always produced first (§10).
- **FAIL → no write** (state and journal untouched).
- **State backup** before any write: copy `state.json` →
  `state.json.<timestamp>.bak`.
- **Idempotence (OQ-3 — strengthened)**: key = `order_id`; when `order_id` is
  empty, fall back to a **deterministic `fill_id` hash** of
  `(target_date, ticker, conid, side, actual_quantity, actual_fill_price,
  timestamp)`. Source of truth = journal `fills`; an already-recorded key is not
  applied again (re-running the same ticket is a no-op). For `filled` / `partial`
  rows `order_id` is strongly recommended; an empty `order_id` raises a warning.
- **Audit log**: append-only record of each run (invoked when, ticket path,
  applied / skipped / failed, strategy deviations, resulting cash/equity).

## 10. Outputs

- **[PATCH 5] Mandatory validation report** `reconciliation_report_<target_date>.md`
  produced **before any apply**, containing: **PASS / FAIL**, applied candidates,
  skipped duplicates, warnings, **strategy deviations**, **cash impact estimate**,
  and (on apply) the **state backup path**. FAIL → no write.
- Updated `state.json` (+ timestamped backup) — apply phase only.
- Journal `fills` records (execution_mode = MANUAL) + `RECONCILIATION` (and any
  `STRATEGY_DEVIATION`) events.
- Reconciliation summary (applied / skipped / failed, cash/equity delta; equity
  flagged provisional if not marked to close).

## 11. Placement

New module `mle_paper_01/reconciliation.py` + a CLI **separate from the runner**
(OQ-6): `python -m mle_paper_01.reconcile --ticket <csv> --plan <csv>` validates
only; add `--apply` to write. Reuses `models` (`Position`, `validate_state`),
`journal` (writer + new `write_fill`, schema 1.1.0), `calendar_util`
(`add_sessions`). Not folded into `daily_runner`.

## 12. OQ resolutions (architect 2026-07-15)

- OQ-1 YES — actual quantity / fill price / fees; no COST_HALF (§3).
- OQ-2 YES — fills write + nullable `execution_mode` + schema 1.1.0; 1.0.0 stays
  readable (§8).
- OQ-3 YES, strengthened — idempotence via journal `fills` `order_id`, fallback
  deterministic `fill_id` hash; empty `order_id` → warning (§9).
- OQ-4 CHANGED — fill session must be `target_date`; other session = FAIL unless
  `override_reason`; on override, date by the actual fill session (§5, §7).
- OQ-5 — BUY over planned only with `override_reason` + `STRATEGY_DEVIATION`;
  EXIT over held = hard FAIL (§5).
- OQ-6 YES — validate-only default, `--apply` explicit, separate `reconcile` CLI
  (§11).
- OQ-7 YES, strengthened — order plan authorizes ticker/side; executability /
  planned quantity verified against the original generated ticket or
  `CAPITAL_FEASIBILITY` event, not the editable filled ticket (§2).

## 13. Tests (render/validation-level, no broker)

- Validation: ticker/conid not in plan → FAIL; side mismatch → FAIL; BUY of a
  DO NOT BUY name → FAIL; BUY already-held → FAIL; EXIT of non-held → FAIL; EXIT
  qty > held → hard FAIL; BUY qty > planned → needs override + STRATEGY_DEVIATION;
  wrong-session timestamp → FAIL unless override (then dated by actual session).
- Status: strict field checks for filled / partial / cancelled; cancelled with
  qty/price → warning/FAIL.
- State: BUY cash/position math with real fees; EXIT proceeds; partial EXIT keeps
  remainder open + flag; equity provisional when no close.
- Safety: FAIL → no write; state backup created; idempotence (re-apply = no-op);
  deterministic fill_id hash; audit log appended.
- Journal: `write_fill` writes `execution_mode=MANUAL`, schema 1.1.0; old 1.0.0
  data still readable.
- No broker / IBKR imports (AST scan).
