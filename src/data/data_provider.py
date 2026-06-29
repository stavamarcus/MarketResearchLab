"""
DataProvider — abstraktní interface pro všechny datové zdroje MRL.

Architektonické pravidlo:
    DataProvider = stabilní kontrakt
    MDSMDataProvider = první implementace (aktuální)
    SharadarDataProvider = budoucí implementace (stejný interface)

Experimenty pracují výhradně s tímto interfacem.
Nikdy nevolají konkrétní implementaci přímo.

Kontrakt:
    load_prices(conids, date_from, date_to) -> dict[int, pd.DataFrame]
    load_universe(universe_name)            -> pd.DataFrame
    available_conids()                      -> list[int]
    provider_name                          -> str
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class DataProviderError(Exception):
    """Chyba při načítání dat z DataProvider."""


class DataProvider(ABC):
    """
    Abstraktní interface pro všechny datové zdroje MRL.

    Každá implementace musí zaručit:
    - READ-ONLY přístup k datům (žádný zápis do zdroje)
    - Standardizovaný výstup (viz kontrakty níže)
    - Transparentní oznámení chybějících dat (KeyError / prázdný DataFrame)

    Výstupní kontrakt load_prices():
        dict[conid -> pd.DataFrame]
        DataFrame:
            index: pd.DatetimeIndex (name="date", UTC-naive, pouze obchodní dny)
            columns: open, high, low, close, volume
            dtype close: float64
            dtype volume: int64 nebo float64
            seřazeno: ASC podle date
            filtrováno: pouze řádky kde date >= date_from AND date <= date_to

    Výstupní kontrakt load_universe():
        pd.DataFrame
            index: conid (int)
            columns: ticker, exchange, currency, instrument_type,
                     sector, industry, subcategory, active_flag
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifikátor zdroje: 'mdsm' | 'sharadar' | ..."""
        ...

    @abstractmethod
    def load_prices(
        self,
        conids: list[int],
        date_from: date,
        date_to: date,
    ) -> dict[int, pd.DataFrame]:
        """
        Načte EOD ceny pro seznam conid v zadaném datovém rozsahu.

        Args:
            conids:    seznam IBKR conid
            date_from: první den rozsahu (včetně)
            date_to:   poslední den rozsahu (včetně)

        Returns:
            dict[conid, DataFrame] — pouze conidy s dostupnými daty.
            Chybějící conid v dict = data nejsou dostupná (ne výjimka).

        Raises:
            DataProviderError: systémová chyba (špatná cesta, korupce dat, ...)
        """
        ...

    @abstractmethod
    def load_universe(self, universe_name: str = "sp500") -> pd.DataFrame:
        """
        Načte universe instrumentů.

        Args:
            universe_name: identifikátor universe ('sp500', 'module', ...)

        Returns:
            DataFrame s indexem conid a standardními sloupci.

        Raises:
            DataProviderError: universe neexistuje nebo není čitelné.
        """
        ...

    @abstractmethod
    def available_conids(self) -> list[int]:
        """
        Vrátí seznam conid pro které existují data v cache.

        Používá se pro validaci experimentů a diagnostiku.
        """
        ...
