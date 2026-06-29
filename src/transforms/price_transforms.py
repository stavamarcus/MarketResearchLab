"""
PriceTransforms — transformace EOD cenových dat pro experimenty.

Zodpovědnost:
    Čisté transformace nad cenovými DataFrame.
    Vstup: dict[conid, DataFrame(OHLCV)] z PriceProvider.
    Výstup: wide-format DataFrame nebo returns Series.

Není provider. Nenačítá data. Netransformuje přes síť.
Používá se uvnitř experimentů přes ExperimentContext.

Příklad:
    close = PriceTransforms.to_close_matrix(context.prices)
    returns = PriceTransforms.to_log_returns(close)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)


class PriceTransformError(Exception):
    """Chyba při transformaci cenových dat."""


class PriceTransforms:
    """
    Statické transformace nad EOD cenovými daty.

    Všechny metody jsou čisté funkce — žádný stav, žádné side effects.
    """

    @staticmethod
    def to_close_matrix(
        prices: dict[int, pd.DataFrame],
        min_coverage: float = 0.5,
    ) -> pd.DataFrame:
        """
        Sestaví wide-format DataFrame close cen.

        Args:
            prices:       dict[conid → DataFrame(OHLCV)] z PriceProvider
            min_coverage: loguje conidy s méně než X podílem dostupných dní

        Returns:
            pd.DataFrame(index=date, columns=conid)
            Chybějící hodnoty = NaN.
        """
        if not prices:
            return pd.DataFrame()

        result = pd.DataFrame({
            conid: df["close"] for conid, df in prices.items()
        }).sort_index()
        result.index.name = "date"

        PriceTransforms._log_coverage(result, min_coverage)
        return result

    @staticmethod
    def to_log_returns(close: pd.DataFrame) -> pd.DataFrame:
        """
        Logaritmické denní výnosy z close matrix.

        Returns:
            pd.DataFrame stejného tvaru. První řádek = NaN.
        """
        if close.empty:
            return pd.DataFrame()
        return np.log(close / close.shift(1))

    @staticmethod
    def to_pct_returns(close: pd.DataFrame) -> pd.DataFrame:
        """
        Procentuální denní výnosy z close matrix.

        Returns:
            pd.DataFrame stejného tvaru. První řádek = NaN.
        """
        if close.empty:
            return pd.DataFrame()
        return close.pct_change()

    @staticmethod
    def to_forward_returns(
        close: pd.DataFrame,
        horizon: int,
    ) -> pd.DataFrame:
        """
        Forward returns s daným horizontem (v obchodních dnech).

        Příklad: horizon=20 → výnos za následujících 20 obchodních dní.

        Returns:
            pd.DataFrame stejného tvaru. Posledních `horizon` řádků = NaN.
        """
        if close.empty:
            return pd.DataFrame()
        return close.shift(-horizon) / close - 1

    @staticmethod
    def _log_coverage(df: pd.DataFrame, min_coverage: float) -> None:
        if df.empty:
            return
        total = len(df)
        for conid in df.columns:
            cov = df[conid].notna().sum() / total
            if cov < min_coverage:
                logger.warning(
                    f"conid={conid}: nízká datová pokrytost "
                    f"{cov:.1%} ({df[conid].notna().sum()}/{total} dní)"
                )
