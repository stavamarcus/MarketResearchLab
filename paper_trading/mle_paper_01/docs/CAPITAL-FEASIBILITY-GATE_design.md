# Capital Feasibility Gate — design specification

Status: **APPROVED FOR IMPLEMENTATION** (architect 2026-07-15). Direction +
OQ-1..4 approved; cash-awareness patch applied (`available_cash_for_buys` +
rank-order cash simulation); runtime-state source semantics made explicit
(§2.1: `equity = PortfolioState.equity`, `available_cash_for_buys =
PortfolioState.cash`, gate must not assume `cash == equity`). The delivered
implementation already honours this (runner passes `state.equity` and
`state.cash` independently). Paper connection check deferred — the gate is
finished first as a clean runtime component over `PortfolioState`.

## 0. Purpose

A runtime component of the Daily Offline Runner that, each day at plan time,
classifies whether today's whole-share order_plan is executable at the account's
actual equity, and surfaces the feasibility metrics for the human/execution
handoff. It is the runtime analogue of what MLE-BT-06 measured historically,
applied to a single day's plan.

## 1. Scope / non-goals (authoritative)

> This gate does not alter resolver decisions. It classifies the whole-share
> executability of today's plan. It may mark BUY decisions as non-executable
> for the human/execution handoff, but it does not substitute rank 11+ and does
> not resize or recycle cash.
>
> All quantities are estimates based on D close. Actual D+1 open execution must
> be reconciled from real fills.

Concretely, the gate is **render/analysis-only**: no change to
signal / regime / DecisionResolver, no broker, no order submission, no state
mutation. It reads the plan and reports.

## 2. Inputs (all available at plan time D)

- `equity` — **`PortfolioState.equity`**, marked to close D (cash + market value
  of open positions).
- `available_cash_for_buys` — **`PortfolioState.cash`**: free cash available for
  new BUYs after close D, after accounting for open positions. **Required.**
  Feasibility is not just "does each name fit 10% of equity" but "does the free
  cash cover the BUYs".
- BUY decisions from the resolver: `ticker`, `conid`, `target_value`
  (= `target_weight * equity`)
- `ref_price[ticker]` = **D close** — proxy for the D+1 open (the actual fill
  price is unknown at plan time). Every output is labelled
  *"estimated using D close; actual D+1 open may differ."*
- Frozen constants: `COST_HALF = 0.00075` (7.5 bps), `target_weight = 0.10`

### 2.1 Runtime-state source semantics (mandatory)

`equity` and `available_cash_for_buys` are **two independent inputs** and the
gate **must not assume `cash == equity`**. Both come from the same
`PortfolioState` the runner uses for `resolve` (from
`runtime_state.load_or_bootstrap` → `mark_to_market` at close D):

- `equity = PortfolioState.equity`
- `available_cash_for_buys = PortfolioState.cash`

In a fresh bootstrap `dry_run` with no open positions they happen to be equal
(`cash == equity`), but that is a coincidence of the empty portfolio — **not** an
invariant. Once positions are held, `cash < equity` (the difference is the
market value of positions); the gate must size BUYs against `cash`, while
`target_value` still scales with `equity` (10% of equity, from the resolver).

`starting_equity` in the runner config is only the **dry_run bootstrap seed**
(used when no state file exists yet) — not a fixed strategy value. Real runtime
equity/cash come from the account / `PortfolioState`, not the config.

## 3. Per-BUY computation — rank-order cash simulation

BUYs are evaluated **in rank order (rank 1 → rank 10)**, carrying a running
`remaining_cash`, mirroring the whole-share Model A fill from BT-06 (no
recycling, no rank-11 substitution):

```
remaining_cash = available_cash_for_buys
for each BUY in rank order, P = ref_price:
    if P is missing:              -> NO_REF_PRICE (skip, remaining_cash unchanged)
    budget          = min(target_value, remaining_cash)
    indicative_qty  = floor(budget / (P * (1 + COST_HALF)))
    if indicative_qty < 1:
        if floor(target_value / (P * (1 + COST_HALF))) < 1:
                                  -> TOO_EXPENSIVE       (capital-size problem)
        else:
                                  -> INSUFFICIENT_CASH   (cash/order/state problem)
        skip (no debit)
    else:
        estimated_debit = indicative_qty * P * (1 + COST_HALF)
        remaining_cash -= estimated_debit
        executable
```

