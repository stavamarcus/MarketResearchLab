"""EXECUTION_DEVIATION / LATE_ENTRY event tests (architect decision 1, P2)."""
import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest

from mle_paper_01 import reconciliation as rec
from mle_paper_01.fills import artifact as art

TD = "2026-07-22"
ACCT = "DUQ199078"
STRAT = "MLE-REGIME200-HOLD10-01"
MODE = "paper_manual"

TICKET_COLS = ["target_date", "ticker", "conid", "side", "planned_quantity",
               "order_timing", "order_type", "actual_fill_price",
               "actual_quantity", "timestamp", "commission_fees", "order_id",
               "status", "broker_account", "perm_id", "fill_id",
               "execution_ids", "gross_notional"]

PLAN_COLS = ["date", "ticker", "conid", "action", "quantity", "target_value",
             "reason", "price_source"]

NAMES = [("AAA", 111, 10, "2028001", "100.00", "1000.00"),
         ("BBB", 222, 5, "2028002", "200.00", "1000.00")]


# ------------------------------------------------------------------ fixtures
def mk_plan(tmp):
    p = tmp / "plan.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(PLAN_COLS)
        for i, (tk, cid, _, _, _, _) in enumerate(NAMES):
            w.writerow([TD, tk, cid, "BUY", "", 1000, f"rank_{i+1}", "next_open"])
    return p


def mk_ticket(tmp):
    p = tmp / "ticket.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TICKET_COLS)
        w.writeheader()
        for tk, cid, qty, perm, price, gross in NAMES:
            w.writerow({"target_date": TD, "ticker": tk, "conid": cid,
                        "side": "BUY", "planned_quantity": qty,
                        "order_timing": "target_date open", "order_type": "TBD",
                        "actual_fill_price": price, "actual_quantity": qty,
                        "gross_notional": gross, "commission_fees": "1.0",
                        "timestamp": f"{TD}T12:00:00-04:00", "order_id": "0",
                        "status": "filled", "broker_account": ACCT,
                        "perm_id": perm, "fill_id": "",
                        "execution_ids": f"E{perm}"})
    return p


def mk_state(tmp, cash=30000.0):
    p = tmp / "state.json"
    p.write_text(json.dumps({"cash": cash, "equity": cash,
                             "last_updated_date": "2026-07-21",
                             "positions": [], "closed_trades": []}),
                 encoding="utf-8")
    return p


def mk_artifact(tmp, ticket, late=True, target_date=TD, orders=None):
    payload = {
        "schema": art.SCHEMA,
        "generated_at_utc": "2026-07-22T20:00:00+00:00",
        "target_date": target_date,
        "source": {
            "dump_path_relative": "order_plans/x/paper_manual/dump.json",
            "dump_sha256": "d" * 64,
            "plan_path_relative": "order_plans/x/paper_manual/plan.csv",
            "plan_sha256": "p" * 64,
            "ticket_path_relative": f"order_plans/x/paper_manual/{ticket.name}",
            "ticket_planned_projection_sha256": "t" * 64,
            "plan_reference_source": "UNAVAILABLE",
            "account": ACCT,
        },
        "operator_assertions": {"terminality": {}, "plan_reference": None},
        "orders": orders if orders is not None else [
            {"plan_row_index": 0, "perm_id": "2028001", "ticker": "AAA",
             "first_fill_timestamp": f"{TD}T11:53:00-04:00",
             "last_fill_timestamp": f"{TD}T11:53:00-04:00"},
            {"plan_row_index": 1, "perm_id": "2028002", "ticker": "BBB",
             "first_fill_timestamp": f"{TD}T12:16:21-04:00",
             "last_fill_timestamp": f"{TD}T12:16:21-04:00"},
        ],
        "plan_rows": [], "summary": {},
        "diagnostics": ([{"code": "LATE_ENTRY", "message": "late",
                          "plan_row_index": None, "perm_id": "", "exec_id": ""}]
                        if late else []),
    }
    payload["canonical_sha256"] = art.canonical_sha256(payload)
    p = tmp / "artifact.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


