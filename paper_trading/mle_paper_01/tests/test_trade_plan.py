"""Render-level tests for the Daily Trade Plan (manual_report). No broker,
no state mutation — pure rendering from constructed inputs."""
import csv
from dataclasses import dataclass
from typing import List, Optional

from mle_paper_01 import manual_report as mr
from mle_paper_01 import capital_feasibility as cf
from mle_paper_01.models import (Action, Decision, PortfolioState, Position,
                                 RegimeState, SignalCandidate, PriceSource)

D, D1 = "2026-07-15", "2026-07-16"



def _has_row(txt, expected_cells):
    """True if some markdown table row has exactly these cell values.
    Whitespace-insensitive: the report pads cells to align columns."""
    for ln in txt.splitlines():
        t = ln.strip()
        if not (t.startswith("|") and t.endswith("|")):
            continue
        if [c.strip() for c in t[1:-1].split("|")] == expected_cells:
            return True
    return False


def _cand(t, c, r): return SignalCandidate(ticker=t, conid=c, rank_10d=r)


def _buy(t, c, tv):
    return Decision(action=Action.BUY, target_date=D1, reason="signal",
                    ticker=t, conid=c, target_value=tv,
                    price_source=PriceSource.NEXT_OPEN)


def _state(cash, equity, positions=None):
    return PortfolioState(cash=cash, equity=equity,
                          last_updated_date=D, positions=positions or [])


def _regime(on):
    return RegimeState(date=D, regime_on=on, index_level=100.0, ma200=90.0)


def _render(state, decisions, candidates, regime, feasibility,
            holds_days_remaining=None):
    return mr.render_report(
        business_date=D, target_date=D1, regime=regime, state=state,
        candidates=candidates, decisions=decisions, warnings=[], errors=[],
        account_label="DU-PAPER (dry_run)", mode="dry_run",
        data_source_meta={"data_source": "DATA06"},
        orders_plan_path="plans/orders_plan_2026-07-16.csv",
        feasibility=feasibility, run_id="RUN1",
        portfolio_state_source="runtime_state (dry_run)",
        estimated_exit_if_filled="2026-07-30",
        holds_days_remaining=holds_days_remaining or {}, max_positions=10)


def test_nine_sections_present():
    buys = [_buy("AAPL", 1, 3000.0)]
    refs = {"AAPL": 200.0}
    feas = cf.evaluate_plan(30000.0, 30000.0, buys, refs)
    txt = _render(_state(30000, 30000), buys, [_cand("AAPL", 1, 1)],
                  _regime(True), feas)
    for h in ("# Daily Trade Plan", "## 1. Header", "## 2. Account",
              "## 3. Regime", "## 4. BUY orders", "## 5. EXIT orders",
              "## 6. HOLD positions", "## 7. Capital Feasibility",
              "## 8. Manual execution checklist",
              # ZMENENO: sekce 9 uz neni "Fill recording template" - ticket
              # plni importer, rucni vyplnovani bylo zruseno v P2
              "## 9. Processing the actual executions"):
        assert h in txt
    # timing statements
    assert "BUY = target_date OPEN" in txt
    assert "EXIT = planned_exit_date CLOSE" in txt
    # rank + estimated exit shown
    assert "planned_exit_if_filled" in txt and "2026-07-30" in txt
    # dry_run banner + neutral runtime strategy id
    assert "DRY_RUN ONLY" in txt
    assert "MLE-REGIME200-HOLD10-01" in txt


def test_cash_not_equal_equity_supported():
    buys = [_buy(f"T{i}", i, 3000.0) for i in range(1, 11)]
    refs = {f"T{i}": 200.0 for i in range(1, 11)}
    feas = cf.evaluate_plan(30000.0, 8000.0, buys, refs)
    txt = _render(_state(8000.0, 30000.0), buys,
                  [_cand(f"T{i}", i, i) for i in range(1, 11)],
                  _regime(True), feas)
    assert "cash != equity" in txt
    assert "sized against **cash**" in txt
    assert "DO NOT BUY" in txt          # some names blocked by cash


