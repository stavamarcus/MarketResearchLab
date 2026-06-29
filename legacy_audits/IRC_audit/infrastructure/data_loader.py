"""
Industry Rank Calendar Audit — Data Loader
audit/data_loader.py

Zodpovědnost:
    Načíst Industry Rank Calendar archiv a přiřadit každému tickeru
    v S&P 500 universe jeho industry kontext pro každý signal date.
    Načíst close prices z MDSM cache pro výpočet forward returns.

Signálový řádek obsahuje:
    date, ticker, industry, industry_rank, industry_persist,
    industry_members, advance_ratio, is_new_entrant

    is_new_entrant = True pokud industry vstoupila do TOP10 poprvé
                     (nebyla v TOP10 předchozí den)
    advance_ratio  = Adv% z archivu (% členů s kladným returnem)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# ── Cesty ────────────────────────────────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).resolve().parents[1]
ARCHIVE_PATH   = PROJECT_ROOT / "output" / "archive" / "industry_rank_calendar_archive.csv"
UNIVERSE_CSV   = Path("C:/Users/stava/Projects/MDSM-Lite/data/universe/sp500_rank_calendar_universe.csv")
MDSM_PATH      = Path("C:/Users/stava/Projects/MDSM-Lite")

SPY_CONID      = 756733
SPY_TICKER     = "SPY"
INDUSTRY_LOOKBACK = 20

FORWARD_WINDOWS = [5, 10, 20, 30]
PERSIST_WINDOW  = 20
PERSIST_TOP_N   = 10
NEW_ENTRANT_TOP_N = 10   # vstup do TOP10 = New Entrant


@dataclass
class AuditData:
    signals:   pd.DataFrame
    close_map: dict[str, pd.Series]
    spy_close: pd.Series
    meta:      dict


def load_audit_data(verbose: bool = True) -> AuditData:
    if verbose:
        print("=" * 60)
        print("INDUSTRY RANK CALENDAR AUDIT — DATA LOADER")
        print("=" * 60)

    arch_df  = _load_archive(verbose)
    universe = _load_universe(verbose)
    signals  = _build_signals(arch_df, universe, verbose)

    if signals.empty:
        raise RuntimeError("Signály jsou prázdné.")

    layer = _init_access_layer(verbose)

    signal_start = signals["date"].min()
    signal_end   = signals["date"].max()

    if verbose:
        print(f"Signal rozsah : {signal_start} → {signal_end}")

    spy_close = _fetch_ticker(layer, SPY_CONID, SPY_TICKER, signal_start, signal_end)
    if spy_close is None:
        raise RuntimeError("SPY data nejsou dostupná.")

    tickers   = sorted(signals["ticker"].unique().tolist())
    close_map = _fetch_all_tickers(layer, tickers, universe, signal_start, signal_end, verbose)

    cache_end = spy_close.index.max().date()

    meta = {
        "signal_date_min":     str(signal_start),
        "signal_date_max":     str(signal_end),
        "signal_rows":         len(signals),
        "signal_dates":        signals["date"].nunique(),
        "tickers_in_universe": len(tickers),
        "tickers_in_cache":    len(close_map),
        "tickers_missing":     len(tickers) - len(close_map),
        "industries":          signals["industry"].nunique(),
        "new_entrant_rows":    int(signals["is_new_entrant"].sum()),
        "cache_end":           str(cache_end),
    }

    if verbose:
        print(f"Tickerů načteno : {len(close_map)} / {len(tickers)}")
        print(f"Industries      : {meta['industries']}")
        print(f"New Entrant řádků: {meta['new_entrant_rows']}")
        print()
        print("Data Loader dokončen.")
        print("=" * 60)

    return AuditData(signals=signals, close_map=close_map, spy_close=spy_close, meta=meta)


# ── Interní funkce ────────────────────────────────────────────────────────────

def _load_archive(verbose: bool) -> pd.DataFrame:
    if not ARCHIVE_PATH.exists():
        raise FileNotFoundError(f"Archiv nenalezen: {ARCHIVE_PATH}")

    df = pd.read_csv(ARCHIVE_PATH, dtype={"date": str, "lookback": str})
    df = df[df["lookback"].astype(str) == str(INDUSTRY_LOOKBACK)].copy()

    required = {"date", "lookback", "rank", "industry", "member_count", "status", "advance_ratio"}
    missing  = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Archivu chybí sloupce: {missing}")

    df["date"]          = pd.to_datetime(df["date"]).dt.date
    df["rank"]          = pd.to_numeric(df["rank"], errors="coerce").astype("Int64")
    df["advance_ratio"] = pd.to_numeric(df["advance_ratio"], errors="coerce")
    df["member_count"]  = pd.to_numeric(df["member_count"], errors="coerce").astype("Int64")
    df = df[df["status"] == "OK"].copy()

    if verbose:
        print(f"Archiv načten   : {len(df)} řádků | {df['date'].nunique()} dní | "
              f"{df['industry'].nunique()} industry skupin")

    return df.reset_index(drop=True)


def _load_universe(verbose: bool) -> pd.DataFrame:
    if not UNIVERSE_CSV.exists():
        raise FileNotFoundError(f"Universe CSV nenalezeno: {UNIVERSE_CSV}")

    df = pd.read_csv(UNIVERSE_CSV)
    df["ticker"]   = df["ticker"].astype(str).str.strip().str.upper()
    df["industry"] = df["industry"].astype(str).str.strip()
    df["conid"]    = df["conid"].astype(int)
    df = df[~df["industry"].isin(["", "nan", "none"])].copy()

    spy_row = pd.DataFrame([{"ticker": SPY_TICKER, "conid": SPY_CONID, "industry": ""}])
    df = pd.concat([df, spy_row], ignore_index=True)

    if verbose:
        print(f"Universe načteno: {len(df) - 1} tickerů s industry metadata")

    return df


def _build_signals(arch_df: pd.DataFrame, universe: pd.DataFrame, verbose: bool) -> pd.DataFrame:
    """
    Sestaví signály: date × ticker × industry kontext.
    Přidává: industry_rank, industry_persist, advance_ratio, is_new_entrant.
    """
    ticker_to_industry = dict(zip(universe["ticker"], universe["industry"]))

    # date × industry → { rank, advance_ratio, members }
    date_ctx: dict[date, dict[str, dict]] = {}
    for _, row in arch_df.iterrows():
        d   = row["date"]
        ind = str(row["industry"])
        if d not in date_ctx:
            date_ctx[d] = {}
        date_ctx[d][ind] = {
            "rank":          int(row["rank"]) if pd.notna(row["rank"]) else 999,
            "advance_ratio": float(row["advance_ratio"]) if pd.notna(row["advance_ratio"]) else None,
            "members":       int(row["member_count"]) if pd.notna(row["member_count"]) else None,
        }

    all_dates = sorted(date_ctx.keys())

    # Persistence per (date, industry)
    persist_map: dict[tuple[date, str], int] = {}
    for i, d in enumerate(all_dates):
        window_dates = all_dates[max(0, i - PERSIST_WINDOW + 1): i + 1]
        for ind in date_ctx[d]:
            count = sum(
                1 for wd in window_dates
                if date_ctx.get(wd, {}).get(ind, {}).get("rank", 999) <= PERSIST_TOP_N
            )
            persist_map[(d, ind)] = count

    # New Entrant: industry vstoupila do TOP{NEW_ENTRANT_TOP_N} dnes,
    # ale včera v TOP{NEW_ENTRANT_TOP_N} nebyla
    new_entrant_set: set[tuple[date, str]] = set()
    for i, d in enumerate(all_dates):
        if i == 0:
            continue
        prev_d = all_dates[i - 1]
        today_top  = {ind for ind, ctx in date_ctx[d].items()         if ctx["rank"] <= NEW_ENTRANT_TOP_N}
        prev_top   = {ind for ind, ctx in date_ctx.get(prev_d, {}).items() if ctx["rank"] <= NEW_ENTRANT_TOP_N}
        for ind in today_top - prev_top:
            new_entrant_set.add((d, ind))

    # Sestav řádky
    tickers = [t for t in universe["ticker"].tolist() if t != SPY_TICKER]
    rows = []

    for d in all_dates:
        ctx_today = date_ctx.get(d, {})
        for ticker in tickers:
            industry = ticker_to_industry.get(ticker, "")
            if not industry or industry.lower() in ("nan", "none", ""):
                continue

            ctx = ctx_today.get(industry)
            if ctx is None:
                continue

            ind_rank   = ctx["rank"]
            adv_ratio  = ctx["advance_ratio"]
            members    = ctx["members"]
            persist    = persist_map.get((d, industry), 0)
            is_new     = (d, industry) in new_entrant_set

            rows.append({
                "date":            d,
                "ticker":          ticker,
                "industry":        industry,
                "industry_rank":   ind_rank,
                "industry_persist": persist,
                "industry_members": members,
                "advance_ratio":   adv_ratio,
                "is_new_entrant":  is_new,
            })

    df = pd.DataFrame(rows)

    if verbose:
        print(f"Signálů sestaveno: {len(df)} "
              f"({df['date'].nunique()} dní × ~{len(tickers)} tickerů)")

    return df.reset_index(drop=True)


def _init_access_layer(verbose: bool):
    mdsm_str = str(MDSM_PATH)
    keys_to_remove = [k for k in sys.modules if k == "src" or k.startswith("src.")]
    for k in keys_to_remove:
        del sys.modules[k]
    if mdsm_str not in sys.path:
        sys.path.insert(0, mdsm_str)

    from src.utils.config_loader import load_config
    from src.access.access_layer import AccessLayer

    config = load_config(MDSM_PATH / "config" / "config.yaml")
    layer  = AccessLayer(config)
    if verbose:
        print("MDSM AccessLayer inicializován")
    return layer


def _fetch_ticker(layer, conid: int, ticker: str, start: date, end: date) -> pd.Series | None:
    try:
        df = layer.get_historical(conid=conid, start=start, end=end, cache_only=True)
        if df is None or df.empty or "close" not in df.columns:
            return None
        s = df["close"].copy()
        s.index = pd.to_datetime(s.index)
        return s
    except Exception:
        return None


def _fetch_all_tickers(layer, tickers, universe, start, end, verbose) -> dict:
    conid_map = dict(zip(universe["ticker"], universe["conid"]))
    close_map = {}
    missing   = []
    for ticker in tickers:
        conid = conid_map.get(ticker)
        if conid is None:
            missing.append(ticker)
            continue
        s = _fetch_ticker(layer, int(conid), ticker, start, end)
        if s is not None:
            close_map[ticker] = s
        else:
            missing.append(ticker)
    if missing and verbose:
        print(f"[WARN] Tickerů bez dat v cache: {len(missing)}")
    return close_map


# ── Forward price helpers ─────────────────────────────────────────────────────

def get_entry_price(close_map: dict, ticker: str, signal_date: date) -> float | None:
    s = close_map.get(ticker)
    if s is None:
        return None
    ts     = pd.Timestamp(signal_date)
    on_day = s[s.index == ts]
    if not on_day.empty:
        return float(on_day.iloc[0])
    before = s[s.index <= ts]
    return float(before.iloc[-1]) if not before.empty else None


def get_forward_price(close_map: dict, ticker: str, signal_date: date, window: int) -> float | None:
    s = close_map.get(ticker)
    if s is None:
        return None
    future = s[s.index > pd.Timestamp(signal_date)]
    return float(future.iloc[window - 1]) if len(future) >= window else None


def get_window_low(close_map: dict, ticker: str, signal_date: date, window: int) -> float | None:
    s = close_map.get(ticker)
    if s is None:
        return None
    future = s[s.index > pd.Timestamp(signal_date)]
    return float(future.iloc[:window].min()) if len(future) >= window else None
