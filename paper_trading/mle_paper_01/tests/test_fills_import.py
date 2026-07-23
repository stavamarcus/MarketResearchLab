"""P2 fill import tests (FILL-IMPORT_design.md)."""
import ast
import csv
import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from mle_paper_01 import import_fills as imp
from mle_paper_01 import reconciliation as rec
from mle_paper_01.fills import artifact as art
from mle_paper_01.fills import matcher, normalize
from mle_paper_01.fills.states import ImportError_
from mle_paper_01.fills import ticket_writer as tw

TD = "2026-07-22"
ACCT = "DUQ199078"

PLAN_COLS = ["date", "ticker", "conid", "action", "quantity", "target_value",
             "reason", "price_source"]
TICKET_COLS = ["target_date", "ticker", "conid", "side", "planned_quantity",
               "order_timing", "order_type", "actual_fill_price",
               "actual_quantity", "timestamp", "commission_fees", "order_id",
               "status"]

NAMES = [("PYPL", 199169591, 53), ("MPC", 89495776, 9)]


def _ex(exec_id, perm, sym, conid, shares, price, comm, ts, acct=ACCT,
        side="BOT"):
    return {"execId": exec_id, "permId": perm, "symbol": sym, "conid": conid,
            "secType": "STK", "currency": "USD", "exchange": "NASDAQ",
            "side": side, "shares": shares, "price": price, "avgPrice": price,
            "cumQty": shares, "commission": comm, "commission_currency": "USD",
            "account": acct, "orderId": 0,
            "timestamp_raw": "20260722 11:53:00 US/Eastern",
            "timestamp_et": ts}


def mk_dump(tmp, executions):
    p = tmp / "dump.json"
    p.write_text(json.dumps({"schema": "broker_execution_dump/1.0",
                             "executions": executions}), encoding="utf-8")
    return p


def mk_plan(tmp, names=NAMES):
    p = tmp / "plan.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(PLAN_COLS)
        for i, (tk, cid, _) in enumerate(names):
            w.writerow([TD, tk, cid, "BUY", "", 3000, f"rank_{i+1}", "next_open"])
    return p


def mk_ticket(tmp, names=NAMES, extra_cols=None, values=None):
    p = tmp / "ticket.csv"
    cols = list(TICKET_COLS) + list(extra_cols or [])
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for tk, cid, qty in names:
            row = {c: "" for c in cols}
            row.update({"target_date": TD, "ticker": tk, "conid": cid,
                        "side": "BUY", "planned_quantity": qty,
                        "order_timing": "target_date open",
                        "order_type": "TBD"})
            if values and tk in values:
                row.update(values[tk])
            w.writerow(row)
    return p


def base_execs():
    return [
        _ex("E1", 2028004632, "PYPL", 199169591, 14, 55.61, 1.0,
            f"{TD}T11:53:00-04:00"),
        _ex("E2", 2028004632, "PYPL", 199169591, 39, 55.61, 0.0001,
            f"{TD}T11:53:01-04:00"),
        _ex("E3", 2028004641, "MPC", 89495776, 9, 317.91, 1.0,
            f"{TD}T11:57:14-04:00"),
    ]


def run_import(tmp, execs=None, names=NAMES, ticket_values=None,
               extra_cols=None, apply_ticket=True, assertions=None):
    dump = mk_dump(tmp, execs if execs is not None else base_execs())
    plan = mk_plan(tmp, names)
    ticket = mk_ticket(tmp, names, extra_cols, ticket_values)
    out = tmp / "artifact.json"
    return imp.run(dump, plan, ticket, out, TD, ACCT, tmp,
                   apply_ticket=apply_ticket, assertions=assertions), ticket, out


# ---------------------------------------------------------------- happy path
def test_all_matched(tmp_path):
    res, ticket, _ = run_import(tmp_path)
    assert res["ok"] and res["ticket_written"]
    rows = list(csv.DictReader(ticket.open(encoding="utf-8")))
    pypl = rows[0]
    assert pypl["actual_quantity"] == "53"
    assert pypl["gross_notional"] == "2947.33"
    assert pypl["commission_fees"] == "1.0001"
    assert pypl["perm_id"] == "2028004632"
    assert pypl["broker_account"] == ACCT
    assert pypl["execution_ids"] == "E1;E2"
    assert pypl["status"] == "filled"


