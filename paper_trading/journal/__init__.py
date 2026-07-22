"""TRADING-JOURNAL-01 — side-effect-only trading/audit journal layer.

Public API::

    from paper_trading.journal import JournalWriter, NullJournalWriter

    with JournalWriter(mode="replay", strategy_id="MLE-PAPER-01",
                       base_dir=".../journal_data") as j:
        j.write_daily_state("2026-07-15", {...})
        j.write_signals("2026-07-15", [ {...}, ... ])
        j.write_event("WARNING", "signal_source", "MISSING_PRICE",
                      business_date="2026-07-15", ticker="XYZ",
                      message="Missing open price, BUY skipped")

Guarantees: never changes the replay result, never mutates history,
never imports broker/execution code.
"""

from .run_context import RunContext, generate_run_id, utc_now_iso
from .schemas import SCHEMA_VERSION, MANDATORY_COLUMNS, table_names
from .writer import JournalWriter, JournalWriteError, NullJournalWriter

__all__ = [
    "JournalWriter",
    "NullJournalWriter",
    "JournalWriteError",
    "RunContext",
    "generate_run_id",
    "utc_now_iso",
    "SCHEMA_VERSION",
    "MANDATORY_COLUMNS",
    "table_names",
]
