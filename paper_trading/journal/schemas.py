"""TRADING-JOURNAL-01 — table schemas (schema_version 1.0.0).

Single source of truth for every journal table. Each schema already
includes the five mandatory identifier columns plus ``source_system``,
so downstream code never has to re-declare them.

Design rules honoured here:
- Mandatory in EVERY table/event: strategy_id, run_id, schema_version,
  mode, created_at  (architect decision, 2026-07-15).
- ``source_system`` added to every table (REPLAY / MDSM / DATA-06 /
  IBKR_PAPER / ...).
- ``fills`` is schema-only in v1 (populated in the paper-execution phase).
- ``trades.mfe_pct`` / ``trades.mae_pct`` are nullable and left NULL in
  the MVP; a later analytic job computes them from positions snapshots.
  The writer never computes trade metrics (it stays a passive recorder).

Type conventions (MVP):
- dates / timestamps are stored as ISO-8601 strings (portable, no tz
  ambiguity in parquet). Upgradable to date32/timestamp later without a
  breaking change if wrapped as 1.x.
- conid is stored as string (nullable, join-safe, no int overflow).
- ranks are float64 (accommodates both integer ranks and percentiles).
"""

from __future__ import annotations

import pyarrow as pa

SCHEMA_VERSION = "1.1.0"  # 1.1.0: fills.execution_mode (nullable, additive)

# The five identifiers that must appear in every table and every event row.
MANDATORY_FIELDS = [
    pa.field("strategy_id", pa.string()),
    pa.field("run_id", pa.string()),
    pa.field("schema_version", pa.string()),
    pa.field("mode", pa.string()),
    pa.field("created_at", pa.string()),  # UTC ISO-8601
]

# Provenance column, added to every table (architect: "source_system").
_SOURCE = [pa.field("source_system", pa.string())]

# The mandatory-identifier column names, exposed for validation tests.
MANDATORY_COLUMNS = [f.name for f in MANDATORY_FIELDS]


def _table(business_fields: list[pa.Field]) -> pa.Schema:
    """Prepend mandatory + source_system fields to a table's business fields."""
    return pa.schema(MANDATORY_FIELDS + _SOURCE + business_fields)


# --------------------------------------------------------------------------
# Business columns per table (order preserved; identifiers are prepended).
# --------------------------------------------------------------------------

_DAILY_STATE = [
    pa.field("date", pa.string()),
    pa.field("account_id", pa.string()),
    pa.field("cash", pa.float64()),
    pa.field("equity", pa.float64()),
    pa.field("net_liquidation", pa.float64()),
    pa.field("gross_exposure", pa.float64()),
    pa.field("net_exposure", pa.float64()),
    pa.field("open_positions_count", pa.int64()),
    pa.field("regime_on", pa.bool_()),
    pa.field("regime_index_level", pa.float64()),
    pa.field("regime_ma200", pa.float64()),
    pa.field("valid_constituents_count", pa.int64()),
    pa.field("kill_switch_active", pa.bool_()),
    pa.field("override_active", pa.bool_()),
    pa.field("orders_planned_count", pa.int64()),
    pa.field("orders_filled_count", pa.int64()),
    pa.field("warnings_count", pa.int64()),
    pa.field("errors_count", pa.int64()),
]

_SIGNALS = [
    pa.field("signal_date", pa.string()),
    pa.field("ticker", pa.string()),
    pa.field("conid", pa.string()),
    pa.field("rank_1d", pa.float64()),
    pa.field("rank_3d", pa.float64()),
    pa.field("rank_5d", pa.float64()),
    pa.field("rank_10d", pa.float64()),
    pa.field("rank_20d", pa.float64()),
    pa.field("is_top10", pa.bool_()),
    pa.field("is_top50", pa.bool_()),
    pa.field("sector", pa.string()),
    pa.field("industry", pa.string()),
    pa.field("price_close", pa.float64()),
    # signal-level data provenance (kept alongside record-level source_system)
    pa.field("source", pa.string()),
]

_DECISIONS = [
    pa.field("decision_id", pa.string()),
    pa.field("signal_date", pa.string()),
    pa.field("target_date", pa.string()),
    pa.field("ticker", pa.string()),
    pa.field("conid", pa.string()),
    pa.field("action", pa.string()),  # BUY / EXIT / DO_NOTHING / SKIP
    pa.field("reason", pa.string()),  # incl. SKIP_* reasons
    pa.field("rank_10d", pa.float64()),
    pa.field("regime_on", pa.bool_()),
    pa.field("cash_before", pa.float64()),
    pa.field("equity_before", pa.float64()),
    pa.field("target_value", pa.float64()),
    pa.field("quantity", pa.float64()),
    pa.field("price_source", pa.string()),  # next_open / close
    pa.field("free_slots_before", pa.int64()),
    pa.field("already_held", pa.bool_()),
    pa.field("pending_exit", pa.bool_()),
]

