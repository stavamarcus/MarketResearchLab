"""Tests for manual fill reconciliation (validate/apply, no broker)."""
import ast
import csv
from pathlib import Path

import pytest

from mle_paper_01 import reconciliation as rec
from mle_paper_01.models import PortfolioState, Position
from mle_paper_01.portfolio_state import save_state

TD = "2026-07-06"


def _next_session(mapping):
    return lambda d: mapping[d]


# 10-session calendar from TD for planned_exit
CAL = {}
_days = ["2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10",
         "2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17",
         "2026-07-20", "2026-07-21"]
for i in range(len(_days) - 1):
    CAL[_days[i]] = _days[i + 1]
NEXT = _next_session(CAL)


def mk_pos(ticker, shares=10.0, price=100.0, conid=1):
    return Position(ticker=ticker, conid=conid, shares=shares,
                    entry_date="2026-06-20", entry_price=price,
                    planned_exit_date="2026-07-05", signal_rank=1)


def mk_state(tmp, cash, positions=()):
    eq = cash + sum(p.shares * p.entry_price for p in positions)
    st = PortfolioState(cash=cash, equity=eq, positions=tuple(positions),
                        last_updated_date=TD)
    p = tmp / "state.json"
    save_state(st, p)
    return p


def mk_plan(tmp, entries):
    p = tmp / "plan.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "ticker", "conid", "action", "quantity",
                    "target_value", "reason", "price_source"])
        for tk, act, cid, tv in entries:
            w.writerow([TD, tk, cid, act, "", tv, "rank_1", "next_open"])
    return p


TCOLS = ["target_date", "ticker", "conid", "side", "planned_quantity",
         "order_timing", "order_type", "actual_fill_price", "actual_quantity",
         "timestamp", "commission_fees", "order_id", "status", "override_reason"]


def mk_ticket(tmp, rows):
    p = tmp / "ticket.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TCOLS)
        w.writeheader()
        for r in rows:
            base = {c: "" for c in TCOLS}
            base.update(r)
            w.writerow(base)
    return p


def buy(ticker, qty, price, planned=14, oid="O1", ts=TD, **extra):
    r = {"ticker": ticker, "conid": "1", "side": "BUY",
         "planned_quantity": planned, "actual_quantity": qty,
         "actual_fill_price": price, "timestamp": ts, "commission_fees": "1.0",
         "order_id": oid, "status": "filled"}
    r.update(extra)
    return r


def run(tmp, ticket_rows, plan_entries, positions=(), cash=30000.0,
        apply=False, journal_factory=None):
    tk = mk_ticket(tmp, ticket_rows)
    pl = mk_plan(tmp, plan_entries)
    stp = mk_state(tmp, cash, positions)
    return rec.reconcile(tk, pl, stp, str(tmp / "j"), "dry_run", str(tmp),
                         target_date=TD, apply=apply,
                         strategy_id="MLE-REGIME200-HOLD10-01",
                         journal_factory=journal_factory,
                         next_session_fn=NEXT), stp


# ---------------------------------------------------------------- validation
def test_ticker_not_in_plan_fails(tmp_path):
    (report, _, _), _ = run(tmp_path, [buy("ZZZ", 5, 100.0)],
                            [("AAA", "BUY", "1", 3000)])
    assert not report.passed


def test_side_mismatch_fails(tmp_path):
    (report, _, _), _ = run(tmp_path, [buy("AAA", 5, 100.0)],
                            [("AAA", "EXIT", "1", 3000)])
    assert not report.passed


def test_do_not_buy_fails(tmp_path):
    # planned_quantity blank -> DO NOT BUY, but recorded as bought
    (report, _, _), _ = run(tmp_path, [buy("AAA", 5, 100.0, planned="")],
                            [("AAA", "BUY", "1", 3000)])
    assert not report.passed


def test_buy_already_held_fails(tmp_path):
    (report, _, _), _ = run(tmp_path, [buy("AAA", 5, 100.0)],
                            [("AAA", "BUY", "1", 3000)],
                            positions=(mk_pos("AAA"),))
    assert not report.passed


