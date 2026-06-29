"""
Provider ABC — kontrakty pro všechny datové zdroje MRL.

Čtyři specializované ABC, každý s jednou zodpovědností:

    PriceProvider    — EOD cenová data (OHLCV)
    UniverseProvider — seznam instrumentů, Asset objekty
    SignalProvider   — výstupy produkčních modulů, Feature objekty
    MetadataProvider — popisná metadata zdrojů a instrumentů

Aktuální implementace: MDSM-Lite (src/providers/mdsm_providers.py)
Budoucí implementace:  SharadarProvider, PolygonProvider, ... (stejný interface)

Pravidla:
    Experiment nikdy nevolá provider přímo.
    Experiment dostane data přes ExperimentContext.
    Provider nezná experimenty ani governance vrstvu.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd

from src.domain.asset import Asset, AssetUniverse
from src.domain.feature import Feature, FeatureSet


class ProviderError(Exception):
    """Základní výjimka pro chyby providerů."""


# ---------------------------------------------------------------------------
# PriceProvider
# ---------------------------------------------------------------------------

class PriceProvider(ABC):
    """
    Kontrakt pro načítání EOD cenových dat.

    Výstupní kontrakt load_prices():
        dict[conid -> pd.DataFrame]
        DataFrame:
            index:   pd.DatetimeIndex (name="date", UTC-naive, pouze obchodní dny)
            columns: open, high, low, close, volume
            dtype close:  float64
            dtype volume: int64 nebo float64
            seřazeno ASC podle date
            filtrováno: date_from <= date <= date_to
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
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
        Načte EOD ceny pro seznam conid v zadaném rozsahu.

        Chybějící conid v output dict = data nejsou dostupná (ne výjimka).
        Raises ProviderError pouze při systémové chybě (špatná cesta, korupce).
        """
        ...

    @abstractmethod
    def get_available_price_range(self, conid: int) -> tuple[date, date] | None:
        """
        Vrátí (první_datum, poslední_datum) dostupných dat pro conid.
        Vrátí None pokud conid nemá data.
        """
        ...

    @abstractmethod
    def available_conids(self) -> list[int]:
        """Vrátí seznam conid pro které existují data."""
        ...

    def file_hash(self, conid: int) -> str | None:
        """
        SHA-256 hash zdrojového souboru pro daný conid.

        Používá ContextBuilder pro source_hashes (reprodukovatelnost).
        Výchozí implementace vrací None — provider nemusí hashování podporovat.
        Implementace přepisují tuto metodu pokud je hash dostupný.
        """
        return None

    def file_hash(self, conid: int) -> str | None:
        """
        SHA-256 hash zdrojového souboru pro daný conid.

        Používá ContextBuilder pro source_hashes v metadata (reprodukovatelnost).
        Implementace volitelná — výchozí vrací None.
        Zdroje bez souborové struktury (API, databáze) vrátí None.
        """
        return None


# ---------------------------------------------------------------------------
# UniverseProvider
# ---------------------------------------------------------------------------

class UniverseProvider(ABC):
    """
    Kontrakt pro načítání universe instrumentů a Asset objektů.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    def load_universe(self, universe_name: str = "sp500") -> pd.DataFrame:
        """
        Načte universe jako DataFrame.

        Returns:
            pd.DataFrame(index=conid, columns=[ticker, exchange, ..., active_flag])
        """
        ...

    @abstractmethod
    def load_assets(self, universe_name: str = "sp500") -> AssetUniverse:
        """
        Načte universe jako kolekci Asset objektů.

        Returns:
            AssetUniverse s plně sestavenými Asset objekty.
        """
        ...

    @abstractmethod
    def get_asset(self, conid: int, universe_name: str = "sp500") -> Asset | None:
        """Vrátí Asset pro konkrétní conid, nebo None."""
        ...


# ---------------------------------------------------------------------------
# SignalProvider
# ---------------------------------------------------------------------------

class SignalProvider(ABC):
    """
    Kontrakt pro načítání výstupů produkčních modulů a Feature objektů.

    Produkční moduly (MLE, IMS, IRC, Breadth, ...) exportují výsledky
    do archivních souborů. SignalProvider čte tyto archivy.

    MRL nikdy nevolá produkční moduly přímo.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    def load_signals(
        self,
        module: str,
        date_from: date,
        date_to: date,
    ) -> pd.DataFrame:
        """
        Načte surové výstupy produkčního modulu jako DataFrame.

        Args:
            module:    název modulu ("MLE", "IMS", "IRC", "breadth", ...)
            date_from: první den rozsahu (včetně)
            date_to:   poslední den rozsahu (včetně)

        Returns:
            pd.DataFrame — struktura závisí na modulu.
        """
        ...

    @abstractmethod
    def load_features(
        self,
        feature_names: list[str],
        conids: list[int],
        date_from: date,
        date_to: date,
    ) -> FeatureSet:
        """
        Načte konkrétní feature jako FeatureSet.

        Přeloží signály modulů na standardní Feature objekty.

        Args:
            feature_names: seznam feature názvů ("MLE_Rank", "Industry_Rank", ...)
            conids:        seznam conid
            date_from:     první den (včetně)
            date_to:       poslední den (včetně)

        Returns:
            FeatureSet indexovaný (conid, date, feature_name).
        """
        ...

    @abstractmethod
    def available_modules(self) -> list[str]:
        """Vrátí seznam dostupných modulů (archivy existují)."""
        ...


# ---------------------------------------------------------------------------
# MetadataProvider
# ---------------------------------------------------------------------------

class MetadataProvider(ABC):
    """
    Kontrakt pro načítání popisných metadat zdrojů a instrumentů.

    Metadata = informace O datech, ne data samotná.
    Příklady: datum poslední aktualizace cache, verze modulu, počet řádků, ...
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    def load_asset_metadata(self, conid: int) -> dict:
        """
        Vrátí metadata pro konkrétní instrument.

        Příklad výstupu:
            {
                "conid": 756733,
                "ticker": "SPY",
                "cache_last_updated": "2026-06-26",
                "cache_rows": 2040,
                "timeframe": "D1",
            }
        """
        ...

    @abstractmethod
    def load_source_metadata(self) -> dict:
        """
        Vrátí metadata celého zdroje dat.

        Příklad výstupu:
            {
                "source": "mdsm",
                "prices_dir": "...",
                "total_instruments": 513,
                "last_gdu_run": "2026-06-26",
            }
        """
        ...
