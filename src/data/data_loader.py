"""
DataLoader — načítání dat z Parquet cache pro experimenty.

Skeleton: rozhraní je definováno, konkrétní implementace vznikne
při prvním experimentu, který data skutečně potřebuje.

Pravidla:
- MRL čte z AccessLayer / Parquet cache v READ-ONLY módu.
- DataLoader nikdy nepíše do produkčního cache.
- Každý načtený soubor je hashován pro metadata reprodukovatelnosti.
"""

import hashlib
from datetime import date
from pathlib import Path

from src.core.experiment_config import ExperimentConfig
from src.core.experiment_data import DataSource, ExperimentData
from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)


class DataLoader:
    """
    Načítá data z Parquet cache pro zadané required_data klíče a datum range.

    cache_root: kořen Parquet cache (z data_paths.yaml)

    Skeleton — metoda load() vrací prázdný ExperimentData dokud
    není implementována konkrétní logika načítání.
    """

    def __init__(self, cache_root: Path):
        self.cache_root = cache_root

    def load(
        self,
        required: list[str],
        config: ExperimentConfig,
    ) -> ExperimentData:
        """
        Načte požadovaná data pro daný experiment config.

        required: seznam klíčů odpovídajících ExperimentDefinition.required_data
                  Příklad: ["prices", "irc_signals"]

        Skeleton: loguje požadavek, vrací prázdný ExperimentData.
        Implementace jednotlivých loaderů přibude při migraci experimentů.
        """
        logger.info(
            f"DataLoader.load() — required={required} | "
            f"{config.date_from} → {config.date_to} | "
            f"universe={config.universe}"
        )

        frames = {}
        sources = []

        for key in required:
            loader_method = getattr(self, f"_load_{key}", None)
            if loader_method is None:
                logger.warning(
                    f"DataLoader: loader pro klíč '{key}' není implementován. "
                    f"Klíč bude v ExperimentData chybět."
                )
                continue
            frame, source = loader_method(config)
            frames[key] = frame
            sources.append(source)

        return ExperimentData(frames=frames, sources=sources)

    # ------------------------------------------------------------------
    # Placeholder loadery — implementovat při první potřebě
    # ------------------------------------------------------------------

    def _load_prices(self, config: ExperimentConfig):
        """
        Načte EOD close prices z Parquet cache.
        TODO: implementovat po napojení na AccessLayer.
        """
        raise NotImplementedError(
            "_load_prices není implementován. "
            "Implementujte při prvním experimentu vyžadujícím 'prices'."
        )

    @staticmethod
    def _hash_file(path: Path) -> str:
        """SHA-256 hash souboru pro metadata reprodukovatelnosti."""
        sha = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()
