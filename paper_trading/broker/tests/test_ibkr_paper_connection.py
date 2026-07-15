"""
test_ibkr_paper_connection.py — safety/unit testy Phase 2A.

Bezi BEZ ibapi a BEZ TWS (mock adapter). Zdroj pravdy: zadani
architekta Phase 2A, bod 5.

Spusteni (z MarketResearchLab/paper_trading/):
    python -m unittest broker.tests.test_ibkr_paper_connection -v

Pokryti:
  C1  expected_account_id chybi -> FAIL (bez pokusu o connect)
  C2  detected != expected -> FAIL + okamzity STOP (zadne dalsi cteni)
  C3  mode != paper -> FAIL
  C4  allow_live_orders == true -> FAIL
  C5  validni paper config + shodny ucet -> PASS + audit log
  C6  connection failure -> FAIL bez side effects (zadne cteni)
  C7  STATICKY SAFETY TEST: zdrojak neobsahuje volani order metod
      (.placeOrder( / .modifyOrder( / .cancelOrder()
  C8  prefix guard: expected ucet nezacina DU -> FAIL
  C9  order_sent je vzdy False; adapter mock potvrzuje, ze se volaly
      jen read-only metody
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from broker.ibkr_paper_connection import (run_connection_check,
                                          validate_account,
                                          validate_profile)

VALID_PROFILE = {
    "mode": "paper", "broker": "ibkr", "host": "127.0.0.1", "port": 7497,
    "client_id": 101, "expected_account_id": "DU1234567",
    "allow_live_orders": False, "read_only_test_mode": True,
}

READ_ONLY_METHODS = {"connect", "managed_accounts", "account_summary",
                     "positions", "open_orders_count", "disconnect"}


class MockAdapter:
    """Read-only mock. Zaznamenava volane metody."""

    def __init__(self, accounts=("DU1234567",), connect_ok=True):
        self._accounts = list(accounts)
        self._connect_ok = connect_ok
        self.calls = []
        self.errors = []

    def connect(self, host, port, client_id):
        self.calls.append("connect")
        return self._connect_ok

    def managed_accounts(self):
        self.calls.append("managed_accounts")
        return list(self._accounts)

    def account_summary(self, account):
        self.calls.append("account_summary")
        return {"NetLiquidation": "100000.00",
                "TotalCashValue": "100000.00",
                "BuyingPower": "400000.00"}

    def positions(self):
        self.calls.append("positions")
        return []

    def open_orders_count(self):
        self.calls.append("open_orders_count")
        return 0

    def disconnect(self):
        self.calls.append("disconnect")


def check(profile, adapter):
    with tempfile.TemporaryDirectory() as td:
        res = run_connection_check(profile, adapter=adapter,
                                   logs_dir=Path(td))
        logs = list(Path(td).glob("paper_connection_check_*.json"))
        # obsah cist JESTE uvnitr with bloku (tempdir se pak maze)
        payloads = [json.loads(p.read_text(encoding="utf-8"))
                    for p in logs]
        return res, logs, payloads


class TestPreConnectGuards(unittest.TestCase):
    def test_C1_missing_expected_account_fails_without_connect(self):
        p = dict(VALID_PROFILE, expected_account_id="")
        a = MockAdapter()
        res, logs, payloads = check(p, a)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(a.calls, [])          # zadny pokus o connect
        self.assertEqual(len(logs), 1)         # FAIL se take audituje
        self.assertFalse(res["order_sent"])

    def test_C3_mode_not_paper_fails(self):
        p = dict(VALID_PROFILE, mode="live")
        res, _, _ = check(p, MockAdapter())
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any("mode" in e for e in res["errors"]))

    def test_C4_allow_live_orders_true_fails(self):
        p = dict(VALID_PROFILE, allow_live_orders=True)
        res, _, _ = check(p, MockAdapter())
        self.assertEqual(res["status"], "FAIL")

    def test_read_only_test_mode_false_fails(self):
        p = dict(VALID_PROFILE, read_only_test_mode=False)
        res, _, _ = check(p, MockAdapter())
        self.assertEqual(res["status"], "FAIL")


class TestAccountGuards(unittest.TestCase):
    def test_C2_account_mismatch_immediate_stop(self):
        a = MockAdapter(accounts=("DU9999999",))
        res, logs, payloads = check(VALID_PROFILE, a)
        self.assertEqual(res["status"], "FAIL")
        self.assertFalse(res["account_match"])
        # okamzity STOP: po managed_accounts uz ZADNE dalsi cteni
        self.assertNotIn("account_summary", a.calls)
        self.assertNotIn("positions", a.calls)
        self.assertIn("disconnect", a.calls)   # ale odpojeni probehlo
        self.assertEqual(len(logs), 1)

    def test_C8_non_DU_prefix_fails(self):
        p = dict(VALID_PROFILE, expected_account_id="U1234567")
        a = MockAdapter(accounts=("U1234567",))
        res, _, _ = check(p, a)
        self.assertEqual(res["status"], "FAIL")
        self.assertTrue(any("DU" in e for e in res["errors"]))
        self.assertNotIn("account_summary", a.calls)

    def test_validate_account_pure(self):
        self.assertEqual(validate_account(["DU1", "DU2"], "DU1"), [])
        self.assertTrue(validate_account(["DU1"], "DU9"))
        self.assertTrue(validate_account(["U555"], "U555"))


class TestHappyAndFailurePaths(unittest.TestCase):
    def test_C5_valid_config_matching_account_pass(self):
        a = MockAdapter()
        res, logs, payloads = check(VALID_PROFILE, a)
        self.assertEqual(res["status"], "PASS")
        self.assertTrue(res["connected"])
        self.assertTrue(res["account_match"])
        self.assertEqual(res["detected_account_id"], "DU1234567")
        self.assertEqual(res["positions_count"], 0)
        self.assertEqual(res["open_orders_count"], 0)
        self.assertFalse(res["order_sent"])
        self.assertFalse(res["orders_allowed"])
        self.assertEqual(len(logs), 1)
        self.assertEqual(payloads[0]["status"], "PASS")

    def test_C6_connection_failure_no_side_effects(self):
        a = MockAdapter(connect_ok=False)
        res, logs, payloads = check(VALID_PROFILE, a)
        self.assertEqual(res["status"], "FAIL")
        self.assertFalse(res["connected"])
        self.assertNotIn("managed_accounts", a.calls)  # zadne cteni
        self.assertEqual(len(logs), 1)

    def test_C9_only_read_only_methods_called(self):
        a = MockAdapter()
        check(VALID_PROFILE, a)
        self.assertTrue(set(a.calls) <= READ_ONLY_METHODS,
                        f"neocekavane volani: {set(a.calls) - READ_ONLY_METHODS}")


class TestStaticOrderMethodScan(unittest.TestCase):
    def test_C7_no_order_submission_calls_in_source(self):
        src_path = Path(__file__).resolve().parent.parent \
            / "ibkr_paper_connection.py"
        src = src_path.read_text(encoding="utf-8")
        # volaci patterny, ne slova v komentarich (dle architekta)
        forbidden = [r"\.placeOrder\s*\(", r"\.modifyOrder\s*\(",
                     r"\.cancelOrder\s*\(", r"\bplaceOrder\s*\(",
                     r"\bmodifyOrder\s*\(", r"\bcancelOrder\s*\("]
        hits = []
        for pat in forbidden:
            for m in re.finditer(pat, src):
                line = src[:m.start()].count("\n") + 1
                hits.append(f"{pat} na radku {line}")
        self.assertEqual(hits, [],
                         f"ZAKAZANE order volani ve zdrojaku: {hits}")

    def test_C7b_validate_profile_pure(self):
        self.assertEqual(validate_profile(VALID_PROFILE), [])
        self.assertTrue(validate_profile(dict(VALID_PROFILE, port="x")))


if __name__ == "__main__":
    unittest.main()
