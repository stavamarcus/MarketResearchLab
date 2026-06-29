"""
UniverseLoader — načítání universe přes DataProvider interface.

Wrapper nad DataProvider.load_universe() s helper metodami
pro filtrování a lookup používanými v experimentech.
"""

from __future__ import annotations

import pandas as pd

from src.data.data_provider import DataProvider
from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)


class UniverseLoader:
    """
    Poskytuje experimenty s universe daty přes DataProvider.

    Příklad použití:
        loader = UniverseLoader(provider=mdsm_provider)
        universe = loader.load("sp500_rank_calendar")
        active_conids = loader.active_conids("sp500_rank_calendar")
        ticker = loader.get_ticker(756733, "sp500_rank_calendar")
    """

    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider
        self._cache: dict[str, pd.DataFrame] = {}

    def load(self, universe_name: str = "sp500") -> pd.DataFrame:
        """
        Načte universe. Výsledek cachuje v paměti (v rámci session).

        Returns:
            DataFrame(index=conid, columns=[ticker, exchange, ..., active_flag])
        """
        if universe_name not in self._cache:
            self._cache[universe_name] = self._provider.load_universe(universe_name)
        return self._cache[universe_name].copy()

    def active_conids(self, universe_name: str = "sp500") -> list[int]:
        """Vrátí seznam conid s active_flag=True."""
        df = self.load(universe_name)
        return list(df[df["active_flag"]].index)

    def all_conids(self, universe_name: str = "sp500") -> list[int]:
        """Vrátí všechny conid (aktivní i neaktivní)."""
        return list(self.load(universe_name).index)

    def get_ticker(self, conid: int, universe_name: str = "sp500") -> str | None:
        """Vrátí ticker pro daný conid, nebo None pokud neexistuje."""
        df = self.load(universe_name)
        if conid not in df.index:
            return None
        return str(df.loc[conid, "ticker"])

    def get_metadata(self, conid: int, universe_name: str = "sp500") -> dict | None:
        """Vrátí kompletní metadata instrumentu jako dict, nebo None."""
        df = self.load(universe_name)
        if conid not in df.index:
            return None
        row = df.loc[conid].to_dict()
        row["conid"] = conid
        return row

    def clear_cache(self) -> None:
        """Vymaže in-memory cache universe dat."""
        self._cache.clear()