Derived per executable BUY:
- `estimated_unused_target = target_value - estimated_debit`
- `max_price_for_estimated_qty = target_value / (indicative_qty * (1 + COST_HALF))`
  (`null` when `indicative_qty == 0`) — OQ-1
- `min_equity_for_name = (P * (1 + COST_HALF)) / target_weight`

**Non-executable reason taxonomy (must be distinguished):**
- `TOO_EXPENSIVE` — `target_value` alone cannot buy one share incl. cost →
  **capital-size** problem (raise account equity to fix).
- `INSUFFICIENT_CASH` — `target_value` could buy ≥1 share, but the running
  `remaining_cash` cannot → **cash / ordering / account-state** problem (not a
  capital-size problem).
- `NO_REF_PRICE` — no D close for the name.

## 4. Plan classification (OQ-2 — advisory, not blocking)

- `EXECUTABLE` — every BUY has `indicative_qty >= 1`
- `PARTIAL` — some BUYs `>= 1`, some `= 0`
- `NOT_EXECUTABLE` — no BUY can be placed

The gate is **advisory**: it never blocks the whole plan because one TOP10 name
is unbuyable (skipping such a name and leaving the slot empty is the defined
whole-share behaviour, per BT-06). But advisory ≠ ignore: any `indicative_qty = 0`
name (whatever the reason — TOO_EXPENSIVE / INSUFFICIENT_CASH / NO_REF_PRICE) is
flagged in the handoff as
**`DO NOT BUY / NO EXECUTABLE WHOLE-SHARE ORDER`** with its reason, so the
handoff never tells a human to buy something with `qty = 0`.

## 5. Plan-level outputs (the four required)

1. **EXACT WHOLE-SHARE PLAN status** — `EXECUTABLE / PARTIAL / NOT_EXECUTABLE`
   (§4), with the list of non-executable names.
2. **min operational capital estimate** =
   `max over today's BUY names of min_equity_for_name`
   — the equity needed to buy every name in today's plan (today-specific).
3. **TOO_EXPENSIVE risk** — count + list of today's BUY names with
   `indicative_qty < 1` due to **TOO_EXPENSIVE** (capital-size).
4. **INSUFFICIENT_CASH** — count + list of today's BUY names skipped because the
   running `remaining_cash` could not fund one share (even though `target_value`
   could).
5. **estimated rounding drag** (OQ-3 — this name, not generic cash_drag):
   - `intended_buy_budget = Σ target_value` over today's BUYs
   - `estimated_actual_buy_debit = Σ estimated_debit`
   - `estimated_rounding_drag = 1 - estimated_actual_buy_debit / intended_buy_budget`
   - `estimated_unused_buy_budget = intended_buy_budget - estimated_actual_buy_debit`
   Labelled **"Estimated rounding drag on today's BUYs"** — today's plan
   estimate, not the BT-06 period-average portfolio cash_drag.
6. **estimated_remaining_cash_after_buys** = `remaining_cash` at the end of the
   rank-order simulation (cash left uninvested after all executable BUYs).
7. **estimated_cash_shortfall** = `max(0, Σ (P·(1+COST_HALF)) over
   INSUFFICIENT_CASH names − estimated_remaining_cash_after_buys)` — approximate
   extra cash today's plan would have needed to also place the cash-blocked
   names; `0` when there are none.

Advisory warnings: `equity < 10_000` → *"below BT-06 tested minimum operational
capital (10k)"*; any TOO_EXPENSIVE / INSUFFICIENT_CASH / NO_REF_PRICE name →
warning listing them; and an explicit **status warning when the plan is `PARTIAL`
or `NOT_EXECUTABLE`** (so the handoff surfaces reduced executability at the
plan level, not only per name).

## 6. Manual report / ticket columns (OQ-4)

Per BUY, the manual report and ticket show:

