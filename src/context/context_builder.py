"""
ContextBuilder — sestaví ExperimentContext pro každý běh experimentu.

Zodpovědnost:
    1. Načte universe a sestaví AssetUniverse
    2. Načte ceny pro aktivní conidy v daném rozsahu
    3. Načte feature (pokud experiment vyžaduje)
    4. Sestaví ExperimentContext s injektovanými providery
    5. Doplní source_hashes pro reprodukovatelnost

Volá ho ExperimentRunner — experiment ContextBuilder nikdy nevolá přímo.

Dependency Injection:
    ContextBuilder dostane providery z ProviderFactory.
    Experiment dostane context — nezná ani ContextBuilder, ani providery.
"""

from __future__ import annotations

from datetime import date

from src.context.experiment_context import ExperimentContext
from src.core.experiment_config import ExperimentConfig
from src.core.experiment_definition import ExperimentDefinition
from src.domain.feature import FeatureSet
from src.infrastructure.logging_manager import get_logger
from src.providers.providers_abc import (
    MetadataProvider,
    PriceProvider,
    SignalProvider,
    UniverseProvider,
)

logger = get_logger(__name__)


class ContextBuilder:
    """
    Sestaví ExperimentContext z providerů a konfigurace.

    Příklad použití (interní — volá ExperimentRunner):
        builder = ContextBuilder(
            price_provider=mdsm_price,
            universe_provider=mdsm_universe,
            signal_provider=mdsm_signal,
            metadata_provider=mdsm_metadata,
        )
        context = builder.build(run_id, definition, config)
    """

    def __init__(
        self,
        price_provider: PriceProvider,
        universe_provider: UniverseProvider,
        signal_provider: SignalProvider | None = None,
        metadata_provider: MetadataProvider | None = None,
    ) -> None:
        self._price_provider = price_provider
        self._universe_provider = universe_provider
        self._signal_provider = signal_provider
        self._metadata_provider = metadata_provider

    def build(
        self,
        run_id: str,
        definition: ExperimentDefinition,
        config: ExperimentConfig,
    ) -> ExperimentContext:
        """
        Sestaví a vrátí ExperimentContext pro daný běh.

        Pořadí sestavení:
            1. Universe → AssetUniverse
            2. Prices → dict[conid, DataFrame]
            3. Features → FeatureSet (pokud experiment vyžaduje)
            4. Source hashes
            5. Sestavení ExperimentContext
        """
        logger.info(
            f"[{run_id}] ContextBuilder: sestavuji context "
            f"| universe={config.universe} | {config.date_from} → {config.date_to}"
        )

        # 1. Universe + Asset objekty
        universe_df = self._universe_provider.load_universe(config.universe)
        asset_universe = self._universe_provider.load_assets(config.universe)

        active_conids = [
            a.conid for a in asset_universe.active()
        ]
        logger.info(
            f"[{run_id}] universe: {len(asset_universe)} instrumentů, "
            f"{len(active_conids)} aktivních"
        )

        # 2. Ceny — pouze pro aktivní conidy
        prices = {}
        if "prices" in definition.required_data:
            prices = self._price_provider.load_prices(
                conids=active_conids,
                date_from=config.date_from,
                date_to=config.date_to,
            )
            logger.info(
                f"[{run_id}] prices: {len(prices)}/{len(active_conids)} conid načteno"
            )

        # 3. Features — pokud experiment deklaruje feature v required_data
        features = FeatureSet.empty()
        feature_keys = [
            k for k in definition.required_data
            if k.startswith("feature:")
        ]
        if feature_keys and self._signal_provider is not None:
            feature_names = [k.removeprefix("feature:") for k in feature_keys]
            # Sestavení ticker→conid mappingu z universe_df pro load_features()
            ticker_to_conid = dict(
                zip(universe_df["ticker"], universe_df.index.astype(int))
            ) if "ticker" in universe_df.columns else {}
            try:
                features = self._signal_provider.load_features(
                    feature_names=feature_names,
                    conids=active_conids,
                    date_from=config.date_from,
                    date_to=config.date_to,
                    ticker_to_conid=ticker_to_conid,
                )
                logger.info(f"[{run_id}] features: {len(features)} načteno")
            except NotImplementedError:
                logger.warning(
                    f"[{run_id}] load_features není implementován — features prázdné."
                )

        # 3b. Benchmark prices — pro alpha výpočet
        # Experiment deklaruje: "benchmark:SPY" v required_data
        benchmark_keys = [
            k for k in definition.required_data
            if k.startswith("benchmark:")
        ]
        for key in benchmark_keys:
            ticker = key.removeprefix("benchmark:")
            # Načti conid z universe nebo pevný mapping
            BENCHMARK_CONIDS = {"SPY": 756733}
            conid = BENCHMARK_CONIDS.get(ticker)
            if conid and conid not in prices:
                bmark = self._price_provider.load_prices(
                    conids=[conid],
                    date_from=config.date_from,
                    date_to=config.date_to,
                )
                prices.update(bmark)
                logger.info(f"[{run_id}] benchmark '{ticker}' (conid={conid}): načteno")

        # 4. Contextual signals — IRC, breadth, market-level (non-asset)
        # Experiment deklaruje: "signal:IRC", "signal:breadth" v required_data
        signals: dict = {}
        signal_keys = [
            k for k in definition.required_data
            if k.startswith("signal:")
        ]
        if signal_keys and self._signal_provider is not None:
            for key in signal_keys:
                module = key.removeprefix("signal:")
                try:
                    df = self._signal_provider.load_signals(
                        module=module,
                        date_from=config.date_from,
                        date_to=config.date_to,
                    )
                    signals[module] = df
                    logger.info(f"[{run_id}] signal '{module}': {len(df)} řádků načteno")
                except (NotImplementedError, Exception) as exc:
                    logger.warning(f"[{run_id}] signal '{module}' nelze načíst: {exc}")

        # 5. Source hashes
        source_hashes = self._collect_hashes(active_conids, prices)

        # 5. Context metadata
        context_metadata = {}
        if self._metadata_provider is not None:
            context_metadata = self._metadata_provider.load_source_metadata()

        context = ExperimentContext(
            run_id=run_id,
            config=config,
            assets=asset_universe,
            prices=prices,
            features=features,
            universe=universe_df,
            price_provider=self._price_provider,
            universe_provider=self._universe_provider,
            signal_provider=self._signal_provider,
            metadata_provider=self._metadata_provider,
            signals=signals,
            source_hashes=source_hashes,
            metadata=context_metadata,
        )

        logger.info(f"[{run_id}] context sestaven: {context.summary()}")
        return context

    def _collect_hashes(
        self,
        conids: list[int],
        prices: dict,
    ) -> dict[str, str]:
        """
        Sbírá SHA-256 hashe zdrojových souborů pro reprodukovatelnost.
        Volá PriceProvider.file_hash() — definováno v ABC, výchozí hodnota None.
        """
        hashes = {}
        for conid in prices:
            h = self._price_provider.file_hash(conid)
            if h:
                hashes[f"price:{conid}"] = h
        return hashes