def test_group_by_perm_id_weighted_average(tmp_path):
    execs = base_execs()
    execs[0]["price"] = 55.00
    execs[1]["price"] = 56.00
    res, ticket, _ = run_import(tmp_path, execs)
    rows = list(csv.DictReader(ticket.open(encoding="utf-8")))
    gross = Decimal("14") * Decimal("55.00") + Decimal("39") * Decimal("56.00")
    assert Decimal(rows[0]["gross_notional"]) == gross
    assert Decimal(rows[0]["actual_fill_price"]) == gross / Decimal(53)


def test_commission_summed_before_rounding(tmp_path):
    res, ticket, _ = run_import(tmp_path)
    rows = list(csv.DictReader(ticket.open(encoding="utf-8")))
    assert Decimal(rows[0]["commission_fees"]) == Decimal("1.0001")


def test_planned_columns_immutable(tmp_path):
    dump = mk_dump(tmp_path, base_execs())
    plan = mk_plan(tmp_path)
    ticket = mk_ticket(tmp_path)
    before = [{k: r[k] for k in tw.PLANNED_COLUMNS}
              for r in csv.DictReader(ticket.open(encoding="utf-8"))]
    imp.run(dump, plan, ticket, tmp_path / "a.json", TD, ACCT, tmp_path)
    after = [{k: r[k] for k in tw.PLANNED_COLUMNS}
             for r in csv.DictReader(ticket.open(encoding="utf-8"))]
    assert before == after


# ---------------------------------------------------------------- blocking
def _blocks(tmp, code, **kw):
    res, ticket, _ = run_import(tmp, **kw)
    assert not res["ok"], f"expected {code}"
    assert res["code"] == code, res["code"]
    assert not res["ticket_written"]
    return res, ticket


def test_commission_null_blocks(tmp_path):
    execs = base_execs()
    execs[1]["commission"] = None
    _blocks(tmp_path, "COMMISSION_PENDING", execs=execs)


def test_commission_zero_is_not_pending(tmp_path):
    execs = base_execs()
    execs[1]["commission"] = 0.0
    res, _, _ = run_import(tmp_path, execs)
    assert res["ok"]


def test_duplicate_exec_id_blocks(tmp_path):
    execs = base_execs()
    execs.append(dict(execs[0]))
    _blocks(tmp_path, "DUPLICATE_EXEC_ID", execs=execs)


def test_cross_session_order_blocks(tmp_path):
    execs = base_execs()
    execs[1]["timestamp_et"] = "2026-07-21T11:53:00-04:00"
    _blocks(tmp_path, "CROSS_SESSION_ORDER", execs=execs)


def test_wrong_session_blocks(tmp_path):
    execs = base_execs()
    for e in execs:
        e["timestamp_et"] = "2026-07-21T11:53:00-04:00"
    _blocks(tmp_path, "WRONG_SESSION", execs=execs)


def test_unparsable_timestamp_blocks(tmp_path):
    execs = base_execs()
    execs[0]["timestamp_et"] = None
    _blocks(tmp_path, "WRONG_SESSION", execs=execs)


def test_foreign_account_blocks(tmp_path):
    execs = base_execs()
    for e in execs:
        if e["permId"] == 2028004641:
            e["account"] = "DU9999999"
    _blocks(tmp_path, "FOREIGN_ACCOUNT", execs=execs)


def test_side_mismatch_blocks(tmp_path):
    execs = base_execs()
    for e in execs:
        e["side"] = "SLD"
    _blocks(tmp_path, "SIDE_MISMATCH", execs=execs)


def test_quantity_over_plan_blocks(tmp_path):
    execs = base_execs()
    execs[1]["shares"] = 60
    _blocks(tmp_path, "QUANTITY_OVER_PLAN", execs=execs)


def test_unmatched_broker_order_blocks(tmp_path):
    execs = base_execs() + [
        _ex("E9", 2028009999, "ZZZ", 42, 5, 10.0, 1.0, f"{TD}T12:00:00-04:00")]
    _blocks(tmp_path, "UNMATCHED_BROKER_ORDER", execs=execs)


def test_ambiguous_two_groups_one_plan_row(tmp_path):
    execs = base_execs() + [
        _ex("E8", 2028007777, "PYPL", 199169591, 1, 55.0, 1.0,
            f"{TD}T12:00:00-04:00")]
    _blocks(tmp_path, "AMBIGUOUS_MATCH", execs=execs)


def test_partial_unresolved_blocks(tmp_path):
    execs = [e for e in base_execs() if e["execId"] != "E2"]
    _blocks(tmp_path, "PARTIAL_UNRESOLVED", execs=execs)


