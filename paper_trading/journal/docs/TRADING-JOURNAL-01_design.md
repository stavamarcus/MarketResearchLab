# TRADING-JOURNAL-01 — Implementation Design

**Status:** APPROVED WITH MINOR CHANGES (architect, 2026-07-15) — changes incorporated below.
**Module:** `MarketResearchLab/paper_trading/journal/`
**Data root:** `MarketResearchLab/paper_trading/journal_data/` (git-ignored)
**Later migration:** `TradingRuntime/trading_runtime/journal/`

## 1. Purpose and hard rules

A **side-effect-only** trading / audit layer that records what the system
did each day and why, so the edge can later be analysed out-of-sample
(which ranks paid off, did regime help, how much slippage cost, simulated
vs paper vs live fills).

Invariants (must never be violated):

- The journal **must not change the replay result** (BT-04R stays bit-exact).
- The journal **must not modify the strategy** or `DecisionResolver`.
- The journal **must not import** any broker / order-execution module.
- The journal is **append-only** — history is never mutated or overwritten.

## 2. Identifiers (in every table and every event row)

| Column | Meaning |
|---|---|
| `strategy_id` | e.g. `"MLE-PAPER-01"` |
| `run_id` | `YYYYMMDDTHHMMSS_<8 hex>`, unique per run, shared by all tables of that run |
| `schema_version` | `"1.0.0"` (see §7) |
| `mode` | `replay` / `dry_run` / `paper` / `live` |
| `created_at` | UTC ISO-8601, stamped per record at write time |
| `source_system` | provenance: `REPLAY` / `MDSM` / `DATA-06` / `IBKR_PAPER` / … |

The writer injects all six automatically; callers never supply them.

## 3. Directory layout

`mode` is the top-level separator, so `live/` never shares a file with
`paper/`. Within a mode, tables are date-partitioned and each run writes
its own file (append-only at the file level).

```
journal_data/
  replay/
    daily_state/date=YYYY-MM-DD/run_id=<run_id>/part.parquet
    signals/    date=YYYY-MM-DD/run_id=<run_id>/part.parquet
    decisions/  …   order_plans/…   fills/…   positions/…   trades/…
    events/events_YYYY-MM.jsonl
    reports/daily_report_YYYY-MM-DD.md      # v1.1 — NOT produced in v1
  paper/   … same structure …
  live/    … same structure …
```

A *run* = one runtime execution. A daily paper run writes one business
date; a full replay writes many `date=…/run_id=<same>` partitions under a
single `run_id`.

## 4. Tables (v1)

`daily_state`, `signals`, `decisions`, `order_plans`, `fills`,
`positions`, `trades` (parquet) + `events` (JSONL). Columns follow the
architect's schema; the six identifiers of §2 are prepended to each.

Key decisions:

- **`order_plans` status** — append-only forbids mutation, so v1 stores a
  terminal dry-run status (`PLANNED` / `SKIPPED`). The `SENT → FILLED`
  transitions are **event-sourced** in the paper-execution phase (a new
  `events` row per transition, keyed by `order_id`), never an overwrite.
- **`fills`** — schema-only in v1; populated in the paper-execution phase.
- **`trades.mfe_pct` / `trades.mae_pct`** — nullable, **left NULL in the
  MVP**. The writer does **not** compute trade metrics (it stays a passive
  recorder). A later analytic job derives MFE/MAE from `positions`
  snapshots.
- **`signals.source`** is kept for signal-level data provenance, alongside
  the record-level `source_system`.
- **Empty tables** — a day with no rows for a table writes an
  empty **schema-correct** parquet file ("ran, nothing happened" beats a
  missing file). See `ensure_empty_tables`.

Type conventions (MVP): dates/timestamps as ISO-8601 strings; `conid` as
string (nullable, join-safe); ranks as float64; counts int64; monetary
values float64; flags bool. Upgradable to `date32`/`timestamp` later as a
non-breaking 1.x change.

## 5. Append-only mechanics

- Append-only is enforced at the **file** level: every partition path
  contains `run_id`, so a re-run writes new files beside the old ones and
  never touches them.
- **Tabular data** is buffered in memory per `(table, business_date)` and
  flushed to parquet at `close()`/context exit (one `part.parquet` per
  partition) — avoids expensive per-row parquet writes.
