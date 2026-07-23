"""permId order groups -> Trade Plan rows, strictly one-to-one.

Matching uses hard attributes only: account, session, conid, side and the
aggregated quantity. The ticker is a cross-check, never the identity - two
orders on the same name, replacement orders or several entries during one day
must not silently collapse into a single ticket row.
"""
from decimal import Decimal

from .states import (AMBIGUOUS_MATCH, FOREIGN_ACCOUNT, ImportError_,
                     PARTIAL_FINAL, MATCHED, MISSING, PARTIAL_UNRESOLVED,
                     QUANTITY_OVER_PLAN, SIDE_MISMATCH, TICKER_CONID_MISMATCH,
                     UNMATCHED_BROKER_ORDER)


def match(groups, plan_rows, ticket_rows, expected_account,
          terminality_assertions=None):
    """Return [(plan_row_index, group, state)] or raise ImportError_.

    plan_rows    : ordered list of dicts from orders_plan_<date>.csv
    ticket_rows  : ordered list of dicts from the ticket (planned_quantity)
    """
    terminality_assertions = terminality_assertions or {}

    planned_qty = {}
    for tr in ticket_rows:
        raw = (tr.get("planned_quantity") or "").strip()
        planned_qty[(tr.get("ticker") or "").strip()] = (
            Decimal(raw) if raw else None)

    claims = {}          # plan_row_index -> [perm_id]
    group_claims = {}    # perm_id -> [plan_row_index]

    for g in groups:
        if g["account"] != expected_account:
            raise ImportError_(
                FOREIGN_ACCOUNT,
                f"permId {g['perm_id']}: account {g['account']} != "
                f"{expected_account}",
                perm_id=g["perm_id"])

        hits = []
        for idx, pr in enumerate(plan_rows):
            if str(pr.get("conid", "")).strip() != str(g["conid"]):
                continue
            if (pr.get("action") or "").strip().upper() != g["side"]:
                continue
            hits.append(idx)

        if not hits:
            raise ImportError_(
                UNMATCHED_BROKER_ORDER,
                f"permId {g['perm_id']} ({g['ticker']}, conid {g['conid']}, "
                f"{g['side']}) matches no plan row",
                perm_id=g["perm_id"])

        group_claims[g["perm_id"]] = hits
        for idx in hits:
            claims.setdefault(idx, []).append(g["perm_id"])

    for idx, perms in claims.items():
        if len(perms) > 1:
            raise ImportError_(
                AMBIGUOUS_MATCH,
                f"plan row {idx} ({plan_rows[idx].get('ticker')}) is claimed by "
                f"{len(perms)} broker orders: {', '.join(perms)}; aggregating "
                f"several orders into one ticket row is not supported",
                plan_row_index=idx)
    for perm_id, idxs in group_claims.items():
        if len(idxs) > 1:
            raise ImportError_(
                AMBIGUOUS_MATCH,
                f"permId {perm_id} matches {len(idxs)} plan rows",
                perm_id=perm_id)

    matched = []
    for g in groups:
        idx = group_claims[g["perm_id"]][0]
        pr = plan_rows[idx]

        if (pr.get("ticker") or "").strip() != g["ticker"]:
            raise ImportError_(
                TICKER_CONID_MISMATCH,
                f"permId {g['perm_id']}: conid {g['conid']} maps to plan "
                f"ticker {pr.get('ticker')} but the broker reports "
                f"{g['ticker']}",
                perm_id=g["perm_id"], plan_row_index=idx)

        planned = planned_qty.get(g["ticker"])
        if planned is None:
            state = MATCHED
        elif g["total_quantity"] > planned:
            raise ImportError_(
                QUANTITY_OVER_PLAN,
                f"{g['ticker']}: filled {g['total_quantity']} > planned "
                f"{planned}",
                perm_id=g["perm_id"], plan_row_index=idx)
        elif g["total_quantity"] < planned:
            # decision 6: terminality is an operator assertion, never inferred
            assertion = terminality_assertions.get(g["perm_id"])
            if not assertion or not (assertion.get("terminality_reason") or "").strip():
                raise ImportError_(
                    PARTIAL_UNRESOLVED,
                    f"{g['ticker']}: filled {g['total_quantity']} of "
                    f"{planned}; the remainder is not confirmed terminal. The "
                    f"importer cannot query open orders, so terminality must "
                    f"be asserted explicitly with a reason.",
                    perm_id=g["perm_id"], plan_row_index=idx)
            state = PARTIAL_FINAL
        else:
            state = MATCHED
        matched.append((idx, g, state))

    # decision 7: order groups follow plan row order
    matched.sort(key=lambda t: t[0])

    plan_states = []
    claimed = {idx for idx, _, _ in matched}
    for idx, pr in enumerate(plan_rows):
        plan_states.append({
            "plan_row_index": idx,
            "ticker": pr.get("ticker"),
            "state": MISSING if idx not in claimed else
            next(s for i, _, s in matched if i == idx),
        })

    return matched, plan_states


def side_mismatch_check(groups, plan_rows):
    """Explicit SIDE_MISMATCH when conid matches but the side does not."""
    by_conid = {}
    for pr in plan_rows:
        by_conid.setdefault(str(pr.get("conid", "")).strip(), []).append(pr)
    for g in groups:
        rows = by_conid.get(str(g["conid"]), [])
        if rows and all((r.get("action") or "").strip().upper() != g["side"]
                        for r in rows):
            raise ImportError_(
                SIDE_MISMATCH,
                f"permId {g['perm_id']} ({g['ticker']}): broker side "
                f"{g['side']}, plan says "
                f"{rows[0].get('action')}",
                perm_id=g["perm_id"])