def test_partial_final_requires_reason(tmp_path):
    execs = [e for e in base_execs() if e["execId"] != "E2"]
    assertions = {"terminality": {"2028004632": {"terminality_asserted": True,
                                                 "terminality_source": "OPERATOR",
                                                 "terminality_reason": ""}}}
    _blocks(tmp_path, "PARTIAL_UNRESOLVED", execs=execs, assertions=assertions)


def test_partial_final_applies_real_quantity(tmp_path):
    execs = [e for e in base_execs() if e["execId"] != "E2"]
    assertions = {"terminality": {"2028004632": {
        "terminality_asserted": True, "terminality_source": "OPERATOR",
        "terminality_asserted_at_utc": "2026-07-22T20:00:00+00:00",
        "terminality_reason": "remainder cancelled in TWS"}}}
    res, ticket, _ = run_import(tmp_path, execs, assertions=assertions)
    assert res["ok"]
    rows = list(csv.DictReader(ticket.open(encoding="utf-8")))
    assert rows[0]["status"] == "partial" and rows[0]["actual_quantity"] == "14"


def test_missing_plan_row_left_blank(tmp_path):
    execs = [e for e in base_execs() if e["permId"] != 2028004641]
    res, ticket, out = run_import(tmp_path, execs)
    assert res["ok"]
    rows = list(csv.DictReader(ticket.open(encoding="utf-8")))
    assert rows[1]["actual_quantity"] == "" and rows[1]["status"] == ""
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["missing_plan_rows"] == 1


def test_conflicting_existing_ticket_blocks(tmp_path):
    vals = {"PYPL": {"actual_quantity": "50", "gross_notional": "1.0",
                     "perm_id": "2028004632", "broker_account": ACCT}}
    _blocks(tmp_path, "CONFLICTING_EXISTING_TICKET",
            ticket_values=vals, extra_cols=list(tw.P2_COLUMNS))


def test_conflict_ignores_derived_price(tmp_path):
    vals = {"PYPL": {"actual_fill_price": "99.99"}}
    res, _, out = run_import(tmp_path, ticket_values=vals,
                             extra_cols=list(tw.P2_COLUMNS))
    assert res["ok"]
    codes = {d["code"] for d in json.loads(out.read_text(encoding="utf-8"))["diagnostics"]}
    assert "DERIVED_FIELD_STALE" in codes


def test_hard_fail_leaves_ticket_byte_identical(tmp_path):
    execs = base_execs()
    execs[1]["commission"] = None
    dump = mk_dump(tmp_path, execs)
    plan = mk_plan(tmp_path)
    ticket = mk_ticket(tmp_path)
    before = ticket.read_bytes()
    res = imp.run(dump, plan, ticket, tmp_path / "a.json", TD, ACCT, tmp_path)
    assert not res["ok"]
    assert ticket.read_bytes() == before
    payload = json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))
    assert any(d["code"] == "COMMISSION_PENDING" for d in payload["diagnostics"])


# ------------------------------------------------------------ canonical form
def test_canonical_excludes_generated_at(tmp_path):
    res, _, out = run_import(tmp_path, apply_ticket=False)
    a = json.loads(out.read_text(encoding="utf-8"))
    b = copy.deepcopy(a)
    b["generated_at_utc"] = "1999-01-01T00:00:00+00:00"
    assert art.canonical_sha256(a) == art.canonical_sha256(b)


def test_reimport_after_ticket_write_has_same_canonical_hash(tmp_path):
    """Decision 1 (this round): the ticket changes after the first import.

    Canonical content uses the planned projection, so the hash is stable.
    """
    dump = mk_dump(tmp_path, base_execs())
    plan = mk_plan(tmp_path)
    ticket = mk_ticket(tmp_path)
    r1 = imp.run(dump, plan, ticket, tmp_path / "a1.json", TD, ACCT, tmp_path)
    assert r1["ok"] and r1["ticket_written"]
    r2 = imp.run(dump, plan, ticket, tmp_path / "a2.json", TD, ACCT, tmp_path)
    assert r2["ok"]
    h1 = art.canonical_sha256(r1["payload"])
    h2 = art.canonical_sha256(r2["payload"])
    assert h1 == h2, "canonical hash must not depend on the ticket fill columns"


def test_no_absolute_paths_in_canonical(tmp_path):
    res, _, out = run_import(tmp_path, apply_ticket=False)
    blob = art.canonical_bytes(res["payload"]).decode("utf-8")
    assert "/home" not in blob and "\\Users" not in blob and ":\\" not in blob
    assert str(tmp_path) not in blob


