"""broker_state_sync.py — seed local PortfolioState from real broker account.

Spec: docs/BROKER-STATE-SYNC_design.md

Reads equity / cash / positions from IBKR Paper via the read-only broker adapter
(reusing the step-4 safety gates) and, on --apply, seeds the local
PortfolioState (state.json) from reality instead of the bootstrap
starting_equity. Read-only vs the broker: no orders. The only write is the local
state.json, and only after a passing validation.

MVP: flat account (0 positions) only. Positions present -> HARD FAIL (the broker
does not know strategy metadata: entry_date / planned_exit_date / signal_rank).
An existing local state is never overwritten without --overwrite (drift is
reported, not applied).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .broker.check import CheckConfig, run_check
from .broker.interface import BrokerReadOnly
from .models import PortfolioState
from .portfolio_state import load_state, save_state, validate_state

_CASH_TOL = 1e-6
_EQUITY_MISMATCH_PCT = 0.05   # warn if |equity-cash|/cash exceeds this (0 pos)


@dataclass
class SyncResult:
    passed: bool = False
    hard_fail: bool = False
    applied: bool = False
    timestamp: str = ""
    broker: Optional[dict] = None
    local_before: Optional[dict] = None
    target: Optional[dict] = None
    drift: List[str] = field(default_factory=list)
    backup_path: Optional[str] = None
    checks: List[dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def run_sync(broker: BrokerReadOnly, check_cfg: CheckConfig, state_path,
             today: str, apply: bool = False,
             overwrite: bool = False) -> SyncResult:
    r = SyncResult(timestamp=datetime.now(timezone.utc).isoformat())

    # 1) read + safety gates via the step-4 check (account match, not-live, ...)
    cr = run_check(broker, check_cfg)
    r.checks = cr.checks
    r.warnings = list(cr.warnings)
    r.errors = list(cr.errors)
    if not cr.passed:
        r.hard_fail = True
        r.errors.append("broker check did not pass — refusing to sync")
        r.passed = False
        return r

    r.broker = {"account_id": cr.account_id, "equity": cr.equity,
                "cash": cr.cash, "positions": len(cr.positions)}

    # 2) MVP: positions present -> HARD FAIL (no fabricated strategy metadata)
    if cr.positions:
        r.hard_fail = True
        r.errors.append(
            f"account holds {len(cr.positions)} position(s); MVP does not import "
            f"broker positions (missing entry_date / planned_exit_date / "
            f"signal_rank). Reconcile or flatten the account, then re-run.")
        r.passed = False
        return r

    # 3) equity vs cash sanity (flat account)
    if cr.equity is not None and cr.cash is not None and cr.cash:
        if abs(cr.equity - cr.cash) / abs(cr.cash) > _EQUITY_MISMATCH_PCT:
            r.warnings.append(
                f"equity ({cr.equity}) differs from cash ({cr.cash}) by "
                f">{_EQUITY_MISMATCH_PCT:.0%} with 0 positions — check the account")

    # 4) build the target seeded state
    target = PortfolioState(cash=cr.cash or 0.0, equity=cr.equity or 0.0,
                            positions=(), last_updated_date=today)
    r.target = {"cash": target.cash, "equity": target.equity, "positions": 0}

    # 5) existing local state? compute drift, gate overwrite
    sp = Path(state_path)
    existing = load_state(sp) if sp.exists() else None
    if existing is not None:
        r.local_before = {"cash": existing.cash, "equity": existing.equity,
                          "positions": len(existing.open_positions())}
        if abs(existing.cash - target.cash) > _CASH_TOL:
            r.drift.append(f"cash: local {existing.cash} vs broker {target.cash}")
        if abs(existing.equity - target.equity) > _CASH_TOL:
            r.drift.append(
                f"equity: local {existing.equity} vs broker {target.equity}")
        if existing.open_positions():
            r.drift.append(
                f"local holds {len(existing.open_positions())} position(s) not "
                f"in the flat broker account")

    r.passed = True  # the sync is valid; write is gated separately below

    # 6) apply (write local state) — gated
    if apply:
        if existing is not None and r.drift and not overwrite:
            r.warnings.append(
                "drift detected and no --overwrite — refusing to overwrite the "
                "existing local state; nothing written")
        else:
            if sp.exists():
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                r.backup_path = str(sp.with_suffix(sp.suffix + f".{ts}.bak"))
                shutil.copy2(sp, r.backup_path)
            sp.parent.mkdir(parents=True, exist_ok=True)
            validate_state(target)
            save_state(target, sp)
            r.applied = True
    return r


def render_json(r: SyncResult) -> str:
    return json.dumps({
        "result": "PASS" if r.passed else "FAIL", "applied": r.applied,
        "hard_fail": r.hard_fail, "timestamp": r.timestamp,
        "broker": r.broker, "local_before": r.local_before, "target": r.target,
        "drift": r.drift, "backup_path": r.backup_path, "checks": r.checks,
        "warnings": r.warnings, "errors": r.errors}, indent=2)


def render_md(r: SyncResult, state_path: str) -> str:
    L = ["# Broker State -> PortfolioState Sync", ""]
    L.append(f"- result: **{'PASS' if r.passed else 'FAIL'}**"
             + ("  (**HARD FAIL**)" if r.hard_fail else "")
             + f"  |  phase: **{'APPLIED' if r.applied else 'VALIDATE-ONLY'}**")
    L.append(f"- timestamp: {r.timestamp}")
    L.append(f"- state file: `{state_path}`")
    if r.broker:
        L.append(f"- broker: account **{r.broker['account_id']}**  |  equity "
                 f"{r.broker['equity']}  |  cash {r.broker['cash']}  |  "
                 f"positions {r.broker['positions']}")
    if r.local_before:
        L.append(f"- local (before): equity {r.local_before['equity']}  |  cash "
                 f"{r.local_before['cash']}  |  positions "
                 f"{r.local_before['positions']}")
    if r.target:
        L.append(f"- target (seed): equity {r.target['equity']}  |  cash "
                 f"{r.target['cash']}  |  positions {r.target['positions']}")
    if r.backup_path:
        L.append(f"- state backup: `{r.backup_path}`")
    L.append("")
    if r.drift:
        L.append(f"## Drift vs existing local state ({len(r.drift)})")
        L += [f"- {d}" for d in r.drift]
        L.append("")
    L.append(f"## Warnings ({len(r.warnings)})")
    L += [f"- {w}" for w in r.warnings] or ["_none_"]
    L.append("")
    if r.errors:
        L.append(f"## Errors ({len(r.errors)})")
        L += [f"- {e}" for e in r.errors]
        L.append("")
    L.append("_Read-only vs the broker: no orders. The only write is the local "
             "state.json (apply phase). A synced state.json takes priority over "
             "starting_equity in the runner._")
    return "\n".join(L)


def _load_check_cfg(path, overrides) -> CheckConfig:
    data = {}
    if path:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.update({k: v for k, v in overrides.items() if v is not None})
    return CheckConfig(
        expected_account_id=data.get("expected_account_id", ""),
        host=data.get("host", "127.0.0.1"), port=int(data.get("port", 7497)),
        client_id=int(data.get("client_id", 102)),
        mode=data.get("mode", "paper"),
        timeout_seconds=float(data.get("timeout_seconds", 15.0)),
        paper_prefix=data.get("paper_prefix", "DU"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Seed PortfolioState from broker")
    ap.add_argument("--config", default=None)
    ap.add_argument("--state", required=True)
    ap.add_argument("--out", default=".")
    ap.add_argument("--today", default=None)
    ap.add_argument("--expected-account-id", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)

    cfg = _load_check_cfg(args.config, {
        "expected_account_id": args.expected_account_id})
    today = args.today or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    from .broker.ib_readonly import IBReadOnlyBroker
    broker = IBReadOnlyBroker(cfg.host, cfg.port, cfg.client_id)

    r = run_sync(broker, cfg, args.state, today, apply=args.apply,
                 overwrite=args.overwrite)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    (out / f"broker_state_sync_{ts}.md").write_text(
        render_md(r, args.state), encoding="utf-8")
    (out / f"broker_state_sync_{ts}.json").write_text(
        render_json(r), encoding="utf-8")
    print(f"result: {'PASS' if r.passed else 'FAIL'}"
          + (" (HARD FAIL)" if r.hard_fail else "")
          + f" | {'APPLIED' if r.applied else 'VALIDATE-ONLY'}"
          + f" | report: {out}/broker_state_sync_{ts}.md")
    return 0 if r.passed else 1


if __name__ == "__main__":
    sys.exit(main())
