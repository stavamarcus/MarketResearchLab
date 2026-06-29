"""
ExperimentDefinition — popisuje, co experiment je.

Neobsahuje výsledky ani runtime data.
Je verzovaný a neměnný po registraci.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperimentDefinition:
    """
    Statický popis experimentu.

    Verze sleduje změny výzkumné logiky.
    Změna logiky = nová verze; stará definice zůstává v registry.
    """

    name: str
    version: str
    hypothesis: str
    description: str
    required_data: list[str]         # např. ["prices", "irc_signals"]
    parameters: dict[str, Any]       # default parametry, přepisovatelné v ExperimentConfig
    tags: list[str] = field(default_factory=list)   # volné štítky: "edge", "backtest", ...
    author: str = ""

    def __post_init__(self):
        if not self.name:
            raise ValueError("ExperimentDefinition.name nesmí být prázdný.")
        if not self.version:
            raise ValueError("ExperimentDefinition.version nesmí být prázdný.")
        if not self.hypothesis:
            raise ValueError("ExperimentDefinition.hypothesis nesmí být prázdný.")
