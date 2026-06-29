"""
ExperimentConfig — konfigurace konkrétního spuštění experimentu.

Oddělena od ExperimentDefinition záměrně:
- Definition popisuje, CO experiment je.
- Config říká, JAK konkrétní běh poběží.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class ExperimentConfig:
    """
    Konfigurace jednoho běhu experimentu.

    date_range definuje rozsah historických dat.
    parameters přepisují nebo rozšiřují defaults z ExperimentDefinition.
    random_seed musí být explicitně nastaven pro reprodukovatelnost
    všude, kde je náhoda relevantní.
    """

    date_from: date
    date_to: date
    parameters: dict[str, Any] = field(default_factory=dict)
    universe: str = "sp500"           # identifikátor vesmíru: "sp500", "custom", ...
    random_seed: int | None = None
    notes: str = ""

    def __post_init__(self):
        if self.date_from >= self.date_to:
            raise ValueError(
                f"date_from ({self.date_from}) musí být před date_to ({self.date_to})."
            )
