"""check.py — read-only paper connection check (pure logic over BrokerReadOnly).

Applies the safety gates and renders the report. Imports only the interface,
never ibapi. No PortfolioState mutation, no journal, no orders.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .interface import (BrokerError, BrokerReadOnly, BrokerTimeout,
                        PositionRow)

READONLY_UNVERIFIED_MSG = (
    "Read-Only API toggle could not be verified programmatically. "
    "Operator must confirm TWS Read-Only API is enabled.")


@dataclass
class CheckConfig:
    expected_account_id: str = ""
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 102
    mode: str = "paper"
    timeout_seconds: float = 15.0
    paper_prefix: str = "DU"


@dataclass
class CheckResult:
    passed: bool = False
    hard_fail: bool = False
    timestamp: str = ""
    account_id: Optional[str] = None
    account_type: str = "unknown"          # paper / live / unknown
    equity: Optional[float] = None
    cash: Optional[float] = None
    positions: List[PositionRow] = field(default_factory=list)
    open_orders_count: Optional[int] = None
    connection: Optional[dict] = None
    checks: List[dict] = field(default_factory=list)   # {name, ok, detail}
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def _add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            self.hard_fail = True


def run_check(broker: BrokerReadOnly, cfg: CheckConfig) -> CheckResult:
    r = CheckResult(timestamp=datetime.now(timezone.utc).isoformat())

    # expected_account_id mandatory — refuse to run blind (no connect)
    if not cfg.expected_account_id:
        r.errors.append("expected_account_id missing in config — refusing to "
                        "run blind")
        r.hard_fail = True
        r.passed = False
        return r

    # connect
    try:
        meta = broker.connect(cfg.timeout_seconds)
        r.connection = {"host": meta.host, "port": meta.port,
                        "client_id": meta.client_id,
                        "server_version": meta.server_version,
                        "connect_time": meta.connect_time,
                        "connected": meta.connected}
        r._add("connect", True, f"connected to {meta.host}:{meta.port}")
    except BrokerTimeout as e:
        r.errors.append(f"timeout: {e}")
        r._add("connect", False, "timeout")
        r.passed = False
        return r
    except (BrokerError, Exception) as e:  # noqa: BLE001 - report any failure
        r.errors.append(f"connect failed: {e}")
        r._add("connect", False, str(e))
        r.passed = False
        return r

    try:
        summary = broker.account_summary()
        detected = summary.account_id or ""
        r.account_id = detected
        r.equity = summary.net_liquidation
        r.cash = summary.total_cash

        # account type from prefix
        if detected.startswith(cfg.paper_prefix):
            r.account_type = "paper"
        elif detected.startswith("U"):
            r.account_type = "live"
        else:
            r.account_type = "unknown"

        # HARD FAIL: live account
        r._add("not_live_account", r.account_type != "live",
               f"detected account_type={r.account_type} ({detected})")
        # HARD FAIL: exact expected match
        r._add("expected_account_match", detected == cfg.expected_account_id,
               f"detected={detected} expected={cfg.expected_account_id}")
        # paper prefix sanity (info-level: part of match, but surfaced)
        r._add("paper_prefix", r.account_type == "paper",
               f"expected paper prefix {cfg.paper_prefix!r}")

        r.positions = broker.positions()
        r.open_orders_count = broker.open_orders_count()

        # read-only toggle cannot be confirmed via API -> WARNING
        r.warnings.append(READONLY_UNVERIFIED_MSG)
    except Exception as e:  # noqa: BLE001
        r.errors.append(f"read failed: {e}")
        r.hard_fail = True
    finally:
        try:
            broker.disconnect()
        except Exception:  # noqa: BLE001
            pass

    r.passed = (not r.hard_fail) and (not r.errors)
    return r


def render_json(r: CheckResult) -> str:
    return json.dumps({
        "result": "PASS" if r.passed else "FAIL",
        "hard_fail": r.hard_fail, "timestamp": r.timestamp,
        "account_id": r.account_id, "account_type": r.account_type,
        "equity": r.equity, "cash": r.cash,
        "open_orders_count": r.open_orders_count,
        "positions": [vars(p) for p in r.positions],
        "connection": r.connection, "checks": r.checks,
        "warnings": r.warnings, "errors": r.errors}, indent=2)


def render_md(r: CheckResult, cfg: CheckConfig) -> str:
    L = [f"# Broker Read-Only / Paper Connection Check", ""]
    L.append(f"- result: **{'PASS' if r.passed else 'FAIL'}**"
             + ("  (**HARD FAIL**)" if r.hard_fail else ""))
    L.append(f"- timestamp: {r.timestamp}  |  mode: **{cfg.mode}**")
    L.append(f"- account_id: **{r.account_id}**  |  type: **{r.account_type}**  "
             f"|  expected: **{cfg.expected_account_id}**")
    L.append(f"- equity (net liquidation): {r.equity}  |  cash: {r.cash}")
    L.append(f"- open orders: {r.open_orders_count}")
    if r.connection:
        L.append(f"- connection: {r.connection['host']}:{r.connection['port']} "
                 f"client_id={r.connection['client_id']} "
                 f"server={r.connection.get('server_version')}")
    L.append("")
    L.append("## Safety checks")
    L.append("| check | ok | detail |")
    L.append("|---|---|---|")
    for c in r.checks:
        L.append(f"| {c['name']} | {'OK' if c['ok'] else 'FAIL'} | {c['detail']} |")
    L.append("")
    L.append(f"## Positions ({len(r.positions)})")
    if r.positions:
        L.append("| symbol | conid | quantity | avg_cost |")
        L.append("|---|---|---|---|")
        for p in r.positions:
            L.append(f"| {p.symbol} | {p.conid} | {p.quantity} | {p.avg_cost} |")
    else:
        L.append("_none_")
    L.append("")
    L.append(f"## Warnings ({len(r.warnings)})")
    L += [f"- {w}" for w in r.warnings] or ["_none_"]
    L.append("")
    if r.errors:
        L.append(f"## Errors ({len(r.errors)})")
        L += [f"- {e}" for e in r.errors]
        L.append("")
    L.append("## Operator checklist (must confirm before trusting this)")
    L.append("- [ ] TWS Paper is running; API enabled; port matches config")
    L.append("- [ ] **TWS Read-Only API is ENABLED** (cannot be verified via API)")
    L.append("- [ ] Trusted IP 127.0.0.1; client_id not in use elsewhere")
    L.append("- [ ] account_id above matches your intended paper account")
    L.append("")
    L.append("_Read + report only: no PortfolioState change, no journal, no "
             "orders. Wiring the real state into the runner is a later step._")
    return "\n".join(L)
