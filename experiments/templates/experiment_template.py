"""
Experiment Template — Phase 2 šablona.

Změna oproti Phase 1:
    run(data, config)  →  run(context)
    validate_inputs()  →  validate(context)

    context obsahuje vše — prices, assets, features, config.
    Experiment si nic sám nevytváří.

Postup pro nový experiment:
    1. Zkopíruj do experiments/{kategorie}/
    2. Přejmenuj třídu: {Název}_v{verze}
    3. Implementuj define(), validate(), run()
    4. Nikdy nevolej providery přímo — vše přes context

Dostupná data v context:
    context.config.date_from / date_to / parameters
    context.assets.active()                     → list[Asset]
    context.assets.get(conid)                   → Asset | None
    context.prices[conid]["close"]              → pd.Series
    context.close_matrix()                      → pd.DataFrame (date × conid)
    context.features.get_value(conid, date, name) → value
    context.has_prices(conid)                   → bool
"""

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult


class ExperimentTemplate(BaseExperiment):
    """
    Šablona experimentu — přejmenuj a implementuj.

    Pravidla:
        run() je čistá funkce — žádné side effects.
        Experiment nevolá providery přímo.
        Experiment nezapisuje soubory — to zajišťuje ArchiveManager.
    """

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="ExperimentTemplate",
            version="0.1.0",
            hypothesis=(
                "Popište zde hypotézu. Co testujete a proč očekáváte daný výsledek."
            ),
            description="Stručný popis experimentu.",
            required_data=[
                "prices",
                # "feature:MLE_Rank",   # odkomentuj pokud potřebuješ MLE_Rank
                # "feature:IRC_Rank",   # odkomentuj pokud potřebuješ IRC_Rank
            ],
            parameters={
                "lookback_days": 20,
                "min_instruments": 50,
            },
            tags=["template"],
            author="",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        """Ověří, zda context obsahuje použitelná data."""
        min_instruments = context.config.parameters.get(
            "min_instruments", self.define().parameters["min_instruments"]
        )

        if len(context.prices) < min_instruments:
            return ValidationResult.failed(
                f"Příliš málo instrumentů s cenami: "
                f"{len(context.prices)} < {min_instruments}"
            )

        close = context.close_matrix()
        lookback = context.config.parameters.get("lookback_days", 20)
        if close.shape[0] < lookback:
            return ValidationResult.failed(
                f"Příliš málo obchodních dní: {close.shape[0]} < {lookback}"
            )

        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        """
        Výzkumná logika experimentu.

        Přístup k datům:
            close = context.close_matrix()
            asset = context.assets.get(conid)
            rank  = context.features.get_value(conid, date, "MLE_Rank")
        """
        close = context.close_matrix()
        lookback = context.config.parameters.get("lookback_days", 20)

        # --- Výpočetní logika ---
        # TODO: implementovat

        return ExperimentResult(
            metrics={
                "n_instruments": len(context.prices),
                "n_trading_days": close.shape[0],
                "lookback_days": lookback,
                "universe": context.config.universe,
                # přidat vlastní metriky
            },
            tables={
                # "results": pd.DataFrame(...)
            },
            artifacts={},
            summary=(
                "TODO: doplň interpretaci výsledků. "
                "Potvrzuje nebo vyvrací hypotézu?"
            ),
        )
