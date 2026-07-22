"""reconciliation.py — Manual fill recording / reconciliation (local, no broker).

Spec: docs/FILL-RECONCILIATION_design.md

Validate a filled ticket against the plan; on --apply (only after a PASS) update
the local PortfolioState and the journal `fills` (execution_mode=MANUAL, schema
1.1.0). No broker, no order submission, no IBKR API. Validate-only by default;
state is mutated only in the explicit apply phase, after validation passes.

Uses ACTUAL quantity / fill price / commission_fees (real fills) — NOT the
backtest COST_HALF model. Reuses Position + validate_state; does not reuse the
backtest apply_buy_fill / apply_exit_fill.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .models import Action, PortfolioState, Position
from .portfolio_state import (load_state, save_state, validate_state,
                              _rank_from_reason)
from .calendar_util import next_session_xnys, add_sessions

HOLD_PERIOD = 10
VALID_STATUS = {"filled", "partial", "cancelled"}
FAIL, APPLY, SKIP = "FAIL", "APPLY", "SKIP"


# --------------------------------------------------------------------- data
@dataclass
class FillRow:
    ticker: str
    conid: Optional[str]
    side: str
    planned_quantity: Optional[float]
    actual_quantity: float
    actual_fill_price: float
    timestamp: str
    commission_fees: float
    order_id: str
    status: str
    override_reason: str = ""
    plan_date: str = ""      # ticket's target_date column (fallback for dating)


@dataclass
class Disposition:
    row: FillRow
    action: str = APPLY
    issues: List[str] = field(default_factory=list)     # FAIL/warn messages
    deviations: List[str] = field(default_factory=list)  # STRATEGY_DEVIATION
    entry_date: Optional[str] = None                     # resolved session date


@dataclass
class ReconReport:
    target_date: str
    dispositions: List[Disposition]
    warnings: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(d.action != FAIL for d in self.dispositions)

    def by(self, action: str) -> List[Disposition]:
        return [d for d in self.dispositions if d.action == action]


# ----------------------------------------------------------------- parsing
def _f(v, default=0.0):
    v = (v or "").strip()
    if v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def parse_ticket(path: str | Path) -> List[FillRow]:
    rows: List[FillRow] = []
    with Path(path).open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            side = (r.get("side") or r.get("action") or "").strip().upper()
            rows.append(FillRow(
                ticker=(r.get("ticker") or "").strip(),
                conid=(r.get("conid") or "").strip() or None,
                side=side,
                planned_quantity=(None if (r.get("planned_quantity") or
                                           r.get("quantity") or "").strip() == ""
                                  else _f(r.get("planned_quantity")
                                          or r.get("quantity"))),
                actual_quantity=_f(r.get("actual_quantity")),
                actual_fill_price=_f(r.get("actual_fill_price")),
                timestamp=(r.get("timestamp") or r.get("actual_timestamp")
                           or "").strip(),
                commission_fees=_f(r.get("commission_fees")),
                order_id=(r.get("order_id") or "").strip(),
                status=(r.get("status") or "").strip().lower(),
                override_reason=(r.get("override_reason") or "").strip(),
                plan_date=(r.get("target_date") or "").strip()))
    return rows


def load_plan(path: str | Path) -> Dict[str, dict]:
    """order_plan CSV -> {ticker: {action, conid, target_value, reason}}."""
    plan: Dict[str, dict] = {}
    with Path(path).open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            tk = (r.get("ticker") or "").strip()
            if not tk:
                continue
            plan[tk] = {
                "action": (r.get("action") or "").strip().upper(),
                "conid": (r.get("conid") or "").strip() or None,
                "target_value": _f(r.get("target_value"), None),
                "reason": (r.get("reason") or "").strip()}
    return plan


def do_not_buy_from_ticket(rows: List[FillRow]) -> set:
    """MVP executability: BUY rows whose runner-written planned_quantity is
    blank/0 were DO NOT BUY. (Hardening path: read the CAPITAL_FEASIBILITY
    journal event instead of the editable ticket — see spec §2.)"""
    dnb = set()
    for r in rows:
        if r.side == "BUY" and (r.planned_quantity is None
                                or r.planned_quantity < 1):
            dnb.add(r.ticker)
    return dnb


def fill_key(row: FillRow, target_date: str) -> str:
    """Idempotence key: order_id if present, else deterministic hash."""
    if row.order_id:
        return f"order:{row.order_id}"
    raw = "|".join(str(x) for x in [target_date, row.ticker, row.conid,
                                    row.side, row.actual_quantity,
                                    row.actual_fill_price, row.timestamp])
    return "hash:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def applied_keys_from_journal(journal_dir: str | Path, mode: str) -> set:
    """Collect already-recorded order_id / fill_id from journal fills."""
    keys = set()
    if not journal_dir:
        return keys                       # no journal (e.g. validate-only)
    base = Path(journal_dir) / mode / "fills"
    if not base.exists():
        return keys
    try:
        import pyarrow.parquet as pq
        for p in base.rglob("*.parquet"):
            t = pq.ParquetFile(str(p)).read().to_pylist()
            for r in t:
                if r.get("order_id"):
                    keys.add(f"order:{r['order_id']}")
                if r.get("fill_id"):
                    keys.add(r["fill_id"])
    except Exception:
        pass
    return keys


# -------------------------------------------------------------- validation
def _session_of(timestamp: str) -> str:
    return (timestamp or "")[:10]   # ISO date part


def validate(rows: List[FillRow], plan: Dict[str, dict], state: PortfolioState,
             target_date: str, do_not_buy: set, applied_keys: set,
             next_session_fn=next_session_xnys) -> ReconReport:
    held = {p.ticker: p for p in state.open_positions()}
    dispositions: List[Disposition] = []
    warnings: List[str] = []

    for row in rows:
        d = Disposition(row=row, entry_date=target_date)

        # blank / unrecorded row (no status, no actual data) -> skip, not fail
        if row.status == "" and row.actual_quantity == 0 \
                and row.actual_fill_price == 0:
            d.action = SKIP
            d.issues.append("no fill recorded (blank) — skipped")
            dispositions.append(d)
            continue

        # status validity
        if row.status not in VALID_STATUS:
            d.action = FAIL
            d.issues.append(f"invalid status '{row.status}'")
            dispositions.append(d)
            continue

        # idempotence
        if fill_key(row, target_date) in applied_keys:
            d.action = SKIP
            d.issues.append("duplicate fill (already applied) — skipped")
            dispositions.append(d)
            continue

        # cancelled: no state change; must not carry qty/price
        if row.status == "cancelled":
            d.action = SKIP
            if row.actual_quantity or row.actual_fill_price:
                d.issues.append("cancelled row carries quantity/price")
                warnings.append(f"{row.ticker}: cancelled but has qty/price")
            dispositions.append(d)
            continue

        # filled / partial strict fields
        if row.actual_quantity <= 0 or row.actual_fill_price <= 0 \
                or not row.timestamp:
            d.action = FAIL
            d.issues.append("filled/partial requires actual_quantity>0, "
                            "actual_fill_price>0, timestamp")
            dispositions.append(d)
            continue
        if not row.order_id:
            warnings.append(f"{row.ticker}: empty order_id (recommended)")

        # ticker/side must be in plan
        planned = plan.get(row.ticker)
        if planned is None:
            d.action = FAIL
            d.issues.append("ticker not in plan (extra / rank-11)")
            dispositions.append(d)
            continue
        if row.side != planned["action"]:
            d.action = FAIL
            d.issues.append(f"side {row.side} != plan {planned['action']}")
            dispositions.append(d)
            continue

        # fill session must be target_date (unless override -> use actual)
        sess = _session_of(row.timestamp)
        if sess and sess != target_date:
            if row.override_reason:
                d.entry_date = sess
                d.deviations.append(
                    f"fill session {sess} != target_date {target_date} "
                    f"(override: {row.override_reason})")
            else:
                d.action = FAIL
                d.issues.append(f"fill session {sess} != target_date "
                                f"{target_date} (needs override_reason)")
                dispositions.append(d)
                continue

        if row.side == "BUY":
            if row.ticker in do_not_buy:
                d.action = FAIL
                d.issues.append("BUY of a DO NOT BUY / non-executable name")
                dispositions.append(d)
                continue
            if row.ticker in held:
                d.action = FAIL
                d.issues.append("BUY of an already-held ticker (MVP: no extend)")
                dispositions.append(d)
                continue
            if row.planned_quantity is not None \
                    and row.actual_quantity > row.planned_quantity:
                if row.override_reason:
                    d.deviations.append(
                        f"BUY qty {row.actual_quantity} > planned "
                        f"{row.planned_quantity} (override: {row.override_reason})")
                    warnings.append(f"{row.ticker}: STRATEGY_DEVIATION buy>planned")
                else:
                    d.action = FAIL
                    d.issues.append(f"BUY qty {row.actual_quantity} > planned "
                                    f"{row.planned_quantity} (needs override)")
                    dispositions.append(d)
                    continue

        elif row.side == "EXIT":
            pos = held.get(row.ticker)
            if pos is None:
                d.action = FAIL
                d.issues.append("EXIT of a non-held position")
                dispositions.append(d)
                continue
            if row.actual_quantity > pos.shares + 1e-9:
                d.action = FAIL
                d.issues.append(f"EXIT qty {row.actual_quantity} > held "
                                f"{pos.shares} (hard fail; no short)")
                dispositions.append(d)
                continue

        dispositions.append(d)   # APPLY

    return ReconReport(target_date=target_date, dispositions=dispositions,
                       warnings=warnings)


# -------------------------------------------------------------- apply state
def apply_to_state(report: ReconReport, state: PortfolioState,
                   plan: Dict[str, dict],
                   next_session_fn=next_session_xnys):
    """Apply APPLY dispositions with REAL cash math. Returns (new_state,
    fill_rows, summary). Partial EXIT leaves the remainder open."""
    positions = list(state.open_positions())
    cash = state.cash
    fill_rows: List[dict] = []
    summary = {"buys": 0, "exits": 0, "partial_exits": [],
               "cash_delta": 0.0}

    for d in report.by(APPLY):
        r = d.row
        if r.side == "BUY":
            entry_date = d.entry_date or report.target_date
            planned_exit = add_sessions(next_session_fn, entry_date, HOLD_PERIOD)
            rank = _rank_from_reason(plan.get(r.ticker, {}).get("reason", "")) \
                if plan.get(r.ticker) else 0
            debit = r.actual_quantity * r.actual_fill_price + r.commission_fees
            cash -= debit
            summary["cash_delta"] -= debit
            summary["buys"] += 1
            positions.append(Position(
                ticker=r.ticker, conid=int(r.conid) if r.conid else 0,
                shares=r.actual_quantity, entry_date=entry_date,
                entry_price=r.actual_fill_price, planned_exit_date=planned_exit,
                signal_rank=rank))
        else:  # EXIT
            proceeds = r.actual_quantity * r.actual_fill_price - r.commission_fees
            cash += proceeds
            summary["cash_delta"] += proceeds
            summary["exits"] += 1
            for i, p in enumerate(positions):
                if p.ticker == r.ticker:
                    remaining = round(p.shares - r.actual_quantity, 8)
                    if remaining <= 1e-9:
                        positions.pop(i)          # full close
                    else:
                        positions[i] = replace(p, shares=remaining)  # partial
                        summary["partial_exits"].append(
                            f"{r.ticker}: {remaining} shares still open "
                            f"(planned_exit {p.planned_exit_date})")
                    break
        fill_rows.append(_fill_record(r, d))

    # provisional equity: mark to entry_price (no close mark available here)
    mv = sum(p.shares * p.entry_price for p in positions)
    equity = cash + mv
    new_state = replace(state, cash=round(cash, 6),
                        positions=tuple(positions), equity=round(equity, 6))
    validate_state(new_state)
    return new_state, fill_rows, summary


def _fill_record(r: FillRow, d: Disposition) -> dict:
    action = "BUY" if r.side == "BUY" else "EXIT"
    return {
        "fill_id": fill_key(r, d.entry_date or ""),
        "order_id": r.order_id, "timestamp": r.timestamp,
        "ticker": r.ticker, "conid": r.conid, "action": action,
        "quantity": r.actual_quantity, "expected_price": None,
        "fill_price": r.actual_fill_price, "slippage_bps": None,
        "commission": r.commission_fees, "fees": 0.0, "total_cost_bps": None,
        "account_id": None, "broker_order_id": None, "status": r.status,
        "execution_mode": "MANUAL"}


# ------------------------------------------------------------------ report
def render_report(report: ReconReport, applied: bool, summary: Optional[dict],
                  backup_path: Optional[str], strategy_id: str,
                  mode: str) -> str:
    L = [f"# Reconciliation Report — {report.target_date}", ""]
    L.append(f"- strategy: **{strategy_id}**  |  mode: **{mode}**  |  "
             f"result: **{'PASS' if report.passed else 'FAIL'}**")
    L.append(f"- phase: **{'APPLIED' if applied else 'VALIDATE-ONLY'}**")
    if report.passed and summary:
        L.append(f"- estimated cash impact: {summary['cash_delta']:.2f} "
                 f"(buys {summary['buys']}, exits {summary['exits']})")
    if backup_path:
        L.append(f"- state backup: `{backup_path}`")
    L.append("")

    def section(title, disp):
        L.append(f"## {title} ({len(disp)})")
        if disp:
            L.append("| ticker | side | qty | price | status | notes |")
            L.append("|---|---|---|---|---|---|")
            for d in disp:
                notes = "; ".join(d.issues + d.deviations)
                L.append(f"| {d.row.ticker} | {d.row.side} | "
                         f"{d.row.actual_quantity} | {d.row.actual_fill_price} | "
                         f"{d.row.status} | {notes} |")
        else:
            L.append("_none_")
        L.append("")

    section("Applied", report.by(APPLY))
    section("Skipped (duplicates / cancelled)", report.by(SKIP))
    section("FAILED", report.by(FAIL))

    devs = [f"{d.row.ticker}: {x}" for d in report.dispositions
            for x in d.deviations]
    L.append(f"## Strategy deviations ({len(devs)})")
    L += [f"- {x}" for x in devs] or ["_none_"]
    L.append("")
    if summary and summary.get("partial_exits"):
        L.append("## PARTIAL EXIT — remaining shares still open, exit-required")
        L += [f"- {x}" for x in summary["partial_exits"]]
        L.append("")
    L.append(f"## Warnings ({len(report.warnings)})")
    L += [f"- {w}" for w in report.warnings] or ["_none_"]
    L.append("")
    if applied:
        L.append("_Equity after reconciliation is **provisional** (marked to "
                 "entry price, not to close); the next Daily Runner re-marks it "
                 "to close. cash / positions / shares / entry_price / "
                 "planned_exit_date are authoritative._")
    else:
        L.append("_Validate-only: no state or journal change. Re-run with "
                 "`--apply` to write (only if PASS)._")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------- run
def reconcile(ticket_path, plan_path, state_path, journal_dir, mode,
              out_dir, target_date=None, apply=False, strategy_id="",
              account_id="", journal_factory=None,
              next_session_fn=next_session_xnys):
    rows = parse_ticket(ticket_path)
    if target_date is None:
        target_date = (next((r.timestamp[:10] for r in rows if r.timestamp), None)
                       or next((r.plan_date for r in rows if r.plan_date), "")
                       or "")
    plan = load_plan(plan_path)
    state = load_state(Path(state_path))
    dnb = do_not_buy_from_ticket(rows)
    applied_keys = applied_keys_from_journal(journal_dir, mode)
    report = validate(rows, plan, state, target_date, dnb, applied_keys,
                      next_session_fn)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = None
    backup_path = None

    do_apply = apply and report.passed
    if apply and not report.passed:
        # FAIL -> no write; still emit the report
        pass
    if do_apply:
        # state backup
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        sp = Path(state_path)
        if sp.exists():
            backup_path = str(sp.with_suffix(sp.suffix + f".{ts}.bak"))
            shutil.copy2(sp, backup_path)
        new_state, fill_rows, summary = apply_to_state(
            report, state, plan, next_session_fn)
        save_state(new_state, sp)
        # journal fills + event
        if journal_factory is not None and fill_rows:
            jw = journal_factory()
            jw.write_fill(target_date, fill_rows, source_system="RECONCILIATION")
            jw.write_event("INFO", "reconciliation", "RECONCILIATION",
                           business_date=target_date, source_system="RECONCILIATION",
                           applied=len(report.by(APPLY)),
                           skipped=len(report.by(SKIP)),
                           failed=len(report.by(FAIL)))
            jw.close()
        # audit log (append-only)
        _audit(out_dir, target_date, ticket_path, report, summary, backup_path)

    text = render_report(report, do_apply, summary, backup_path,
                         strategy_id, mode)
    report_path = out_dir / f"reconciliation_report_{target_date}.md"
    report_path.write_text(text, encoding="utf-8")
    return report, do_apply, str(report_path)


def _audit(out_dir: Path, target_date, ticket_path, report, summary, backup):
    rec = {"ts": datetime.now(timezone.utc).isoformat(),
           "target_date": target_date, "ticket": str(ticket_path),
           "applied": len(report.by(APPLY)), "skipped": len(report.by(SKIP)),
           "failed": len(report.by(FAIL)),
           "cash_delta": summary.get("cash_delta") if summary else None,
           "backup": backup}
    with (out_dir / "reconciliation_audit.log").open(
            "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Manual fill reconciliation")
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--journal-dir", default=None)
    ap.add_argument("--mode", default="dry_run")
    ap.add_argument("--out", default=".")
    ap.add_argument("--target-date", default=None)
    ap.add_argument("--strategy-id", default="MLE-REGIME200-HOLD10-01")
    ap.add_argument("--account-id", default="")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    jf = None
    if args.apply and args.journal_dir:
        from journal import JournalWriter

        def jf():
            return JournalWriter(mode=args.mode, strategy_id=args.strategy_id,
                                 base_dir=args.journal_dir,
                                 source_system="RECONCILIATION")

    report, applied, report_path = reconcile(
        args.ticket, args.plan, args.state, args.journal_dir, args.mode,
        args.out, target_date=args.target_date, apply=args.apply,
        strategy_id=args.strategy_id, account_id=args.account_id,
        journal_factory=jf)
    print(f"result: {'PASS' if report.passed else 'FAIL'} | "
          f"{'APPLIED' if applied else 'VALIDATE-ONLY'} | report: {report_path}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