def test_exit_non_held_fails(tmp_path):
    row = {"ticker": "AAA", "conid": "1", "side": "EXIT",
           "actual_quantity": "5", "actual_fill_price": "100",
           "timestamp": TD, "order_id": "E1", "status": "filled"}
    (report, _, _), _ = run(tmp_path, [row], [("AAA", "EXIT", "1", "")])
    assert not report.passed


def test_exit_over_held_hard_fails(tmp_path):
    row = {"ticker": "AAA", "conid": "1", "side": "EXIT",
           "actual_quantity": "20", "actual_fill_price": "100",
           "timestamp": TD, "order_id": "E1", "status": "filled"}
    (report, _, _), _ = run(tmp_path, [row], [("AAA", "EXIT", "1", "")],
                            positions=(mk_pos("AAA", shares=10),))
    assert not report.passed


def test_buy_over_planned_needs_override(tmp_path):
    (r1, _, _), _ = run(tmp_path, [buy("AAA", 20, 100.0, planned=14)],
                        [("AAA", "BUY", "1", 3000)])
    assert not r1.passed
    (r2, _, _), _ = run(tmp_path, [buy("AAA", 20, 100.0, planned=14,
                                       override_reason="manual add")],
                        [("AAA", "BUY", "1", 3000)])
    assert r2.passed
    assert any(d.deviations for d in r2.dispositions)


def test_wrong_session_fails_unless_override(tmp_path):
    (r1, _, _), _ = run(tmp_path, [buy("AAA", 5, 100.0, ts="2026-07-07")],
                        [("AAA", "BUY", "1", 3000)])
    assert not r1.passed
    (r2, _, _), _ = run(tmp_path, [buy("AAA", 5, 100.0, ts="2026-07-07",
                                       override_reason="late fill")],
                        [("AAA", "BUY", "1", 3000)])
    assert r2.passed
    d = r2.dispositions[0]
    assert d.entry_date == "2026-07-07"      # dated by actual session


def test_status_strict(tmp_path):
    # filled missing price -> FAIL
    row = buy("AAA", 5, 0.0)
    (r, _, _), _ = run(tmp_path, [row], [("AAA", "BUY", "1", 3000)])
    assert not r.passed


def test_cancelled_no_change(tmp_path):
    row = {"ticker": "AAA", "conid": "1", "side": "BUY", "planned_quantity": 14,
           "status": "cancelled", "order_id": "C1"}
    (report, _, _), _ = run(tmp_path, [row], [("AAA", "BUY", "1", 3000)])
    assert report.passed
    assert report.by(rec.SKIP) and not report.by(rec.APPLY)


# ----------------------------------------------------------------- apply
def test_apply_buy_cash_and_position(tmp_path):
    (report, applied, rpath), stp = run(
        tmp_path, [buy("AAA", 10, 100.0, planned=14)],
        [("AAA", "BUY", "1", 3000)], cash=30000.0, apply=True)
    assert report.passed and applied
    from mle_paper_01.portfolio_state import load_state
    st = load_state(stp)
    # cash = 30000 - (10*100 + 1 fee) = 28999
    assert abs(st.cash - 28999.0) < 1e-6
    pos = [p for p in st.open_positions() if p.ticker == "AAA"][0]
    assert pos.shares == 10 and pos.entry_price == 100.0
    assert pos.planned_exit_date == "2026-07-20"   # +10 sessions from TD
    # backup created
    assert any(p.name.startswith("state.json") and ".bak" in p.name
               for p in tmp_path.iterdir())
    assert "provisional" in Path(rpath).read_text(encoding="utf-8")


