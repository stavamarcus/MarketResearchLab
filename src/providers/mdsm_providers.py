"""
MDSM Provider — implementace specializovaných providerů pro MDSM-Lite cache.

Čtyři třídy, jedna zodpovědnost každá:
    MDSMPriceProvider    — čte data/cache/prices/{conid}_D1.parquet
    MDSMUniverseProvider — čte data/universe/*.csv
    MDSMSignalProvider   — čte archivní výstupy modulů (skeleton)
    MDSMMetadataProvider — čte data/cache/metadata/{conid}_D1.json

Pravidla:
    READ-ONLY: nikdy nepíše do MDSM-Lite
    Žádná cross-project závislost na MDSM-Lite src/
    Cesty přicházejí z konstruktoru (injektované z ProviderFactory)
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.domain.asset import Asset, AssetUniverse
from src.domain.feature import Feature, FeatureSet
from src.providers.providers_abc import (
    MetadataProvider,
    ProviderError,
    PriceProvider,
    SignalProvider,
    UniverseProvider,
)
from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)

TIMEFRAME = "D1"
PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]

UNIVERSE_REQUIRED = [
    "conid", "ticker", "exchange", "currency",
    "instrument_type", "sector", "industry", "active_flag",
]
UNIVERSE_OPTIONAL = ["subcategory"]

SUPPORTED_MODULES = ["MLE", "IMS", "IRC", "breadth", "rank_calendar"]


# ---------------------------------------------------------------------------
# MDSMPriceProvider
# ---------------------------------------------------------------------------

class MDSMPriceProvider(PriceProvider):
    """Čte EOD ceny z MDSM-Lite Parquet cache."""

    def __init__(self, prices_dir: Path) -> None:
        self._prices_dir = Path(prices_dir)

    @property
    def source_name(self) -> str:
        return "mdsm"

    def load_prices(
        self,
        conids: list[int],
        date_from: date,
        date_to: date,
    ) -> dict[int, pd.DataFrame]:
        if date_from > date_to:
            raise ProviderError(f"date_from ({date_from}) > date_to ({date_to})")

        result: dict[int, pd.DataFrame] = {}
        missing: list[int] = []

        for conid in conids:
            df = self._read_parquet(conid)
            if df is None:
                missing.append(conid)
                continue
            df = self._filter_range(df, date_from, date_to)
            if not df.empty:
                result[conid] = df

        if missing:
            logger.warning(
                f"MDSMPriceProvider: {len(missing)} conid bez dat "
                f"({missing[:5]}{'...' if len(missing) > 5 else ''})"
            )
        logger.info(
            f"load_prices: {len(result)}/{len(conids)} conid | "
            f"{date_from} → {date_to}"
        )
        return result

    def get_available_price_range(self, conid: int) -> tuple[date, date] | None:
        df = self._read_parquet(conid)
        if df is None or df.empty:
            return None
        return df.index[0].date(), df.index[-1].date()

    def available_conids(self) -> list[int]:
        conids = []
        for f in sorted(self._prices_dir.glob(f"*_{TIMEFRAME}.parquet")):
            try:
                conids.append(int(f.stem.rsplit("_", 1)[0]))
            except (ValueError, IndexError):
                pass
        return conids

    def file_hash(self, conid: int) -> str | None:
        """SHA-256 souboru pro metadata reprodukovatelnosti."""
        path = self._path(conid)
        if not path.exists():
            return None
        sha = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    # --- interní ---

    def _path(self, conid: int) -> Path:
        return self._prices_dir / f"{conid}_{TIMEFRAME}.parquet"

    def _read_parquet(self, conid: int) -> pd.DataFrame | None:
        path = self._path(conid)
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path, engine="pyarrow")
        except Exception as exc:
            logger.error(f"conid={conid} read error: {exc}")
            return None

        missing = [c for c in PRICE_COLUMNS if c not in df.columns]
        if missing or df.empty:
            return None

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index.name = "date"
        return df[PRICE_COLUMNS].sort_index()

    def _filter_range(self, df: pd.DataFrame, d_from: date, d_to: date) -> pd.DataFrame:
        return df.loc[(df.index >= pd.Timestamp(d_from)) & (df.index <= pd.Timestamp(d_to))]


# ---------------------------------------------------------------------------
# MDSMUniverseProvider
# ---------------------------------------------------------------------------

class MDSMUniverseProvider(UniverseProvider):
    """Čte universe CSV z MDSM-Lite."""

    def __init__(self, universe_dir: Path) -> None:
        self._universe_dir = Path(universe_dir)
        self._cache: dict[str, pd.DataFrame] = {}

    @property
    def source_name(self) -> str:
        return "mdsm"

    def load_universe(self, universe_name: str = "sp500") -> pd.DataFrame:
        if universe_name not in self._cache:
            self._cache[universe_name] = self._read_universe(universe_name)
        return self._cache[universe_name].copy()

    def load_assets(self, universe_name: str = "sp500") -> AssetUniverse:
        df = self.load_universe(universe_name)
        assets = [
            Asset.from_universe_row(int(conid), row.to_dict())
            for conid, row in df.iterrows()
        ]
        return AssetUniverse(assets)

    def get_asset(self, conid: int, universe_name: str = "sp500") -> Asset | None:
        df = self.load_universe(universe_name)
        if conid not in df.index:
            return None
        return Asset.from_universe_row(conid, df.loc[conid].to_dict())

    # --- interní ---

    def _read_universe(self, universe_name: str) -> pd.DataFrame:
        candidates = [
            self._universe_dir / f"{universe_name}_universe.csv",
            self._universe_dir / f"{universe_name}.csv",
            self._universe_dir / "universe.csv",
        ]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            raise ProviderError(
                f"Universe '{universe_name}' nenalezeno v {self._universe_dir}"
            )
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise ProviderError(f"Chyba čtení universe '{path}': {exc}") from exc

        missing = [c for c in UNIVERSE_REQUIRED if c not in df.columns]
        if missing:
            raise ProviderError(f"Universe '{path.name}' chybí sloupce: {missing}")

        for col in UNIVERSE_OPTIONAL:
            if col not in df.columns:
                df[col] = ""

        df["conid"] = pd.to_numeric(df["conid"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["conid"])
        df["conid"] = df["conid"].astype(int)
        df["active_flag"] = df["active_flag"].apply(_parse_bool)

        str_cols = ["ticker", "exchange", "currency", "instrument_type",
                    "sector", "industry", "subcategory"]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        df = df.set_index("conid")
        logger.info(
            f"load_universe '{universe_name}': {len(df)} instrumentů "
            f"({df['active_flag'].sum()} aktivních) z {path.name}"
        )
        return df


# ---------------------------------------------------------------------------
# MDSMSignalProvider
# ---------------------------------------------------------------------------

class MDSMSignalProvider(SignalProvider):
    """
    Čte archivní výstupy produkčních modulů z MDSM-Lite.
    Skeleton — konkrétní loadery implementovat při prvním experimentu.
    """

    def __init__(self, signals_dir: Path) -> None:
        self._signals_dir = Path(signals_dir)

    @property
    def source_name(self) -> str:
        return "mdsm"

    def load_signals(self, module: str, date_from: date, date_to: date) -> pd.DataFrame:
        if module not in SUPPORTED_MODULES:
            raise ProviderError(
                f"Nepodporovaný modul: '{module}'. Dostupné: {SUPPORTED_MODULES}"
            )
        method = getattr(self, f"_load_{module}", None)
        if method is None:
            raise NotImplementedError(
                f"MDSMSignalProvider._load_{module}() není implementován. "
                "Implementujte při prvním experimentu vyžadujícím tento modul."
            )
        return method(date_from, date_to)

    def load_features(
        self,
        feature_names: list[str],
        conids: list[int],
        date_from: date,
        date_to: date,
    ) -> FeatureSet:
        """
        Skeleton — přeloží signály modulů na Feature objekty.
        Implementovat při prvním experimentu vyžadujícím Feature.
        """
        raise NotImplementedError(
            "MDSMSignalProvider.load_features() není implementován. "
            "Implementujte při prvním výzkumném experimentu."
        )

    def available_modules(self) -> list[str]:
        """Vrátí moduly pro které existuje archivní adresář."""
        if not self._signals_dir.exists():
            return []
        return [
            m for m in SUPPORTED_MODULES
            if (self._signals_dir / m.lower()).exists()
        ]

    # --- skeleton loadery ---

    def _load_MLE(self, date_from: date, date_to: date) -> pd.DataFrame:
        raise NotImplementedError("_load_MLE: implementovat při prvním MLE experimentu.")

    def _load_IMS(self, date_from: date, date_to: date) -> pd.DataFrame:
        raise NotImplementedError("_load_IMS: implementovat při prvním IMS experimentu.")

    def _load_IRC(self, date_from: date, date_to: date) -> pd.DataFrame:
        raise NotImplementedError("_load_IRC: implementovat při prvním IRC experimentu.")

    def _load_breadth(self, date_from: date, date_to: date) -> pd.DataFrame:
        raise NotImplementedError("_load_breadth: implementovat při prvním Breadth experimentu.")

    def _load_rank_calendar(self, date_from: date, date_to: date) -> pd.DataFrame:
        raise NotImplementedError("_load_rank_calendar: implementovat při prvním experimentu.")


# ---------------------------------------------------------------------------
# MDSMMetadataProvider
# ---------------------------------------------------------------------------

class MDSMMetadataProvider(MetadataProvider):
    """Čte metadata z MDSM-Lite data/cache/metadata/{conid}_D1.json."""

    def __init__(self, metadata_dir: Path, prices_dir: Path) -> None:
        self._metadata_dir = Path(metadata_dir)
        self._prices_dir = Path(prices_dir)

    @property
    def source_name(self) -> str:
        return "mdsm"

    def load_asset_metadata(self, conid: int) -> dict:
        path = self._metadata_dir / f"{conid}_{TIMEFRAME}.json"
        if not path.exists():
            return {"conid": conid, "available": False}
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            data["conid"] = conid
            data["available"] = True
            return data
        except Exception as exc:
            logger.warning(f"metadata conid={conid}: {exc}")
            return {"conid": conid, "available": False, "error": str(exc)}

    def load_source_metadata(self) -> dict:
        price_files = list(self._prices_dir.glob(f"*_{TIMEFRAME}.parquet"))
        return {
            "source": "mdsm",
            "prices_dir": str(self._prices_dir),
            "metadata_dir": str(self._metadata_dir),
            "total_instruments": len(price_files),
            "retrieved_at": datetime.utcnow().isoformat(),
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_bool(value: object) -> bool:
    """Převede různé formáty boolean hodnoty (active_flag) na bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1")
    return False
