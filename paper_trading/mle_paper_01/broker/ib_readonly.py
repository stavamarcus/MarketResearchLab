"""ib_readonly.py — real BrokerReadOnly adapter over native ibapi.

Read-only: this adapter calls ONLY read/subscription requests
(reqManagedAccts, reqAccountSummary, reqPositions, reqAllOpenOrders) and their
subscription cancels. It never places, cancels, or modifies an order — proven by
the AST scan in the tests. ibapi is imported lazily so this module imports fine
even where ibapi is not installed (e.g. CI without TWS).
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import List, Optional

from .interface import (AccountSummary, BrokerError, BrokerTimeout,
                        ConnectionMeta, PositionRow)

_SUMMARY_TAGS = "NetLiquidation,TotalCashValue,AvailableFunds"


def _make_app():
    """Build the EWrapper+EClient app class lazily (needs ibapi imported)."""
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper

    class _App(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.accounts: List[str] = []
            self.summary: dict = {}
            self._positions: List[PositionRow] = []
            self.open_orders = 0
            self.err: List[str] = []
            self.ev_accts = threading.Event()
            self.ev_summary = threading.Event()
            self.ev_positions = threading.Event()
            self.ev_orders = threading.Event()

        # -- connection / accounts --
        def managedAccounts(self, accountsList: str):
            self.accounts = [a for a in accountsList.split(",") if a]
            self.ev_accts.set()

        # -- account summary --
        def accountSummary(self, reqId, account, tag, value, currency):
            self.summary[tag] = value

        def accountSummaryEnd(self, reqId):
            self.ev_summary.set()

        # -- positions --
        def position(self, account, contract, position, avgCost):
            self._positions.append(PositionRow(
                symbol=getattr(contract, "symbol", ""),
                conid=getattr(contract, "conId", None),
                quantity=float(position), avg_cost=float(avgCost)))

        def positionEnd(self):
            self.ev_positions.set()

        # -- open orders (read only: count) --
        def openOrder(self, orderId, contract, order, orderState):
            self.open_orders += 1

        def openOrderEnd(self):
            self.ev_orders.set()

        # -- errors --
        def error(self, reqId, errorCode, errorString, *args):
            # 2104/2106/2158 are benign "market data farm connected" notices
            if errorCode not in (2104, 2106, 2158, 2107, 2119):
                self.err.append(f"[{errorCode}] {errorString}")

    return _App()


class IBReadOnlyBroker:
    """Read-only ibapi adapter implementing the BrokerReadOnly interface."""

    def __init__(self, host: str = "127.0.0.1", port: int = 7497,
                 client_id: int = 102):
        self._meta = ConnectionMeta(host=host, port=port, client_id=client_id)
        self._app = None
        self._thread: Optional[threading.Thread] = None
        self._timeout = 15.0

    def connect(self, timeout: float) -> ConnectionMeta:
        self._timeout = timeout
        try:
            self._app = _make_app()
        except Exception as e:  # ibapi missing / import failure
            raise BrokerError(f"ibapi unavailable: {e}")
        try:
            self._app.connect(self._meta.host, self._meta.port,
                              self._meta.client_id)
            self._thread = threading.Thread(target=self._app.run, daemon=True)
            self._thread.start()
            if not self._app.ev_accts.wait(timeout):
                raise BrokerTimeout("no managedAccounts within timeout")
            self._meta.connected = self._app.isConnected()
            self._meta.server_version = str(self._app.serverVersion())
            self._meta.connect_time = datetime.now(timezone.utc).isoformat()
            return self._meta
        except BrokerTimeout:
            raise
        except Exception as e:  # noqa: BLE001
            raise BrokerError(f"connect failed: {e}")

    def account_summary(self) -> AccountSummary:
        app = self._require()
        app.ev_summary.clear()
        app.reqAccountSummary(9001, "All", _SUMMARY_TAGS)
        if not app.ev_summary.wait(self._timeout):
            raise BrokerTimeout("accountSummaryEnd not received")
        try:
            app.cancelAccountSummary(9001)   # subscription cancel (not an order)
        except Exception:  # noqa: BLE001
            pass
        acct = app.accounts[0] if app.accounts else ""

        def _num(tag):
            v = app.summary.get(tag)
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        return AccountSummary(account_id=acct,
                              net_liquidation=_num("NetLiquidation"),
                              total_cash=_num("TotalCashValue"),
                              raw=dict(app.summary))

    def positions(self) -> List[PositionRow]:
        app = self._require()
        app._positions = []
        app.ev_positions.clear()
        app.reqPositions()
        if not app.ev_positions.wait(self._timeout):
            raise BrokerTimeout("positionEnd not received")
        try:
            app.cancelPositions()            # subscription cancel (not an order)
        except Exception:  # noqa: BLE001
            pass
        return list(app._positions)

    def open_orders_count(self) -> int:
        app = self._require()
        app.open_orders = 0
        app.ev_orders.clear()
        app.reqAllOpenOrders()               # read-only request
        if not app.ev_orders.wait(self._timeout):
            raise BrokerTimeout("openOrderEnd not received")
        return app.open_orders

    def connection_meta(self) -> ConnectionMeta:
        return self._meta

    def disconnect(self) -> None:
        if self._app is not None:
            try:
                self._app.disconnect()
            except Exception:  # noqa: BLE001
                pass
        self._meta.connected = False

    def _require(self):
        if self._app is None:
            raise BrokerError("not connected")
        return self._app
