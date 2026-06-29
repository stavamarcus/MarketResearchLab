"""
ConfigManager — načítání a validace YAML konfigurace MRL.
"""

from pathlib import Path

import yaml


class ConfigManager:
    """
    Načítá settings.yaml a data_paths.yaml.

    Příklad použití:
        cfg = ConfigManager(config_dir=Path("config"))
        paths = cfg.data_paths()
        settings = cfg.settings()
    """

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir

    def settings(self) -> dict:
        return self._load("settings.yaml")

    def data_paths(self) -> dict:
        return self._load("data_paths.yaml")

    def _load(self, filename: str) -> dict:
        path = self.config_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Konfigurační soubor nenalezen: {path}")
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
