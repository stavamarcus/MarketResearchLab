"""import_fills.py - broker executions -> normalized artifact + ticket (P2).

Spec: mle_paper_01/docs/FILL-IMPORT_design.md

    dump + plan + ticket  ->  artifact + ticket

This module NEVER reads the journal, NEVER calls TWS and NEVER writes
PortfolioState or the journal. Any blocking condition writes the artifact with
diagnostics and leaves the ticket byte-identical (rule 12).
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .fills import artifact as art
from .fills import matcher, normalize
from .fills.states import (COMPLETENESS_FULL, COMPLETENESS_NONE,
                           COMPLETENESS_PARTIAL, Diagnostic, ImportError_,
                           LATE_ENTRY, MISSING, MISSING_MAX_PRICE_FOR_QTY,
                           MISSING_REF_PRICE, PARTIAL_FINAL,
                           PLAN_PRICE_DEVIATION, PRICE_CAP_EXCEEDED)
from .fills.ticket_writer import (PLANNED_COLUMNS, build_row_values,
                                  detect_conflicts, read_ticket, write_ticket)

SESSION_OPEN_ET = "09:30"


def _plain(v):
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    return v


def _plan_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _planned_projection_sha256(header, rows) -> str:
    """Hash of the PLANNED columns only (decision 1, this round).

    ticket_sha256_before_import changes as soon as the first import writes the
    fill columns, so a second run over the same dump would produce a different
    canonical hash even though dump, plan and broker facts are unchanged. The
    planned projection is stable across imports.
    """
    cols = [c for c in PLANNED_COLUMNS if c in header]
    payload = "\n".join(
        "\x1f".join((r.get(c) or "").strip() for c in cols) for r in rows)
    return art.sha256_text("\x1e".join(cols) + "\x1e" + payload)


def _minutes_after_open(ts_et: str) -> int | None:
    try:
        dt = datetime.fromisoformat(ts_et)
    except Exception:
        return None
    open_dt = dt.replace(hour=9, minute=30, second=0, microsecond=0)
    return int((dt - open_dt).total_seconds() // 60)


def build_artifact(dump_path, plan_path, ticket_path, target_date,
                   expected_account, root, groups, matched, plan_states,
                   diagnostics, assertions, plan_reference_source,
                   plan_reference_completeness="NONE",
                   missing_ref_price=0, missing_max_price_for_qty=0):
    header, ticket_rows = read_ticket(ticket_path)
    orders = []
    for idx, g, state in matched:
        orders.append({
            "plan_row_index": idx,
            "perm_id": g["perm_id"],
            "order_id": g["order_id"],
            "account": g["account"],
            "ticker": g["ticker"],
            "conid": g["conid"],
            "sec_type": g["sec_type"],
            "currency": g["currency"],
            "side": g["side"],
            "broker_side": g["broker_side"],
            "session": g["session"],
            "total_quantity": _plain(g["total_quantity"]),
            "gross_notional": _plain(g["gross_notional"]),
            "commission_total": _plain(g["commission_total"]),
            "commission_currency": g["commission_currency"],
            "avg_fill_price": _plain(g["avg_fill_price"]),
            "first_fill_timestamp": g["first_fill_timestamp"],
            "last_fill_timestamp": g["last_fill_timestamp"],
            "execution_ids": list(g["execution_ids"]),
            "executions": [{k: _plain(v) for k, v in e.items()}
                           for e in g["executions"]],
            "match_state": state,
        })

    return {
        "schema": art.SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_date": target_date,
        "source": {
            "dump_path_relative": art.relative_path(dump_path, root),
            "dump_sha256": art.sha256_file(dump_path),
            "plan_path_relative": art.relative_path(plan_path, root),
            "plan_sha256": art.sha256_file(plan_path),
            "ticket_path_relative": art.relative_path(ticket_path, root),
            "ticket_planned_projection_sha256":
                _planned_projection_sha256(header, ticket_rows),
            "plan_reference_source": plan_reference_source,
            "plan_reference_completeness": plan_reference_completeness,
            "account": expected_account,
        },
        "operator_assertions": assertions,
        "orders": orders,
        "plan_rows": plan_states,
        "diagnostics": [d.to_dict()
                        for d in sorted(diagnostics, key=lambda x: x.sort_key())],
        "summary": {
            "broker_orders": len(groups),
            "executions": sum(len(g["executions"]) for g in groups),
            "matched": len(matched),
            "missing_plan_rows": sum(1 for p in plan_states
                                     if p["state"] == MISSING),
            "partial_final": sum(1 for _, _, s in matched
                                 if s == PARTIAL_FINAL),
            "missing_ref_price": missing_ref_price,
            "missing_max_price_for_qty": missing_max_price_for_qty,
        },
        "non_canonical_metadata": {
            "ticket_sha256_before_import": art.sha256_file(ticket_path),
        },
    }


def run(dump_path, plan_path, ticket_path, out_path, target_date,
        expected_account, root, apply_ticket=True, conflict_artifact=False,
        assertions=None):
    assertions = assertions or {"terminality": {}, "plan_reference": None}
    diagnostics: list[Diagnostic] = []
    plan_reference_source = ("OPERATOR_ASSERTION"
                             if assertions.get("plan_reference")
                             else "UNAVAILABLE")
    # Zdroj a uplnost jsou dve ruzne veci: plan muze mit nove sloupce
    # a presto u nekterych radku hodnotu nemit.
    plan_reference_completeness = COMPLETENESS_NONE
    missing_ref_price = missing_max_price_for_qty = 0
    groups, matched, plan_states = [], [], []
    blocking = None

    try:
        dump = normalize.load_dump(dump_path)
        groups = normalize.normalize(dump, target_date, expected_account)
        plan_rows = _plan_rows(plan_path)
        header, ticket_rows = read_ticket(ticket_path)
        matcher.side_mismatch_check(groups, plan_rows)
        # One-to-one kontrakt plan vs ticket musi projit DRIV, nez se
        # zacnou parovat broker exekuce - jinak by se overovalo proti
        # neoverenemu zakladu.
        matcher.check_plan_ticket_contract(plan_rows, ticket_rows)
        matched, plan_states = matcher.match(
            groups, plan_rows, ticket_rows, expected_account,
            assertions.get("terminality"))

        proposed = {idx: build_row_values(g, s) for idx, g, s in matched}
        diagnostics.extend(detect_conflicts(ticket_rows, proposed))

        # Cenove odchylky se pocitaji VYHRADNE ze strojovych poli planu.
        # Markdown report se nikdy neparsuje - prehozeny sloupec by tise
        # zmenil vysledek.
        if matcher.is_p5_plan(plan_rows):
            plan_reference_source = "ORDERS_PLAN"
            by_idx = {i: plan_rows[i] for i in range(len(plan_rows))}
            have_ref = have_cap = 0
            for idx, g, _st in matched:
                pr = by_idx.get(idx, {})
                avg = g["avg_fill_price"]
                cap = (pr.get("max_price_for_qty") or "").strip()
                ref = (pr.get("ref_price") or "").strip()
                # Chybejici hodnota u jednoho radku nesmi zablokovat vypocet
                # u ostatnich - hlasi se, ale ostatni radky se pocitaji dal.
                if cap:
                    have_cap += 1
                    if avg > Decimal(cap):
                        excess = (avg - Decimal(cap)) / Decimal(cap) * 100
                        diagnostics.append(Diagnostic(
                            PRICE_CAP_EXCEEDED,
                            f"{g['ticker']}: fill {avg} > max_price_for_qty "
                            f"{cap} (+{excess:.2f} %)", plan_row_index=idx,
                            perm_id=str(g["perm_id"])))
                else:
                    diagnostics.append(Diagnostic(
                        MISSING_MAX_PRICE_FOR_QTY,
                        f"{g['ticker']}: plan nema max_price_for_qty, "
                        f"cenovy strop se neoveruje", plan_row_index=idx,
                        perm_id=str(g["perm_id"])))
                if ref and Decimal(ref) != 0:
                    have_ref += 1
                    bps = (avg - Decimal(ref)) / Decimal(ref) * 10000
                    diagnostics.append(Diagnostic(
                        PLAN_PRICE_DEVIATION,
                        f"{g['ticker']}: fill {avg} vs plan ref {ref} "
                        f"({bps:+.1f} bps)", plan_row_index=idx,
                        perm_id=str(g["perm_id"])))
                else:
                    diagnostics.append(Diagnostic(
                        MISSING_REF_PRICE,
                        f"{g['ticker']}: plan nema ref_price, odchylka proti "
                        f"planu se nepocita", plan_row_index=idx,
                        perm_id=str(g["perm_id"])))
            n = len(matched)
            if n and have_ref == n and have_cap == n:
                plan_reference_completeness = COMPLETENESS_FULL
            elif have_ref or have_cap:
                plan_reference_completeness = COMPLETENESS_PARTIAL
            missing_ref_price = n - have_ref
            missing_max_price_for_qty = n - have_cap

        # LATE_ENTRY is computed from execution timestamps only (decision 3)
        if matched:
            first = min(g["first_fill_timestamp"] for _, g, _ in matched)
            last = max(g["last_fill_timestamp"] for _, g, _ in matched)
            mins = _minutes_after_open(first)
            if mins is not None and mins > 5:
                diagnostics.append(Diagnostic(
                    LATE_ENTRY,
                    f"first fill {first} ({mins} min after the {SESSION_OPEN_ET} "
                    f"ET open), last fill {last}"))
    except ImportError_ as exc:
        blocking = exc
        diagnostics.append(Diagnostic(exc.code, exc.message,
                                      exc.context.get("plan_row_index"),
                                      str(exc.context.get("perm_id") or ""),
                                      str(exc.context.get("exec_id") or "")))
        proposed = {}

    payload = build_artifact(dump_path, plan_path, ticket_path, target_date,
                             expected_account, root, groups, matched,
                             plan_states, diagnostics, assertions,
                             plan_reference_source,
                             plan_reference_completeness,
                             missing_ref_price, missing_max_price_for_qty)
    artifact_state = art.write_artifact(payload, out_path,
                                        conflict_artifact=conflict_artifact)

    if blocking is not None:
        return {"ok": False, "code": blocking.code, "message": blocking.message,
                "artifact": artifact_state, "ticket_written": False,
                "proposed": {}, "payload": payload}

    ticket_written = False
    if apply_ticket and proposed:
        header, ticket_rows = read_ticket(ticket_path)
        write_ticket(ticket_path, header, ticket_rows, proposed)
        ticket_written = True

    return {"ok": True, "code": "OK", "message": "", "artifact": artifact_state,
            "ticket_written": ticket_written, "proposed": proposed,
            "payload": payload}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Import broker fills into the ticket")
    ap.add_argument("--dump", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--out", required=True, help="normalized artifact path")
    ap.add_argument("--target-date", required=True)
    ap.add_argument("--account", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true",
                    help="write the artifact, leave the ticket untouched")
    ap.add_argument("--conflict-artifact", action="store_true")
    args = ap.parse_args(argv)

    res = run(args.dump, args.plan, args.ticket, args.out, args.target_date,
              args.account, args.root, apply_ticket=not args.dry_run,
              conflict_artifact=args.conflict_artifact)

    s = res["payload"]["summary"]
    print(f"artifact: {res['artifact']} | canonical_sha256: "
          f"{res['payload'].get('canonical_sha256', art.canonical_sha256(res['payload']))}")
    print(f"broker orders: {s['broker_orders']} | executions: {s['executions']} "
          f"| matched: {s['matched']} | missing plan rows: "
          f"{s['missing_plan_rows']}")
    for d in res["payload"]["diagnostics"]:
        print(f"  [{d['code']}] {d['message']}")
    if not res["ok"]:
        print(f"IMPORT BLOCKED: {res['code']}")
        print("  ticket unchanged")
        return 2
    print("ticket written" if res["ticket_written"]
          else "ticket unchanged (dry run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
