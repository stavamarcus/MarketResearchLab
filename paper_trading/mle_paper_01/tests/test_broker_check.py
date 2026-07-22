"""Tests for the read-only paper connection check (fake adapter, no live TWS)."""
import ast
from pathlib import Path

from mle_paper_01.broker.check import (CheckConfig, run_check, render_md,
                                       render_json, READONLY_UNVERIFIED_MSG)
from mle_paper_01.broker.fake import FakeBroker
from mle_paper_01.broker.interface import PositionRow

EXPECTED = "DU1234567"


def cfg(**kw):
    base = dict(expected_account_id=EXPECTED, paper_prefix="DU")
    base.update(kw)
    return CheckConfig(**base)


def test_happy_path_paper_pass():
    r = run_check(FakeBroker(account_id=EXPECTED), cfg())
    assert r.passed and not r.hard_fail
    assert r.account_type == "paper" and r.account_id == EXPECTED
    assert READONLY_UNVERIFIED_MSG in r.warnings


def test_account_mismatch_hard_fail():
    r = run_check(FakeBroker(account_id="DU9999999"), cfg())
    assert not r.passed and r.hard_fail
    assert any(c["name"] == "expected_account_match" and not c["ok"]
               for c in r.checks)


def test_live_account_hard_fail():
    r = run_check(FakeBroker(account_id="U7654321"),
                  cfg(expected_account_id="U7654321"))
    assert not r.passed and r.hard_fail
    assert r.account_type == "live"
    assert any(c["name"] == "not_live_account" and not c["ok"]
               for c in r.checks)


def test_missing_expected_account_id_fails_without_connect():
    r = run_check(FakeBroker(account_id=EXPECTED), cfg(expected_account_id=""))
    assert not r.passed and r.hard_fail
    assert r.connection is None                # never connected
    assert any("expected_account_id missing" in e for e in r.errors)


def test_timeout_fails_no_hang():
    r = run_check(FakeBroker(account_id=EXPECTED, raise_timeout=True), cfg())
    assert not r.passed
    assert any("timeout" in e for e in r.errors)


def test_empty_positions_pass():
    r = run_check(FakeBroker(account_id=EXPECTED, positions=[]), cfg())
    assert r.passed and r.positions == []


def test_positions_present_parsed():
    pos = [PositionRow(symbol="AXON", conid=272104927, quantity=5,
                       avg_cost=597.04),
           PositionRow(symbol="MRNA", conid=344809106, quantity=37,
                       avg_cost=79.76)]
    r = run_check(FakeBroker(account_id=EXPECTED, positions=pos), cfg())
    assert r.passed and len(r.positions) == 2
    assert r.positions[0].symbol == "AXON" and r.positions[0].quantity == 5


def test_cash_equity_parse():
    r = run_check(FakeBroker(account_id=EXPECTED, net_liquidation=31234.5,
                             total_cash=8765.4), cfg())
    assert r.equity == 31234.5 and r.cash == 8765.4


def test_open_orders_count():
    r = run_check(FakeBroker(account_id=EXPECTED, open_orders=3), cfg())
    assert r.open_orders_count == 3


def test_reports_render_pass_and_fail():
    ok = run_check(FakeBroker(account_id=EXPECTED), cfg())
    md = render_md(ok, cfg())
    assert "PASS" in md and "Operator checklist" in md
    assert READONLY_UNVERIFIED_MSG in md
    assert '"result": "PASS"' in render_json(ok)
    bad = run_check(FakeBroker(account_id="DU0000000"), cfg())
    assert "HARD FAIL" in render_md(bad, cfg())


def test_no_order_methods_in_broker_package():
    """AST: no order submission/cancel/modify calls anywhere in broker code."""
    forbidden = {"placeOrder", "cancelOrder", "modifyOrder", "reqGlobalCancel"}
    import mle_paper_01.broker as bpkg
    pkg_dir = Path(bpkg.__file__).resolve().parent
    files = list(pkg_dir.glob("*.py"))
    files.append(pkg_dir.parent / "broker_check.py")
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func,
                                                         ast.Attribute):
                assert node.func.attr not in forbidden, \
                    f"forbidden order call {node.func.attr} in {f.name}"
            if isinstance(node, ast.FunctionDef):
                assert node.name not in forbidden, \
                    f"forbidden order method def {node.name} in {f.name}"


def test_ib_readonly_imports_without_ibapi():
    """The real adapter module must import even when ibapi is absent (lazy)."""
    import importlib
    m = importlib.import_module("mle_paper_01.broker.ib_readonly")
    assert hasattr(m, "IBReadOnlyBroker")
