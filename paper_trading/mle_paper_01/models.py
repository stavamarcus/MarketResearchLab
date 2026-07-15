"""
models.py — MLE-PAPER-01 datove kontrakty (Faze 1).

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md (APPROVED/FROZEN).
Kontrakty odpovidaji specu §5.4 (Decision), §8 (stavovy model) a C-4:
  - BUY nese target_value (quantity se urci az z open ceny D+1)
  - EXIT nese quantity (skutecne drzene shares)
  - PortfolioState je immutable z pohledu resolveru; mutace stavu
    provadi vyhradne stavova vrstva podle skutecnych fillu

Vsechny datove tridy jsou frozen dataclasses -> resolver fyzicky
nemuze mutovat vstupy (kauzalni cistota vynucena typem, ne konvenci).

Datumy: ISO retezce "YYYY-MM-DD" (lexikograficke porovnani = chronologicke).

Edge cases / predpoklady:
  - PortfolioState.equity = cash + mark-to-market za close D; pocita ji
    stavova vrstva (resolver nema pristup k cenam - cista funkce).
  - Position.status: resolver pracuje jen s OPEN pozicemi; CLOSED
    drzi stavova vrstva v closed_trades.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

MAX_POSITIONS = 10
TARGET_WEIGHT = 0.10  # 10 % equity per pozice
COST_BPS_ROUND_TRIP = 15
COST_HALF = COST_BPS_ROUND_TRIP / 2.0 / 10000.0  # 7.5 bps na stranu


class Action(str, Enum):
    BUY = "BUY"
    EXIT = "EXIT"
    DO_NOTHING = "DO_NOTHING"


class PriceSource(str, Enum):
    NEXT_OPEN = "next_open"  # BUY: fill na open D+1
    CLOSE = "close"          # EXIT: fill na close planned_exit_date


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class SignalCandidate:
    """Jeden kandidat z MLE_TOP10 (spec §3)."""
    ticker: str
    conid: int
    rank_10d: int  # 1 = nejsilnejsi; kandidati razeni vzestupne


@dataclass(frozen=True)
class RegimeState:
    """Stav regime200 po close signalniho dne D (spec §4).

    date = signalni den D. Pro vstupy na open D+1 se pouziva VYHRADNE
    tento stav (kauzalita) - nikdy regime z D+1.
    """
    date: str
    regime_on: bool
    index_level: Optional[float] = None       # pro audit/logging
    ma200: Optional[float] = None              # pro audit/logging
    valid_constituents: Optional[int] = None   # pro audit/logging


@dataclass(frozen=True)
class Position:
    """Otevrena pozice (spec §8)."""
    ticker: str
    conid: int
    shares: float
    entry_date: str
    entry_price: float
    planned_exit_date: str  # exit na CLOSE tohoto dne (spec §2, §6)
    signal_rank: int
    regime_at_entry: bool = True
    status: PositionStatus = PositionStatus.OPEN


@dataclass(frozen=True)
class ClosedTrade:
    """Audit zaznam uzavreneho obchodu (spec §8)."""
    ticker: str
    conid: int
    shares: float
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    pnl: float
    reason: str


@dataclass(frozen=True)
class PortfolioState:
    """Stav paper portfolia po close dne D (spec §8).

    equity = cash + mark-to-market OPEN pozic za close D
    (pocita stavova vrstva; invariant spec §8).
    Resolver tento objekt POUZE cte.
    """
    cash: float
    equity: float
    positions: Tuple[Position, ...] = field(default_factory=tuple)
    closed_trades: Tuple[ClosedTrade, ...] = field(default_factory=tuple)
    last_updated_date: str = ""

    def open_positions(self) -> Tuple[Position, ...]:
        return tuple(p for p in self.positions
                     if p.status == PositionStatus.OPEN)


@dataclass(frozen=True)
class Decision:
    """Vystup Decision Resolveru (spec §5.4).

    BUY:  target_value vyplneno, quantity=None, price_source=NEXT_OPEN,
          target_date = D+1 (fill na open)
    EXIT: quantity vyplneno, target_value=None, price_source=CLOSE,
          target_date = planned_exit_date pozice (fill na close)
    DO_NOTHING: pouze target_date + reason
    """
    action: Action
    target_date: str
    reason: str
    ticker: Optional[str] = None
    conid: Optional[int] = None
    target_value: Optional[float] = None
    quantity: Optional[float] = None
    price_source: Optional[PriceSource] = None

    def __post_init__(self):
        """Invarianty kontraktu (hardening H4) — fail-fast pri konstrukci."""
        if self.action == Action.BUY:
            if not self.ticker or self.conid is None:
                raise ValueError("Decision BUY: chybi ticker/conid")
            if self.target_value is None or self.target_value <= 0:
                raise ValueError(
                    f"Decision BUY: neplatny target_value {self.target_value}")
            if self.quantity is not None:
                raise ValueError("Decision BUY: quantity musi byt None "
                                 "(urci se az z fill ceny — C-4)")
            if self.price_source != PriceSource.NEXT_OPEN:
                raise ValueError(
                    f"Decision BUY: price_source musi byt next_open, "
                    f"je {self.price_source}")
        elif self.action == Action.EXIT:
            if not self.ticker or self.conid is None:
                raise ValueError("Decision EXIT: chybi ticker/conid")
            if self.quantity is None or self.quantity <= 0:
                raise ValueError(
                    f"Decision EXIT: neplatna quantity {self.quantity}")
            if self.target_value is not None:
                raise ValueError("Decision EXIT: target_value musi byt None")
            if self.price_source != PriceSource.CLOSE:
                raise ValueError(
                    f"Decision EXIT: price_source musi byt close, "
                    f"je {self.price_source}")
        else:  # DO_NOTHING
            if (self.ticker or self.conid is not None
                    or self.target_value is not None
                    or self.quantity is not None
                    or self.price_source is not None):
                raise ValueError(
                    "Decision DO_NOTHING: nesmi nest ticker/hodnoty")
