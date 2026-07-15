"""
ibkr_paper_connection.py — MLE-PAPER-01 Phase 2A: Paper Connection
Safety Layer (READ-ONLY).

Zdroj pravdy: zadani architekta Phase 2A (2026-07-14).

UCEL: bezpecne overit pripojeni ke SPRAVNEMU IBKR paper uctu, precist
stav uctu a pozice, odpojit se. TENTO MODUL NIKDY NEPOSILA ORDERY.

Hard safety guardy (pred-connect):
  - mode == "paper"
  - allow_live_orders == false
  - read_only_test_mode == true
  - expected_account_id vyplneny
Hard safety guardy (po-connect):
  - detected account == expected_account_id (hlavni autorita)
  - detected account zacina "DU" — SEKUNDARNI bezpecnostni pojistka
    (IBKR paper ucty maji prefix DU, live U). NENI nahrada presne
    kontroly account ID; chrani proti preklepu v expected_account_id,
    ktery by omylem ukazoval na live ucet.
  - jakykoli guard FAIL -> okamzity STOP + disconnect, zadne dalsi cteni

Zakazano (vynuceno statickym safety testem, ne jen disciplinou):
  placeOrder / modifyOrder / cancelOrder ani zadne wrappery na ne.
  reqOpenOrders je povoleny READ-ONLY dotaz (jen pocet).

Architektonicka zasada (§9 zadani): DATA role (live TWS / GDU / MDSM
cache) a EXECUTION role (paper TWS) se NIKDY nemichaji. Tento modul
patri vyhradne do EXECUTION role a smi mluvit jen s paper uctem.

Spusteni (MRL env, TWS paper prihlaseny):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab\\paper_trading
    python -m broker.ibkr_paper_connection
    (volitelne --config <cesta> --timeout <s>)

Audit log: paper_trading/logs/paper_connection_check_YYYY-MM-DD_HHMMSS.json

Edge cases / predpoklady:
  - ibapi se importuje LINE (jen v IbkrAdapter) -> unit testy bezi bez
    nainstalovaneho ibapi i bez TWS.
  - timeouty: connect i kazde cteni maji timeout (default 15 s);
    timeout = FAIL bez side effects.
  - managedAccounts muze vratit vic uctu; guard vyzaduje, aby expected
    byl mezi nimi, a pracuje se VYHRADNE s expected uctem.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_TIMEOUT_S = 15.0
ACCOUNT_SUMMARY_TAGS = "NetLiquidation,TotalCashValue,BuyingPower"
PAPER_ACCOUNT_PREFIX = "DU"


# ---------------------------------------------------------------- guardy
def validate_profile(profile: Dict) -> List[str]:
    """Pred-connect hard guardy. Vraci seznam chyb (prazdny = OK).
    Cista funkce — testovatelna bez brokeru."""
    errors: List[str] = []
    if profile.get("mode") != "paper":
        errors.append(f"GUARD FAIL: mode musi byt 'paper', "
                      f"je {profile.get('mode')!r}")
    if profile.get("broker") != "ibkr":
        errors.append(f"GUARD FAIL: broker musi byt 'ibkr', "
                      f"je {profile.get('broker')!r}")
    if profile.get("allow_live_orders") is not False:
        errors.append("GUARD FAIL: allow_live_orders musi byt false")
    if profile.get("read_only_test_mode") is not True:
        errors.append("GUARD FAIL: read_only_test_mode musi byt true")
    if not str(profile.get("expected_account_id") or "").strip():
        errors.append("GUARD FAIL: expected_account_id neni vyplneny "
                      "(doplnit rucne ID paper uctu do configu)")
    if not isinstance(profile.get("port"), int):
        errors.append("GUARD FAIL: port musi byt cislo")
    if not isinstance(profile.get("client_id"), int):
        errors.append("GUARD FAIL: client_id musi byt cislo")
    return errors


def validate_account(detected_accounts: List[str],
                     expected: str) -> List[str]:
    """Po-connect hard guardy na account ID. Cista funkce."""
    errors: List[str] = []
    if expected not in detected_accounts:
        errors.append(
            f"GUARD FAIL: expected account {expected!r} neni mezi "
            f"detekovanymi {detected_accounts} - OKAMZITY STOP")
    if not expected.startswith(PAPER_ACCOUNT_PREFIX):
        # sekundarni pojistka (viz docstring) — hard fail v Phase 2A
        errors.append(
            f"GUARD FAIL: account {expected!r} nezacina "
            f"'{PAPER_ACCOUNT_PREFIX}' (paper prefix) - podezreni na "
            f"live ucet, OKAMZITY STOP")
    return errors


# ---------------------------------------------------------------- adapter
class IbkrAdapter:
    """Read-only adapter nad nativnim ibapi (EClient/EWrapper).

    Vedome NEOBSAHUJE zadnou order metodu. Import ibapi je liny —
    unit testy tento adapter nevytvareji.
    """

    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S):
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper

        timeout = timeout_s
        outer = self

        class _App(EWrapper, EClient):
            def __init__(self):
                EClient.__init__(self, self)
                self.accounts: List[str] = []
                self.summary: Dict[str, str] = {}
                self.pos: List[Dict] = []
                self.open_orders = 0
                self.ev_accounts = threading.Event()
                self.ev_summary = threading.Event()
                self.ev_positions = threading.Event()
                self.ev_orders = threading.Event()
                self.ev_connected = threading.Event()

            # --- callbacks (read-only) ---
            def managedAccounts(self, accountsList: str):
                self.accounts = [a for a in accountsList.split(",") if a]
                self.ev_accounts.set()

            def nextValidId(self, orderId: int):
                # POZOR: orderId se NIKDY nepouziva — zadne ordery.
                self.ev_connected.set()

            def accountSummary(self, reqId, account, tag, value, currency):
                self.summary[tag] = value

            def accountSummaryEnd(self, reqId):
                self.ev_summary.set()

            def position(self, account, contract, position, avgCost):
                self.pos.append({"account": account,
                                 "symbol": contract.symbol,
                                 "secType": contract.secType,
                                 "position": float(position),
                                 "avgCost": float(avgCost)})

            def positionEnd(self):
                self.ev_positions.set()

            def openOrder(self, orderId, contract, order, orderState):
                self.open_orders += 1

            def openOrderEnd(self):
                self.ev_orders.set()

            def error(self, reqId, errorCode, errorString,
                      advancedOrderRejectJson=""):
                # informacni kody (2104/2106/2158 market data farm)
                # nejsou chyby pripojeni
                if errorCode in (2104, 2106, 2107, 2158):
                    return
                outer.errors.append(f"[{errorCode}] {errorString}")

        self._App = _App
        self._app = None
        self._thread = None
        self._timeout = timeout
        self.errors: List[str] = []

    def connect(self, host: str, port: int, client_id: int) -> bool:
        self._app = self._App()
        self._app.connect(host, port, client_id)
        self._thread = threading.Thread(target=self._app.run, daemon=True)
        self._thread.start()
        ok = self._app.ev_connected.wait(self._timeout)
        return ok and self._app.isConnected()

    def managed_accounts(self) -> List[str]:
        self._app.ev_accounts.wait(self._timeout)
        return list(self._app.accounts)

    def account_summary(self, account: str) -> Dict[str, str]:
        self._app.reqAccountSummary(9001, "All", ACCOUNT_SUMMARY_TAGS)
        self._app.ev_summary.wait(self._timeout)
        self._app.cancelAccountSummary(9001)  # ukonceni SUBSCRIPCE cteni,
        # nikoli order operace (cancelAccountSummary != cancelOrder)
        return dict(self._app.summary)

    def positions(self) -> List[Dict]:
        self._app.reqPositions()
        self._app.ev_positions.wait(self._timeout)
        self._app.cancelPositions()  # ukonceni subscripce cteni pozic
        return list(self._app.pos)

    def open_orders_count(self) -> int:
        self._app.reqOpenOrders()  # READ-ONLY vycet
        self._app.ev_orders.wait(min(self._timeout, 5.0))
        return int(self._app.open_orders)

    def disconnect(self) -> None:
        if self._app is not None and self._app.isConnected():
            self._app.disconnect()
        time.sleep(0.2)


# ---------------------------------------------------------------- check
def run_connection_check(profile: Dict, adapter=None,
                         logs_dir: Optional[Path] = None,
                         timeout_s: float = DEFAULT_TIMEOUT_S) -> Dict:
    """Provede read-only connection safety check. Vraci result dict a
    zapise audit log. NIKDY neposila order."""
    ts = datetime.now()
    result: Dict = {
        "timestamp": ts.isoformat(),
        "host": profile.get("host"), "port": profile.get("port"),
        "client_id": profile.get("client_id"),
        "mode": profile.get("mode"),
        "allow_live_orders": profile.get("allow_live_orders"),
        "expected_account_id": profile.get("expected_account_id"),
        "detected_account_id": None,
        "account_match": False,
        "orders_allowed": False,
        "connected": False,
        "account_summary": {},
        "positions": [], "positions_count": 0,
        "open_orders_count": None,
        "order_sent": False,   # invariant Phase 2A — vzdy False
        "errors": [],
        "status": "FAIL",
    }

    # --- pred-connect guardy ---
    errs = validate_profile(profile)
    if errs:
        result["errors"] = errs
        _write_log(result, logs_dir)
        return result

    own_adapter = adapter is None
    if own_adapter:
        adapter = IbkrAdapter(timeout_s=timeout_s)

    try:
        if not adapter.connect(profile["host"], profile["port"],
                               profile["client_id"]):
            result["errors"].append(
                "CONNECT FAIL: TWS paper nedostupny (bezi TWS? spravny "
                "port? API povolene v TWS: Configure -> API -> Settings)")
            _write_log(result, logs_dir)
            return result
        result["connected"] = True

        accounts = adapter.managed_accounts()
        result["detected_account_id"] = accounts[0] if accounts else None
        expected = str(profile["expected_account_id"]).strip()

        acc_errs = validate_account(accounts, expected)
        if acc_errs:
            result["errors"] += acc_errs
            return result  # STOP — zadne dalsi cteni (finally odpoji)
        result["account_match"] = True
        result["detected_account_id"] = expected

        result["account_summary"] = adapter.account_summary(expected)
        pos = adapter.positions()
        result["positions"] = pos
        result["positions_count"] = len(pos)
        result["open_orders_count"] = adapter.open_orders_count()
        result["status"] = "PASS"
    except Exception as e:  # zadne side effects, jen FAIL zaznam
        result["errors"].append(f"EXCEPTION: {type(e).__name__}: {e}")
        result["status"] = "FAIL"
    finally:
        try:
            adapter.disconnect()
        except Exception:
            pass
        adapter_errs = getattr(adapter, "errors", [])
        if adapter_errs:
            result["errors"] += adapter_errs
        _write_log(result, logs_dir)
    return result


def _write_log(result: Dict, logs_dir: Optional[Path]) -> Path:
    if logs_dir is None:
        logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = logs_dir / f"paper_connection_check_{stamp}.json"
    path.write_text(json.dumps(result, indent=2, default=str),
                    encoding="utf-8")
    return path


def load_profile(path: Path) -> Dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    default_cfg = (Path(__file__).resolve().parent.parent / "config"
                   / "execution_profile_paper.json")
    ap.add_argument("--config", default=str(default_cfg))
    ap.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    args = ap.parse_args(argv)

    profile = load_profile(Path(args.config))
    result = run_connection_check(profile, timeout_s=args.timeout)

    print(f"status:              {result['status']}")
    print(f"connected:           {result['connected']}")
    print(f"account_id_expected: {result['expected_account_id']}")
    print(f"account_id_detected: {result['detected_account_id']}")
    print(f"account_match:       {result['account_match']}")
    print(f"mode:                {result['mode']}")
    print(f"orders_allowed:      {result['orders_allowed']}")
    print(f"positions_count:     {result['positions_count']}")
    print(f"account_summary:     {result['account_summary']}")
    print(f"open_orders_count:   {result['open_orders_count']}")
    print(f"order_sent:          {result['order_sent']}")
    for e in result["errors"]:
        print(f"  ! {e}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
