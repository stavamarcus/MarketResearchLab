"""
exit_rules.py — RP-0011-EXIT-TIMING

Abstrakce výstupních pravidel pro Exit Validation framework.

Zásady (PM approval 2026-07-02):
    - Pravidlo POUZE signalizuje (check → bool). Fill exekuuje výhradně
      exit_engine podle deklarované FillPolicy pravidla.
    - Nová exit logika (ATR stop, Chandelier, Highest Close, ...) =
      nová třída ExitRule. Žádná změna enginu.
    - Pravidlo pracuje nad ticker-lokální sérií closes (numpy array);
      prepare() se volá jednou per trade-série před simulací.

EMA definice (pre-registrováno, zamčeno 2026-07-02):
    alpha = 2/(n+1); seed = SMA prvních n closes (EMA definována od
    baru n-1 lokální série); rekurzivně dál. Žádný look-ahead — EMA(k)
    používá pouze closes[0..k].
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

import numpy as np


class FillPolicy(Enum):
    """Jak engine realizuje signál. Deklarace pravidla, exekuce enginu."""
    CLOSE = "close"            # exit na close baru signálu (time exit)
    NEXT_OPEN = "next_open"    # signál na close, fill open následujícího baru


class ExitRule(ABC):
    """Výstupní pravidlo. Stateless mezi trades — prepare() resetuje."""

    name: str
    fill: FillPolicy

    @abstractmethod
    def prepare(self, closes: np.ndarray) -> None:
        """Předpočet nad lokální sérií closes (per trade)."""

    @abstractmethod
    def check(self, pos: int, entry_pos: int) -> bool:
        """Signál na close baru `pos` (lokální index)? Look-ahead zakázán."""

    @abstractmethod
    def min_history(self) -> int:
        """Minimální počet barů PŘED entry, aby bylo pravidlo definované."""


class TimeExit(ExitRule):
    """Fixní hold n barů. Fill = close(entry+n). Baseline pravidlo."""

    fill = FillPolicy.CLOSE

    def __init__(self, n_days: int):
        self.n_days = int(n_days)
        self.name = f"TIME_{self.n_days}"

    def prepare(self, closes: np.ndarray) -> None:
        pass

    def check(self, pos: int, entry_pos: int) -> bool:
        return (pos - entry_pos) >= self.n_days

    def min_history(self) -> int:
        return 0


class EMAExit(ExitRule):
    """Signál: close(pos) < EMA(period)(pos). Fill = next open.

    EMA: alpha=2/(n+1), SMA seed. EMA nedefinovaná (NaN) prvních n-1
    barů lokální série → check tam vrací False (žádný signál).
    """

    fill = FillPolicy.NEXT_OPEN
    WARMUP_MULT = 3  # zámek: >= 3× perioda barů historie před entry

    def __init__(self, period: int):
        self.period = int(period)
        self.name = f"EMA_{self.period}"
        self._ema: np.ndarray | None = None
        self._closes: np.ndarray | None = None

    def prepare(self, closes: np.ndarray) -> None:
        n = self.period
        ema = np.full(len(closes), np.nan)
        if len(closes) >= n:
            ema[n - 1] = closes[:n].mean()          # SMA seed
            alpha = 2.0 / (n + 1.0)
            for i in range(n, len(closes)):
                ema[i] = alpha * closes[i] + (1.0 - alpha) * ema[i - 1]
        self._ema = ema
        self._closes = closes

    def check(self, pos: int, entry_pos: int) -> bool:
        e = self._ema[pos]
        if np.isnan(e):
            return False
        return bool(self._closes[pos] < e)

    def min_history(self) -> int:
        return self.WARMUP_MULT * self.period

    def ema_at(self, pos: int) -> float:
        """Diagnostika (reporting), ne rozhodovací API."""
        return float(self._ema[pos])


class RankLossExit(ExitRule):
    """RP-0012: signál = aux rank série > threshold na close(pos).

    Rank as-of close(pos) (D1 batch po close). Fill = next open.
    Aux série se dodává přes set_series() PŘED prepare() — zarovnaná
    na ticker-lokální bary (NaN = chybějící rank). NaN → žádný signál;
    censoring chybějících ranků řeší experiment (vyloučení trade),
    NE pravidlo — pravidlo musí být bezpečné i při NaN.
    """

    fill = FillPolicy.NEXT_OPEN

    def __init__(self, threshold: int):
        self.threshold = int(threshold)
        self.name = f"RANK_{self.threshold}"
        self._ranks: np.ndarray | None = None

    def set_series(self, ranks: np.ndarray) -> None:
        """Rank hodnoty zarovnané 1:1 na lokální bary (NaN = missing)."""
        self._ranks = ranks

    def prepare(self, closes: np.ndarray) -> None:
        if self._ranks is None:
            raise RuntimeError(f"{self.name}: set_series() nevoláno před prepare().")
        if len(self._ranks) != len(closes):
            raise RuntimeError(
                f"{self.name}: délka ranks ({len(self._ranks)}) != closes ({len(closes)})."
            )

    def check(self, pos: int, entry_pos: int) -> bool:
        r = self._ranks[pos]
        if np.isnan(r):
            return False
        return bool(r > self.threshold)

    def min_history(self) -> int:
        return 0