- **Events** stream immediately (append one JSON line), so an event
  survives a crash before the tabular flush.
- **Re-run** of the same day → new `run_id` → new files; analysis selects
  the latest run by `created_at`, history is retained.
- Defensive backstop: flushing onto an existing `part.parquet` raises
  `JournalWriteError` (a `run_id` collision should be impossible).

## 6. Writer API

```python
JournalWriter(mode, strategy_id, base_dir, run_id=None, source_system="REPLAY")

  # buffered — flushed at close()/__exit__
  write_daily_state(business_date, state: dict)
  write_signals(business_date, rows: list[dict])
  write_decisions(business_date, rows: list[dict])
  write_order_plan(business_date, rows: list[dict])
  write_positions_snapshot(business_date, rows: list[dict])
  write_trade_closed(business_date, row: dict)     # mfe/mae left NULL
  ensure_empty_tables(business_date, tables: list[str])

  # streamed — appended to events_YYYY-MM.jsonl immediately
  write_event(severity, component, event_type, business_date=None, **fields)

  close()                    # flush all buffers
  __enter__ / __exit__       # context manager (flushes on exit)

NullJournalWriter(...)       # identical API, all no-ops
```

`business_date` is the partition key per call, so the same writer serves
both a single-day paper run and a multi-day replay.

## 7. Schema versioning

`SCHEMA_VERSION = "1.0.0"`. Convention: `1.0.0` first stable schema;
`1.1.0` backwards-compatible column additions; `2.0.0` breaking change.

## 8. Parity guarantee

The runtime receives a writer **by injection** (`JournalWriter` when on,
`NullJournalWriter` when off). Because the runtime's code path is
identical either way and the writer is side-effect-only, the replay
result **cannot** depend on the journal — parity is structural, not just
tested.

`test_parity_replay` validates the mechanism with a deterministic stub
replay. **Integration step (separate from this MVP):** wire the same
injection into the real BT-04R engine and assert the golden master
(CAGR 34.504% / total 337.652% / maxDD −32.7% / Sharpe 1.182 /
990 trades / avg exposure 0.787).

## 9. Test plan (all passing)

| Test | Verifies |
|---|---|
| `test_schemas` | tables present, mandatory + `source_system` columns, nullable MFE/MAE, empty tables keep schema |
| `test_run_id_metadata_present` | every table row and every event carries the six identifiers, non-empty, matching the run |
| `test_writer_append_only` | re-run → new run_id/file, old file byte-identical; overwrite backstop raises |
| `test_mode_isolation` | `mode=paper` never writes under `live/` or `replay/`; unknown mode rejected |
| `test_empty_tables` | empty write produces a schema-correct 0-row file |
| `test_events_jsonl` | events are append-only, one valid JSON per line, append across writers |
| `test_no_broker_dependency` | AST scan: no import of broker/execution modules |
| `test_parity_replay` | journal-on result == journal-off result (mechanism) |

## 10. Assumptions / follow-ups

- Small-file count (~250/year/table/mode) is fine for daily cadence;
  future compaction candidate (mirrors `sharadar_snapshot_store`).
- `journal_data/` must be added to `.gitignore`.
- Dependencies: `pyarrow`, `pandas` (already in env), `uuid`/`json`/
  `datetime` (stdlib).
- Daily Markdown report deferred to **v1.1** (user output, not core audit
  infrastructure).
- MFE/MAE computation deferred to a later analytic job (writer stays
  passive).

## 11. Read-side note (important for analytics)

The partition directories use hive-style keys (`date=…`, `run_id=…`) and
the same names also exist as columns *inside* each parquet file
(`run_id` is a mandatory column; `date` is a business column). When a
parquet reader auto-infers hive partitioning from the directory names,
it creates partition columns `date`/`run_id` that collide with the
in-file columns, raising e.g.
`ArrowTypeError: Unable to merge: Field run_id has incompatible types`.
This behaviour is pyarrow-version-dependent.

Read journal data one of these two ways (both use the authoritative
in-file columns and never hit the collision):

- Single partition file:
  `pyarrow.parquet.ParquetFile(str(path)).read()`
- Whole table across dates/runs (analytics):
  `pyarrow.dataset.dataset(root, partitioning=None).to_table()`

Do **not** rely on hive partition inference for these tables. (The test
suite reads single files via `ParquetFile(...).read()` for exactly this
reason.)