| column | meaning |
|---|---|
| target_value | resolver target (10% equity) |
| ref_price (D close) | estimate basis |
| indicative_qty | `floor(target_value / (P*(1+COST_HALF)))` |
| estimated_debit | `indicative_qty * P * (1+COST_HALF)` |
| estimated_unused_target | `target_value - estimated_debit` |
| max_price_for_estimated_qty | §3 |
| non_executable_reason | none / TOO_EXPENSIVE / INSUFFICIENT_CASH / NO_REF_PRICE; if set → `DO NOT BUY / NO EXECUTABLE WHOLE-SHARE ORDER` |

With the standing note:
**"Indicative qty based on D close, not guaranteed D+1 open fill qty."**

## 7. Integration

- New module `mle_paper_01/capital_feasibility.py` — pure functions
  (`evaluate_plan(equity, available_cash_for_buys, buys, ref_prices) ->
  FeasibilityReport`).
- `daily_runner` calls it after `resolve` / `write_orders_plan`, passing
  `equity = PortfolioState.equity` and `available_cash_for_buys =
  PortfolioState.cash` (independently — §2.1); adds a
  **Capital Feasibility** section to the manual report; writes a journal event
  `CAPITAL_FEASIBILITY` with the plan status + the four outputs; appends a
  warning to `warnings` when `PARTIAL` / `NOT_EXECUTABLE` or `equity < 10k`.
- No change to resolver / signal / regime; no broker; journal schema unchanged
  (event only, consistent with OQ-6 = events for MVP).

## 8. Edge cases

- BUY name missing a D close → mark `ref_price` unknown → treat as
  non-executable-for-estimate with reason `NO_REF_PRICE` (distinct from
  TOO_EXPENSIVE); does not crash the plan.
- `NOT_EXECUTABLE` (all names unbuyable) is possible only at implausibly low
  equity; still advisory (plan is produced, handoff flags everything).
- Estimates use D close; the report states actuals reconcile from real D+1
  fills — the gate never claims the qty is guaranteed.

## 9. Acceptance criteria

- Rank-order cash simulation over BUYs carrying `remaining_cash` from
  `available_cash_for_buys` (matches BT-06 Model A: `min(target_value,
  remaining_cash)`, floor, no recycle, no rank-11).
- Reproduces the required outputs; per-name math matches BT-06's
  `floor(budget/(P*(1+COST_HALF)))`.
- Advisory only: never blocks or resizes; never substitutes rank 11+.
- `indicative_qty = 0` names are marked DO NOT BUY in the handoff, with the
  correct reason.
- `estimated_rounding_drag` uses today's BUYs only (not period cash_drag);
  `estimated_remaining_cash_after_buys` and `estimated_cash_shortfall` reported.
- Unit tests: EXECUTABLE / PARTIAL / NOT_EXECUTABLE; the three-way reason split
  **TOO_EXPENSIVE vs INSUFFICIENT_CASH vs NO_REF_PRICE** (incl. a case where the
  same name is buyable by target but blocked by cash → INSUFFICIENT_CASH);
  rank-order cash exhaustion; rounding-drag and shortfall math; no
  resolver/broker calls (AST scan). Includes an **`equity != cash`** case
  (e.g. equity 30k, cash 8k) proving the gate sizes against cash, not equity.

### 9.1 Dry-run verification matrix (before Trade Plan / manual flow)

After implementation, verify the gate in `dry_run` across states, then proceed:

- equity 10k / cash 10k (bootstrap) — at/near minimum operational capital.
- equity 30k / cash 30k (bootstrap) — Marcus's working capital.
- **equity 30k / cash 8k** (positions held) — the `cash != equity` case: BUYs
  must be sized against the 8k cash; expect INSUFFICIENT_CASH / PARTIAL when the
  targets (10% of 30k = 3k each) exceed the free cash.

Paper connection check remains deferred; the gate is finished first as a clean
runtime component over the local `PortfolioState`.

## 10. Open items

- None blocking. Concrete `order_type` for the eventual real execution remains
  TBD (as in the runner design) — the gate only estimates quantities.
