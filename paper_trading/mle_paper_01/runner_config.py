"""runner_config.py — configuration for the Daily Offline Runner.

Paths default to the replay_engine values but are **configurable** via JSON —
no absolute Windows paths are hardcoded inside daily_runner.py (architect
OQ-B). Bootstrap uses starting_equity = 30_000 for dry_run (architect OQ-A).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .data_source import DataSourceProfile

# defaults lifted from replay_engine.py — overridable via config file
DEFAULT_UNIVERSE_PATH = (
    r"C:\Users\stava\Projects\MDSM-Lite\data\universe"
    r"\sp500_rank_calendar_universe.csv")
DEFAULT_DATA06_VIEW_DIR = (
    r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots"
    r"\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
DEFAULT_MLE_PROJECT_PATH = r"C:\Users\stava\Projects\MarketLeadershipEngine"
DEFAULT_MDSM_PROJECT_PATH = r"C:\Users\stava\Projects\MDSM-Lite"


@dataclass(frozen=True)
class RunnerConfig:
    # identity / mode
    strategy_id: str = "MLE-REGIME200-HOLD10-01"  # legacy working name: MLE-PAPER-01
    mode: str = "dry_run"

    # data source
    data_source: DataSourceProfile = DataSourceProfile.DATA06
    universe_path: str = DEFAULT_UNIVERSE_PATH
    data06_view_dir: str = DEFAULT_DATA06_VIEW_DIR
    mle_project_path: str = DEFAULT_MLE_PROJECT_PATH
    mdsm_project_path: str = DEFAULT_MDSM_PROJECT_PATH
    signal_cache_path: str | None = None
    recompute_signals: bool = False

    # bootstrap (dry_run only) — architect OQ-A
    starting_equity: float = 30_000.0
    max_positions: int = 10          # informational; sizing lives in resolver
    target_weight: float = 0.10      # informational; sizing lives in resolver

    # output roots (relative to paper_trading unless absolute)
    state_path: str = "runtime_state/mle_paper_01/dry_run/state.json"
    order_plans_dir: str = "order_plans/mle_paper_01/dry_run"
    reports_dir: str = "reports/mle_paper_01/dry_run"
    journal_base_dir: str = "journal_data"

    account_label: str = "DU-PAPER (dry_run)"  # for the manual safety checklist

    def with_base(self, base: Path) -> "RunnerConfig":
        """Resolve relative output paths against a base dir (paper_trading)."""
        def r(p: str) -> str:
            pp = Path(p)
            return str(pp if pp.is_absolute() else base / pp)
        from dataclasses import replace
        return replace(
            self,
            state_path=r(self.state_path),
            order_plans_dir=r(self.order_plans_dir),
            reports_dir=r(self.reports_dir),
            journal_base_dir=r(self.journal_base_dir))


def load_config(path: str | Path | None) -> RunnerConfig:
    """Load a RunnerConfig from JSON; missing keys fall back to defaults."""
    if path is None:
        return RunnerConfig()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ds = data.get("data_source")
    if isinstance(ds, str):
        data["data_source"] = DataSourceProfile(ds)
    # keep only recognised fields
    valid = RunnerConfig.__dataclass_fields__.keys()
    clean = {k: v for k, v in data.items() if k in valid}
    return RunnerConfig(**clean)
