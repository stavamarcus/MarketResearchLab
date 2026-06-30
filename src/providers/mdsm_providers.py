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

# MDSMSignalProvider — plná implementace (nahrazuje skeleton)
# Vložit do mdsm_providers.py místo skeleton třídy

SUPPORTED_MODULES = ["MLE", "IMS", "IRC", "breadth"]

# Povinné sloupce každého archivu
MLE_REQUIRED_COLS     = ["date", "ticker", "rank_1d", "ret_1d", "rank_5d", "ret_5d", "rank_10d", "ret_10d", "rank_20d", "ret_20d"]
IMS_REQUIRED_COLS     = ["date", "ticker", "score", "priority_group"]
IRC_REQUIRED_COLS     = ["date", "lookback", "rank", "industry", "sector", "median_return", "member_count"]
BREADTH_REQUIRED_COLS = ["date", "above_ma50_pct", "above_ma200_pct", "advance_count", "decline_count"]


class MDSMSignalProvider(SignalProvider):
    """
    Čte archivní výstupy produkčních modulů.

    signals_dir musí obsahovat:
        rank_matrix_archive.csv          ← MLE
        ims_candidates_archive.csv       ← IMS
        industry_rank_calendar_archive.csv ← IRC
        breadth_history.csv              ← market_breadth

    Pravidla:
        READ-ONLY — žádný zápis do archivů
        Žádná obchodní logika — pouze převod na standardní DataFrame
        Validace povinných sloupců a datového rozsahu
    """

    def __init__(
        self,
        signals_dir: Path | None = None,
        module_paths: dict[str, Path] | None = None,
    ) -> None:
        """
        signals_dir:  jeden adresář pro všechny moduly (legacy, skeleton použití)
        module_paths: per-module cesty {"MLE": Path(...), "IMS": Path(...), ...}
                      klíče odpovídají názvům modulů, hodnoty jsou adresáře
                      kde leží archivní soubory daného modulu.
        """
        self._signals_dir = Path(signals_dir) if signals_dir else Path()
        self._module_paths: dict[str, Path] = module_paths or {}

    @property
    def source_name(self) -> str:
        return "mdsm"

    def load_signals(self, module: str, date_from: date, date_to: date) -> pd.DataFrame:
        """
        Načte archivní výstupy daného modulu filtrované na [date_from, date_to].

        Returns:
            pd.DataFrame s date sloupcem jako pd.Timestamp, seřazený ASC.

        Raises:
            ProviderError: modul není podporován, soubor neexistuje, chybí sloupce.
        """
        if module not in SUPPORTED_MODULES:
            raise ProviderError(
                f"Nepodporovaný modul: '{module}'. Dostupné: {SUPPORTED_MODULES}"
            )
        method = getattr(self, f"_load_{module}")
        return method(date_from, date_to)

    # Feature map: CSV sloupec → MRL feature_name
    # Experiment pracuje s feature_name, nikdy s CSV sloupcem.
    MLE_FEATURE_MAP: dict[str, str] = {
        "rank_1d":  "MLE_Rank_1d",
        "ret_1d":   "MLE_Ret_1d",
        "rank_5d":  "MLE_Rank_5d",
        "ret_5d":   "MLE_Ret_5d",
        "rank_10d": "MLE_Rank_10d",
        "ret_10d":  "MLE_Ret_10d",
        "rank_20d": "MLE_Rank_20d",
        "ret_20d":  "MLE_Ret_20d",
    }
    IMS_FEATURE_MAP: dict[str, str] = {
        "score":                "IMS_Score",
        "priority_group":       "IMS_Priority_Group",
        "rs_vs_spy_20d":        "IMS_RS_vs_SPY_20d",
        "rank_improvement_20d": "IMS_Rank_Improvement_20d",
        "rank_stability_20d":   "IMS_Rank_Stability_20d",
        "rank_today":           "IMS_Rank_Today",
    }

    def load_features(
        self,
        feature_names: list[str],
        conids: list[int],
        date_from: date,
        date_to: date,
        ticker_to_conid: dict[str, int] | None = None,
    ) -> FeatureSet:
        """
        Převede signály MLE a IMS na FeatureSet (asset-level only).

        IRC a breadth nejsou asset-level — nelze převést na Feature.
        Dostanou se do experimentu přes context.signals["IRC"] / ["breadth"].

        Args:
            feature_names:    seznam MRL feature names ("MLE_Rank_20d", "IMS_Score", ...)
            conids:           seznam conid pro filtrování
            date_from / to:   datový rozsah
            ticker_to_conid:  dict[ticker → conid] z UniverseProvider

        Returns:
            FeatureSet indexovaný (conid, date, feature_name).
        """
        if ticker_to_conid is None:
            raise ValueError(
                "load_features() vyžaduje ticker_to_conid mapping. "
                "Předej ho z UniverseProvider.load_universe()."
            )

        mle_features = [fn for fn in feature_names if fn.startswith("MLE_")]
        ims_features  = [fn for fn in feature_names if fn.startswith("IMS_")]
        unknown = [
            fn for fn in feature_names
            if not fn.startswith(("MLE_", "IMS_"))
        ]
        if unknown:
            logger.warning(
                f"load_features: neznámé/non-asset feature names přeskočeny: {unknown}. "
                "IRC/breadth jsou kontextuální signály — použij context.signals."
            )

        conid_set = set(conids) if conids else None
        features: list[Feature] = []

        if mle_features:
            features.extend(
                self._mle_to_features(
                    mle_features, conid_set, date_from, date_to, ticker_to_conid
                )
            )
        if ims_features:
            features.extend(
                self._ims_to_features(
                    ims_features, conid_set, date_from, date_to, ticker_to_conid
                )
            )

        logger.info(
            f"load_features: {len(features):,} Feature objektů | "
            f"MLE: {len(mle_features)} names, IMS: {len(ims_features)} names"
        )
        return FeatureSet(features)

    def _mle_to_features(
        self,
        feature_names: list[str],
        conid_set: set[int] | None,
        date_from: date,
        date_to: date,
        ticker_to_conid: dict[str, int],
    ) -> list[Feature]:
        """Převede MLE archivní DataFrame na Feature objekty."""
        df = self._load_MLE(date_from, date_to)
        name_to_col = {v: k for k, v in self.MLE_FEATURE_MAP.items()}
        requested = {
            fn: name_to_col[fn]
            for fn in feature_names
            if fn in name_to_col and name_to_col[fn] in df.columns
        }
        features = []
        for _, row in df.iterrows():
            conid = ticker_to_conid.get(row["ticker"])
            if conid is None:
                continue
            if conid_set and conid not in conid_set:
                continue
            dt = row["date"].date()
            for feature_name, col in requested.items():
                val = row[col]
                if pd.isna(val):
                    continue
                features.append(Feature(
                    conid=conid, date=dt,
                    feature_name=feature_name, value=float(val),
                    source_module="MLE",
                ))
        return features

    def _ims_to_features(
        self,
        feature_names: list[str],
        conid_set: set[int] | None,
        date_from: date,
        date_to: date,
        ticker_to_conid: dict[str, int],
    ) -> list[Feature]:
        """Převede IMS archivní DataFrame na Feature objekty."""
        df = self._load_IMS(date_from, date_to)
        name_to_col = {v: k for k, v in self.IMS_FEATURE_MAP.items()}
        requested = {
            fn: name_to_col[fn]
            for fn in feature_names
            if fn in name_to_col and name_to_col[fn] in df.columns
        }
        features = []
        for _, row in df.iterrows():
            conid = ticker_to_conid.get(row["ticker"])
            if conid is None:
                continue
            if conid_set and conid not in conid_set:
                continue
            dt = row["date"].date()
            for feature_name, col in requested.items():
                val = row[col]
                if pd.isna(val):
                    continue
                if feature_name == "IMS_Priority_Group":
                    features.append(Feature(
                        conid=conid, date=dt,
                        feature_name=feature_name, value=str(val),
                        source_module="IMS",
                    ))
                else:
                    try:
                        features.append(Feature(
                            conid=conid, date=dt,
                            feature_name=feature_name, value=float(val),
                            source_module="IMS",
                        ))
                    except (ValueError, TypeError):
                        pass
        return features

    def available_modules(self) -> list[str]:
        """Vrátí moduly pro které existuje archivní soubor."""
        mapping = {
            "MLE":     "rank_matrix_archive.csv",
            "IMS":     "ims_candidates_archive.csv",
            "IRC":     "industry_rank_calendar_archive.csv",
            "breadth": "breadth_history.csv",
        }
        return [m for m, f in mapping.items() if (self._signals_dir / f).exists()]

    # ------------------------------------------------------------------
    # MLE loader
    # ------------------------------------------------------------------

    def _load_MLE(self, date_from: date, date_to: date) -> pd.DataFrame:
        """
        Načte rank_matrix_archive.csv.

        Výstup (sloupce):
            date, ticker, sector, industry, subcategory,
            rank_1d, ret_1d, rank_2d, ret_2d, ..., rank_10d, ret_10d, rank_20d, ret_20d

        Každý řádek = jeden ticker v jeden den s ranky napříč lookbacky.
        """
        path = self._resolve_path("MLE", "rank_matrix_archive.csv")
        df = self._read_csv(path, "MLE", MLE_REQUIRED_COLS)
        df = self._filter_dates(df, date_from, date_to, "MLE")

        # Normalizace rank sloupců na int (mohou obsahovat NaN → Int64)
        rank_cols = [c for c in df.columns if c.startswith("rank_")]
        for col in rank_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # ret sloupce na float
        ret_cols = [c for c in df.columns if c.startswith("ret_")]
        for col in ret_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        logger.info(
            f"MLE loaded: {len(df):,} rows | "
            f"{df['date'].min().date()} → {df['date'].max().date()} | "
            f"{df['ticker'].nunique()} unique tickers"
        )
        return df

    # ------------------------------------------------------------------
    # IMS loader
    # ------------------------------------------------------------------

    def _load_IMS(self, date_from: date, date_to: date) -> pd.DataFrame:
        """
        Načte ims_candidates_archive.csv.

        Výstup (sloupce):
            date, ticker, sector, industry, subcategory,
            priority_group, score, rank_today, rank_improvement_20d,
            rank_improvement_40d, rs_vs_spy_20d, up_down_volume_ratio_20d,
            rank_stability_20d, avg_volume_20d, close, ema200,
            price_vs_52w_high, negative_extreme_days_60d, is_new_entry

        Každý řádek = jeden IMS kandidát v jeden den.
        """
        path = self._resolve_path("IMS", "ims_candidates_archive.csv")
        df = self._read_csv(path, "IMS", IMS_REQUIRED_COLS)
        df = self._filter_dates(df, date_from, date_to, "IMS")

        # Normalizace
        df["score"] = pd.to_numeric(df["score"], errors="coerce")
        if "is_new_entry" in df.columns:
            df["is_new_entry"] = df["is_new_entry"].apply(_parse_bool)

        logger.info(
            f"IMS loaded: {len(df):,} rows | "
            f"{df['date'].min().date()} → {df['date'].max().date()} | "
            f"{df['ticker'].nunique()} unique tickers | "
            f"priority groups: {sorted(df['priority_group'].unique())}"
        )
        return df

    # ------------------------------------------------------------------
    # IRC loader
    # ------------------------------------------------------------------

    def _load_IRC(self, date_from: date, date_to: date) -> pd.DataFrame:
        """
        Načte industry_rank_calendar_archive.csv.

        Výstup (sloupce):
            date, lookback, rank, industry, sector,
            median_return, mean_return, member_count, advance_ratio,
            top_1_ticker, top_1_return, top_2_ticker, top_2_return,
            top_3_ticker, top_3_return, status

        Každý řádek = jedna industrie pro jeden lookback v jeden den.
        Jeden den obsahuje N industrií × M lookbacků řádků.
        """
        path = self._resolve_path("IRC", "industry_rank_calendar_archive.csv")
        df = self._read_csv(path, "IRC", IRC_REQUIRED_COLS)
        df = self._filter_dates(df, date_from, date_to, "IRC")

        df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
        df["lookback"] = pd.to_numeric(df["lookback"], errors="coerce")
        df["median_return"] = pd.to_numeric(df["median_return"], errors="coerce")
        df["member_count"] = pd.to_numeric(df["member_count"], errors="coerce")

        logger.info(
            f"IRC loaded: {len(df):,} rows | "
            f"{df['date'].min().date()} → {df['date'].max().date()} | "
            f"{df['industry'].nunique()} industries | "
            f"lookbacks: {sorted(df['lookback'].dropna().unique().astype(int).tolist())}"
        )
        return df

    # ------------------------------------------------------------------
    # Breadth loader
    # ------------------------------------------------------------------

    def _load_breadth(self, date_from: date, date_to: date) -> pd.DataFrame:
        """
        Načte breadth_history.csv.

        Výstup (sloupce):
            date, universe_size, valid_ma50/100/200,
            above_ma50_pct, above_ma100_pct, above_ma200_pct,
            advance_count, decline_count, advance_decline_net,
            new_highs, new_lows, mcclellan,
            above_ma50_1d/3d/5d/10d/20d_change_pp, (atd. pro ma100, ma200)

        Každý řádek = jeden obchodní den, jeden řádek na den.
        """
        path = self._resolve_path("breadth", "breadth_history.csv")
        df = self._read_csv(path, "breadth", BREADTH_REQUIRED_COLS)
        df = self._filter_dates(df, date_from, date_to, "breadth")

        # Numerické sloupce
        numeric_cols = [c for c in df.columns if c != "date"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Počet validních řádků (mohou existovat dny s NaN breadth)
        valid = df["above_ma50_pct"].notna().sum()
        logger.info(
            f"breadth loaded: {len(df)} rows ({valid} valid) | "
            f"{df['date'].min().date()} → {df['date'].max().date()}"
        )
        return df

    # ------------------------------------------------------------------
    # Interní metody
    # ------------------------------------------------------------------


    def _resolve_path(self, module: str, filename: str) -> Path:
        """Vrátí cestu k archivnímu souboru — z module_paths nebo signals_dir."""
        if module in self._module_paths:
            return self._module_paths[module] / filename
        return self._signals_dir / filename

    def _read_csv(self, path: Path, module: str, required_cols: list[str]) -> pd.DataFrame:
        """Načte CSV, ověří existenci a povinné sloupce."""
        if not path.exists():
            raise ProviderError(
                f"{module} archiv nenalezen: {path}. "
                f"Zkontroluj signals_dir v data_paths.yaml."
            )
        try:
            df = pd.read_csv(path, low_memory=False)
        except Exception as exc:
            raise ProviderError(f"{module} chyba čtení '{path}': {exc}") from exc

        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ProviderError(
                f"{module} archiv chybí povinné sloupce: {missing}. "
                f"Dostupné: {list(df.columns)}"
            )

        # Normalizace date sloupce
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        invalid_dates = df["date"].isna().sum()
        if invalid_dates > 0:
            logger.warning(f"{module}: {invalid_dates} řádků s neplatným datem — přeskočeny")
            df = df.dropna(subset=["date"])

        return df.sort_values("date").reset_index(drop=True)

    def _filter_dates(
        self, df: pd.DataFrame, date_from: date, date_to: date, module: str
    ) -> pd.DataFrame:
        """Filtruje DataFrame na [date_from, date_to] včetně."""
        ts_from = pd.Timestamp(date_from)
        ts_to   = pd.Timestamp(date_to)
        filtered = df[(df["date"] >= ts_from) & (df["date"] <= ts_to)].copy()
        if filtered.empty:
            logger.warning(
                f"{module}: žádná data v rozsahu {date_from} → {date_to}. "
                f"Dostupný rozsah: {df['date'].min().date()} → {df['date'].max().date()}"
            )
        return filtered


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

    def load_prices(self, conids: list[int], date_from: date, date_to: date) -> dict[int, pd.DataFrame]:
        if date_from > date_to:
            raise ProviderError(f"date_from ({date_from}) > date_to ({date_to})")
        result = {}
        missing = []
        for conid in conids:
            df = self._read_parquet(conid)
            if df is None:
                missing.append(conid)
                continue
            df = df.loc[(df.index >= pd.Timestamp(date_from)) & (df.index <= pd.Timestamp(date_to))]
            if not df.empty:
                result[conid] = df
        if missing:
            logger.warning(f"MDSMPriceProvider: {len(missing)} conid bez dat")
        logger.info(f"load_prices: {len(result)}/{len(conids)} conid | {date_from} -> {date_to}")
        return result

    def get_available_price_range(self, conid: int):
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

    def file_hash(self, conid: int):
        path = self._prices_dir / f"{conid}_{TIMEFRAME}.parquet"
        if not path.exists():
            return None
        sha = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _read_parquet(self, conid: int):
        path = self._prices_dir / f"{conid}_{TIMEFRAME}.parquet"
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path, engine="pyarrow")
        except Exception as exc:
            logger.error(f"conid={conid} read error: {exc}")
            return None
        if any(c not in df.columns for c in PRICE_COLUMNS) or df.empty:
            return None
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        df.index.name = "date"
        return df[PRICE_COLUMNS].sort_index()


