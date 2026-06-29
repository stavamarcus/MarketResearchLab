"""
Feature — doménový objekt pro vypočtenou informaci použitelnou v experimentech.

Filozofie:
    Experiment feature nedopočítává. Pouze ji dostane.
    Feature přichází z produkčních modulů (MLE, IMS, IRC, Breadth, ...)
    nebo je vypočtena FeatureEngine uvnitř frameworku.

    Toto je datový model. Konkrétní výpočty přijdou v Phase 3+.

Příklady budoucích feature:
    MLE_Rank            — rank instrumentu v MLE (1–500)
    MLE_Top50_Flag      — bool: instrument v TOP50 MLE
    Industry_Rank       — rank odvětví v IRC
    Persistence         — kolik dní po sobě v TOP skupině
    Breadth_Regime      — stav breadth (RISK_ON / RISK_OFF / NEUTRAL)
    Volume_Ratio        — objem vůči 20D průměru
    RS_vs_SPY_20d       — relative strength vůči SPY za 20D
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Feature:
    """
    Jedna vypočtená feature pro konkrétní instrument a datum.

    Povinná pole:
        conid:          IBKR conid identifikuje instrument
        date:           datum platnosti feature
        feature_name:   název feature (např. "MLE_Rank", "Industry_Rank")
        value:          hodnota (float, int, bool, str)

    Volitelná pole:
        source_module:  odkud feature pochází ("MLE", "IMS", "IRC", "computed")
        source_version: verze modulu nebo výpočtu ("2.1", "audit_v4")
        metadata:       rozšiřitelný dict pro kontext

    Pravidla:
        Feature je immutable po vytvoření.
        feature_name musí být neprázdný string.
        value může být libovolný skalár — experiment odpovídá za správnou interpretaci.
    """

    conid: int
    date: date
    feature_name: str
    value: Any

    source_module: str = ""
    source_version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.feature_name or not self.feature_name.strip():
            raise ValueError("Feature.feature_name nesmí být prázdný.")

    def __repr__(self) -> str:
        return (
            f"Feature(conid={self.conid}, date={self.date}, "
            f"name={self.feature_name!r}, value={self.value!r})"
        )


class FeatureSet:
    """
    Kolekce Feature objektů pro experiment.

    Poskytuje rychlý lookup podle (conid, date, feature_name).
    Experiment dostane FeatureSet přes ExperimentContext.
    """

    def __init__(self, features: list[Feature]) -> None:
        # Index: (conid, date, feature_name) -> Feature
        self._index: dict[tuple[int, date, str], Feature] = {}
        for f in features:
            self._index[(f.conid, f.date, f.feature_name)] = f

    def get(self, conid: int, date: date, feature_name: str) -> Feature | None:
        """Vrátí Feature pro daný (conid, date, feature_name), nebo None."""
        return self._index.get((conid, date, feature_name))

    def get_value(
        self,
        conid: int,
        date: date,
        feature_name: str,
        default: Any = None,
    ) -> Any:
        """Vrátí hodnotu feature nebo default."""
        f = self.get(conid, date, feature_name)
        return f.value if f is not None else default

    def all_for_conid(self, conid: int) -> list[Feature]:
        """Vrátí všechny feature pro daný conid."""
        return [f for f in self._index.values() if f.conid == conid]

    def all_for_date(self, date: date) -> list[Feature]:
        """Vrátí všechny feature pro daný datum."""
        return [f for f in self._index.values() if f.date == date]

    def all_for_name(self, feature_name: str) -> list[Feature]:
        """Vrátí všechny feature daného jména (napříč conid a daty)."""
        return [f for f in self._index.values() if f.feature_name == feature_name]

    def feature_names(self) -> set[str]:
        """Vrátí seznam unikátních názvů feature v setu."""
        return {f.feature_name for f in self._index.values()}

    def is_empty(self) -> bool:
        return len(self._index) == 0

    def __len__(self) -> int:
        return len(self._index)

    def __repr__(self) -> str:
        names = self.feature_names()
        return f"FeatureSet(n={len(self)}, features={sorted(names)})"

    @classmethod
    def empty(cls) -> "FeatureSet":
        """Prázdný FeatureSet — pro experimenty které feature nepotřebují."""
        return cls([])
