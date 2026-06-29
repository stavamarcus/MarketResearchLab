"""
ExperimentResult — výstup jednoho běhu experimentu.
ValidationResult — výsledek experiment.validate(context).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ValidationStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    FAILED = "failed"


@dataclass
class ValidationResult:
    """
    Výsledek experiment.validate(context).

    Framework odmítne spustit experiment, pokud status == FAILED.
    WARNING spuštění nevyblokuje, ale uloží se do metadata.
    """

    status: ValidationStatus
    messages: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(status=ValidationStatus.OK)

    @classmethod
    def failed(cls, reason: str) -> "ValidationResult":
        return cls(status=ValidationStatus.FAILED, messages=[reason])

    @classmethod
    def warning(cls, message: str) -> "ValidationResult":
        return cls(status=ValidationStatus.WARNING, messages=[message])

    def is_valid(self) -> bool:
        return self.status != ValidationStatus.FAILED


@dataclass
class ExperimentResult:
    """
    Výstup jednoho běhu experimentu.

    metrics:   číselné metriky (alpha, win_rate, N, ...)
    tables:    pojmenované tabulky (pd.DataFrame nebo dict)
    artifacts: libovolné výstupy (grafy, soubory, ...)
    summary:   volný text — interpretace výsledku autorem experimentu

    run_id a completed_at nastavuje ExperimentRunner, ne experiment.
    """

    metrics: dict[str, float | int | str] = field(default_factory=dict)
    tables: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    # Nastavuje framework:
    run_id: str = ""
    completed_at: datetime | None = None
    result_hash: str = ""            # SHA-256 metrics + tables — pro detekci změn
