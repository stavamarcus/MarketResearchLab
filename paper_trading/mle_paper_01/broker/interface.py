"""interface.py — read-only broker contract.

The BrokerReadOnly Protocol exposes ONLY read methods. There is intentionally no
placeOrder / cancelOrder / modifyOrder here: read-only is structural. Everything
outside the real adapter imports this interface, never ibapi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol


class BrokerTimeout(Exception):
    """Raised when a connect/read exceeds the configured timeout."""


class BrokerError(Exception):
    """Raised on a non-timeout broker/connection failure."""


@dataclass
class ConnectionMeta:
    host: str
    port: int
    client_id: int
    connected: bool = False
    server_version: Optional[str] = None
    connect_time: Optional[str] = None


@dataclass
class AccountSummary:
    account_id: str
    net_liquidation: Optional[float] = None
    total_cash: Optional[float] = None
    raw: dict = field(default_factory=dict)


@dataclass
class PositionRow:
    symbol: str
    conid: Optional[int]
    quantity: float
    avg_cost: Optional[float] = None


class BrokerReadOnly(Protocol):
    """Read-only broker access. No order methods exist on this contract."""

    def connect(self, timeout: float) -> ConnectionMeta: ...

    def account_summary(self) -> AccountSummary: ...

    def positions(self) -> List[PositionRow]: ...

    def open_orders_count(self) -> int: ...

    def connection_meta(self) -> ConnectionMeta: ...

    def disconnect(self) -> None: ...