class FakeJournal:
    """Minimal writer that appends events to a real jsonl file."""

    def __init__(self, base, mode):
        self.dir = Path(base) / mode / "events"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.fills = []

    def write_fill(self, business_date, rows, **kw):
        self.fills.append((business_date, rows))

    def write_event(self, severity, component, event_type,
                    business_date=None, source_system=None, **fields):
        rec = dict(fields)
        rec.update({"severity": severity, "component": component,
                    "event_type": event_type, "date": business_date,
                    "created_at": "2026-07-22T20:00:00+00:00"})
        with (self.dir / "events_2026-07.jsonl").open(
                "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def close(self):
        pass


def events(journal_dir, mode=MODE):
    f = Path(journal_dir) / mode / "events" / "events_2026-07.jsonl"
    if not f.exists():
        return []
    return [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def deviations(journal_dir, mode=MODE):
    return [e for e in events(journal_dir, mode)
            if e.get("event_type") == rec.EVENT_EXECUTION_DEVIATION]


def run(tmp, apply=False, artifact=None, ticket=None, state=None,
        journal=True):
    plan = mk_plan(tmp)
    ticket = ticket or mk_ticket(tmp)
    state = state or mk_state(tmp)
    jdir = tmp / "journal"
    factory = (lambda: FakeJournal(jdir, MODE)) if journal else None
    out = tmp / "out"
    out.mkdir(exist_ok=True)
    report, applied, path = rec.reconcile(
        ticket, plan, state, jdir, MODE, out, target_date=TD, apply=apply,
        strategy_id=STRAT, journal_factory=factory,
        artifact_path=artifact if artifact is not None else mk_artifact(tmp, ticket))
    return report, applied, Path(path), jdir, state


# --------------------------------------------------------------------- tests
def test_valid_apply_writes_exactly_one_late_entry(tmp_path):
    report, applied, rpath, jdir, _ = run(tmp_path, apply=True)
    assert report.verdict == rec.V_PASS and applied
    devs = deviations(jdir)
    assert len(devs) == 1
    d = devs[0]
    assert d["deviation_code"] == "LATE_ENTRY"
    assert d["strategy_id"] == STRAT and d["mode"] == MODE
    assert d["target_date"] == TD
    assert d["planned_execution"] == "TARGET_DATE_OPEN"
    assert d["reason"] == "MANUAL_FIRST_CYCLE_EXECUTION"
    assert d["source"] == "IBKR_EXECUTION_DUMP"
    assert d["affected_order_count"] == 2
    assert d["affected_tickers"] == ["AAA", "BBB"]
    assert "audit_events_written: **1**" in rpath.read_text(encoding="utf-8")


def test_event_uses_broker_timestamps_from_artifact(tmp_path):
    _, _, _, jdir, _ = run(tmp_path, apply=True)
    d = deviations(jdir)[0]
    assert d["actual_first_fill_timestamp"] == f"{TD}T11:53:00-04:00"
    assert d["actual_last_fill_timestamp"] == f"{TD}T12:16:21-04:00"
    # separate first/last minutes, never one ambiguous field
    assert d["first_fill_minutes_after_open"] == 143
    assert d["last_fill_minutes_after_open"] == 166
    assert "minutes_after_open" not in d


def test_event_carries_artifact_canonical_hash(tmp_path):
    plan = mk_plan(tmp_path)
    ticket = mk_ticket(tmp_path)
    apath = mk_artifact(tmp_path, ticket)
    expected = json.loads(apath.read_text(encoding="utf-8"))["canonical_sha256"]
    _, _, _, jdir, _ = run(tmp_path, apply=True, artifact=apath, ticket=ticket)
    d = deviations(jdir)[0]
    assert d["normalized_artifact_canonical_sha256"] == expected
    assert d["source_dump_sha256"] == "d" * 64
    assert d["deviation_key"].endswith(expected)


def test_validate_writes_no_event(tmp_path):
    report, applied, _, jdir, _ = run(tmp_path, apply=False)
    assert report.verdict == rec.V_PASS and not applied
    assert deviations(jdir) == []


def test_blocked_apply_writes_no_event(tmp_path):
    """Blank row -> INCOMPLETE_TICKET -> no state, no fills, no event."""
    ticket = mk_ticket(tmp_path)
    rows = list(csv.DictReader(ticket.open(encoding="utf-8")))
    rows[1].update({k: "" for k in ("actual_quantity", "actual_fill_price",
                                    "gross_notional", "status", "perm_id",
                                    "commission_fees", "execution_ids")})
    with ticket.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TICKET_COLS)
        w.writeheader()
        w.writerows(rows)
    state = mk_state(tmp_path)
    before = state.read_bytes()
    report, applied, _, jdir, _ = run(tmp_path, apply=True, ticket=ticket,
                                      state=state)
    assert report.verdict == rec.V_INCOMPLETE and not applied
    assert deviations(jdir) == []
    assert state.read_bytes() == before


def test_repeated_apply_creates_no_duplicate(tmp_path):
    """Realny opakovany APPLY: prvni bezi normalne, druhy uz vidi filly
    v journalu (ALREADY_APPLIED) a nesmi pripsat druhy stejny event.

    Bez patchnuti applied_keys by druhy beh skoncil na 'already held' FAIL
    a test by prochazel z uplne jineho duvodu nez kvuli deduplikaci.
    """
    plan = mk_plan(tmp_path)
    ticket = mk_ticket(tmp_path)
    apath = mk_artifact(tmp_path, ticket)
    state = mk_state(tmp_path)
    jdir = tmp_path / "journal"
    out = tmp_path / "out"
    out.mkdir()

    r1, a1, _ = rec.reconcile(ticket, plan, state, jdir, MODE, out,
                              target_date=TD, apply=True, strategy_id=STRAT,
                              journal_factory=lambda: FakeJournal(jdir, MODE),
                              artifact_path=apath)
    assert a1 and len(deviations(jdir)) == 1

    rows = rec.parse_ticket(ticket)
    keys = {rec.fill_key(r, TD, rec.SCHEMA_P2) for r in rows}
    orig = rec.applied_keys_from_journal
    rec.applied_keys_from_journal = lambda *a, **k: keys
    try:
        state_after_first = state.read_bytes()
        r2, a2, _ = rec.reconcile(
            ticket, plan, state, jdir, MODE, out, target_date=TD, apply=True,
            strategy_id=STRAT,
            journal_factory=lambda: FakeJournal(jdir, MODE),
            artifact_path=apath)
    finally:
        rec.applied_keys_from_journal = orig

    assert r2.verdict == rec.V_PASS_ALREADY_APPLIED and not a2
    assert len(deviations(jdir)) == 1, "second APPLY must not duplicate"
    assert state.read_bytes() == state_after_first


def test_already_applied_missing_event_repairs_without_touching_state(tmp_path):
    """Fills already recorded, event missing -> write ONLY the event."""
    plan = mk_plan(tmp_path)
    ticket = mk_ticket(tmp_path)
    apath = mk_artifact(tmp_path, ticket)
    state = mk_state(tmp_path)
    jdir = tmp_path / "journal"
    out = tmp_path / "out"
    out.mkdir()

    rows = rec.parse_ticket(ticket)
    applied_keys = {rec.fill_key(r, TD, rec.SCHEMA_P2) for r in rows}
    orig = rec.applied_keys_from_journal
    rec.applied_keys_from_journal = lambda *a, **k: applied_keys
    try:
        before_state = state.read_bytes()
        report, applied, rpath = rec.reconcile(
            ticket, plan, state, jdir, MODE, out, target_date=TD, apply=True,
            strategy_id=STRAT,
            journal_factory=lambda: FakeJournal(jdir, MODE),
            artifact_path=apath)
    finally:
        rec.applied_keys_from_journal = orig

    assert report.verdict == rec.V_PASS_ALREADY_APPLIED
    assert not applied, "audit repair must not count as APPLIED"
    assert state.read_bytes() == before_state, "state must not change"
    assert not list(state.parent.glob("state.json.*.bak")), "no backup"
    devs = deviations(jdir)
    assert len(devs) == 1
    fills = [e for e in events(jdir) if e.get("event_type") == "RECONCILIATION"]
    assert not fills, "no fill/reconciliation event during audit repair"
    txt = Path(rpath).read_text(encoding="utf-8")
    assert "audit_repair: **LATE_ENTRY_WRITTEN**" in txt


def test_already_applied_with_event_is_full_noop(tmp_path):
    plan = mk_plan(tmp_path)
    ticket = mk_ticket(tmp_path)
    apath = mk_artifact(tmp_path, ticket)
    state = mk_state(tmp_path)
    jdir = tmp_path / "journal"
    out = tmp_path / "out"
    out.mkdir()

    rows = rec.parse_ticket(ticket)
    applied_keys = {rec.fill_key(r, TD, rec.SCHEMA_P2) for r in rows}
    orig = rec.applied_keys_from_journal
    rec.applied_keys_from_journal = lambda *a, **k: applied_keys
    try:
        rec.reconcile(ticket, plan, state, jdir, MODE, out, target_date=TD,
                      apply=True, strategy_id=STRAT,
                      journal_factory=lambda: FakeJournal(jdir, MODE),
                      artifact_path=apath)
        assert len(deviations(jdir)) == 1
        before_state = state.read_bytes()
        before_events = events(jdir)
        report, applied, rpath = rec.reconcile(
            ticket, plan, state, jdir, MODE, out, target_date=TD, apply=True,
            strategy_id=STRAT,
            journal_factory=lambda: FakeJournal(jdir, MODE),
            artifact_path=apath)
    finally:
        rec.applied_keys_from_journal = orig

    assert report.verdict == rec.V_PASS_ALREADY_APPLIED and not applied
    assert state.read_bytes() == before_state
    assert events(jdir) == before_events, "nothing may be appended"
    assert "audit_repair" not in Path(rpath).read_text(encoding="utf-8")


# ------------------------------------------------------------------- guards
def test_no_event_when_artifact_missing(tmp_path):
    _, _, _, jdir, _ = run(tmp_path, apply=True,
                           artifact=tmp_path / "does-not-exist.json")
    assert deviations(jdir) == []


def test_no_event_without_late_entry_diagnostic(tmp_path):
    ticket = mk_ticket(tmp_path)
    apath = mk_artifact(tmp_path, ticket, late=False)
    _, _, _, jdir, _ = run(tmp_path, apply=True, artifact=apath, ticket=ticket)
    assert deviations(jdir) == []


def test_no_event_on_target_date_mismatch(tmp_path):
    ticket = mk_ticket(tmp_path)
    apath = mk_artifact(tmp_path, ticket, target_date="2026-07-21")
    _, _, _, jdir, _ = run(tmp_path, apply=True, artifact=apath, ticket=ticket)
    assert deviations(jdir) == []


def test_no_event_on_tampered_canonical_hash(tmp_path):
    ticket = mk_ticket(tmp_path)
    apath = mk_artifact(tmp_path, ticket)
    payload = json.loads(apath.read_text(encoding="utf-8"))
    payload["orders"][0]["ticker"] = "TAMPERED"      # hash no longer matches
    apath.write_text(json.dumps(payload), encoding="utf-8")
    _, _, _, jdir, _ = run(tmp_path, apply=True, artifact=apath, ticket=ticket)
    assert deviations(jdir) == []


def test_no_event_on_ticket_mismatch(tmp_path):
    ticket = mk_ticket(tmp_path)
    payload = json.loads(mk_artifact(tmp_path, ticket).read_text(encoding="utf-8"))
    payload["source"]["ticket_path_relative"] = "order_plans/x/other_ticket.csv"
    payload["canonical_sha256"] = art.canonical_sha256(payload)
    apath = tmp_path / "artifact2.json"
    apath.write_text(json.dumps(payload), encoding="utf-8")
    _, _, _, jdir, _ = run(tmp_path, apply=True, artifact=apath, ticket=ticket)
    assert deviations(jdir) == []


# --------------------------------------------------- importer independence
def test_importer_unchanged_by_this_work():
    """The deviation event lives in reconciliation only."""
    base = Path(rec.__file__).parent
    sources = [base / "import_fills.py"] + sorted((base / "fills").glob("*.py"))
    for p in sources:
        src = p.read_text(encoding="utf-8")
        assert "EXECUTION_DEVIATION" not in src, p.name
        assert "deviation_key" not in src, p.name
        assert "write_event" not in src, p.name


def test_deviation_key_is_deterministic():
    k1 = rec.deviation_key(STRAT, MODE, TD, "LATE_ENTRY", "abc")
    k2 = rec.deviation_key(STRAT, MODE, TD, "LATE_ENTRY", "abc")
    assert k1 == k2
    assert k1 == f"execution_deviation:{STRAT}:{MODE}:{TD}:LATE_ENTRY:abc"
    assert rec.deviation_key(STRAT, MODE, TD, "LATE_ENTRY", "xyz") != k1
