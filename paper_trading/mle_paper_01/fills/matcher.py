"""permId order groups -> Trade Plan rows, strictly one-to-one.

Matching uses hard attributes only: account, session, conid, side and the
aggregated quantity. The ticker is a cross-check, never the identity - two
orders on the same name, replacement orders or several entries during one day
must not silently collapse into a single ticket row.
"""
from decimal import Decimal

from .states import (AMBIGUOUS_MATCH, DUPLICATE_PLAN_ROW,
                     DUPLICATE_TICKET_ROW, FOREIGN_ACCOUNT, ImportError_,
                     PLAN_ROW_MISSING_IN_TICKET, TICKET_ROW_NOT_IN_PLAN,
                     PARTIAL_FINAL, MATCHED, MISSING, PARTIAL_UNRESOLVED,
                     PLAN_TICKET_QUANTITY_MISMATCH, QUANTITY_OVER_PLAN,
                     SIDE_MISMATCH, TICKER_CONID_MISMATCH,
                     UNMATCHED_BROKER_ORDER)


# Akce, ktere se skutecne zadavaji do TWS. DO_NOTHING je auditni radek,
# do one-to-one kontraktu nepatri.
EXECUTABLE_ACTIONS = ("BUY", "EXIT", "SELL")


def _qty(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except Exception:
        return None


def _is_executable(action, qty) -> bool:
    return (action or "").strip().upper() in EXECUTABLE_ACTIONS and \
        qty is not None and qty > 0


def is_p5_plan(plan_rows) -> bool:
    """Novy kontrakt poznam podle pritomnosti plan-reference sloupcu."""
    if not plan_rows:
        return False
    keys = set(plan_rows[0].keys())
    return bool(keys & {"ref_price", "ref_price_date", "max_price_for_qty",
                        "planned_exit_if_filled"})


def check_plan_ticket_contract(plan_rows, ticket_rows) -> None:
    """Obousmerna one-to-one kontrola plan vs ticket (P5 kontrakt).

    Identita je target_date + conid + action. Ticker je krizova kontrola,
    ne identita - conid je stabilni, ticker se muze zmenit.

    Bezi jen pro novy plan; stary plan bez plan-reference sloupcu zustava
    v legacy rezimu, kde je jedinym zdrojem planovaneho mnozstvi ticket.

    UNMATCHED_BROKER_ORDER tuhle kontrolu nenahrazuje - ta porovnava az
    broker exekuce proti UZ overenemu plan-ticket kontraktu.
    """
    if not is_p5_plan(plan_rows):
        return

    def index(rows, date_key, action_key, qty_key, dup_code, what):
        out = {}
        for r in rows:
            action = (r.get(action_key) or "").strip().upper()
            qty = _qty(r.get(qty_key))
            if not _is_executable(action, qty):
                continue
            key = ((r.get(date_key) or "").strip(),
                   str(r.get("conid") or "").strip(), action)
            if key in out:
                raise ImportError_(
                    dup_code,
                    f"{what} obsahuje dva executable radky se stejnou "
                    f"identitou {key}")
            out[key] = (r, qty)
        return out

    plan_idx = index(plan_rows, "date", "action", "quantity",
                     DUPLICATE_PLAN_ROW, "orders_plan")
    tick_idx = index(ticket_rows, "target_date", "side", "planned_quantity",
                     DUPLICATE_TICKET_ROW, "ticket")

    for key, (r, _q) in sorted(plan_idx.items()):
        if key not in tick_idx:
            raise ImportError_(
                PLAN_ROW_MISSING_IN_TICKET,
                f"plan ma executable radek {r.get('ticker')} {key}, "
                f"ticket odpovidajici radek nema")
    for key, (r, _q) in sorted(tick_idx.items()):
        if key not in plan_idx:
            raise ImportError_(
                TICKET_ROW_NOT_IN_PLAN,
                f"ticket ma executable radek {r.get('ticker')} {key}, "
                f"plan odpovidajici radek nema")

    for key in sorted(plan_idx):
        pr, pq = plan_idx[key]
        tr, tq = tick_idx[key]
        if pq != tq:
            raise ImportError_(
                PLAN_TICKET_QUANTITY_MISMATCH,
                f"{pr.get('ticker')}: orders_plan.quantity {pq} != "
                f"ticket.planned_quantity {tq}")
        pt = (pr.get("ticker") or "").strip()
        tt = (tr.get("ticker") or "").strip()
        if pt and tt and pt != tt:
            raise ImportError_(
                TICKER_CONID_MISMATCH,
                f"conid {key[1]}: plan rika {pt}, ticket {tt}")


def match(groups, plan_rows, ticket_rows, expected_account,
          terminality_assertions=None):
    """Return [(plan_row_index, group, state)] or raise ImportError_.

    plan_rows    : ordered list of dicts from orders_plan_<date>.csv
    ticket_rows  : ordered list of dicts from the ticket (planned_quantity)
    """
    terminality_assertions = terminality_assertions or {}

    # Planovane mnozstvi: NOVY plan je autoritativni zdroj. Ticket zustava
    # exekucnim artefaktem. Starsi plany maji quantity prazdnou - tam se
    # legacy fallbackem cte dal z ticketu.
    ticket_qty = {}
    for tr in ticket_rows:
        raw = (tr.get("planned_quantity") or "").strip()
        ticket_qty[(tr.get("ticker") or "").strip()] = (
            Decimal(raw) if raw else None)

    planned_qty, plan_qty_source = {}, {}
    for pr in plan_rows:
        tk = (pr.get("ticker") or "").strip()
        if not tk:
            continue
        raw = (pr.get("quantity") or "").strip()
        if raw:
            planned_qty[tk] = Decimal(raw)
            plan_qty_source[tk] = "PLAN"
        else:
            planned_qty[tk] = ticket_qty.get(tk)
            plan_qty_source[tk] = "TICKET_LEGACY"

    # Kdyz mnozstvi zna plan i ticket a nesouhlasi, nevime ktere plati.
    # Hadat je horsi nez zastavit - ticket se nesmi zmenit.
    for tk, src in plan_qty_source.items():
        if src != "PLAN":
            continue
        tq = ticket_qty.get(tk)
        if tq is not None and tq != planned_qty[tk]:
            raise ImportError_(
                PLAN_TICKET_QUANTITY_MISMATCH,
                f"{tk}: orders_plan.quantity {planned_qty[tk]} != "
                f"ticket.planned_quantity {tq}")

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
