"""runtime_state.py — dry_run portfolio-state load / bootstrap for the runner.

Wraps the frozen ``portfolio_state`` persistence. The runner is
**execution-read-only** (architect):
  - allowed: bootstrap a dry_run state if missing; in-memory mark-to-market
  - forbidden: applying fills, simulating fills, creating/removing positions
    from the order_plan, mutating state from planned orders

Bootstrap is dry_run/replay-like only; paper/live obtain state via
reconciliation later.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

from .models import PortfolioState
from .portfolio_state import load_state, save_state


def bootstrap_state(starting_equity: float) -> PortfolioState:
    """Fresh dry_run state: all cash, no positions, not yet marked (last_updated
    is set when the runner marks to market at business_date D)."""
    return PortfolioState(cash=float(starting_equity),
                          equity=float(starting_equity),
                          last_updated_date="")


def load_or_bootstrap(state_path: str | Path,
                      starting_equity: float) -> Tuple[PortfolioState, bool]:
    """Return (state, was_bootstrapped). Bootstraps if the file is absent."""
    p = Path(state_path)
    if p.exists():
        return load_state(p), False
    return bootstrap_state(starting_equity), True


def persist(state: PortfolioState, state_path: str | Path) -> None:
    save_state(state, Path(state_path))
