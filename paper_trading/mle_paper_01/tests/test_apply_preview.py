"""Apply preview + PREVIEW_STALE tests (architekt 2026-07-23)."""
import csv
import json
from decimal import Decimal
from pathlib import Path

import pytest

from mle_paper_01 import reconciliation as rec

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


class FakeJournal:
    def __init__(self, base):
        self.dir = Path(base) / MODE / "events"
        self.dir.mkdir(parents=True, exist_ok=True)

    def write_fill(self, *a, **k):
        pass

    def write_event(self, severity, component, event_type,
                    business_date=None, source_system=None, **fields):
        rec_ = dict(fields)
        rec_.update({"event_type": event_type, "date": business_date})
        with (self.dir / "events_2026-07.jsonl").open("a",
                                                      encoding="utf-8") as f:
            f.write(json.dumps(rec_) + "\n")

    def close(self):
        pass


def mk_plan(tmp):
    p = tmp / "plan.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(PLAN_COLS)
        for i, (tk, cid, *_rest) in enumerate(NAMES):
            w.writerow([TD, tk, cid, "BUY", "", 1000, f"rank_{i+1}",
                        "next_open"])
    return p


def mk_ticket(tmp):
    p = tmp / "ticket.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TICKET_COLS)
        w.writeheader()
        for tk, cid, qty, perm, price, gross in NAMES:
            w.writerow({"target_date": TD, "ticker": tk, "conid": cid,
                        "side": "BUY", "planned_quantity": qty,
                        "order_timing": "target_date open",
                        "order_type": "TBD", "actual_fill_price": price,
                        "actual_quantity": qty, "gross_notional": gross,
                        "commission_fees": "1.0", "status": "filled",
                        "timestamp": f"{TD}T12:00:00-04:00", "order_id": "0",
                        "broker_account": ACCT, "perm_id": perm,
                        "fill_id": "", "execution_ids": f"E{perm}"})
    return p


def mk_state(tmp):
    p = tmp / "state.json"
    p.write_text(json.dumps({"cash": 30000.0, "equity": 30000.0,
                             "last_updated_date": "2026-07-21",
                             "positions": [], "closed_trades": []}),
                 encoding="utf-8")
    return p


def mk_artifact(tmp, ticket):
    from mle_paper_01.fills import artifact as art
    payload = {
        "schema": art.SCHEMA, "generated_at_utc": "2026-07-22T20:00:00+00:00",
        "target_date": TD,
        "source": {"dump_path_relative": "d.json", "dump_sha256": "d" * 64,
                   "plan_path_relative": "p.csv", "plan_sha256": "p" * 64,
                   "ticket_path_relative": f"x/{ticket.name}",
                   "ticket_planned_projection_sha256": "t" * 64,
                   "plan_reference_source": "UNAVAILABLE", "account": ACCT},
        "operator_assertions": {}, "plan_rows": [], "summary": {},
        "orders": [{"plan_row_index": 0, "perm_id": "2028001", "ticker": "AAA",
                    "first_fill_timestamp": f"{TD}T11:53:00-04:00",
                    "last_fill_timestamp": f"{TD}T11:53:00-04:00"}],
        "diagnostics": [{"code": "LATE_ENTRY", "message": "late",
                         "plan_row_index": None, "perm_id": "", "exec_id": ""}],
    }
    payload["canonical_sha256"] = art.canonical_sha256(payload)
    p = tmp / "artifact.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


class Env:
    def __init__(self, tmp):
        self.tmp = tmp
        self.plan = mk_plan(tmp)
        self.ticket = mk_ticket(tmp)
        self.state = mk_state(tmp)
        self.artifact = mk_artifact(tmp, self.ticket)
        self.jdir = tmp / "journal"
        self.out = tmp / "out"
        self.out.mkdir()
        self.preview = tmp / "preview.json"

    def call(self, **kw):
        return rec.reconcile(
            self.ticket, self.plan, self.state, self.jdir, MODE, self.out,
            target_date=TD, strategy_id=STRAT,
            journal_factory=lambda: FakeJournal(self.jdir),
            artifact_path=self.artifact, **kw)

    def take_preview(self):
        return self.call(preview_out=self.preview)

    def apply(self, use_preview=True):
        return self.call(apply=True,
                         preview_path=self.preview if use_preview else None)

    @property
    def report(self):
        return self.out / f"reconciliation_report_{TD}.md"


# ------------------------------------------------------------------ preview
def test_preview_writes_artifact_and_nothing_else(tmp_path):
    e = Env(tmp_path)
    state_before = e.state.read_bytes()
    e.take_preview()
    assert e.preview.exists()
    assert e.state.read_bytes() == state_before, "stav se nesmi zmenit"
    assert not e.report.exists(), "nahled nesmi psat finalni report"
    assert not list(tmp_path.glob("state.json.*.bak"))
    assert not (e.jdir / MODE / "events" / "events_2026-07.jsonl").exists()