def test_artifact_has_no_journal_derived_state(tmp_path):
    res, _, _ = run_import(tmp_path, apply_ticket=False)
    blob = art.canonical_bytes(res["payload"]).decode("utf-8")
    assert "already_applied" not in blob and "import_state" not in blob


def test_executions_sorted_canonically(tmp_path):
    execs = list(reversed(base_execs()))
    res, _, _ = run_import(tmp_path, execs, apply_ticket=False)
    order = res["payload"]["orders"][0]
    ids = [e["exec_id"] for e in order["executions"]]
    assert ids == sorted(ids)
    assert order["execution_ids"] == ids


def test_order_groups_follow_plan_row_order(tmp_path):
    res, _, _ = run_import(tmp_path, apply_ticket=False)
    idxs = [o["plan_row_index"] for o in res["payload"]["orders"]]
    assert idxs == sorted(idxs)


def test_diagnostics_stable_sort(tmp_path):
    from mle_paper_01.fills.states import Diagnostic
    ds = [Diagnostic("B", "m", 2, "p2", "e2"), Diagnostic("A", "m", 1, "p1"),
          Diagnostic("A", "m", None, "p0")]
    keys = [d.sort_key() for d in sorted(ds, key=lambda x: x.sort_key())]
    assert keys == sorted(keys)


# ------------------------------------------------------- artifact conflicts
def test_artifact_same_hash_is_noop(tmp_path):
    res, _, out = run_import(tmp_path, apply_ticket=False)
    mtime = out.stat().st_mtime_ns
    state = art.write_artifact(res["payload"], out)
    assert state == "unchanged" and out.stat().st_mtime_ns == mtime


def test_artifact_different_hash_conflicts(tmp_path):
    res, _, out = run_import(tmp_path, apply_ticket=False)
    before = out.read_bytes()
    changed = copy.deepcopy(res["payload"])
    changed["target_date"] = "2026-07-23"
    with pytest.raises(ImportError_) as e:
        art.write_artifact(changed, out)
    assert e.value.code == "NORMALIZED_ARTIFACT_CONFLICT"
    assert out.read_bytes() == before


def test_conflict_artifact_is_versioned_and_still_stops(tmp_path):
    res, _, out = run_import(tmp_path, apply_ticket=False)
    changed = copy.deepcopy(res["payload"])
    changed["target_date"] = "2026-07-23"
    changed["generated_at_utc"] = "2026-07-22T21:00:00+00:00"
    with pytest.raises(ImportError_):
        art.write_artifact(changed, out, conflict_artifact=True)
    assert list(out.parent.glob("artifact.conflict_*.json"))


# ------------------------------------------------------------ layer contract
def _sources():
    base = Path(imp.__file__).parent
    return [base / "import_fills.py"] + sorted((base / "fills").glob("*.py"))


def test_importer_never_calls_tws():
    for p in _sources():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                mods = ([a.name for a in n.names]
                        if isinstance(n, ast.Import) else [n.module or ""])
                for m in mods:
                    assert "ibapi" not in (m or ""), f"{p.name} imports {m}"


