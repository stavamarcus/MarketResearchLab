"""
BaseExperiment — abstraktní třída pro všechny MRL experimenty.

Phase 2 změna:
    run(data, config)    →    run(context)

    ExperimentContext obsahuje vše:
        context.config      — parametry běhu
        context.assets      — AssetUniverse
        context.prices      — dict[conid, DataFrame]
        context.features    — FeatureSet
        context.universe    — raw DataFrame
        context.providers   — lazy-load providery (pokročilé případy)

Experiment implementuje:
    define()          — statický popis, hypotéza, required_data
    validate()        — jsou data v contextu použitelná?
    run(context)      — výzkumná logika

Framework zajišťuje:
    sestavení ExperimentContext (ContextBuilder)
    orchestrace (ExperimentRunner)
    archivaci (ArchiveManager)
    registry (JSONL)
    report (ReportBuilder)

Experiment NESMÍ:
    volat MDSMPriceProvider() přímo
    číst Parquet soubory přímo
    zapisovat soubory
    mít side effects mimo vrácenou hodnotu run()
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.context.experiment_context import ExperimentContext
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult


class BaseExperiment(ABC):
    """
    Abstraktní třída pro všechny MRL experimenty.

    Konvence pojmenování podtříd:
        {Název}_v{verze}
        Příklad: IrcEdgeValidation_v1

    ExperimentDefinition.required_data konvence:
        "prices"            — načíst EOD ceny pro aktivní conidy
        "feature:MLE_Rank"  — načíst feature MLE_Rank
        "feature:IRC_Rank"  — načíst feature IRC_Rank
        (bez prefixu)       — speciální požadavek, ContextBuilder ho ignoruje
    """

    @abstractmethod
    def define(self) -> ExperimentDefinition:
        """
        Statický popis experimentu.

        Volá se před sestavením contextu — musí být deterministický
        a nesmí záviset na runtime stavu.
        """
        ...

    @abstractmethod
    def validate(self, context: ExperimentContext) -> ValidationResult:
        """
        Ověří, zda ExperimentContext obsahuje použitelná data.

        Framework experiment nespustí, pokud ValidationResult.is_valid() == False.

        Typické kontroly:
            len(context.prices) >= min_instruments
            context.close_matrix().shape[0] >= min_trading_days
            context.has_feature("MLE_Rank")
        """
        ...

    @abstractmethod
    def run(self, context: ExperimentContext) -> ExperimentResult:
        """
        Výzkumná logika experimentu.

        Musí být čistá funkce:
            stejný context → stejné výstupy
            žádné side effects
            žádné soubory, žádná síť, žádné externí volání

        Veškeré výstupy vrátit v ExperimentResult.
        Framework zajistí archivaci a report.
        """
        ...
