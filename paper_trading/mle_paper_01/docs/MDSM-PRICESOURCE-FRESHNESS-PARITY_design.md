# MDSM PriceSource + Freshness Gate + DATA06/MDSM Parity — design specification

Status: **DESIGN — awaiting approval. No code until signed off.** Goal: move from
the historical DATA06 test plan to a **current MDSM-backed** paper_manual Trade
Plan, safely and without a silent change of data lineage. Data bridge + safety /
parity reporting only — **no broker orders, no execution, no PortfolioState change
beyond the runner's existing mark-to-market.**

## 0. Context (verified against the uploaded MDSM-Lite)

- MDSM-Lite D1 cache is **current** (`{conid}_D1.parquet`, OHLCV, date index;
  516 conids; `end_date` 2026-07-16; GDU-updated). Same universe file the runner
  already uses.
- **Read contract for D1 EOD is the V1 access layer** `src/access/access_layer.py`
  (`AccessLayer.get_historical(conid, start, end, timeframe="D1",
  cache_only=True) -> DataFrame`). V2 (`access_layer2.py`) is intraday only
  (5min/1min) and is **not** used here.
- **Freshness metadata already exists**: `MetadataManager.read(conid, "D1")`
  returns `end_date`, `last_updated`, `is_valid`, `permissions_status`,
  `start_date`, `rows`. No addition to the access layer is required for the
  freshness gate.
- GDU is run manually by the operator and is out of scope (not built/automated
  here).

## 1. Architecture boundary (hard rule)

    daily_runner -> MdsmPriceSource -> MDSM-Lite AccessLayer (V1, cache_only) -> cache

**No direct parquet reads from the runtime.** `MdsmPriceSource` must obtain all
prices through `AccessLayer.get_historical(..., cache_only=True)`. The runtime
must not know cache paths, the `{conid}_D1.parquet` layout, index/date handling,
or the cache format version — those belong to MDSM-Lite. If the cache changes,
MDSM-Lite/access layer is fixed, not the runner.

## 1a. Inventory of the real runtime pipeline (grounding)

Verified against the current code (`daily_runner.run()`), so this spec assumes
only what actually exists:

- **Price source is used via a small interface** — the runner calls, on the
  built `PriceDataSource`: `metadata()`, `last_completed_session()`,
  `regime_state(D)`, `signal_candidates(D)`, `closes_at(D, tickers)`. That is the
  **entire contract** a data source must satisfy.
- **BUY candidates + TOP10/rank** arise inside `signal_candidates(D)` — the source
  builds price matrices and runs `SignalSource(..., compute_rank_matrix, ...)`,
  where `compute_rank_matrix` is the **injected MLE ranker** (rank_10d). The
  source returns `List[SignalCandidate]`.
