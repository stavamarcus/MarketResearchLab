"""
ExperimentContext — jednotný objekt předávaný každému experimentu.

Filozofie:
    Experiment dostane jeden context objekt.
    Experiment si sám nevytváří providery ani loadery.
    Experiment nevolá MDSMPriceProvider() přímo.
    Vše prochází přes context.

    ExperimentRunner sestaví context před voláním experiment.run().
    Experiment context pouze čte — nikdy nepíše.

Dependency Injection:
    Providery jsou injektovány do contextu Runnerem.
    Experiment nezná konkrétní implementaci — pracuje s ABC interfacem.
    To umožňuje v budoucnu vyměnit MDSM za Sharadar bez změny experimentů.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from src.core.experiment_config import ExperimentConfig
from src.domain.asset import Asset, AssetUniverse
from src.domain.feature import FeatureSet
from src.providers.providers_abc import (
    MetadataProvider,
    PriceProvider,
    SignalProvider,
    UniverseProvider,
)


@dataclass
class ExperimentContext:
    """
    Jednotný vstupní objekt pro každý experiment.

    Experiment dostane ExperimentContext přes run(context, config).
    Experiment si sám nic nezačíná — používá pouze to, co context obsahuje.

    Pole:
        run_id:    UUID tohoto běhu (nastavuje Runner)
        config:    parametry běhu (date_from, date_to, parameters, ...)

        assets:    AssetUniverse — kolekce Asset objektů pro tento experiment
        prices:    dict[conid -> DataFrame(OHLCV)] — EOD ceny
        features:  FeatureSet — vypočtené feature (může být prázdný)
        universe:  pd.DataFrame — raw universe (index=conid) pro pokročilé dotazy

        providers: přístup k providerům pro lazy-loading v experimentu
                   (pouze pro pokročilé případy — většina experimentů
                   vystačí s prices, assets, features)

        source_hashes: dict[klíč -> SHA-256] pro reprodukovatelnost
        metadata:      libovolné dodatečné informace o datech

    Datový model — granularita signálů:

        FeatureSet (asset-level only):
            context.features.get_value(conid, date, "MLE_Rank_20d")
            context.features.get_value(conid, date, "IMS_Score")
            Platí pro: MLE, IMS — ticker/conid level signály.

        signals (contextual, non-asset):
            context.signals["IRC"]     → pd.DataFrame (industry-level)
            context.signals["breadth"] → pd.DataFrame (market-level)
            IRC a breadth NEJSOU asset-level — nemají conid.
            Experimenty je dostanou jako raw DataFrame.

    Pravidla přístupu k datům v experimentu:
        ✓  context.prices[conid]["close"]
        ✓  context.assets.get(conid).ticker
        ✓  context.features.get_value(conid, date, "MLE_Rank_20d")
        ✓  context.signals["IRC"]       — industry-level DataFrame
        ✓  context.signals["breadth"]   — market-level DataFrame
        ✓  context.config.parameters["lookback_days"]
        ✗  MDSMPriceProvider(prices_dir=...)   — zakázáno
        ✗  pd.read_parquet(...)                — zakázáno
        ✗  open("C:/...")                      — zakázáno
    """

    run_id: str
    config: ExperimentConfig

    # Doménové objekty
    assets: AssetUniverse = field(default_factory=lambda: AssetUniverse([]))
    prices: dict[int, pd.DataFrame] = field(default_factory=dict)
    features: FeatureSet = field(default_factory=FeatureSet.empty)
    universe: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Lazy-load providery (pro pokročilé experimenty)
    price_provider: PriceProvider | None = None
    universe_provider: UniverseProvider | None = None
    signal_provider: SignalProvider | None = None
    metadata_provider: MetadataProvider | None = None

    # Kontextuální signály (non-asset level)
    # IRC = industry-level DataFrame, breadth = market-level DataFrame
    # Nemají conid — nelze převést na Feature objekty.
    signals: dict[str, pd.DataFrame] = field(default_factory=dict)

    # Fundamentals (MRL-FUND-01): lazy read-only zdroj PIT SF1 snapshotů
    # (MRLSharadarFundamentalSource). None = fundamentals nejsou konfigurovány;
    # existující experimenty se bez něj chovají beze změny.
    # Typ Any: adapter je optional dependency — žádný import zde.
    fundamental_source: Any | None = None

    # Reprodukovatelnost
    source_hashes: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Helper metody pro experimenty
    # ------------------------------------------------------------------

    def get_close(self, conid: int) -> pd.Series | None:
        """
        Vrátí close price series pro daný conid, nebo None.

        Zkratka pro context.prices[conid]["close"].
        """
        df = self.prices.get(conid)
        if df is None or df.empty:
            return None
        return df["close"]

    def get_asset(self, conid: int) -> Asset | None:
        """Vrátí Asset pro daný conid, nebo None."""
        return self.assets.get(conid)

    def close_matrix(self) -> pd.DataFrame:
        """
        Vrátí wide-format DataFrame close cen.

        Returns:
            pd.DataFrame(index=date, columns=conid)
            Chybějící hodnoty = NaN.
        """
        if not self.prices:
            return pd.DataFrame()
        series = {conid: df["close"] for conid, df in self.prices.items()}
        result = pd.DataFrame(series).sort_index()
        result.index.name = "date"
        return result

    def available_conids(self) -> list[int]:
        """Vrátí seznam conid pro které jsou načteny ceny."""
        return list(self.prices.keys())

    def has_prices(self, conid: int) -> bool:
        """Vrátí True pokud jsou pro daný conid načteny ceny."""
        return conid in self.prices and not self.prices[conid].empty

    def has_feature(self, feature_name: str) -> bool:
        """Vrátí True pokud FeatureSet obsahuje danou feature (asset-level only)."""
        return feature_name in self.features.feature_names()

    def has_signal(self, signal_name: str) -> bool:
        """Vrátí True pokud context obsahuje daný kontextuální signál (IRC, breadth, ...)."""
        return signal_name in self.signals and not self.signals[signal_name].empty

    def has_fundamental_source(self) -> bool:
        """Vrátí True pokud je nakonfigurován fundamental source (MRL-FUND-01)."""
        return self.fundamental_source is not None

    def get_signal(self, signal_name: str) -> pd.DataFrame | None:
        """Vrátí kontextuální signál jako DataFrame, nebo None."""
        return self.signals.get(signal_name)

    def summary(self) -> dict:
        """Souhrn obsahu contextu — pro logování a metadata."""
        return {
            "run_id": self.run_id,
            "date_from": self.config.date_from.isoformat(),
            "date_to": self.config.date_to.isoformat(),
            "universe": self.config.universe,
            "assets_total": len(self.assets),
            "assets_active": len(self.assets.active()),
            "conids_with_prices": len(self.prices),
            "features_total": len(self.features),
            "feature_names": sorted(self.features.feature_names()),
            "signals": list(self.signals.keys()),
            "source_hashes_count": len(self.source_hashes),
        }