def _identifiers(path):
    """Names actually referenced in code - docstrings and comments excluded.

    A prose sentence saying the importer never touches the journal must not
    make the scan fail; only real references count.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            names.add(n.attr)
        elif isinstance(n, ast.Import):
            names.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            names.add(n.module or "")
            names.update(a.name for a in n.names)
    # string literals count too (a hardcoded path would be a reference),
    # but docstrings are prose and must not trip the scan
    docstring_nodes = set()
    for n in ast.walk(tree):
        body = getattr(n, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstring_nodes.add(id(first.value))
    for n in ast.walk(tree):
        if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docstring_nodes):
            names.add(n.value)
    return names


def test_importer_never_reads_journal():
    for p in _sources():
        for ident in _identifiers(p):
            assert "journal" not in str(ident).lower(), \
                f"{p.name} references {ident}"


def test_importer_never_writes_state_or_journal():
    for p in _sources():
        idents = _identifiers(p)
        for bad in ("save_state", "write_fill", "write_event",
                    "PortfolioState", "load_state"):
            assert bad not in idents, f"{p.name} references {bad}"


# ------------------------------------------------- reconciliation identity
def _row(**kw):
    base = dict(ticker="AAA", conid="1", side="BUY",
                planned_quantity=Decimal(10), actual_quantity=Decimal(10),
                actual_fill_price=Decimal("100"), timestamp=TD,
                commission_fees=Decimal("1"), order_id="", status="filled")
    base.update(kw)
    return rec.FillRow(**base)


def test_key_is_account_scoped():
    r = _row(broker_account=ACCT, perm_id="2028004632")
    assert rec.fill_key(r, TD, rec.SCHEMA_P2) == f"ibkr:{ACCT}:perm:2028004632"


def test_order_id_zero_never_enters_key():
    keys = {rec.fill_key(_row(broker_account=ACCT, perm_id=str(1000 + i),
                              order_id="0"), TD, rec.SCHEMA_P2)
            for i in range(10)}
    assert len(keys) == 10
    assert not any(k.endswith(":order:0") for k in keys)


def test_key_precedence_perm_over_fill_id():
    r = _row(broker_account=ACCT, perm_id="7", fill_id="uuid-1")
    assert rec.fill_key(r, TD, rec.SCHEMA_P2).endswith(":perm:7")


def test_p2_manual_row_uses_fill_id():
    r = _row(fill_id="uuid-1")
    assert rec.fill_key(r, TD, rec.SCHEMA_P2) == "fill:uuid-1"


def test_p2_ticket_never_uses_legacy_hash():
    with pytest.raises(rec.InvalidFillIdentity):
        rec.fill_key(_row(order_id="12345"), TD, rec.SCHEMA_P2)


def test_pre_p2_ticket_still_uses_order_id_and_hash():
    assert rec.fill_key(_row(order_id="DUP"), TD, rec.SCHEMA_LEGACY) == "order:DUP"
    assert rec.fill_key(_row(), TD, rec.SCHEMA_LEGACY).startswith("hash:")


@pytest.mark.parametrize("value,valid", [
    ("0", False), (0, False), ("0.0", False), ("", False), (None, False),
    ("2028004632", True), ("DUP", True)])
def test_valid_id(value, valid):
    assert rec._valid_id(value) is valid


# ------------------------------------------------------- ticket schema
def _schema_ticket(tmp, cols):
    p = tmp / "t.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(TICKET_COLS) + list(cols))
        w.writeheader()
    return p


def test_schema_all_five_is_p2(tmp_path):
    assert rec.ticket_schema(_schema_ticket(tmp_path, rec.P2_COLUMNS)) == rec.SCHEMA_P2


def test_schema_none_is_legacy(tmp_path):
    assert rec.ticket_schema(_schema_ticket(tmp_path, [])) == rec.SCHEMA_LEGACY


@pytest.mark.parametrize("subset", [
    ("perm_id",), ("perm_id", "fill_id"),
    ("broker_account", "perm_id", "fill_id", "execution_ids")])
def test_schema_partial_is_invalid(tmp_path, subset):
    assert rec.ticket_schema(_schema_ticket(tmp_path, subset)) == rec.SCHEMA_INVALID


# ------------------------------------------------------------- cash math
def test_cash_delta_buy():
    r = _row(broker_account=ACCT, perm_id="1", actual_quantity=Decimal(53),
             actual_fill_price=Decimal("55.61"),
             gross_notional=Decimal("2947.33"),
             commission_fees=Decimal("1.0001"))
    assert -(r.notional + r.commission_fees) == Decimal("-2948.3301")


def test_cash_delta_sell():
    r = _row(side="EXIT", broker_account=ACCT, perm_id="1",
             actual_quantity=Decimal(53), actual_fill_price=Decimal("55.61"),
             gross_notional=Decimal("2947.33"),
             commission_fees=Decimal("1.0001"))
    assert (r.notional - r.commission_fees) == Decimal("2946.3299")


def test_notional_prefers_gross_over_recompute():
    r = _row(gross_notional=Decimal("2947.33"), actual_quantity=Decimal(53),
             actual_fill_price=Decimal("55.6100000001"))
    assert r.notional == Decimal("2947.33")


def test_decimal_survives_ticket_parsing(tmp_path):
    ticket = mk_ticket(tmp_path, extra_cols=list(tw.P2_COLUMNS),
                       values={"PYPL": {"actual_quantity": "53",
                                        "actual_fill_price": "55.61",
                                        "gross_notional": "2947.33",
                                        "commission_fees": "1.0001"}})
    row = rec.parse_ticket(ticket)[0]
    for f in ("actual_quantity", "actual_fill_price", "gross_notional",
              "commission_fees", "planned_quantity"):
        assert isinstance(getattr(row, f), Decimal), f