# ---------------------------------------------------------------------------
# MDSMUniverseProvider
# ---------------------------------------------------------------------------

class MDSMUniverseProvider(UniverseProvider):
    """Cte universe CSV z MDSM-Lite."""

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
        assets = []
        for conid, row in df.iterrows():
            assets.append(Asset.from_universe_row(int(conid), row.to_dict()))
        return AssetUniverse(assets)

    def get_asset(self, conid: int, universe_name: str = "sp500"):
        df = self.load_universe(universe_name)
        if conid not in df.index:
            return None
        return Asset.from_universe_row(conid, df.loc[conid].to_dict())

    def _read_universe(self, universe_name: str) -> pd.DataFrame:
        candidates = [
            self._universe_dir / f"{universe_name}_universe.csv",
            self._universe_dir / f"{universe_name}.csv",
            self._universe_dir / "universe.csv",
        ]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            raise ProviderError(f"Universe '{universe_name}' nenalezeno v {self._universe_dir}")
        df = pd.read_csv(path)
        missing = [c for c in UNIVERSE_REQUIRED if c not in df.columns]
        if missing:
            raise ProviderError(f"Universe '{path.name}' chybi sloupce: {missing}")
        for col in UNIVERSE_OPTIONAL:
            if col not in df.columns:
                df[col] = ""
        df["conid"] = pd.to_numeric(df["conid"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["conid"])
        df["conid"] = df["conid"].astype(int)
        df["active_flag"] = df["active_flag"].apply(_parse_bool)
        for col in ["ticker","exchange","currency","instrument_type","sector","industry","subcategory"]:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        df = df.set_index("conid")
        logger.info(f"load_universe '{universe_name}': {len(df)} instrumentu")
        return df


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
