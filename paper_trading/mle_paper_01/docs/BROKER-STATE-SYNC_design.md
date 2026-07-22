# Broker State → PortfolioState Sync — design specification

Status: **APPROVED FOR IMPLEMENTATION (OQ-1..5 answered).** Step 5 in the
architect's safe sequence. Builds on the passed read-only broker check
(DUQ199078, paper, equity/cash read OK). **Read-only vs the broker: no orders,
no placeOrder/cancel/modify.** The only write is to the LOCAL `state.json`, and
only under explicit confirmation.

## 0. Purpose

Replace the bootstrap `starting_equity = 30000` with the **real account state**
read from IBKR Paper, so the Daily Trade Plan starts from what the account
actually holds. Concretely: read `equity` / `cash` / `positions` via the
existing read-only broker adapter and produce (on confirmation) a
`PortfolioState` seeded from reality.

## 1. Scope / non-goals

- **Read-only vs the broker.** Reuses the step-4 `BrokerReadOnly` interface +
  `ibapi` adapter. No order methods, no execution.
- Writes only the local `state.json` (the runtime `PortfolioState`), and only in
  an explicit apply phase after a validation report (same two-phase pattern as
  reconciliation).
- Not in scope: trading, order placement, the daily run itself. This only seeds
  the state the runner will then use.

## 2. The core problem — broker positions lack strategy metadata

The broker reports a position as `symbol, conid, quantity, avg_cost`. But
`PortfolioState.Position` needs strategy metadata the broker does not know:
`entry_date`, `planned_exit_date`, `signal_rank`, `regime_at_entry`. A blind
1:1 map would fabricate these and corrupt the hold/exit logic (the runner would
not know when to exit an imported position).

Design stance (MVP): the sync is **safe only for a flat account** and for
seeding equity/cash. Positions are handled as follows:

- **0 positions (current case)** → clean seed: `PortfolioState` with the real
  `cash`, `equity`, empty positions. This is the immediate need.
- **Positions present** → do **not** fabricate metadata. Options (OQ-2):
  (a) **HARD FAIL** with a clear message ("account holds positions the local
  state doesn't know; reconcile manually first") — safest MVP; or
  (b) import positions but mark them `imported` with `entry_date = today`,
  `planned_exit_date = unknown/None`, and flag them as **exit-required /
  metadata-missing** so the operator resolves them. Proposed: **(a) for MVP**,
  (b) later.

## 3. Two-phase safety

1. **Validate / preview (default, read-only both sides)** → produce a sync
   report: what the broker shows, what the local state currently is, the diff,
   and what the apply would write. **No local write.**
2. **Apply (explicit `--apply`)** → back up the existing `state.json`
   (`state.json.<ts>.bak`), write the new seeded `PortfolioState`,
   `validate_state`. Only if validation passes.

## 4. Reconciliation vs. seeding (which mode)

Two distinct situations the spec must separate:

- **Seed / bootstrap** — no local state yet (or empty). Take broker equity/cash
  as the starting truth. This is today's need.
- **Drift check** — a local state already exists. Then the sync must **compare**
  local vs broker (cash, equity, position set) and **report drift**, NOT silently
  overwrite. Overwriting a live local state from the broker could erase strategy
  metadata (entry/exit dates). Proposed: drift → report + require explicit
  `--apply --overwrite` acknowledgement (OQ-3).

## 5. Safety gates

- Reuses the step-4 safety gates first (account match, not-live, paper prefix,
  timeout) — a sync never runs against an unverified/live account.
- **Equity vs cash sanity**: if `positions == 0`, expect `equity ≈ cash`
  (small residual OK); a large mismatch with no positions → WARNING.
- **Existing local state present** → never overwrite without explicit
  acknowledgement (§4 drift).
- **Positions present** → MVP HARD FAIL (§2) unless the operator opts into the
  import path.
- All broker-side operations remain read-only.

## 6. What it reads / writes

Reads (via broker adapter): `account_id`, `equity` (net liquidation), `cash`,
`positions`, timestamp, connection meta — same as the step-4 check.

Writes (apply phase only): local `state.json` = `PortfolioState(cash=<broker
cash>, equity=<broker equity>, positions=<empty for MVP flat account>,
last_updated_date=<today>)`, plus a `state.json.<ts>.bak` backup.

## 7. Outputs

- `broker_state_sync_<timestamp>.md` + `.json`: broker snapshot, current local
  state (if any), the diff, validation verdict (PASS/FAIL), and — on apply — the
  backup path and the written state summary.
- No journal event in this step (consistent with step 4), unless the architect
  wants a `STATE_SYNC` event (OQ-4).

## 8. Placement

New module `mle_paper_01/broker_state_sync.py` (or under `broker/`), reusing
`broker/check.py`'s safety gates, `broker/ib_readonly.py` (real reads),
`portfolio_state` (`load_state`/`save_state`/`validate_state`), `calendar_util`.
CLI: `python -m mle_paper_01.broker_state_sync --config ... [--apply]`.

## 9. Tests (fake adapter, no live TWS)

- Flat account seed → `PortfolioState` cash/equity match broker; positions empty;
  `validate_state` passes.
- Apply writes `state.json` + creates backup; validate-only writes nothing.
- Existing local state + no `--overwrite` → drift reported, no write.
- Positions present (MVP) → HARD FAIL, no write.
- Equity≠cash with 0 positions → WARNING.
- Reuses step-4 gates: account mismatch / live → HARD FAIL (no sync).
- Report renders PASS/FAIL; JSON matches MD.

## 10. Open questions

- **OQ-1** — MVP handles the **flat account** (0 positions) as a clean seed of
  cash/equity. Confirm this is the immediate target (matches your current
  0-position paper account).
- **OQ-2** — positions present: **HARD FAIL** for MVP (safest), or import with
  `imported` flag + missing-metadata warning? Proposed HARD FAIL.
- **OQ-3** — existing local state: drift → **report only**, overwrite requires
  explicit `--apply --overwrite`. Confirm.
- **OQ-4** — journal: no event this step (like step 4), or record a `STATE_SYNC`
  event? Proposed: none for now.
- **OQ-5** — RESOLVED: keep `starting_equity` **only as a development fallback**.
  Priority: (1) existing synced `PortfolioState`, (2) `broker_state_sync` apply,
  (3) `starting_equity` fallback only for pure dry_run/dev bootstrap when no state
  exists and no broker sync has been applied. **For paper/manual mode, if a synced
  `state.json` exists, the runner must use it and ignore `starting_equity`.**

## 11. OQ resolutions (architect 2026-07-17)

- OQ-1 YES — MVP targets the flat-account seed (0 positions → cash/equity seeded,
  positions []). Matches the current paper account.
- OQ-2 — positions present = **HARD FAIL** for MVP; no automatic import (no
  fabricated strategy metadata).
- OQ-3 YES — existing local state drift = report only; overwrite requires
  `--apply --overwrite`.
- OQ-4 — no journal event this step; `.md` + `.json` audit report is enough.
- OQ-5 — `starting_equity` is a dev fallback only; synced `state.json` has
  priority and, when present in paper/manual mode, `starting_equity` is ignored.
