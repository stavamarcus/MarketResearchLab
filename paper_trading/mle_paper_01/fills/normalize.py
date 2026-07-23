"""Raw broker dump -> permId order groups.

Decimal everywhere (decision 9). Values are built with ``Decimal(str(v))``,
never ``Decimal(float)``, so binary representation error never enters the
money math. Sums are computed before any rounding.
"""
import json
from decimal import Decimal
from pathlib import Path

from .states import (COMMISSION_PENDING, CROSS_SESSION_ORDER,
                     DUPLICATE_EXEC_ID, GROUP_INCONSISTENT, ImportError_,
                     WRONG_SESSION)

SIDE_MAP = {"BOT": "BUY", "SLD": "SELL"}


def _dec(v) -> Decimal:
    return Decimal(str(v))


def load_dump(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _session_of(execution) -> str:
    ts = execution.get("timestamp_et")
    if not ts:
        raise ImportError_(
            WRONG_SESSION,
            f"execution {execution.get('execId')} has no parsable timestamp; "
            f"a session is never assumed",
            exec_id=execution.get("execId"))
    return ts[:10]


def normalize(dump: dict, target_date: str, expected_account: str) -> list:
    """Return permId groups, each with Decimal aggregates.

    Raises ImportError_ on any blocking condition.
    """
    executions = dump.get("executions") or []

    seen = {}
    for e in executions:
        eid = e.get("execId")
        if eid in seen:
            raise ImportError_(
                DUPLICATE_EXEC_ID,
                f"execId {eid} appears more than once in the dump; "
                f"deduplicating silently would hide a broker or dump error",
                exec_id=eid)
        seen[eid] = e

    groups = {}
    for e in executions:
        groups.setdefault(str(e.get("permId")), []).append(e)

    out = []
    for perm_id, execs in groups.items():
        # decision 7: canonical execution order
        execs = sorted(execs, key=lambda x: (x.get("timestamp_et") or "",
                                             x.get("execId") or ""))

        accounts = {e.get("account") for e in execs}
        conids = {e.get("conid") for e in execs}
        sides = {e.get("side") for e in execs}
        if len(accounts) > 1 or len(conids) > 1 or len(sides) > 1:
            raise ImportError_(
                GROUP_INCONSISTENT,
                f"permId {perm_id}: executions disagree on account/conid/side",
                perm_id=perm_id)

        # decision 10 (previous round): session validated PER EXECUTION
        sessions = {_session_of(e) for e in execs}
        if len(sessions) > 1:
            raise ImportError_(
                CROSS_SESSION_ORDER,
                f"permId {perm_id}: executions span sessions {sorted(sessions)}",
                perm_id=perm_id)
        session = sessions.pop()
        if session != target_date:
            raise ImportError_(
                WRONG_SESSION,
                f"permId {perm_id}: session {session} != target_date "
                f"{target_date}",
                perm_id=perm_id)

        # decision 5 (previous round): commission null blocks, 0.0 does not
        missing = [e.get("execId") for e in execs if e.get("commission") is None]
        if missing:
            raise ImportError_(
                COMMISSION_PENDING,
                f"permId {perm_id}: commission report missing for "
                f"{', '.join(missing)}; re-run the dump once IBKR has reported "
                f"them (0.0 would mean a real zero commission)",
                perm_id=perm_id)

        total_qty = sum((_dec(e["shares"]) for e in execs), Decimal(0))
        gross = sum((_dec(e["shares"]) * _dec(e["price"]) for e in execs),
                    Decimal(0))
        commission = sum((_dec(e["commission"]) for e in execs), Decimal(0))

        broker_side = sides.pop()
        side = SIDE_MAP.get(broker_side)
        if side is None:
            raise ImportError_(
                GROUP_INCONSISTENT,
                f"permId {perm_id}: unknown broker side {broker_side!r}",
                perm_id=perm_id)

        times = [e.get("timestamp_et") for e in execs]
        out.append({
            "perm_id": perm_id,
            "order_id": str(execs[0].get("orderId")),
            "account": accounts.pop(),
            "ticker": execs[0].get("symbol"),
            "conid": conids.pop(),
            "sec_type": execs[0].get("secType"),
            "currency": execs[0].get("currency"),
            "side": side,
            "broker_side": broker_side,
            "session": session,
            "total_quantity": total_qty,
            "gross_notional": gross,
            "commission_total": commission,
            "commission_currency": execs[0].get("commission_currency"),
            "avg_fill_price": (gross / total_qty if total_qty else Decimal(0)),
            "first_fill_timestamp": min(times),
            "last_fill_timestamp": max(times),
            "execution_ids": [e.get("execId") for e in execs],
            "executions": [{
                "exec_id": e.get("execId"),
                "shares": _dec(e["shares"]),
                "price": _dec(e["price"]),
                "cum_qty": _dec(e["cumQty"]),
                "commission": _dec(e["commission"]),
                "exchange": e.get("exchange"),
                "timestamp_raw": e.get("timestamp_raw"),
                "timestamp_et": e.get("timestamp_et"),
            } for e in execs],
        })
    return out