_ORDER_PLANS = [
    pa.field("plan_id", pa.string()),
    pa.field("signal_date", pa.string()),
    pa.field("target_date", pa.string()),
    pa.field("ticker", pa.string()),
    pa.field("conid", pa.string()),
    pa.field("action", pa.string()),
    pa.field("target_value", pa.float64()),
    pa.field("quantity", pa.float64()),
    pa.field("price_source", pa.string()),
    pa.field("order_type", pa.string()),
    # v1 terminal states for dry-run: PLANNED / SKIPPED.
    # SENT/FILLED transitions are event-sourced in the execution phase.
    pa.field("status", pa.string()),
    pa.field("reason", pa.string()),
]

# fills — schema-only in v1 (no writer method yet; populated in paper exec).
_FILLS = [
    pa.field("fill_id", pa.string()),
    pa.field("order_id", pa.string()),
    pa.field("timestamp", pa.string()),
    pa.field("ticker", pa.string()),
    pa.field("conid", pa.string()),
    pa.field("action", pa.string()),
    pa.field("quantity", pa.float64()),
    pa.field("expected_price", pa.float64()),
    pa.field("fill_price", pa.float64()),
    pa.field("slippage_bps", pa.float64()),
    pa.field("commission", pa.float64()),
    pa.field("fees", pa.float64()),
    pa.field("total_cost_bps", pa.float64()),
    pa.field("account_id", pa.string()),
    pa.field("broker_order_id", pa.string()),
    pa.field("status", pa.string()),
    # 1.1.0: execution_mode (nullable) — MANUAL for reconciled manual fills;
    # NULL/absent in older data keeps 1.0.0 readable.
    pa.field("execution_mode", pa.string()),
]

_POSITIONS = [
    pa.field("date", pa.string()),
    pa.field("ticker", pa.string()),
    pa.field("conid", pa.string()),
    pa.field("shares", pa.float64()),
    pa.field("entry_date", pa.string()),
    pa.field("entry_price", pa.float64()),
    pa.field("current_close", pa.float64()),
    pa.field("market_value", pa.float64()),
    pa.field("unrealized_pnl", pa.float64()),
    pa.field("unrealized_pnl_pct", pa.float64()),
    pa.field("planned_exit_date", pa.string()),
    pa.field("days_held", pa.int64()),
    pa.field("rank_at_entry", pa.float64()),
    pa.field("regime_at_entry", pa.bool_()),
    pa.field("status", pa.string()),
]

_TRADES = [
    pa.field("trade_id", pa.string()),
    pa.field("ticker", pa.string()),
    pa.field("conid", pa.string()),
    pa.field("entry_date", pa.string()),
    pa.field("exit_date", pa.string()),
    pa.field("entry_price", pa.float64()),
    pa.field("exit_price", pa.float64()),
    pa.field("shares", pa.float64()),
    pa.field("entry_value", pa.float64()),
    pa.field("exit_value", pa.float64()),
    pa.field("pnl", pa.float64()),
    pa.field("pnl_pct", pa.float64()),
    pa.field("holding_days", pa.int64()),
    pa.field("rank_10d_at_entry", pa.float64()),
    pa.field("regime_at_entry", pa.bool_()),
    # nullable, left NULL in MVP — computed later by an analytic job.
    pa.field("mfe_pct", pa.float64()),
    pa.field("mae_pct", pa.float64()),
    pa.field("exit_reason", pa.string()),
    pa.field("cost_bps", pa.float64()),
    pa.field("slippage_bps", pa.float64()),
]

# Registry of all parquet-backed tables.
TABLE_SCHEMAS: dict[str, pa.Schema] = {
    "daily_state": _table(_DAILY_STATE),
    "signals": _table(_SIGNALS),
    "decisions": _table(_DECISIONS),
    "order_plans": _table(_ORDER_PLANS),
    "fills": _table(_FILLS),
    "positions": _table(_POSITIONS),
    "trades": _table(_TRADES),
}

# Events are JSONL, not parquet. This is the minimum key set every event
# row must carry (mandatory identifiers + the three event descriptors).
EVENT_MANDATORY_KEYS = MANDATORY_COLUMNS + [
    "source_system",
    "severity",
    "component",
    "event_type",
]


def table_names() -> list[str]:
    return list(TABLE_SCHEMAS.keys())


def get_schema(table: str) -> pa.Schema:
    if table not in TABLE_SCHEMAS:
        raise KeyError(f"Unknown journal table: {table!r}")
    return TABLE_SCHEMAS[table]
