"""
MetricsEngine — modulární výpočet metrik pro experimenty.

Filozofie:
- Metriky jsou explicitně vyžádány experimentem, ne automaticky aplikovány.
- Žádná metrika není "default". Experiment deklaruje, co chce měřit.
- Statistické testy (bootstrap, permutation test, ...) jsou volitelné
  add-ony, ne součást základu.

Aktuální stav: skeleton s rozhraním.
Konkrétní implementace metrik přibude postupně s experimenty.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class MetricResult:
    """Výsledek jedné metriky."""
    name: str
    value: float | int | str | None
    unit: str = ""
    description: str = ""
    n: int | None = None     # počet pozorování, pokud relevantní


class MetricsEngine:
    """
    Výpočet metrik nad výsledky experimentu.

    Použití:
        engine = MetricsEngine()
        alpha = engine.compute("alpha", returns=returns, benchmark=spy_returns)

    Každá metrika je samostatná metoda s explicitními vstupními parametry.
    Bez magie — žádné auto-discovery, žádné globální registry metrik.
    """

    def compute(self, metric_name: str, **kwargs) -> MetricResult:
        """
        Dispatche výpočet metriky podle názvu.

        Raises NotImplementedError pro dosud neimplementované metriky.
        """
        method = getattr(self, f"_metric_{metric_name}", None)
        if method is None:
            raise NotImplementedError(
                f"Metrika '{metric_name}' není implementována. "
                f"Přidejte metodu _metric_{metric_name}() do MetricsEngine."
            )
        return method(**kwargs)

    # ------------------------------------------------------------------
    # Základní metriky — implementovat postupně
    # ------------------------------------------------------------------

    def _metric_alpha(self, returns, benchmark_returns) -> MetricResult:
        """
        Průměrný excess return vůči benchmarku.
        Implementovat při prvním experimentu měřícím alpha.
        """
        raise NotImplementedError("_metric_alpha není implementována.")

    def _metric_win_rate(self, returns) -> MetricResult:
        """
        Podíl pozitivních výnosů.
        Implementovat při prvním experimentu.
        """
        raise NotImplementedError("_metric_win_rate není implementována.")

    def _metric_sample_size(self, returns) -> MetricResult:
        """Počet pozorování."""
        raise NotImplementedError("_metric_sample_size není implementována.")

    # Poznámka k statistickým testům:
    # Statistické testy (bootstrap CI, permutation test, ...)
    # budou přidány jako samostatné metody až při konkrétní potřebě.
    # Nejsou součástí skeleton infrastruktury.
