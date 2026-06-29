"""
MDSMDataProvider — DataProvider implementace pro MDSM-Lite Parquet cache.

Čte data z:
    data/cache/prices/{conid}_D1.parquet
    data/universe/{universe_name}_universe.csv

Pravidla:
    - READ-ONLY: nikdy nepíše do MDSM-Lite
    - Nepoužívá MDSM-Lite src/ (žádná cross-project závislost)
    - Cesty přicházejí z MRL config/data_paths.yaml
    - Výstup je normalizován na DataProvider kontrakt

Konvence souborů MDSM-Lite:
    prices/{conid}_D1.parquet
        index: date (datetime64, UTC-naive)
        columns: open, high, low, close, volume

    universe/{name}_universe.csv nebo universe/universe.csv
        columns: conid, ticker, exchange, currency,
                 instrument_type, sector, industry, subcategory, active_flag
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.data.data_provider import DataProvider, DataProviderError
from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)

TIMEFRAME = "D1"
PRICE_COLUMNS = ["open", "high", "low", "close", "volume"]
UNIVERSE_REQUIRED_COLUMNS = [
    "conid", "ticker", "exchange", "currency",
    "instrument_type", "sector", "industry", "active_flag",
]
UNIVERSE_OPTIONAL_COLUMNS = ["subcategory"]


class MDSMDataProvider(DataProvider):
    """
    Načítá data z MDSM-Lite Parquet cache.

    Příklad použití:
        provider = MDSMDataProvider(
            prices_dir=Path("C:/Users/stava/Projects/MDSM-Lite/data/cache/prices"),
            universe_dir=Path("C:/Users/stava/Projects/MDSM-Lite/data/universe"),
        )
        prices = provider.load_prices([756733, 4065], date(2025,1,1), date(2026,1,1))
        universe = provider.load_universe("sp500_rank_calendar")
    """

    def __init__(
        self,
        prices_dir: Path,
        universe_dir: Path,
    ) -> None:
        self._prices_dir = Path(prices_dir)
        self._universe_dir = Path(universe_dir)
        self._validate_dirs()

    @property
    def provider_name(self) -> str:
        return "mdsm"

    # ------------------------------------------------------------------
    # load_prices
    # ------------------------------------------------------------------

    def load_prices(
        self,
        conids: list[int],
        date_from: date,
        date_to: date,
    ) -> dict[int, pd.DataFrame]:
        """
        Načte EOD ceny pro seznam conid z MDSM-Lite Parquet cache.

        Chybějící soubor = conid přeskočen (bez výjimky, s logem).
        Vrácený DataFrame je filtrován na [date_from, date_to].
        """
        if date_from > date_to:
            raise DataProviderError(
                f"date_from ({date_from}) musí být <= date_to ({date_to})."
            )

        result: dict[int, pd.DataFrame] = {}
        missing: list[int] = []

        for conid in conids:
            df = self._read_parquet(conid)
            if df is None:
                missing.append(conid)
                continue

            df = self._filter_date_range(df, date_from, date_to)
            if df.empty:
                logger.debug(f"conid={conid} — žádná data v rozsahu {date_from}:{date_to}")
                continue

            result[conid] = df

        if missing:
            logger.warning(
                f"MDSMDataProvider: {len(missing)} conid bez dat v cache: "
                f"{missing[:10]}{'...' if len(missing) > 10 else ''}"
            )

        logger.info(
            f"load_prices: {len(result)}/{len(conids)} conid načteno | "
            f"{date_from} → {date_to}"
        )
        return result

    # ------------------------------------------------------------------
    # load_universe
    # ------------------------------------------------------------------

    def load_universe(self, universe_name: str = "sp500") -> pd.DataFrame:
        """
        Načte universe CSV z MDSM-Lite.

        Hledá v pořadí:
            {universe_name}_universe.csv
            {universe_name}.csv
            universe.csv (fallback)

        Args:
            universe_name: 'sp500_rank_calendar' | 'module' | 'sp500' | ...

        Raises:
            DataProviderError: žádný soubor nenalezen.
        """
        candidates = [
            self._universe_dir / f"{universe_name}_universe.csv",
            self._universe_dir / f"{universe_name}.csv",
            self._universe_dir / "universe.csv",
        ]

        path = None
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break

        if path is None:
            raise DataProviderError(
                f"Universe '{universe_name}' nenalezeno. "
                f"Hledáno v: {[str(c) for c in candidates]}"
            )

        try:
            df = pd.read_csv(path)
        except Exception as exc:
            raise DataProviderError(f"Chyba při čtení universe '{path}': {exc}") from exc

        df = self._normalize_universe(df, path)
        logger.info(
            f"load_universe: '{universe_name}' načteno z {path.name} | "
            f"instrumentů: {len(df)} | aktivních: {df['active_flag'].sum()}"
        )
        return df

    # ------------------------------------------------------------------
    # available_conids
    # ------------------------------------------------------------------

    def available_conids(self) -> list[int]:
        """
        Vrátí seznam conid pro které existuje Parquet soubor v cache.
        Parsuje název souboru: {conid}_D1.parquet
        """
        conids = []
        for f in sorted(self._prices_dir.glob(f"*_{TIMEFRAME}.parquet")):
            stem = f.stem  # např. "756733_D1"
            parts = stem.rsplit("_", 1)
            if len(parts) == 2:
                try:
                    conids.append(int(parts[0]))
                except ValueError:
                    pass
        return conids

    def file_hash(self, conid: int) -> str | None:
        """
        SHA-256 hash Parquet souboru pro daný conid.
        Používá se v ExperimentData.source_hashes() pro reprodukovatelnost.
        Vrátí None pokud soubor neexistuje.
        """
        path = self._parquet_path(conid)
        if not path.exists():
            return None
        sha = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    # ------------------------------------------------------------------
    # Interní metody
    # ------------------------------------------------------------------

    def _parquet_path(self, conid: int) -> Path:
        return self._prices_dir / f"{conid}_{TIMEFRAME}.parquet"

    def _read_parquet(self, conid: int) -> pd.DataFrame | None:
        """Načte Parquet soubor pro conid. Vrátí None při chybě nebo absenci."""
        path = self._parquet_path(conid)
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path, engine="pyarrow")
        except Exception as exc:
            logger.error(f"conid={conid} — chyba čtení Parquet: {exc}")
            return None

        missing = [c for c in PRICE_COLUMNS if c not in df.columns]
        if missing:
            logger.error(f"conid={conid} — chybí sloupce: {missing}")
            return None

        if df.empty:
            return None

        # Normalizace indexu na date (UTC-naive DatetimeIndex)
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception as exc:
                logger.error(f"conid={conid} — nelze převést index na datetime: {exc}")
                return None

        # Odstranění timezone pokud přítomna
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        df.index.name = "date"
        df = df.sort_index()
        return df[PRICE_COLUMNS]

    def _filter_date_range(
        self,
        df: pd.DataFrame,
        date_from: date,
        date_to: date,
    ) -> pd.DataFrame:
        """Filtruje DataFrame na [date_from, date_to] včetně."""
        ts_from = pd.Timestamp(date_from)
        ts_to = pd.Timestamp(date_to)
        return df.loc[(df.index >= ts_from) & (df.index <= ts_to)]

    def _normalize_universe(self, df: pd.DataFrame, path: Path) -> pd.DataFrame:
        """Normalizuje universe DataFrame na standardní kontrakt."""
        missing = [c for c in UNIVERSE_REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise DataProviderError(
                f"Universe '{path.name}' chybí povinné sloupce: {missing}"
            )

        for col in UNIVERSE_OPTIONAL_COLUMNS:
            if col not in df.columns:
                df[col] = ""

        # Normalizace conid
        df["conid"] = pd.to_numeric(df["conid"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["conid"])
        df["conid"] = df["conid"].astype(int)

        # Normalizace active_flag na bool
        df["active_flag"] = df["active_flag"].apply(_parse_active_flag)

        # String sloupce — strip whitespace
        str_cols = ["ticker", "exchange", "currency", "instrument_type",
                    "sector", "industry", "subcategory"]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()

        df = df.set_index("conid")
        return df

    def _validate_dirs(self) -> None:
        """Validuje, že adresáře cache existují (varování, ne výjimka)."""
        if not self._prices_dir.exists():
            logger.warning(
                f"MDSMDataProvider: prices_dir neexistuje: {self._prices_dir}. "
                "Zkontroluj config/data_paths.yaml."
            )
        if not self._universe_dir.exists():
            logger.warning(
                f"MDSMDataProvider: universe_dir neexistuje: {self._universe_dir}. "
                "Zkontroluj config/data_paths.yaml."
            )


def _parse_active_flag(value: object) -> bool:
    """Převede různé formáty active_flag na bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1")
    return False
