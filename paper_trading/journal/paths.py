"""TRADING-JOURNAL-01 — path routing.

Layout (mode is the top-level separator so live/ never shares a file
with paper/):

    <base>/<mode>/<table>/date=<YYYY-MM-DD>/run_id=<run_id>/part.parquet
    <base>/<mode>/events/events_<YYYY-MM>.jsonl
    <base>/<mode>/reports/daily_report_<YYYY-MM-DD>.md   # v1.1, not written yet
"""

from __future__ import annotations

from pathlib import Path

_ALLOWED_MODES = ("replay", "dry_run", "paper", "paper_manual", "live")


def _check_mode(mode: str) -> None:
    if mode not in _ALLOWED_MODES:
        raise ValueError(f"Unknown mode {mode!r}; expected one of {_ALLOWED_MODES}")


def mode_root(base_dir: Path | str, mode: str) -> Path:
    _check_mode(mode)
    return Path(base_dir) / mode


def partition_dir(base_dir: Path | str, mode: str, table: str,
                  business_date: str, run_id: str) -> Path:
    """Directory that holds a single (table, date, run) partition file."""
    return (
        mode_root(base_dir, mode)
        / table
        / f"date={business_date}"
        / f"run_id={run_id}"
    )


def partition_file(base_dir: Path | str, mode: str, table: str,
                   business_date: str, run_id: str) -> Path:
    """Full path to a partition's ``part.parquet``."""
    return partition_dir(base_dir, mode, table, business_date, run_id) / "part.parquet"


def events_file(base_dir: Path | str, mode: str, year_month: str) -> Path:
    """Monthly append-only events log, e.g. year_month='2026-07'."""
    return mode_root(base_dir, mode) / "events" / f"events_{year_month}.jsonl"


def reports_dir(base_dir: Path | str, mode: str) -> Path:
    """Reserved for the v1.1 daily Markdown report (not produced in v1)."""
    return mode_root(base_dir, mode) / "reports"
