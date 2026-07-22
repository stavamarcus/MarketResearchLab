# MLE-BT-06 — Whole-Share Execution Reality (specification)

Status: **APPROVED FOR IMPLEMENTATION** (required cost-aware patch applied,
2026-07-15). Owner decisions locked: Model A; validation gate + per-level
fractional baseline; no rank-11 substitution; rank-ascending buys; three skip
reasons; cash-drag/deployment from daily MTM equity; research location; capital
sweep incl. 30k. **Patch applied:** §3 fill accounting is cost-aware (quantity
derived net of BUY cost; cash never negative; exact BT-04R `COST_HALF`
convention on both sides; skip logic includes buy costs; EXIT uses the frozen
sell convention).

## 0. Scope statement (authoritative)

> **BT-06 does not change the strategy signal or DecisionResolver.
> BT-06 tests whether the existing strategy edge survives a realistic
> whole-share fill model.**

This is an execution-realism study, not a strategy change.

## 1. Objective & hypothesis

BT-04R and the prior backtests assume fractional shares
(`quantity = target_value / price`). Real trading without fractions means
`quantity = floor(target_value / price)`, and if `target_value < price` then
`quantity = 0` and the trade cannot be placed cleanly.

Hypothesis to test: **does the edge survive whole-share execution, and from
what capital level does whole-share reality stop degrading it?**

## 2. Frozen vs changed

**Frozen (unchanged, reused as-is):** MLE TOP10 signal (`signal_source`),
regime200 (`regime_source`), `decision_resolver.resolve` (still emits
`target_value`), `max_positions = 10`, `target_weight = 0.10`, BUY at next
open, EXIT at planned_exit_date close, hold10, 15 bps round-trip.

**Changed (only this):** the fill/accounting layer, parameterised by
`fill_mode ∈ {fractional, whole_share}`.

## 3. Fill model — Model A (no intra-day cash recycling)

The DecisionResolver computes `target_value` exactly as today. The fill layer
only rounds quantity down; leftover cash is **not** recycled into other buys the
same day. Quantity is derived **cost-aware** (net of costs) so cash can never go
negative.

### 3.1 Cost convention (frozen — reused exactly, not reinterpreted)

BT-06 uses the **exact BT-04R cost constants and formulas** from
`mle_paper_01/models.py` + `portfolio_state.py`. Do not reinterpret "15 bps":

- `COST_BPS_ROUND_TRIP = 15`; `COST_HALF = 7.5 bps = 0.00075` **one-way**,
  applied on **each** side (round-trip 15 bps).
- The frozen BUY already derives quantity net of cost:
  `qty = spend / (price · (1 + COST_HALF))`, `cash_debit = qty · price · (1 + COST_HALF)` (`= spend`).
- The frozen EXIT: `proceeds = shares · price · (1 − COST_HALF)`, `cash += proceeds`.

The harness must reuse these exact formulas. If the cost convention differs in
any way, the harness is invalid (§6 gate catches it).

### 3.2 BUY, in rank-ascending order (rank 1 first)

1. `price = open_D+1[ticker]`. If missing → **skip `DATA_MISSING`**.
2. `budget = min(decision.target_value, available_cash)`.
   The `min` only ever *reduces* — it never raises target_value with leftover
   (Model A invariant). In correct operation `budget == target_value` (the
   resolver already caps `sum(target_value) ≤ cash`; whole_share spends even
   less, so `available_cash` is always ≥ the fractional path — the belt never
   binds in Model A, it only guards).
3. `max_notional = budget / (1 + COST_HALF)`
   - `fractional`:  `qty = max_notional / price`
   - `whole_share`: `qty = floor(max_notional / price)`
4. If `qty < 1` (whole_share):
   - if `floor(decision.target_value / (price · (1 + COST_HALF))) < 1`
     → **skip `TOO_EXPENSIVE_FOR_TARGET`** (the 10% target itself, net of cost,
     cannot buy one share)
   - else → **skip `INSUFFICIENT_CASH`** (target could, but remaining cash cannot)
5. `notional = qty · price`; `cost = notional · COST_HALF`;
   `cash_debit = notional + cost = qty · price · (1 + COST_HALF)`;
   `available_cash -= cash_debit`.

Because `qty · price · (1 + COST_HALF) ≤ budget ≤ available_cash`, cash never
goes negative, and the position (incl. cost) never exceeds `target_value`.

### 3.3 EXIT

Sells the **actual held whole quantity** (positions are integer in whole_share
mode → clean):