def test_preview_does_not_overwrite_existing_report(tmp_path):
    e = Env(tmp_path)
    e.apply(use_preview=False)
    before = e.report.read_bytes()
    e.take_preview()
    assert e.report.read_bytes() == before


def test_preview_contains_required_fields(tmp_path):
    e = Env(tmp_path)
    e.take_preview()
    pv = json.loads(e.preview.read_text(encoding="utf-8"))
    for f in ("broker_account", "strategy_id", "target_date", "new_fills",
              "cash_before", "cash_delta", "cash_after", "positions_before",
              "positions_after", "events_to_write", "fingerprint"):
        assert f in pv, f
    assert pv["broker_account"] == ACCT
    assert pv["strategy_id"] == STRAT and pv["target_date"] == TD
    assert pv["new_fills"] == 2
    assert pv["positions_before"] == 0 and pv["positions_after"] == 2
    assert pv["events_to_write"] == ["EXECUTION_DEVIATION/LATE_ENTRY"]


def test_preview_numbers_match_actual_apply(tmp_path):
    """Nahled musi pouzit TOUTEZ logiku jako nasledny zapis."""
    e = Env(tmp_path)
    e.take_preview()
    pv = json.loads(e.preview.read_text(encoding="utf-8"))
    e.apply()
    st = json.loads(e.state.read_text(encoding="utf-8"))
    assert Decimal(pv["cash_after"]) == Decimal(str(st["cash"]))
    assert pv["positions_after"] == len(st["positions"])


# ------------------------------------------------------------ staleness
def test_apply_with_matching_preview_succeeds(tmp_path):
    e = Env(tmp_path)
    e.take_preview()
    report, applied, _ = e.apply()
    assert applied and report.verdict == rec.V_PASS
    assert not any(w.startswith(rec.PREVIEW_STALE) for w in report.warnings)


@pytest.mark.parametrize("what", ["ticket", "state", "artifact"])
def test_stale_preview_blocks_apply(tmp_path, what):
    e = Env(tmp_path)
    e.take_preview()
    if what == "ticket":
        e.ticket.write_text(e.ticket.read_text(encoding="utf-8") + "\n",
                            encoding="utf-8")
    elif what == "state":
        st = json.loads(e.state.read_text(encoding="utf-8"))
        st["cash"] = 29999.0
        e.state.write_text(json.dumps(st), encoding="utf-8")
    else:
        a = json.loads(e.artifact.read_text(encoding="utf-8"))
        a["canonical_sha256"] = "0" * 64
        e.artifact.write_text(json.dumps(a), encoding="utf-8")
    before = e.state.read_bytes()
    report, applied, _ = e.apply()
    assert not applied, what
    assert any(w.startswith(rec.PREVIEW_STALE) for w in report.warnings), what
    assert e.state.read_bytes() == before, what
    assert not list(tmp_path.glob("state.json.*.bak")), what


def test_stale_preview_detected_via_applied_keys(tmp_path):
    e = Env(tmp_path)
    e.take_preview()
    orig = rec.applied_keys_from_journal
    rec.applied_keys_from_journal = lambda *a, **k: {"ibkr:X:perm:1"}
    try:
        report, applied, _ = e.apply()
    finally:
        rec.applied_keys_from_journal = orig
    assert not applied
    assert any("applied_keys_sha256" in w for w in report.warnings)


def test_missing_preview_file_blocks_apply(tmp_path):
    e = Env(tmp_path)
    report, applied, _ = e.apply()          # preview nikdy nevznikl
    assert not applied
    assert any(w.startswith(rec.PREVIEW_STALE) for w in report.warnings)


def test_stale_preview_report_says_so(tmp_path):
    e = Env(tmp_path)
    e.take_preview()
    e.ticket.write_text(e.ticket.read_text(encoding="utf-8") + "\n",
                        encoding="utf-8")
    e.apply()
    txt = e.report.read_text(encoding="utf-8")
    assert "phase: **APPLY_BLOCKED**" in txt
    assert rec.PREVIEW_STALE in txt
    assert "Fix the ticket and re-run" not in txt


def test_apply_without_preview_still_works(tmp_path):
    """Zpetna kompatibilita: bez --preview se chova jako driv."""
    e = Env(tmp_path)
    report, applied, _ = e.apply(use_preview=False)
    assert applied and report.verdict == rec.V_PASS


def test_fingerprint_is_stable_for_unchanged_inputs(tmp_path):
    e = Env(tmp_path)
    f1 = rec.preview_fingerprint(e.ticket, e.artifact, e.state, set())
    f2 = rec.preview_fingerprint(e.ticket, e.artifact, e.state, set())
    assert f1 == f2 and all(f1.values())
