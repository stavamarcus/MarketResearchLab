import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mle_paper_01 import capital_feasibility as cf


@dataclass
class FakeBuy:
    ticker: str
    conid: int
    target_value: float


def test_all_executable():
    buys = [FakeBuy("AAPL", 1, 3000.0), FakeBuy("MSFT", 2, 3000.0)]
    refs = {"AAPL": 200.0, "MSFT": 400.0}
    r = cf.evaluate_plan(30000.0, 30000.0, buys, refs)
    assert r.status == "EXECUTABLE"
    assert r.n_executable == 2
    assert r.too_expensive == [] and r.insufficient_cash == []
    a = next(b for b in r.per_buy if b.ticker == "AAPL")
    assert a.indicative_qty == 14        # floor(3000/(200*1.00075))
    assert a.executable and a.non_executable_reason is None
    assert r.estimated_remaining_cash_after_buys > 0


def test_too_expensive():
    buys = [FakeBuy("NVR", 1, 300.0)]           # target 300, price 5000
    r = cf.evaluate_plan(3000.0, 3000.0, buys, {"NVR": 5000.0})
    assert r.status == "NOT_EXECUTABLE"
    assert r.too_expensive == ["NVR"] and r.insufficient_cash == []
    b = r.per_buy[0]
    assert b.indicative_qty == 0 and b.non_executable_reason == cf.TOO_EXPENSIVE


def test_insufficient_cash():
    # target could buy 1 share, but remaining cash cannot (exhausted by first buy)
    buys = [FakeBuy("AAA", 1, 3000.0), FakeBuy("BBB", 2, 3000.0)]
    refs = {"AAA": 200.0, "BBB": 200.0}
    r = cf.evaluate_plan(30000.0, 250.0, buys, refs)   # only 250 cash
    assert r.status == "PARTIAL"
    assert r.insufficient_cash == ["BBB"] and r.too_expensive == []
    bbb = next(b for b in r.per_buy if b.ticker == "BBB")
    assert bbb.non_executable_reason == cf.INSUFFICIENT_CASH
    # cash shortfall > 0 (needed ~200 more)
    assert r.estimated_cash_shortfall > 0


def test_no_ref_price():
    buys = [FakeBuy("AAA", 1, 3000.0), FakeBuy("GHOST", 2, 3000.0)]
    r = cf.evaluate_plan(30000.0, 30000.0, buys, {"AAA": 200.0})  # GHOST missing
    assert r.no_ref_price == ["GHOST"]
    g = next(b for b in r.per_buy if b.ticker == "GHOST")
    assert g.non_executable_reason == cf.NO_REF_PRICE and g.indicative_qty == 0
    assert r.status == "PARTIAL"


def test_rounding_drag_and_min_capital():
    buys = [FakeBuy("X", 1, 1000.0)]
    r = cf.evaluate_plan(10000.0, 10000.0, buys, {"X": 300.0})
    b = r.per_buy[0]
    # qty = floor(1000/(300*1.00075)) = 3 ; debit = 3*300.225 = 900.675
    assert b.indicative_qty == 3
    assert abs(b.estimated_debit - 900.68) < 0.02
    assert abs(r.estimated_rounding_drag - round(1 - 900.675/1000, 4)) < 1e-6
    # min operational capital for X = 300*1.00075/0.10 = 3002.25
    assert abs(r.min_operational_capital_estimate - 3002.25) < 0.1
    # max_price_for_estimated_qty = 1000/(3*1.00075)
    assert abs(b.max_price_for_estimated_qty - 1000/(3*1.00075)) < 1e-3


def test_empty_plan_executable():
    r = cf.evaluate_plan(30000.0, 30000.0, [], {})
    assert r.status == "EXECUTABLE" and r.n_buys == 0


def test_low_equity_warning():
    buys = [FakeBuy("AAA", 1, 300.0)]
    r = cf.evaluate_plan(3000.0, 3000.0, buys, {"AAA": 100.0})
    assert any("below BT-06 tested minimum" in w for w in r.warnings)


def test_equity_not_equal_cash():
    # equity 30k but only 8k free cash -> gate must size against cash, not equity.
    # 10 targets of 3000 each; 8k cash covers ~2-3 names, rest INSUFFICIENT_CASH.
    buys = [FakeBuy(f"T{i}", i, 3000.0) for i in range(1, 11)]
    refs = {f"T{i}": 200.0 for i in range(1, 11)}
    r = cf.evaluate_plan(30000.0, 8000.0, buys, refs)
    assert r.equity == 30000.0 and r.available_cash_for_buys == 8000.0
    assert r.status == "PARTIAL"            # some buyable, some cash-blocked
    assert len(r.insufficient_cash) > 0     # cash runs out before all 10
    assert r.too_expensive == []            # 200 is not too expensive per target
    # executable debits must not exceed available cash
    assert r.estimated_actual_buy_debit <= 8000.0 + 1e-6
    assert r.estimated_remaining_cash_after_buys >= 0
    assert any("PARTIAL" in w for w in r.warnings)


def test_no_broker_import():
    pkg = Path(__file__).resolve().parents[1]
    forbidden = {"broker", "ib_insync", "ibapi", "ibkr", "tws", "execution"}
    tree = ast.parse((pkg / "capital_feasibility.py").read_text())
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for n in names:
            assert n.split(".")[0] not in forbidden
