"""
PriceLoader — načítání EOD cen přes DataProvider interface.

Zodpovědnost:
    Sestavit wide-format DataFrame (pivot: date × conid) z cen
    načtených přes DataProvider. Experimenty volají PriceLoader,
    nikdy DataProvider přímo.

Výstupní formát:
    pd.DataFrame
        index: pd.DatetimeIndex (date)
        columns: MultiIndex (sloupec, conid)
                 nebo jednoduché sloupce pokud pouze jedna price série

    Příklad:
        close_prices = price_loader.load_close(conids, date_from, date_to)
        # close_prices.columns = [756733, 4065, 12259, ...]
        # close_prices.index = DatetimeIndex [2025-01-02, 2025-01-03, ...]
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.data.data_provider import DataProvider, DataProviderError
from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)


class PriceLoader:
    """
    Sestavuje price DataFrame z DataProvider pro experimenty.

    Příklad použití:
        loader = PriceLoader(provider=mdsm_provider)
        close = loader.load_close(conids=[756733, 4065], date_from=..., date_to=...)
        ohlcv = loader.load_ohlcv(conids=[756733], date_from=..., date_to=...)
    """

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider

    def load_close(
        self,
        conids: list[int],
        date_from: date,
        date_to: date,
        min_coverage: float = 0.5,
    ) -> pd.DataFrame:
        """
        Načte close ceny pro seznam conid jako wide DataFrame.

        Args:
            conids:       seznam IBKR conid
            date_from:    první den (včetně)
            date_to:      poslední den (včetně)
            min_coverage: minimální podíl dnů s daty (0.0–1.0).
                          Conidy pod prahem jsou zahrnuty ale vylogged.

        Returns:
            pd.DataFrame(index=date, columns=conid) — close prices.
            Chybějící hodnoty = NaN (conid nemá data pro daný den).
        """
        prices = self._provider.load_prices(conids, date_from, date_to)

        if not prices:
            logger.warning(
                f"PriceLoader.load_close: žádná data načtena pro "
                f"{len(conids)} conid | {date_from} → {date_to}"
            )
            return pd.DataFrame()

        series = {}
        for conid, df in prices.items():
            series[conid] = df["close"]

        result = pd.DataFrame(series)
        result.index.name = "date"
        result = result.sort_index()

        self._log_coverage(result, conids, min_coverage)
        return result

    def load_ohlcv(
        self,
        conids: list[int],
        date_from: date,
        date_to: date,
    ) -> dict[int, pd.DataFrame]:
        """
        Načte kompletní OHLCV pro seznam conid.

        Returns:
            dict[conid, DataFrame(open, high, low, close, volume)]
        """
        return self._provider.load_prices(conids, date_from, date_to)

    def load_returns(
        self,
        conids: list[int],
        date_from: date,
        date_to: date,
        method: str = "log",
    ) -> pd.DataFrame:
        """
        Načte denní výnosy vypočítané z close cen.

        Args:
            method: 'log' (logaritmické) nebo 'pct' (procentuální)

        Returns:
            pd.DataFrame(index=date, columns=conid) — denní výnosy.
            První řádek je NaN (žádný předchozí den pro výpočet).
        """
        close = self.load_close(conids, date_from, date_to)
        if close.empty:
            return pd.DataFrame()

        if method == "log":
            import numpy as np
            returns = np.log(close / close.shift(1))
        elif method == "pct":
            returns = close.pct_change()
        else:
            raise DataProviderError(
                f"Neznámá metoda výpočtu výnosů: '{method}'. "
                "Použij 'log' nebo 'pct'."
            )

        return returns

    # ------------------------------------------------------------------
    # Interní metody
    # ------------------------------------------------------------------

    def _log_coverage(
        self,
        df: pd.DataFrame,
        requested: list[int],
        min_coverage: float,
    ) -> None:
        """Loguje conidy s nízkou datovou pokrytostí."""
        if df.empty:
            return
        total_days = len(df)
        for conid in df.columns:
            available = df[conid].notna().sum()
            coverage = available / total_days if total_days > 0 else 0.0
            if coverage < min_coverage:
                logger.warning(
                    f"conid={conid} nízká pokrytost dat: "
                    f"{available}/{total_days} dní ({coverage:.1%})"
                )

        missing_entirely = [c for c in requested if c not in df.columns]
        if missing_entirely:
            logger.warning(
                f"PriceLoader: {len(missing_entirely)} conid bez jakýchkoliv dat: "
                f"{missing_entirely[:5]}{'...' if len(missing_entirely) > 5 else ''}"
            )
