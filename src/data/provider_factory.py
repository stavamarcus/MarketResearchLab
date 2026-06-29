"""
ProviderFactory — sestaví DataProvider instanci z konfigurace.

Čte config/data_paths.yaml a vrátí správnou implementaci.
ExperimentRunner volá ProviderFactory při sestavení DataLoaderu.

Přidání nového providera:
    1. Implementuj DataProvider interface
    2. Přidej case do _build()
    3. Přidej sekci do data_paths.yaml
    Žádné další změny frameworku nejsou potřeba.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from src.data.data_provider import DataProvider
from src.data.mdsm_data_provider import MDSMDataProvider
from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)


class ProviderFactoryError(Exception):
    """Chyba při sestavení DataProvider."""


class ProviderFactory:
    """
    Sestaví DataProvider podle sekce active_provider v data_paths.yaml.

    Příklad použití:
        factory = ProviderFactory(config_dir=Path("config"))
        provider = factory.build()
        # provider je MDSMDataProvider nebo jiná implementace
    """

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = Path(config_dir)

    def build(self) -> DataProvider:
        """
        Načte data_paths.yaml a vrátí příslušnou DataProvider instanci.

        Raises:
            ProviderFactoryError: neznámý provider nebo chybná konfigurace.
        """
        config = self._load_config()
        active = config.get("active_provider", "mdsm")
        logger.info(f"ProviderFactory: sestavuji '{active}' DataProvider")
        return self._build(active, config)

    def _build(self, provider_name: str, config: dict) -> DataProvider:
        if provider_name == "mdsm":
            return self._build_mdsm(config)
        raise ProviderFactoryError(
            f"Neznámý provider: '{provider_name}'. "
            f"Dostupné: ['mdsm']"
        )

    def _build_mdsm(self, config: dict) -> MDSMDataProvider:
        mdsm_cfg = config.get("mdsm")
        if not mdsm_cfg:
            raise ProviderFactoryError(
                "Sekce 'mdsm' chybí v data_paths.yaml."
            )
        prices_dir = Path(mdsm_cfg.get("prices_dir", ""))
        universe_dir = Path(mdsm_cfg.get("universe_dir", ""))

        if not prices_dir.parts:
            raise ProviderFactoryError("mdsm.prices_dir nesmí být prázdný.")
        if not universe_dir.parts:
            raise ProviderFactoryError("mdsm.universe_dir nesmí být prázdný.")

        return MDSMDataProvider(
            prices_dir=prices_dir,
            universe_dir=universe_dir,
        )

    def _load_config(self) -> dict:
        path = self._config_dir / "data_paths.yaml"
        if not path.exists():
            raise ProviderFactoryError(
                f"config/data_paths.yaml nenalezen: {path}"
            )
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