def test_regime_off_note():
    txt = _render(_state(30000, 30000), [], [], _regime(False), None)
    assert "regime OFF" in txt
    assert "no new BUYs" in txt


def test_do_not_buy_for_too_expensive():
    buys = [_buy("NVR", 1, 3000.0)]
    feas = cf.evaluate_plan(30000.0, 30000.0, buys, {"NVR": 8000.0})
    txt = _render(_state(30000, 30000), buys, [_cand("NVR", 1, 1)],
                  _regime(True), feas)
    assert "DO NOT BUY — TOO_EXPENSIVE" in txt


def test_hold_days_remaining():
    pos = Position(ticker="HLD", conid=9, shares=10.0, entry_date="2026-07-01",
                   entry_price=100.0, planned_exit_date="2026-07-25",
                   signal_rank=1)
    st = _state(5000.0, 7000.0, positions=[pos])
    txt = _render(st, [], [], _regime(True), None,
                  holds_days_remaining={"HLD": 7})
    assert "## 6. HOLD positions" in txt
    assert "HLD" in txt and "2026-07-01" in txt and "2026-07-25" in txt
    assert any(c.strip() == "7"          # days_remaining rendered
               for ln in txt.splitlines() if ln.strip().startswith("|")
               for c in ln.strip()[1:-1].split("|"))


def test_section9_points_to_importer_not_manual_entry(tmp_path):
    """ZMENENO: drive test_fill_recording_blank_and_ticket_columns.

    Sekce 9 driv obsahovala tabulku k rucnimu vyplneni fillu. Od P2 ticket
    plni importer (volba 3) a rucni editace je zakazana, takze pokyn
    neodpovidal skutecnosti.
    """
    buys = [_buy("AAPL", 1, 3000.0)]
    feas = cf.evaluate_plan(30000.0, 30000.0, buys, {"AAPL": 200.0})
    txt = _render(_state(30000, 30000), buys, [_cand("AAPL", 1, 1)],
                  _regime(True), feas)
    assert "Import broker fills" in txt
    assert "Do not edit it by hand" in txt
    for gone in ("Fill recording template", "fill in AFTER execution",
                 "record actual fills on the ticket"):
        assert gone not in txt, gone
    # ticket columns: planning + blank actual-fill; execution_mode/notes gone
    path = mr.write_ticket(D1, buys, tmp_path, feasibility=feas)
    header = next(csv.reader(open(path, encoding="utf-8")))
    for col in ("ticker", "side", "planned_quantity", "actual_fill_price",
                "actual_quantity", "timestamp", "commission_fees",
                "order_id", "status"):
        assert col in header
    # BUY planned_quantity = indicative_qty (14), actual columns blank
    row = next(r for r in csv.DictReader(open(path, encoding="utf-8")) if r["ticker"] == "AAPL")
    assert row["side"] == "BUY" and row["planned_quantity"] == "14"
    assert row["actual_fill_price"] == "" and row["status"] == ""


def test_no_broker_import():
    import ast
    from pathlib import Path
    pkg = Path(mr.__file__).resolve().parent
    forbidden = {"broker", "ib_insync", "ibapi", "ibkr", "tws", "execution"}
    tree = ast.parse(Path(mr.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module] if isinstance(node, ast.ImportFrom) and node.module
                else [])
        for m in mods:
            assert m.split(".")[0] not in forbidden


def test_paper_manual_banner_and_checklist():
    txt = mr.render_report(
        business_date=D, target_date=D1,
        regime=_regime(True), state=_state(30000, 30086.08),
        candidates=[], decisions=[], warnings=[], errors=[],
        account_label="DU-PAPER (paper_manual)", mode="paper_manual",
        data_source_meta={"data_source": "DATA06"}, orders_plan_path="x")
    assert "PAPER_MANUAL - PAPER ORDERS ONLY" in txt
    assert "NO LIVE ORDERS" in txt
    assert "place PAPER orders manually" in txt
    assert "DRY_RUN ONLY" not in txt          # not the dry_run banner
