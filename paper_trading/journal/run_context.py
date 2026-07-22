"""TRADING-JOURNAL-01 — run context and run_id generation.

A *run* is one execution of the runtime (a daily paper run, or a full
replay). Every table and event produced by a run shares the same
``run_id``; date partitioning happens per business day within the run,
so a multi-day replay writes many ``date=.../run_id=<same>`` partitions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .schemas import SCHEMA_VERSION

VALID_MODES = ("replay", "dry_run", "paper", "paper_manual", "live")


def generate_run_id() -> str:
    """Unique, sortable run id: ``YYYYMMDDTHHMMSS_<8 hex>`` (UTC)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def utc_now_iso() -> str:
    """Current time as UTC ISO-8601 string (used for created_at)."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RunContext:
    """Immutable identifiers shared by every record of a single run."""

    strategy_id: str
    mode: str
    source_system: str
    run_id: str = field(default_factory=generate_run_id)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.mode not in VALID_MODES:
            raise ValueError(
                f"mode must be one of {VALID_MODES}, got {self.mode!r}"
            )
        if not self.strategy_id:
            raise ValueError("strategy_id must be a non-empty string")

    def identifier_fields(self) -> dict[str, str]:
        """The five mandatory identifiers + source_system, as a dict.

        ``created_at`` is intentionally NOT included here — it is stamped
        per record at write time, not per run.
        """
        return {
            "strategy_id": self.strategy_id,
            "run_id": self.run_id,
            "schema_version": self.schema_version,
            "mode": self.mode,
            "source_system": self.source_system,
        }
