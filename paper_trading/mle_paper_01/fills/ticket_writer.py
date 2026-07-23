"""Ticket writer: fills the broker columns, never the planned ones.

Planned columns are copied through byte-for-byte. Conflict detection uses
broker facts only (decision 9); ``actual_fill_price`` is derived and is not a
source of identity or conflict.
"""
import csv
import os
from decimal import Decimal
from pathlib import Path

from .states import (CONFLICTING_EXISTING_TICKET, DERIVED_FIELD_STALE,
                     Diagnostic, ImportError_)

PLANNED_COLUMNS = ("target_date", "ticker", "conid", "side",
                   "planned_quantity", "order_timing", "order_type")

P2_COLUMNS = ("broker_account", "perm_id", "fill_id", "execution_ids",
              "gross_notional")

FILL_COLUMNS = ("actual_fill_price", "actual_quantity", "timestamp",
                "commission_fees", "order_id", "status") + P2_COLUMNS

# Broker facts that define a conflict (decision 9).
CONFLICT_FIELDS = ("actual_quantity", "gross_notional", "commission_fees",
                   "broker_account", "perm_id", "execution_ids")


def _plain(v) -> str:
    """Decimal -> string without exponent notation or trailing noise."""
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    return "" if v is None else str(v)


def read_ticket(path):
    with Path(path).open(encoding="utf-8", newline="") as fh:
        r = csv.DictReader(fh)
        return list(r.fieldnames or []), list(r)


def build_row_values(group, state) -> dict:
    """Broker columns for one matched order group."""
    from .states import PARTIAL_FINAL
    return {
        "actual_quantity": _plain(group["total_quantity"]),
        "actual_fill_price": _plain(group["avg_fill_price"]),
        "gross_notional": _plain(group["gross_notional"]),
        "commission_fees": _plain(group["commission_total"]),
        "timestamp": group["last_fill_timestamp"],
        "status": "partial" if state == PARTIAL_FINAL else "filled",
        "broker_account": group["account"],
        "perm_id": str(group["perm_id"]),
        "order_id": str(group["order_id"]),
        "fill_id": "",
        "execution_ids": ";".join(group["execution_ids"]),
    }


def detect_conflicts(existing_rows, proposed):
    """Blocking conflict on broker facts; stale derived price is a warning."""
    diagnostics = []
    for idx, values in proposed.items():
        row = existing_rows[idx]
        differing = []
        for field in CONFLICT_FIELDS:
            old = (row.get(field) or "").strip()
            if old == "":
                continue                     # blank row: nothing to conflict
            new = values[field]
            if field in ("actual_quantity", "gross_notional",
                         "commission_fees"):
                try:
                    if Decimal(old) != Decimal(new):
                        differing.append(f"{field}: {old} != {new}")
                except Exception:
                    differing.append(f"{field}: {old} != {new} (unparsable)")
            elif old != new:
                differing.append(f"{field}: {old} != {new}")
        if differing:
            raise ImportError_(
                CONFLICTING_EXISTING_TICKET,
                f"row {idx} ({row.get('ticker')}): existing ticket values "
                f"contradict broker data - " + "; ".join(differing),
                plan_row_index=idx)

        old_price = (row.get("actual_fill_price") or "").strip()
        if old_price:
            try:
                if Decimal(old_price) != Decimal(values["actual_fill_price"]):
                    diagnostics.append(Diagnostic(
                        DERIVED_FIELD_STALE,
                        f"row {idx} ({row.get('ticker')}): stored "
                        f"actual_fill_price {old_price} differs from the "
                        f"recomputed gross_notional/quantity "
                        f"{values['actual_fill_price']}",
                        plan_row_index=idx))
            except Exception:
                pass
    return diagnostics


def write_ticket(path, header, rows, proposed):
    """Atomic write. Planned columns are never modified."""
    out_header = list(header)
    for col in P2_COLUMNS:
        if col not in out_header:
            out_header.append(col)

    new_rows = []
    for idx, row in enumerate(rows):
        merged = {c: row.get(c, "") for c in out_header}
        if idx in proposed:
            for k, v in proposed[idx].items():
                if k in PLANNED_COLUMNS:
                    raise AssertionError(f"refusing to write planned column {k}")
                merged[k] = v
        new_rows.append(merged)

    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_header)
        w.writeheader()
        for r in new_rows:
            w.writerow(r)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return out_header, new_rows