def test_apply_partial_exit_flags_remainder(tmp_path):
    row = {"ticker": "AAA", "conid": "1", "side": "EXIT",
           "actual_quantity": "4", "actual_fill_price": "120",
           "timestamp": TD, "commission_fees": "1.0", "order_id": "E1",
           "status": "partial"}
    (report, applied, rpath), stp = run(
        tmp_path, [row], [("AAA", "EXIT", "1", "")],
        positions=(mk_pos("AAA", shares=10, price=100),), cash=5000.0,
        apply=True)
    assert applied
    from mle_paper_01.portfolio_state import load_state
    st = load_state(stp)
    pos = [p for p in st.open_positions() if p.ticker == "AAA"][0]
    assert abs(pos.shares - 6.0) < 1e-9        # remainder open
    txt = Path(rpath).read_text(encoding="utf-8")
    assert "PARTIAL EXIT" in txt


def test_fail_no_write(tmp_path):
    (report, applied, _), stp = run(
        tmp_path, [buy("ZZZ", 5, 100.0)], [("AAA", "BUY", "1", 3000)],
        apply=True)
    assert not report.passed and not applied
    # no backup written on fail
    assert not any(".bak" in p.name for p in tmp_path.iterdir())


def test_idempotence_skips_duplicate(tmp_path):
    from mle_paper_01.reconciliation import validate, parse_ticket, load_plan
    from mle_paper_01.portfolio_state import load_state
    tk = mk_ticket(tmp_path, [buy("AAA", 10, 100.0, oid="DUP")])
    pl = mk_plan(tmp_path, [("AAA", "BUY", "1", 3000)])
    stp = mk_state(tmp_path, 30000.0)
    rows = parse_ticket(tk)
    report = validate(rows, load_plan(pl), load_state(stp), TD, set(),
                      {"order:DUP"}, NEXT)
    assert report.by(rec.SKIP) and not report.by(rec.APPLY)


def test_journal_fill_execution_mode_manual(tmp_path):
    from journal import JournalWriter
    import pyarrow.parquet as pq

    def jf():
        return JournalWriter(mode="dry_run",
                             strategy_id="MLE-REGIME200-HOLD10-01",
                             base_dir=str(tmp_path / "j"),
                             source_system="RECONCILIATION")

    (report, applied, _), _ = run(
        tmp_path, [buy("AAA", 10, 100.0, planned=14)],
        [("AAA", "BUY", "1", 3000)], apply=True, journal_factory=jf)
    assert applied
    fills = list((tmp_path / "j" / "dry_run" / "fills").rglob("*.parquet"))
    assert fills
    rows = pq.ParquetFile(str(fills[0])).read().to_pylist()
    assert rows[0]["execution_mode"] == "MANUAL"
    assert rows[0]["schema_version"] == "1.1.0"


def test_no_broker_import():
    pkg = Path(rec.__file__).resolve().parent
    forbidden = {"broker", "ib_insync", "ibapi", "ibkr", "tws", "execution"}
    tree = ast.parse(Path(rec.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module] if isinstance(node, ast.ImportFrom)
                and node.module else [])
        for m in mods:
            assert m.split(".")[0] not in forbidden


def test_blank_ticket_passes_and_skips(tmp_path):
    # unfilled ticket rows (no status, no actual data) -> SKIP, PASS overall
    blank = {"target_date": TD, "ticker": "AAA", "conid": "1", "side": "BUY",
             "planned_quantity": "5"}
    (report, applied, rpath), _ = run(tmp_path, [blank],
                                      [("AAA", "BUY", "1", 3000)])
    assert report.passed and not applied
    assert report.by(rec.SKIP) and not report.by(rec.APPLY)
    # report filename carries the date from the ticket target_date column
    assert Path(rpath).name == f"reconciliation_report_{TD}.md"


def test_partial_ticket_mixes_apply_and_skip(tmp_path):
    filled = buy("AAA", 5, 100.0, planned=5)
    blank = {"target_date": TD, "ticker": "BBB", "conid": "2", "side": "BUY",
             "planned_quantity": "10"}
    (report, _, _), _ = run(tmp_path, [filled, blank],
                            [("AAA", "BUY", "1", 3000), ("BBB", "BUY", "2", 3000)])
    assert report.passed
    assert len(report.by(rec.APPLY)) == 1 and len(report.by(rec.SKIP)) == 1