- **Regime** arises inside `regime_state(D)` (`RegimeSource(close_m)`).
- **Order plan** is assembled **downstream of the source**, by the existing
  daily_runner order-plan generation path. Verified in the current code: this path
  is the concrete local function `mle_paper_01/decision_resolver.py::resolve(
  candidates, regime, state, target_date) -> List[Decision]` that `daily_runner`
  imports and calls, followed by `capital_feasibility.evaluate_plan(...)` and
  `order_planner.write_orders_plan(...)`. (This lower-case local module is a small
  order-planning function; it is **not** the system-wide future/target "Decision
  Resolver" architecture.)
- **Exact interface MdsmPriceSource must satisfy** = the `PriceDataSource`
  Protocol (`profile`, `last_completed_session`, `signal_candidates`,
  `regime_state`, `closes_at`, `metadata`) — nothing more. MdsmPriceSource is a
  **pure data bridge** and never touches `decision_resolver`, feasibility, or
  `order_planner`.

Note on terminology: a system-wide **"Decision Resolver" is a future/target
architectural concept**, not the thing this data bridge plugs into. The current
runtime contains only a small local module `mle_paper_01/decision_resolver.py`
(a `resolve()` function), verified to exist and be called by `daily_runner`; it
sits **downstream** of the price source and is **not modified** here. This spec
must not assume or depend on the future system-wide Decision Resolver component,
and does not use "Decision Resolver" to mean current runtime code.

## 2. MdsmPriceSource

Implements the existing `PriceDataSource` Protocol so it is a drop-in for
`Data06PriceSource`. The runner needs exactly these (unchanged):
`last_completed_session()`, `signal_candidates(business_date)`,
`regime_state(business_date)`, `closes_at(business_date, tickers)`,
`metadata()`.

Only the **matrix-building step** differs from DATA06. DATA06 builds
`close_m` / `open_m` by reading parquets directly (`load_price_matrices(view_dir,
...)`). MDSM builds the **same** `close_m` / `open_m` (dates x tickers) by calling
the access layer per conid:

- resolve the universe with the **same** `load_universe(universe_path)` (same
  identity mapping ticker<->conid the runtime already uses)
- for each conid, `AccessLayer.get_historical(conid, start, end, timeframe="D1",
  cache_only=True)` -> OHLCV frame; assemble the close and open matrices
- feed the **existing, shared** `RegimeSource(close_m)` and
  `SignalSource(close_m, instruments, t2c, compute_rank_matrix, ...)` — the **MLE
  ranker is injected, never reimplemented**. Everything downstream of the price
  source — the existing `daily_runner` order-plan generation workflow (candidate
  selection, ranking, the local order-planning function
  `mle_paper_01/decision_resolver.py::resolve()`, sizing, hold/exit rules,
  capital feasibility, `order_planner`) — is **untouched**.

Result: identical interface + identical downstream (MLE ranks, regime) as DATA06;
only the source of the price matrices changes (access layer instead of parquet).

New runner config field: `mdsm_project_path` (path to MDSM-Lite, for importing
`AccessLayer` + `Config`), mirroring the existing `mle_project_path`. `view_dir`
is not used by the MDSM source.

Constraints (from the task): must not read parquet cache directly; must not
duplicate MLE ranking; must not change strategy rules, candidate selection, ranking, sizing, hold/exit rules, or the existing order-plan generation logic; must
deliver the same matrices/interface as DATA06; must use the same universe/identity
mapping.

## 3. Freshness gate (data_source = MDSM only)

Before a paper_manual plan is generated on MDSM data, the runner verifies the
cache is current; otherwise it **STOPs / FAILs** — no plan from stale data.

- **Signal**: `MetadataManager.read(conid, "D1").end_date` per conid (the last
  cached session), plus `is_valid` / `permissions_status`. The effective
  freshness = the min/most-common `end_date` across the traded universe.
- **Expected session**: the last completed XNYS session on/before "now" (via the
  runtime calendar). Gate rule: `cache_end_date >= expected_last_session` for the
  universe; else **FAIL** (stale).
- **Coverage**: count conids that are fresh + valid vs missing / stale / invalid;
  a coverage shortfall beyond a threshold -> **FAIL** (or WARN — see OQ-2).
- The gate reads freshness **through the access layer / MetadataManager**, not by
  stat-ing files. Access layer already provides everything needed (§0), so no
  minimal addition is required.
- DATA06 is unaffected (no freshness gate; it is a frozen snapshot by design).

Output: an **MDSM freshness report** (per-universe end_date, coverage, stale /
missing / invalid lists, PASS/FAIL). On FAIL the runner refuses to write a
paper_manual Trade Plan.

## 4. DATA06 vs MDSM parity check

DATA06 = Sharadar lineage; MDSM = IBKR/TWS lineage. Same format, different source.
Before the first real paper_manual plan we must know MDSM is not silently
diverging from the validated DATA06/BT lineage.

Run for an **overlapping historical D** (both sources cover it; overlap window =
up to DATA06's frozen end ~2026-07-05, e.g. D=2026-07-02 / target 2026-07-06 which
we already have on DATA06). Build both sources for that D and compare:

- **universe coverage** and **missing tickers/conids** (each side)
- **close/open availability** at D
- **ref prices** (close at D per ticker) — Sharadar vs IBKR
- **regime200** ON/OFF
- **MLE TOP10** tickers
- **rank order** (1..10)
- resulting **planned BUYs**

Verdicts:

- **PASS** — sufficiently identical: same regime, same TOP10 set, same coverage,
  ref prices within tolerance.
- **WARN** — small, explainable price differences between Sharadar and IBKR
  (e.g. minor close deltas, same TOP10 & regime). Does **not** auto-block, but is
  made **consciously visible** in the report.
- **FAIL** — material difference in TOP10, regime, coverage, or missing data.
  **Blocks** the first paper_manual cycle until the cause is explained.

Output: a **DATA06 vs MDSM parity report** (side-by-side, per-item PASS/WARN/FAIL,
overall verdict).

## 5. Integration boundaries

- No broker order code; no `placeOrder` / `cancelOrder` / `modifyOrder`.
- No live execution.
- No PortfolioState change beyond the runner's existing daily mark-to-market.
- This task is the **data bridge + safety/parity report** only.

## 6. Tests (no live IBKR; fake/small access layer)

- Fake/small access-layer stub returns canned D1 frames -> MdsmPriceSource
  assembles the **expected matrix shape** (dates x tickers), close/open aligned.
- Missing-data handling: a conid with a cache miss / invalid metadata is handled
  (excluded + reported), not a crash.
- **Stale cache -> freshness FAIL**; **fresh cache -> PASS**.
- **daily_runner refuses a paper_manual plan when MDSM data is stale** (freshness
  FAIL -> no Trade Plan).
- Parity PASS / WARN / FAIL rendering (report reflects each verdict).
- **No direct parquet access** from `daily_runner` / `MdsmPriceSource` — AST scan
  asserts no `read_parquet` / `{conid}_D1.parquet` / cache-path usage in those
  modules; all reads go through the access layer.
- MdsmPriceSource matches the `PriceDataSource` Protocol (interface parity with
  DATA06).

## 7. Output artifacts

- **MDSM freshness report** (`mdsm_freshness_<ts>.md` / `.json`).
- **DATA06 vs MDSM parity report** (`data06_mdsm_parity_<date>.md` / `.json`).
- A **Daily Trade Plan with `data_source=MDSM`** — produced **only after the
  freshness gate passes** (and, for the first cycle, after parity is PASS/WARN,
  not FAIL).

## 8. Daily workflow (target)

1. operator runs GDU (manual) -> MDSM-Lite cache updated
2. verify MDSM cache is current (freshness gate)
3. `daily_runner` with `data_source=MDSM`
4. current Daily Trade Plan (paper_manual)
5. then the paper_manual workflow per the runbook

## 9. Open questions

- **OQ-1** — MdsmPriceSource reads D1 via **V1 `AccessLayer.get_historical(...,
  timeframe="D1", cache_only=True)`** and assembles close/open matrices, reusing
  the frozen SignalSource / RegimeSource / MLE ranker (no duplication). Confirm.
- **OQ-2** — freshness coverage shortfall (some conids stale/missing while most
  are fresh): hard **FAIL**, or **WARN + proceed on the fresh subset**? Proposed:
  FAIL if the effective universe end_date is behind the expected session; WARN for
  a small number of individually missing conids. Confirm the thresholds.
- **OQ-3** — parity tolerance for ref prices (WARN band) — proposed e.g. <= 0.5%
  per-ticker close delta with identical TOP10 & regime = WARN; TOP10/regime/
  coverage change = FAIL. Confirm the numbers.
- **OQ-4** — where the freshness gate lives: inside `MdsmPriceSource`
  (`freshness_report()`) with the runner gating on it, vs a separate freshness
  module the runner calls. Proposed: method on the source, runner enforces.
- **OQ-5** — config: add `mdsm_project_path` to the runner config for importing
  the MDSM-Lite access layer; a `config/runner_config_paper_manual.json` variant
  (or the same file) with `data_source: "MDSM"`. Confirm placement.
- **OQ-6** — parity report is a **precondition artifact** for the first cycle
  (run once, reviewed), not a per-day step. Confirm it is one-off (re-run only
  when the data path changes), while the freshness gate runs every day.


## 10. OQ resolutions (architect 2026-07-17)

- **OQ-1** YES — AccessLayer V1, D1, `cache_only=True`.
- **OQ-2** — REVISED (architect 2026-07-17): strict-all-503 is operationally
  impossible (known dead/invalid names never reach the latest session). New
  policy: **PASS_WITH_WARNINGS** if most of the universe is fresh, the
  stale/missing/invalid names are outside the day's BUY/EXIT plan, and the count
  <= 25 of 503. **HARD FAIL** if any BUY/EXIT ticker is not fresh, or the count
  > 25 (GDU clearly did not run). The freshness report lists every
  stale/missing/invalid name (ticker, conid, end_date, reason). Verified on real
  data: 497/503 fresh, 6 tolerated (XOM/HON stale, EXE/PSKY/Q/SNDK invalid) ->
  PASS_WITH_WARNINGS; a stale name inside the plan -> FAIL.
- **OQ-3** — parity PASS / WARN / FAIL graded by impact on **TOP10 / regime /
  plan**: identical TOP10 + regime + coverage with only small explainable price
  deltas = WARN; any TOP10 / regime / coverage change or missing data = FAIL.
- **OQ-4** — `freshness_report()` lives on `MdsmPriceSource`; the runner
  **enforces STOP** on FAIL.
- **OQ-5** — a **separate** `runner_config_paper_manual.json` with
  `data_source = MDSM`.
- **OQ-6** — parity report is a **one-off precondition**; the freshness gate runs
  **every day**.

Status: **APPROVED FOR IMPLEMENTATION** (naming/inventory patch applied; OQ
resolved).
