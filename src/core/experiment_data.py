"""
ExperimentData — vstupní data připravená frameworkem pro experiment.

DataLoader sestaví tento objekt z Parquet cache.
Experiment dostane ExperimentData jako read-only vstup.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DataSource:
    """Metadata jednoho datového zdroje načteného pro experiment."""

    key: str                    # identifikátor: "prices", "irc_signals", ...
    path: Path                  # absolutní cesta ke zdrojovému souboru
    file_hash: str              # SHA-256 souboru — základ reprodukovatelnosti
    loaded_at: datetime
    row_count: int


@dataclass
class ExperimentData:
    """
    Kontejner vstupních dat pro jeden experiment run.

    frames: dict[str, Any] — typicky dict[str, pd.DataFrame]
    sources: metadata o každém načteném souboru (hash, cesta, čas)

    Experiment smí pouze číst z frames.
    Zápis do produkčního cache je zakázán.
    """

    frames: dict[str, Any] = field(default_factory=dict)
    sources: list[DataSource] = field(default_factory=list)

    def get(self, key: str) -> Any:
        if key not in self.frames:
            raise KeyError(
                f"ExperimentData neobsahuje klíč '{key}'. "
                f"Dostupné klíče: {list(self.frames.keys())}"
            )
        return self.frames[key]

    def source_hashes(self) -> dict[str, str]:
        """Vrací {key: file_hash} pro uložení do metadata."""
        return {s.key: s.file_hash for s in self.sources}
