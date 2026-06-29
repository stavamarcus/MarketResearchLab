"""
SignalLoader — načítání archivních výstupů produkčních modulů (MLE, IMS, IRC, ...).

Pravidlo:
    MRL nikdy nevolá produkční moduly přímo.
    Čte pouze jejich archivní výstupy (Parquet / CSV soubory).
    Cesty přicházejí z config/data_paths.yaml.

Skeleton — rozhraní definováno, implementace jednotlivých modulů
vznikne při prvním experimentu, který signály potřebuje.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)

SUPPORTED_MODULES = ["MLE", "IMS", "IRC", "breadth", "rank_calendar"]


class SignalLoaderError(Exception):
    """Chyba při načítání signálů."""


class SignalLoader:
    """
    Načítá archivní výstupy produkčních modulů pro experimenty.

    signals_root: kořenový adresář archivů signálů (z data_paths.yaml)

    Každý modul má vlastní loader metodu:
        _load_MLE()         — MarketLeadershipEngine výstupy
        _load_IMS()         — InstitutionalMomentumScanner výstupy
        _load_IRC()         — IndustryRankCalendar výstupy
        _load_breadth()     — MarketBreadth výstupy
        _load_rank_calendar() — SP500RankCalendar výstupy

    Všechny jsou skeleton — implementovat při první potřebě.
    """

    def __init__(self, signals_root: Path) -> None:
        self._signals_root = Path(signals_root)

    def load(
        self,
        module: str,
        date_from: date,
        date_to: date,
    ) -> pd.DataFrame:
        """
        Načte archivní výstupy daného produkčního modulu.

        Args:
            module:    název modulu — jeden z SUPPORTED_MODULES
            date_from: první den rozsahu (včetně)
            date_to:   poslední den rozsahu (včetně)

        Returns:
            pd.DataFrame s výstupy modulu pro zadaný rozsah.

        Raises:
            SignalLoaderError: modul není podporován nebo data nelze načíst.
        """
        if module not in SUPPORTED_MODULES:
            raise SignalLoaderError(
                f"Nepodporovaný modul: '{module}'. "
                f"Podporované: {SUPPORTED_MODULES}"
            )

        loader_method = getattr(self, f"_load_{module}", None)
        if loader_method is None:
            raise SignalLoaderError(
                f"Loader pro modul '{module}' není implementován."
            )

        logger.info(
            f"SignalLoader: načítám '{module}' | {date_from} → {date_to}"
        )
        return loader_method(date_from, date_to)

    # ------------------------------------------------------------------
    # Skeleton loadery — implementovat při první potřebě
    # ------------------------------------------------------------------

    def _load_MLE(self, date_from: date, date_to: date) -> pd.DataFrame:
        """
        Načte archivní výstupy MarketLeadershipEngine.
        TODO: implementovat při prvním MLE experimentu.
        Očekávaný výstup: DataFrame s rank_Xd sloupci indexovaný date × conid.
        """
        raise NotImplementedError(
            "SignalLoader._load_MLE() není implementován. "
            "Implementujte při prvním experimentu vyžadujícím MLE signály."
        )

    def _load_IMS(self, date_from: date, date_to: date) -> pd.DataFrame:
        """
        Načte archivní výstupy InstitutionalMomentumScanner.
        TODO: implementovat při prvním IMS experimentu.
        """
        raise NotImplementedError(
            "SignalLoader._load_IMS() není implementován."
        )

    def _load_IRC(self, date_from: date, date_to: date) -> pd.DataFrame:
        """
        Načte archivní výstupy IndustryRankCalendar.
        TODO: implementovat při prvním IRC experimentu.
        """
        raise NotImplementedError(
            "SignalLoader._load_IRC() není implementován."
        )

    def _load_breadth(self, date_from: date, date_to: date) -> pd.DataFrame:
        raise NotImplementedError("SignalLoader._load_breadth() není implementován.")

    def _load_rank_calendar(self, date_from: date, date_to: date) -> pd.DataFrame:
        raise NotImplementedError("SignalLoader._load_rank_calendar() není implementován.")
