# API Inventory — frozen MLE-PAPER-01 modules

Read from the real source (2026-07-15). Documents the interfaces the Daily
Offline Runner binds to via thin adapters, and the wiring decisions that follow.

## Data contracts (`models.py`, frozen dataclasses)

- `SignalCandidate(ticker: str, conid: int, rank_10d: int)` — rank 1..10.
- `RegimeState(date: str, regime_on: bool, index_level, ma200, valid_constituents)`.
- `Position(ticker, conid, shares, entry_date, entry_price, planned_exit_date, signal_rank, regime_at_entry=True, status=OPEN)`.
- `PortfolioState(cash, equity, positions=(), closed_trades=(), last_updated_date="")` with `.open_positions()`.
- `Decision(action, target_date, reason, ticker, conid, target_value, quantity, price_source)` — strict `__post_init__` invariants; `Action{BUY,EXIT,DO_NOTHING}`, `PriceSource{NEXT_OPEN,CLOSE}`.
- Constants: `MAX_POSITIONS=10`, `TARGET_WEIGHT=0.10`, `COST_BPS_ROUND_TRIP=15`, `COST_HALF=7.5bps`.

## Strategy modules (called as-is)

- `decision_resolver.resolve(mle_top10, regime, portfolio, target_date) -> List[Decision]` — pure function. Enforces (fail-fast): `regime.date < target_date`; **`portfolio.last_updated_date == regime.date`**; `cash >= 0`; `<=10` open; no dup tickers; no stale positions (`planned_exit_date < target_date`); candidates `rank_10d in 1..10`.
- `portfolio_state.mark_to_market(state, closes: Mapping[str,float], date) -> PortfolioState` (sets `equity`, `last_updated_date`); `apply_buy_fill(...)`, `apply_exit_fill(...)` (runner does NOT use — no fills); `save_state(state, path)`, `load_state(path)`.
- `order_planner.write_orders_plan(decisions, out_dir) -> Path` → **`orders_plan_<target_date>.csv`**; columns `date,ticker,conid,action,quantity,target_value,reason,price_source`. Reused as-is (not reimplemented).

## Data / signal modules (wrapped by the DATA06 adapter)

- `signal_source.load_universe(csv) -> (instruments, t2c, t2i, t2s)`.
- `signal_source.load_price_matrices(view_dir, instruments, t2c) -> (close_m, open_m)` — reads DATA-06 `{conid}_D1.parquet`.
- `signal_source.SignalSource(close_m, instruments, t2c, compute_rank_matrix, cache_path=None, recompute=False).candidates(D) -> List[SignalCandidate]` — MLE TOP10; window D-45..D; `compute_rank_matrix` injected.
- `regime_source.RegimeSource(close_m).state(D) -> RegimeState`.

## External dependency

MLE ranker: `MarketLeadershipEngine/src/engines/rank_matrix_engine.compute_rank_matrix`
— injected via `sys.path` (never reimplemented in the runner).

## Data paths (defaults from `replay_engine.py`, made configurable)

- universe: `C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv`
- DATA-06 view: `C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view`
- MLE engine: `C:\Users\stava\Projects\MarketLeadershipEngine`

## Wiring decisions (consequences for the runner)

1. **Mark-to-market before resolve.** Because `resolve` requires
   `portfolio.last_updated_date == regime.date == D`, the runner must
   `mark_to_market(state, closes_D, D)` before calling `resolve`. Bootstrap
   state must also be marked to D. If any open position lacks a valid close at
   D → STOP (fail-closed), no orders_plan.
2. **Reuse `write_orders_plan`** → output name `orders_plan_<D+1>.csv`
   (the frozen convention; not `order_plan_<D+1>.csv`).
3. **MLE ranker stays external** — DATA06 adapter injects `compute_rank_matrix`;
   no local rank_10d logic.
4. `last_completed_session()` = max date in the close matrix (data-driven).
   `target_date` D+1 = next XNYS session (label only; no D+1 data loaded).
5. `planned_exit_date` for new BUYs = 10 sessions after fill; assigned at
   fill time (execution/reconciliation), not by the runner.
6. Bootstrap `starting_equity = 30_000` (dry_run → paper account), vs the
   replay's 100k (backtest reproduction).

## Journal note

To record per-table `source_system` (signals=DATA06, decisions/order_plans=
DAILY_RUNNER, positions=RUNTIME_STATE), the JournalWriter gained an optional
`source_system` override per write call — a backwards-compatible, schema-neutral
addition (SCHEMA_VERSION unchanged; existing journal tests still pass).
