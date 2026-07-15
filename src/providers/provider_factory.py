"""
ProviderFactory — sestaví specializované providery z config/data_paths.yaml.

Vrací ProviderBundle s čtveřicí specializovaných providerů.

Přidání nového zdroje dat:
    1. Implementuj PriceProvider, UniverseProvider, SignalProvider, MetadataProvider
    2. Přidej case do _build_*() metod
    3. Přidej sekci do data_paths.yaml
    Žádné další změny frameworku nejsou potřeba.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from src.infrastructure.logging_manager import get_logger
from src.providers.mdsm_providers import (
    MDSMMetadataProvider,
    MDSMPriceProvider,
    MDSMSignalProvider,
    MDSMUniverseProvider,
)
from src.providers.providers_abc import (
    MetadataProvider,
    PriceProvider,
    SignalProvider,
    UniverseProvider,
)

logger = get_logger(__name__)


class ProviderFactoryError(Exception):
    """Chyba při sestavení providerů."""


@dataclass
class ProviderBundle:
    """
    Čtveřice specializovaných providerů pro jeden zdroj dat.

    ExperimentRunner dostane ProviderBundle a předá ho ContextBuilderu.

    fundamental (MRL-FUND-01): optional MRLSharadarFundamentalSource;
    None = fundamentals nekonfigurovány. build() ho NEsestavuje —
    konstrukce (store load + full hash check) je explicitní přes
    build_fundamental_source(), aby běhy bez fundamentals nenesly
    žádný overhead a nemohly selhat na Sharadar konfiguraci.
    Typ object: adapter je optional dependency (žádný import zde).
    """
    price: PriceProvider
    universe: UniverseProvider
    signal: SignalProvider
    metadata: MetadataProvider
    source_name: str
    fundamental: object | None = None


class ProviderFactory:
    """
    Sestaví ProviderBundle z config/data_paths.yaml.

    Příklad použití:
        factory = ProviderFactory(config_dir=Path("config"))
        bundle = factory.build()
        # bundle.price, bundle.universe, bundle.signal, bundle.metadata
    """

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = Path(config_dir)

    def build(self) -> ProviderBundle:
        config = self._load_config()
        active = config.get("active_provider", "mdsm")
        logger.info(f"ProviderFactory: sestavuji '{active}' provider bundle")

        if active == "mdsm":
            bundle = self._build_mdsm(config)
            # MRL-FUND-02: optional fundamentals — POUZE při explicitní
            # aktivaci (enabled: true). Default false = nulový overhead,
            # žádný experiment nedostane fundamentals náhodně. Chyba
            # konstrukce (CACHE_MISSING, ...) je setup-level → build()
            # selže a run se nespustí.
            fundamental = self.build_fundamental_source()
            if fundamental is not None:
                bundle.fundamental = fundamental
            return bundle

        raise ProviderFactoryError(
            f"Neznámý provider: '{active}'. Dostupné: ['mdsm']"
        )

    def build_fundamental_source(self, allow_latest: bool = False):
        """
        MRL-FUND-01: sestaví MRLSharadarFundamentalSource z optional sekce
        `sharadar_fundamentals` v data_paths.yaml.

        Returns:
            MRLSharadarFundamentalSource | None
            None pokud sekce chybí nebo enabled != true — existující
            experimenty bez fundamentals se nesmí rozbít (schválený požadavek).

        Raises:
            ProviderFactoryError: sekce enabled, ale nekompletní
            (adapter_config / snapshot_id chybí). Chyby konstrukce
            (adapter neimportovatelný, CACHE_MISSING, ...) propadají
            volajícímu — jsou setup-level a run se nesmí spustit.
        """
        config = self._load_config()
        cfg = config.get("sharadar_fundamentals")
        if not cfg or not cfg.get("enabled", False):
            return None
        adapter_config = cfg.get("adapter_config", "")
        snapshot_id = cfg.get("snapshot_id", "")
        if not adapter_config or not snapshot_id:
            raise ProviderFactoryError(
                "sharadar_fundamentals: enabled, ale chybí adapter_config "
                "nebo snapshot_id v data_paths.yaml."
            )
        # Lazy import — adapter je optional dependency MRL.
        from src.providers.sharadar_fundamental_source import (
            build_fundamental_source,
        )
        return build_fundamental_source(
            adapter_config_path=adapter_config,
            snapshot_id=str(snapshot_id),
            allow_latest=allow_latest,
        )

    def _build_mdsm(self, config: dict) -> ProviderBundle:
        cfg = config.get("mdsm")
        if not cfg:
            raise ProviderFactoryError("Sekce 'mdsm' chybí v data_paths.yaml.")

        prices_dir   = self._require_path(cfg, "prices_dir",   "mdsm.prices_dir")
        universe_dir = self._require_path(cfg, "universe_dir", "mdsm.universe_dir")
        metadata_dir = self._derive_metadata_dir(prices_dir)

        # Per-module cesty pro SignalProvider (mdsm.signals.MLE / IMS / IRC / breadth)
        signals_cfg  = cfg.get("signals", {})
        module_paths = {m: Path(p) for m, p in signals_cfg.items() if p}

        return ProviderBundle(
            price=MDSMPriceProvider(prices_dir=prices_dir),
            universe=MDSMUniverseProvider(universe_dir=universe_dir),
            signal=MDSMSignalProvider(module_paths=module_paths),
            metadata=MDSMMetadataProvider(
                metadata_dir=metadata_dir,
                prices_dir=prices_dir,
            ),
            source_name="mdsm",
        )

    def _load_config(self) -> dict:
        path = self._config_dir / "data_paths.yaml"
        if not path.exists():
            raise ProviderFactoryError(f"data_paths.yaml nenalezen: {path}")
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _require_path(self, cfg: dict, key: str, label: str) -> Path:
        raw = cfg.get(key, "")
        if not raw:
            raise ProviderFactoryError(f"{label} nesmí být prázdný v data_paths.yaml.")
        return Path(raw)

    def _derive_metadata_dir(self, prices_dir: Path) -> Path:
        """
        Odvodí cestu k metadata adresáři z prices_dir.
        MDSM-Lite struktura: data/cache/prices/ → data/cache/metadata/
        """
        return prices_dir.parent / "metadata"
