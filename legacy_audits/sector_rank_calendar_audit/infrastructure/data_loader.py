"""
Sector Leadership Audit Robot — Data Loader
audit/data_loader.py

Zodpovědnost:
    Načte všechna data potřebná pro audit testy jednou.
    Sdílený vstupní bod pro všechny testy.

    Audit Robot nikdy nestahuje tržní data.
    Audit Robot nikdy nepočítá ranking.
    Pouze analyzuje historické výsledky.

Data:
    sector_rank_history.parquet   — rank history
    sector_health_history.parquet — health history
    close prices z MDSM cache     — pro true forward returns

Forward returns:
    Počítány přímo z close prices:
    forward_return_Nd = price(D+N) / price(D) - 1
    Ne z rank history return_pct (to je lookback return).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

# Nastav sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from config import OUTPUT_DIR, MDSM_PATH, UNIVERSE_CSV, TICKERS

RANK_HISTORY_PATH   = OUTPUT_DIR / "sector_rank_history.parquet"
HEALTH_HISTORY_PATH = OUTPUT_DIR / "sector_health_history.parquet"

FORWARD_WINDOWS = [5, 10, 20, 30]  # obchodní dny
HEALTH_BUCKETS  = [(90, 100), (80, 89), (70, 79), (60, 69), (0, 59)]
BUCKET_LABELS   = ["90-100", "80-89", "70-79", "60-69", "<60"]


class AuditData:
    """
    Kontejner pro všechna audit data.
    Načtěte jednou, předejte všem testům.
    """

    def __init__(
        self,
        rank_df: pd.DataFrame,
        health_df: pd.DataFrame,
        close_prices: pd.DataFrame,
    ):
        self.rank_df      = rank_df       # date, lookback, sector, rank, return_pct
        self.health_df    = health_df     # date, lookback, sector, health, komponenty, delta_health
        self.close_prices = close_prices  # index=date, columns=tickers

        # Předpočítej forward returns pro všechna okna
        self.forward_returns = _compute_forward_returns(close_prices)

    def health_for_lookback(self, lookback: int) -> pd.DataFrame:
        return self.health_df[self.health_df["lookback"] == lookback].copy()

    def rank_for_lookback(self, lookback: int) -> pd.DataFrame:
        return self.rank_df[self.rank_df["lookback"] == lookback].copy()


def load_audit_data() -> AuditData:
    """
    Načte všechna data pro audit. Volat jednou na začátku.
    """
    print("[INFO] Načítám rank history...")
    rank_df = pd.read_parquet(RANK_HISTORY_PATH)
    rank_df["date"] = pd.to_datetime(rank_df["date"]).dt.date
    print(f"       {len(rank_df):,} řádků, {rank_df['date'].nunique()} dní")

    print("[INFO] Načítám health history...")
    health_df = pd.read_parquet(HEALTH_HISTORY_PATH)
    health_df["date"] = pd.to_datetime(health_df["date"]).dt.date
    print(f"       {len(health_df):,} řádků")

    print("[INFO] Načítám close prices...")
    close_prices = _load_close_prices()
    print(f"       {len(close_prices)} dní × {len(close_prices.columns)} tickerů")

    return AuditData(rank_df, health_df, close_prices)


def _load_close_prices() -> pd.DataFrame:
    """
    Načte close prices z MDSM cache pro všechny tickery.
    """
    from src.utils.config_loader import load_config
    from src.utils.universe_loader import UniverseLoader
    from src.access.access_layer import AccessLayer, CacheMissError
    from datetime import timedelta

    loader = UniverseLoader(UNIVERSE_CSV)
    loader.load()
    df_universe = loader.get_all()

    conid_map: dict[str, int] = {
        str(row["ticker"]).strip().upper(): int(conid)
        for conid, row in df_universe.iterrows()
    }

    config = load_config(MDSM_PATH / "config" / "config.yaml")
    layer  = AccessLayer(config)

    from datetime import date as date_type
    start = date_type(2018, 7, 1)
    end   = date_type.today()

    series_list = []
    for ticker in TICKERS:
        conid = conid_map[ticker]
        df = layer.get_historical(
            conid=conid, start=start, end=end,
            timeframe="D1", cache_only=True,
        )
        if df is not None and not df.empty:
            series_list.append(df["close"].rename(ticker))

    prices = pd.concat(series_list, axis=1)
    prices.index = pd.to_datetime(prices.index)
    return prices.sort_index()


def _compute_forward_returns(close_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Vypočítá forward returns pro všechna okna.

    Returns:
        DataFrame: index=date, columns=MultiIndex(ticker, window)
        Hodnoty jsou procentuální forward returns.
    """
    result_frames = []
    for window in FORWARD_WINDOWS:
        # forward return = price(D+N) / price(D) - 1
        fwd = close_prices.shift(-window) / close_prices - 1
        fwd = fwd * 100  # v procentech
        fwd.columns = pd.MultiIndex.from_product(
            [close_prices.columns, [f"fwd_{window}d"]],
            names=["sector", "window"]
        )
        result_frames.append(fwd)

    combined = pd.concat(result_frames, axis=1)
    return combined


def get_forward_return(
    forward_returns: pd.DataFrame,
    dt: date,
    ticker: str,
    window: int,
) -> float | None:
    """
    Vrátí forward return pro daný ticker, datum a okno.
    None pokud data nejsou dostupná.
    """
    ts = pd.Timestamp(dt)
    if ts not in forward_returns.index:
        return None
    try:
        val = forward_returns.loc[ts, (ticker, f"fwd_{window}d")]
        if pd.isna(val):
            return None
        return float(val)
    except KeyError:
        return None


def health_bucket(health: int) -> str:
    """Vrátí label bucketu pro danou Health hodnotu."""
    if health >= 90: return "90-100"
    if health >= 80: return "80-89"
    if health >= 70: return "70-79"
    if health >= 60: return "60-69"
    return "<60"
