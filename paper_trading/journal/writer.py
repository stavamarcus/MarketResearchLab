"""TRADING-JOURNAL-01 — journal writer.

Side-effect-only audit layer. The writer NEVER returns a value the
runtime uses in a computation, NEVER touches DecisionResolver /
portfolio state, and NEVER imports broker or order-execution modules.

Mechanics
---------
- Tabular data is buffered in memory per (table, business_date) and
  flushed to parquet at close/exit (one part.parquet per partition).
- Events stream immediately to a monthly append-only JSONL file, so an
  event survives a crash that happens before the tabular flush.
- Append-only is enforced at the *file* level: every partition path
  includes run_id, so a re-run writes new files beside the old ones and
  never mutates or overwrites them. As a defensive backstop, flushing
  onto an existing part.parquet raises JournalWriteError.
- The five mandatory identifiers + source_system are injected
  automatically into every record; created_at is stamped per record at
  write time. Callers never supply them.

Empty tables
------------
Calling a write_* method with an empty list registers the
(table, business_date) partition so that flush writes an empty,
schema-correct file ("ran, nothing happened" beats a missing file).
Use ``ensure_empty_tables`` to declare tables that produced nothing.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import paths
from .run_context import RunContext, utc_now_iso
from .schemas import (
    EVENT_MANDATORY_KEYS,
    TABLE_SCHEMAS,
    get_schema,
)


class JournalWriteError(RuntimeError):
    """Raised when an append-only invariant would be violated."""


class JournalWriter:
    """Buffered, append-only writer for one run.

    Parameters
    ----------
    mode : one of replay / dry_run / paper / live
    strategy_id : e.g. "MLE-PAPER-01"
    base_dir : journal_data root (the mode subdir is added automatically)
    run_id : optional; generated if omitted
    source_system : record-level provenance (REPLAY / MDSM / IBKR_PAPER / ...)
    """

    def __init__(
        self,
        mode: str,
        strategy_id: str,
        base_dir: str | Path,
        run_id: str | None = None,
        source_system: str = "REPLAY",
    ) -> None:
        ctx_kwargs = dict(
            strategy_id=strategy_id, mode=mode, source_system=source_system
        )
        if run_id is not None:
            ctx_kwargs["run_id"] = run_id
        self.ctx = RunContext(**ctx_kwargs)
        self.base_dir = Path(base_dir)
        # buffer[(table, business_date)] -> list[dict]
        self._buffer: dict[tuple[str, str], list[dict]] = {}
        self._closed = False

    # -- properties -------------------------------------------------------
    @property
    def run_id(self) -> str:
        return self.ctx.run_id

    @property
    def mode(self) -> str:
        return self.ctx.mode

    # -- internal ---------------------------------------------------------
    def _stamp(self, record: dict, source_system: str | None = None) -> dict:
        """Return a copy of ``record`` with identifiers + created_at injected.

        Caller-supplied identifier keys are overwritten to keep the audit
        trail authoritative (the writer owns provenance, not the caller).
        ``source_system`` optionally overrides the run default for this record
        (e.g. per-table provenance: signals=DATA06, decisions=DAILY_RUNNER).
        """
        stamped = dict(record)
        stamped.update(self.ctx.identifier_fields())
        if source_system is not None:
            stamped["source_system"] = source_system
        stamped["created_at"] = utc_now_iso()
        return stamped

    def _register(self, table: str, business_date: str, rows: list[dict],
                  source_system: str | None = None) -> None:
        if self._closed:
            raise JournalWriteError("writer is closed; cannot register more rows")
        if table not in TABLE_SCHEMAS:
            raise KeyError(f"Unknown journal table: {table!r}")
        key = (table, str(business_date))
        bucket = self._buffer.setdefault(key, [])
        for row in rows:
            bucket.append(self._stamp(row, source_system))

    # -- tabular write API (buffered) ------------------------------------
    def write_daily_state(self, business_date: str, state: dict,
                          source_system: str | None = None) -> None:
        self._register("daily_state", business_date, [state], source_system)

    def write_signals(self, business_date: str, rows: list[dict],
                      source_system: str | None = None) -> None:
        self._register("signals", business_date, list(rows), source_system)

    def write_decisions(self, business_date: str, rows: list[dict],
                        source_system: str | None = None) -> None:
        self._register("decisions", business_date, list(rows), source_system)

    def write_order_plan(self, business_date: str, rows: list[dict],
                         source_system: str | None = None) -> None:
        self._register("order_plans", business_date, list(rows), source_system)

    def write_positions_snapshot(self, business_date: str, rows: list[dict],
                                 source_system: str | None = None) -> None:
        self._register("positions", business_date, list(rows), source_system)

    def write_trade_closed(self, business_date: str, row: dict,
                           source_system: str | None = None) -> None:
        # MVP: mfe_pct / mae_pct are left NULL. The writer does not compute
        # trade metrics — a later analytic job derives them from positions.
        self._register("trades", business_date, [row], source_system)

    def write_fill(self, business_date: str, rows: list[dict],
                   source_system: str | None = None) -> None:
        # 1.1.0: real fills (manual reconciliation). execution_mode e.g. MANUAL.
        self._register("fills", business_date, list(rows), source_system)

    def ensure_empty_tables(self, business_date: str, tables: list[str]) -> None:
        """Register (table, date) partitions that produced no rows, so flush
        writes an empty schema-correct file instead of omitting it."""
        for table in tables:
            self._register(table, business_date, [])

    # -- event write API (streamed) --------------------------------------
    def write_event(
        self,
        severity: str,
        component: str,
        event_type: str,
        business_date: str | None = None,
        source_system: str | None = None,
        **fields,
    ) -> None:
        if self._closed:
            raise JournalWriteError("writer is closed; cannot write events")
        import json  # local import keeps module import surface minimal

        record = dict(fields)
        record.update(self.ctx.identifier_fields())
        if source_system is not None:
            record["source_system"] = source_system
        record["created_at"] = utc_now_iso()
        record["severity"] = severity
        record["component"] = component
        record["event_type"] = event_type
        if business_date is not None:
            record.setdefault("date", str(business_date))

        # every event must carry the mandatory metadata keys
        missing = [k for k in EVENT_MANDATORY_KEYS if k not in record]
        if missing:
            raise JournalWriteError(f"event missing mandatory keys: {missing}")

        year_month = record["created_at"][:7]  # 'YYYY-MM'
        path = paths.events_file(self.base_dir, self.mode, year_month)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # -- flush / close ----------------------------------------------------
    def _flush(self) -> None:
        for (table, business_date), rows in self._buffer.items():
            schema = get_schema(table)
            if rows:
                arr_table = pa.Table.from_pylist(rows, schema=schema)
            else:
                arr_table = schema.empty_table()  # empty but schema-correct
            out = paths.partition_file(
                self.base_dir, self.mode, table, business_date, self.run_id
            )
            if out.exists():
                # run_id makes this practically impossible; guard anyway.
                raise JournalWriteError(
                    f"refusing to overwrite existing partition: {out}"
                )
            out.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(arr_table, out)
        self._buffer.clear()

    def close(self) -> None:
        if self._closed:
            return
        self._flush()
        self._closed = True

    def __enter__(self) -> "JournalWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Flush whatever was buffered even on the happy path; on an
        # exception we still flush so partial audit data is not lost.
        self.close()


class NullJournalWriter:
    """No-op writer with the identical API.

    Injected into the runtime when journalling is disabled. Because the
    runtime's code path is the same with either writer, the replay result
    cannot depend on the journal — this is what makes the parity
    guarantee structural rather than merely tested.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._run_id = kwargs.get("run_id", "null")

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def mode(self) -> str:
        return "null"

    def write_daily_state(self, *a, **k) -> None: ...
    def write_signals(self, *a, **k) -> None: ...
    def write_decisions(self, *a, **k) -> None: ...
    def write_order_plan(self, *a, **k) -> None: ...
    def write_positions_snapshot(self, *a, **k) -> None: ...
    def write_trade_closed(self, *a, **k) -> None: ...
    def write_fill(self, *a, **k) -> None: ...
    def ensure_empty_tables(self, *a, **k) -> None: ...
    def write_event(self, *a, **k) -> None: ...
    def close(self) -> None: ...

    def __enter__(self) -> "NullJournalWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None: ...
