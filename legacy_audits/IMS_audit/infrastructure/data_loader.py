"""
IMS Audit — Data Loader
audit/data_loader.py

Zodpovědnost:
    Načíst IMS archiv a close prices z MDSM cache.
    Sestavit dataset signálů s forward cenami pro každý ticker.
    Poskytnout čistý interface pro audit testy.

Výstupy:
    AuditData dataclass:
        signals     — DataFrame všech signálů z archivu
        close_map   — dict[ticker, pd.Series] close prices z MDSM cache
        spy_close   — pd.Series SPY close prices
        meta        — dict s informacemi o datasetu

Předpoklady:
    - ims_candidates_archive.csv obsahuje sloupce:
      date, ticker, score, priority_group, sector, industry
    - MDSM cache obsahuje close prices pro všechny tickery v archivu
    - SPY (conid=756733) je v cache
    - Spouštěno z kořene IMS projektu

Použití:
    from audit.data_loader import load_audit_data
    data = load_audit_data()
    print(data.meta)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# ── Cesty ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PATH = PROJECT_ROOT / "output" / "archive" / "ims_candidates_archive.csv"

SPY_CONID    = 756733
SPY_TICKER   = "SPY"

# Forward windows v obchodních dnech
FORWARD_WINDOWS = [5, 10, 20, 30]

# Score buckety pro audit
SCORE_BUCKETS = {
    "RADAR":  (60, 70),
    "H70-79": (70, 80),
    "H80-89": (80, 90),
    "H90-94": (90, 95),
    "H95+":   (95, 101),
}


# ── Výstupní dataclass ────────────────────────────────────────────────────────

@dataclass
class AuditData:
    signals:   pd.DataFrame                    # signály z archivu
    close_map: dict[str, pd.Series]            # ticker → close series
    spy_close: pd.Series                       # SPY close series
    meta:      dict                            # informace o datasetu


# ── Hlavní funkce ─────────────────────────────────────────────────────────────

def load_audit_data(
    archive_path: Path | None = None,
    verbose: bool = True,
) -> AuditData:
    """
    Načte IMS archiv a close prices z MDSM cache.

    Args:
        archive_path: cesta k archivu (výchozí: output/archive/ims_candidates_archive.csv)
        verbose:      logovat průběh na stdout

    Returns:
        AuditData

    Raises:
        FileNotFoundError: archiv neexistuje
        RuntimeError:      kritická chyba při načítání dat
    """
    path = archive_path or ARCHIVE_PATH

    if verbose:
        print("=" * 60)
        print("IMS AUDIT — DATA LOADER")
        print("=" * 60)

    # ── 1. Načti archiv ───────────────────────────────────────────────
    signals = _load_archive(path, verbose)

    # ── 2. Zjisti unikátní tickery ────────────────────────────────────
    tickers = sorted(signals["ticker"].unique().tolist())
    if verbose:
        print(f"Unikátních tickerů v archivu : {len(tickers)}")

    # ── 3. Inicializuj MDSM AccessLayer ──────────────────────────────
    layer, universe_map = _init_access_layer(verbose)

    # ── 4. Urči rozsah dat ────────────────────────────────────────────
    signal_start = signals["date"].min()
    signal_end   = signals["date"].max()

    # Buffer: potřebujeme close prices 30D za posledním signal date
    fetch_start = signal_start
    fetch_end   = signal_end

    if verbose:
        print(f"Signal rozsah  : {signal_start} → {signal_end}")
        print(f"Fetch rozsah   : {fetch_start} → {fetch_end}")
        print()

    # ── 5. Načti SPY ──────────────────────────────────────────────────
    spy_close = _fetch_ticker(layer, SPY_CONID, SPY_TICKER, fetch_start, fetch_end, verbose)
    if spy_close is None:
        raise RuntimeError("SPY data nejsou dostupná v MDSM cache. Spusť GDU.")

    # ── 6. Načti close prices pro všechny tickery ─────────────────────
    close_map = _fetch_all_tickers(
        layer, tickers, universe_map, fetch_start, fetch_end, verbose
    )

    # ── 7. Data availability per forward window ───────────────────────
    cache_end      = spy_close.index.max().date()
    availability   = _compute_availability(signal_end, cache_end)

    # ── 8. Meta ───────────────────────────────────────────────────────
    meta = {
        "signal_date_min":    str(signal_start),
        "signal_date_max":    str(signal_end),
        "signal_rows":        len(signals),
        "signal_dates":       signals["date"].nunique(),
        "tickers_in_archive": len(tickers),
        "tickers_in_cache":   len(close_map),
        "tickers_missing":    len(tickers) - len(close_map),
        "cache_end":          str(cache_end),
        "availability":       availability,
    }

    if verbose:
        print()
        print("DATA AVAILABILITY")
        print("-" * 40)
        for window, info in availability.items():
            print(
                f"  {window:>3}D : usable through {info['usable_through']}"
                f"  |  signal dates = {info['signal_dates']}"
                f"  |  rows = {info['signal_rows']}"
            )
        print()
        print(f"Tickerů načteno : {len(close_map)} / {len(tickers)}")
        if meta["tickers_missing"] > 0:
            missing = set(tickers) - set(close_map.keys())
            print(f"Chybí v cache   : {sorted(missing)}")
        print()
        print("Data Loader dokončen.")
        print("=" * 60)

    return AuditData(
        signals=signals,
        close_map=close_map,
        spy_close=spy_close,
        meta=meta,
    )


# ── Interní funkce ────────────────────────────────────────────────────────────

def _load_archive(path: Path, verbose: bool) -> pd.DataFrame:
    """Načte a validuje IMS archiv."""
    if not path.exists():
        raise FileNotFoundError(f"Archiv nenalezen: {path}")

    df = pd.read_csv(path, dtype={"date": str})

    required = {"date", "ticker", "score", "priority_group"}
    missing  = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Archivu chybí sloupce: {missing}")

    df["date"] = pd.to_datetime(df["date"]).dt.date

    # Filtruj score < 60 (nemělo by existovat, ale defensivně)
    before = len(df)
    df = df[df["score"] >= 60].copy()
    after  = len(df)
    if before != after and verbose:
        print(f"[WARN] Odstraněno {before - after} řádků se score < 60")

    if verbose:
        print(f"Archiv načten   : {len(df)} řádků | {df['date'].nunique()} dní")
        print(f"  HIGH (≥70)    : {(df['score'] >= 70).sum()}")
        print(f"  RADAR (60–69) : {((df['score'] >= 60) & (df['score'] < 70)).sum()}")

    return df.reset_index(drop=True)


def _init_access_layer(verbose: bool):
    """
    Inicializuje MDSM AccessLayer a načte universe map (ticker → conid).
    Vrátí (layer, universe_map).
    """
    # Načti IMS config pro mdsm_path a universe_csv
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.utils.config_loader import load_config
    ims_config = load_config()

    mdsm_path = ims_config.mdsm_path
    if not mdsm_path.exists():
        raise RuntimeError(f"MDSM path neexistuje: {mdsm_path}")

    # Načti universe map
    universe_csv  = Path(ims_config.universe_csv)
    universe_map  = _load_universe_map(universe_csv)

    # Init MDSM AccessLayer
    mdsm_str = str(mdsm_path)
    keys_to_remove = [k for k in sys.modules if k == "src" or k.startswith("src.")]
    for k in keys_to_remove:
        del sys.modules[k]

    if mdsm_str in sys.path:
        sys.path.remove(mdsm_str)
    sys.path.insert(0, mdsm_str)

    from src.utils.config_loader import load_config as mdsm_load_config
    from src.access.access_layer import AccessLayer

    mdsm_config = mdsm_load_config(mdsm_path / "config" / "config.yaml")
    layer = AccessLayer(mdsm_config)

    # Obnov IMS sys.path
    if mdsm_str in sys.path:
        sys.path.remove(mdsm_str)
    ims_str = str(PROJECT_ROOT)
    if ims_str not in sys.path:
        sys.path.insert(0, ims_str)

    if verbose:
        print(f"MDSM AccessLayer inicializován | universe: {len(universe_map)} tickerů")

    return layer, universe_map


def _load_universe_map(universe_csv: Path) -> dict[str, int]:
    """Vrátí {ticker: conid} mapu z universe CSV."""
    if not universe_csv.exists():
        raise FileNotFoundError(f"Universe CSV nenalezeno: {universe_csv}")

    df = pd.read_csv(universe_csv, dtype={"conid": int})
    result = {}
    for _, row in df.iterrows():
        ticker = str(row["ticker"]).strip().upper()
        result[ticker] = int(row["conid"])

    # Přidej SPY pokud není
    if SPY_TICKER not in result:
        result[SPY_TICKER] = SPY_CONID

    return result


def _fetch_ticker(
    layer,
    conid: int,
    ticker: str,
    start: date,
    end: date,
    verbose: bool,
) -> pd.Series | None:
    """Načte close series pro jeden ticker z MDSM cache."""
    try:
        df = layer.get_historical(
            conid=conid,
            start=start,
            end=end,
            timeframe="D1",
            cache_only=True,
        )
        if df is None or df.empty or "close" not in df.columns:
            return None
        series = df["close"].copy()
        series.index = pd.to_datetime(series.index)
        return series
    except Exception:
        return None


def _fetch_all_tickers(
    layer,
    tickers: list[str],
    universe_map: dict[str, int],
    start: date,
    end: date,
    verbose: bool,
) -> dict[str, pd.Series]:
    """Načte close prices pro všechny tickery z MDSM cache."""
    close_map = {}
    missing   = []

    for ticker in tickers:
        conid = universe_map.get(ticker)
        if conid is None:
            missing.append(f"{ticker} (conid neznámý)")
            continue

        series = _fetch_ticker(layer, conid, ticker, start, end, verbose=False)
        if series is not None:
            close_map[ticker] = series
        else:
            missing.append(ticker)

    if missing and verbose:
        print(f"[WARN] Tickerů bez dat v cache: {len(missing)}")
        if len(missing) <= 10:
            for t in missing:
                print(f"  {t}")

    return close_map


def _compute_availability(
    signal_end: date,
    cache_end: date,
) -> dict[int, dict]:
    """
    Vypočítá dostupnost dat per forward window.
    Usable through = poslední signal date pro který existují forward data.
    Aproximace: 1 obchodní den ≈ 1.4 kalendářního dne.
    """
    result = {}
    for window in FORWARD_WINDOWS:
        # Kalendářní buffer pro daný window (konzervativní odhad)
        cal_days    = int(window * 1.5) + 5
        usable_date = cache_end - timedelta(days=cal_days)
        # Ořeže na signal_end pokud je dřívější
        usable_date = min(usable_date, signal_end)
        result[window] = {
            "usable_through": str(usable_date),
            # Přesné počty se vypočítají v forward_returns.py kde jsou reálná data
            "signal_dates":   "TBD",
            "signal_rows":    "TBD",
        }
    return result


# ── Helper pro audit testy ────────────────────────────────────────────────────

def get_forward_price(
    close_map: dict[str, pd.Series],
    ticker: str,
    signal_date: date,
    window: int,
) -> float | None:
    """
    Vrátí close price N obchodních dní po signal_date.

    Args:
        close_map:   dict[ticker, pd.Series]
        ticker:      ticker symbol
        signal_date: datum signálu (entry close = close na signal_date)
        window:      počet obchodních dní dopředu

    Returns:
        float close price nebo None pokud data nejsou dostupná
    """
    series = close_map.get(ticker)
    if series is None:
        return None

    signal_ts = pd.Timestamp(signal_date)
    future    = series[series.index > signal_ts]

    if len(future) < window:
        return None

    return float(future.iloc[window - 1])


def get_entry_price(
    close_map: dict[str, pd.Series],
    ticker: str,
    signal_date: date,
) -> float | None:
    """
    Vrátí close price na signal_date (entry price).
    """
    series = close_map.get(ticker)
    if series is None:
        return None

    signal_ts = pd.Timestamp(signal_date)
    day_data  = series[series.index == signal_ts]

    if day_data.empty:
        # Zkus nejbližší předchozí den
        before = series[series.index <= signal_ts]
        if before.empty:
            return None
        return float(before.iloc[-1])

    return float(day_data.iloc[0])


def get_window_low(
    close_map: dict[str, pd.Series],
    ticker: str,
    signal_date: date,
    window: int,
) -> float | None:
    """
    Vrátí nejnižší close price v okně D+1 až D+window.
    Používá se pro entry-to-low drawdown výpočet.
    """
    series = close_map.get(ticker)
    if series is None:
        return None

    signal_ts = pd.Timestamp(signal_date)
    future    = series[series.index > signal_ts]

    if len(future) < window:
        return None

    return float(future.iloc[:window].min())
