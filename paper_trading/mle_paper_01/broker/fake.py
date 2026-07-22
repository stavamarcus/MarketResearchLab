"""fake.py — in-memory BrokerReadOnly for tests (no live connection).

Configurable to simulate: normal paper account, account mismatch, live account,
timeout, empty vs populated positions. Read-only, like the real adapter.
"""
from __future__ import annotations

from typing import List, Optional

from .interface import (AccountSummary, BrokerTimeout, ConnectionMeta,
                        PositionRow)


class FakeBroker:
    def __init__(self, account_id: str = "DU1234567",
                 net_liquidation: Optional[float] = 30000.0,
                 total_cash: Optional[float] = 30000.0,
                 positions: Optional[List[PositionRow]] = None,
                 open_orders: int = 0, raise_timeout: bool = False,
                 host: str = "127.0.0.1", port: int = 7497,
                 client_id: int = 102):
        self._account_id = account_id
        self._nlv = net_liquidation
        self._cash = total_cash
        self._positions = positions or []
        self._open_orders = open_orders
        self._raise_timeout = raise_timeout
        self._meta = ConnectionMeta(host=host, port=port, client_id=client_id)

    def connect(self, timeout: float) -> ConnectionMeta:
        if self._raise_timeout:
            raise BrokerTimeout(f"fake connect timed out after {timeout}s")
        self._meta.connected = True
        self._meta.server_version = "FAKE"
        self._meta.connect_time = "2026-07-06T14:30:00Z"
        return self._meta

    def account_summary(self) -> AccountSummary:
        return AccountSummary(account_id=self._account_id,
                              net_liquidation=self._nlv,
                              total_cash=self._cash,
                              raw={"NetLiquidation": self._nlv,
                                   "TotalCashValue": self._cash})

    def positions(self) -> List[PositionRow]:
        return list(self._positions)

    def open_orders_count(self) -> int:
        return self._open_orders

    def connection_meta(self) -> ConnectionMeta:
        return self._meta

    def disconnect(self) -> None:
        self._meta.connected = False