`exit_notional = qty · close_price`; `exit_cost = exit_notional · COST_HALF`;
`cash_credit = exit_notional · (1 − COST_HALF)`; `available_cash += cash_credit`.

### 3.4 Recommended implementation (to guarantee the §6 gate)

For `fractional` mode, **reuse the frozen `apply_buy_fill` / `apply_exit_fill`
directly**. For `whole_share`, use a variant that computes
`qty = floor(target_value / (price · (1 + COST_HALF)))` and then applies the
**same** cash math as the frozen fill. This keeps one cost convention across
both modes.

## 4. Skip taxonomy (must be tracked separately)

- `TOO_EXPENSIVE_FOR_TARGET` — `price > target_value`: the 10% target cannot buy
  one share. **Primary metric of interest.**
- `INSUFFICIENT_CASH` — target could afford ≥1 share but remaining cash cannot.
- `DATA_MISSING` — no D+1 open for the ticker.

A skip leaves the slot **empty** — no substitution to rank 11+ (frozen strategy
is TOP10, not top-N fill-down). Fewer than 10 positions on such days is a
measured outcome, not an error.

## 5. Capital sweep & run matrix

Capital levels: **3k, 5k, 10k, 25k, 30k, 50k, 100k, 250k**.
`target_weight = 10%` applied to current (marked-to-market) equity at each level.

Run matrix = 8 levels × 2 fill modes = **16 runs**. Every level runs **both**
`fractional` and `whole_share`, so the delta isolates the fractional→whole
effect at that level (not confounded with the capital-level effect). We compare
whole-share@Xk against fractional@Xk — never against fractional@100k.

## 6. Validation gate (must pass before whole-share numbers are trusted)

The BT-06 harness in `fractional` mode must **reproduce BT-04R exactly**:
337.652 % total / CAGR 34.504 % / maxDD −32.7 % / Sharpe 1.182 / 990 trades /
exposure 0.787 (at 100k, the BT-04R capital). Reproduction must hold **including
costs** — the fractional path reuses the frozen cost formulas (§3.1). If the
cost convention differs in any way, or the numbers do not reproduce, the harness
is wrong and whole-share results are invalid. This gate runs first.

## 7. Metrics & report layout

Per capital level, reported for **fractional**, **whole_share**, and **delta**
(whole_share − fractional):

- total return, CAGR, Sharpe, maxDD
- number of trades, average exposure
- **cash_drag** = mean(daily `cash / equity`), from daily marked-to-market equity
- **deployment_ratio** = mean(daily `1 − cash/equity`)
- average number of open positions
- days at 10/10 vs days < 10/10
- BUY skips broken down by reason (TOO_EXPENSIVE_FOR_TARGET / INSUFFICIENT_CASH /
  DATA_MISSING)

Top of report: a summary "edge vs capital" table answering the headline
question — at what capital does whole-share stop destroying the edge.

The report must clearly separate the three views:
`fractional baseline` · `whole-share reality` · `delta`.

## 8. Location & structure

Research/backtest problem — **not** runtime/manual. Fits the existing backtest
collection (one file per backtest, `mle_bt_0X_*.py`):

```
MarketResearchLab/reports/backtests/MLE-BT-06_whole_share_spec.md   (this file)
MarketResearchLab/research_projects/tests/mle_bt_06_whole_share_reality.py  (harness, after sign-off)
```

The reference BT-04R backtest lives alongside at
`research_projects/tests/mle_bt_04r_causal_execution_correction.py` — the §6
gate validates against it directly.

Reuses frozen `signal_source`, `regime_source`, `decision_resolver`,
`portfolio_state` from `paper_trading/mle_paper_01/` unchanged; the whole-share
fill layer is new and local to BT-06. Does **not** live in `paper_trading/`.

## 9. Acceptance criteria

- Fractional mode reproduces BT-04R (§6) — hard gate.
- Whole-share mode implements Model A exactly (§3), with the three skip reasons
  (§4) and no rank-11 substitution.
- 16-run matrix (§5) produced with the full metric set (§7), split
  fractional / whole-share / delta.
- No change to signal, regime, or DecisionResolver (§2).

## 10. Deferred / out of scope

- **Model B** (intra-day cash recycling on actual remaining cash) — a later
  experiment, not this gate.
- Implementation approach (extend replay vs standalone loop) — decided at
  implementation; whichever is chosen must satisfy the §6 reproduction gate.
- All paused runtime/manual/execution work remains paused until BT-06 answers
  the survival question.
