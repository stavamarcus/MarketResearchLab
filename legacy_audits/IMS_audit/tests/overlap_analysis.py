"""
IMS Audit v3 — IMS × MLE Overlap Analysis
audit/tests/overlap_analysis.py

Zodpovědnost:
    Sestavit signálové skupiny z IMS a MLE archivů.
    Vypočítat forward returns pro každou skupinu.
    Porovnat: IMS only, MLE only, IMS ∩ MLE, IMS ELITE, IMS ELITE ∩ MLE.

Definice signálů:
    IMS signal    : score >= 60
    IMS ELITE     : 90 <= score < 95
    MLE signal    : rank_10d <= 50
    Overlap       : stejný date + ticker v IMS i MLE TOP50

Výstup:
    signals_df  — jeden řádek per (date, ticker) s group labelem
    summary_df  — agregované metriky per (group, window)
"""

from __future__ import annotations

from pathlib import Path
from datetime import date

import pandas as pd

# Cesty
PROJECT_ROOT     = Path(__file__).resolve().parents[2]
IMS_ARCHIVE      = PROJECT_ROOT / "output" / "archive" / "ims_candidates_archive.csv"
MLE_ARCHIVE_PATH = Path("C:/Users/stava/Projects/MarketLeadershipEngine/output/archive/rank_matrix_archive.csv")
SPY_TICKER       = "SPY"

FORWARD_WINDOWS  = [5, 10, 20, 30]

# Skupiny
GROUPS = [
    "IMS_only",
    "MLE_only",
    "IMS_MLE",
    "IMS_ELITE",
    "IMS_ELITE_MLE",
]


def load_signals(
    ims_archive:  Path = IMS_ARCHIVE,
    mle_archive:  Path = MLE_ARCHIVE_PATH,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Načte IMS a MLE archivy, sestaví signálové skupiny.

    Returns:
        DataFrame s sloupci: date, ticker, group
        Jeden ticker může být ve více skupinách → více řádků.
    """
    # ── IMS ──────────────────────────────────────────────────────────
    ims = pd.read_csv(ims_archive, dtype={"date": str})
    ims["date"] = pd.to_datetime(ims["date"]).dt.date
    ims = ims[ims["score"] >= 60][["date", "ticker", "score"]].copy()

    # ── MLE ──────────────────────────────────────────────────────────
    mle = pd.read_csv(mle_archive, dtype={"date": str})
    mle["date"] = pd.to_datetime(mle["date"]).dt.date
    mle_top50 = mle[mle["rank_10d"] <= 50][["date", "ticker"]].copy()
    mle_top50["in_mle"] = True

    # ── Merge ─────────────────────────────────────────────────────────
    merged = ims.merge(mle_top50, on=["date", "ticker"], how="outer")
    merged["in_ims"]   = merged["score"].notna()
    merged["in_mle"]   = merged["in_mle"].fillna(False)
    merged["is_elite"] = (merged["score"] >= 90) & (merged["score"] < 95)

    # Omez na dny kde oba archivy existují
    ims_dates = set(ims["date"].unique())
    mle_dates = set(mle_top50["date"].unique())
    common_dates = ims_dates & mle_dates

    if verbose:
        print(f"IMS dní          : {len(ims_dates)}")
        print(f"MLE dní          : {len(mle_dates)}")
        print(f"Společných dní   : {len(common_dates)}")

    merged = merged[merged["date"].isin(common_dates)].copy()

    # ── Sestavení skupin ──────────────────────────────────────────────
    rows = []

    for _, row in merged.iterrows():
        in_ims   = bool(row["in_ims"])
        in_mle   = bool(row["in_mle"])
        is_elite = bool(row.get("is_elite", False))
        ticker   = row["ticker"]
        dt       = row["date"]
        score    = row["score"] if not pd.isna(row.get("score", float("nan"))) else None

        if in_ims and not in_mle:
            rows.append({"date": dt, "ticker": ticker, "group": "IMS_only", "score": score})
        if in_mle and not in_ims:
            rows.append({"date": dt, "ticker": ticker, "group": "MLE_only", "score": None})
        if in_ims and in_mle:
            rows.append({"date": dt, "ticker": ticker, "group": "IMS_MLE", "score": score})
        if is_elite:
            rows.append({"date": dt, "ticker": ticker, "group": "IMS_ELITE", "score": score})
        if is_elite and in_mle:
            rows.append({"date": dt, "ticker": ticker, "group": "IMS_ELITE_MLE", "score": score})

    signals = pd.DataFrame(rows)

    if verbose:
        print()
        print("SIGNÁLY PER SKUPINA:")
        for g in GROUPS:
            n = len(signals[signals["group"] == g])
            n_dates = signals[signals["group"] == g]["date"].nunique()
            print(f"  {g:<20} : {n:>6} řádků  |  {n_dates} dní")

    return signals


def compute_group_returns(
    signals:   pd.DataFrame,
    close_map: dict[str, pd.Series],
    spy_close: pd.Series,
    verbose:   bool = True,
) -> pd.DataFrame:
    """
    Vypočítá forward returns pro každý signál.

    Returns:
        DataFrame — jeden řádek per (date, ticker, group)
    """
    rows = []

    for _, sig in signals.iterrows():
        ticker = sig["ticker"]
        dt     = sig["date"]
        group  = sig["group"]

        entry_close = _get_price(close_map, ticker, dt, offset=0)
        spy_entry   = _get_price({"SPY": spy_close}, SPY_TICKER, dt, offset=0)

        if entry_close is None or spy_entry is None or entry_close <= 0 or spy_entry <= 0:
            continue

        row = {
            "date":   dt,
            "ticker": ticker,
            "group":  group,
            "score":  sig.get("score"),
            "entry":  round(entry_close, 4),
        }

        for window in FORWARD_WINDOWS:
            fwd_price = _get_price(close_map, ticker, dt, offset=window)
            spy_fwd   = _get_price({"SPY": spy_close}, SPY_TICKER, dt, offset=window)
            low_price = _get_window_low(close_map, ticker, dt, window)

            if fwd_price is not None and spy_fwd is not None and low_price is not None:
                fwd_ret  = (fwd_price / entry_close - 1) * 100
                spy_ret  = (spy_fwd   / spy_entry   - 1) * 100
                alpha    = fwd_ret - spy_ret
                drawdown = (low_price / entry_close - 1) * 100

                row[f"fwd_{window}d"]   = round(fwd_ret, 4)
                row[f"spy_{window}d"]   = round(spy_ret, 4)
                row[f"alpha_{window}d"] = round(alpha, 4)
                row[f"dd_{window}d"]    = round(drawdown, 4)
                row[f"ok_{window}d"]    = True
            else:
                row[f"fwd_{window}d"]   = None
                row[f"spy_{window}d"]   = None
                row[f"alpha_{window}d"] = None
                row[f"dd_{window}d"]    = None
                row[f"ok_{window}d"]    = False

        rows.append(row)

    df = pd.DataFrame(rows)

    if verbose:
        print()
        print("USABLE ROWS PER SKUPINA A WINDOW:")
        for g in GROUPS:
            sub = df[df["group"] == g]
            parts = []
            for w in FORWARD_WINDOWS:
                col = f"ok_{w}d"
                if col in sub.columns:
                    parts.append(f"{w}D={int(sub[col].sum())}")
            print(f"  {g:<20} : {' | '.join(parts)}")

    return df


def aggregate_summary(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Agreguje metriky per (group, window).
    """
    rows = []

    for group in GROUPS:
        sub = results_df[results_df["group"] == group]
        if sub.empty:
            continue

        for window in FORWARD_WINDOWS:
            col_fwd   = f"fwd_{window}d"
            col_alpha = f"alpha_{window}d"
            col_dd    = f"dd_{window}d"
            col_ok    = f"ok_{window}d"

            if col_ok not in sub.columns:
                continue

            usable     = sub[sub[col_ok] == True]
            fwd_vals   = usable[col_fwd].dropna()
            alpha_vals = usable[col_alpha].dropna()
            dd_vals    = usable[col_dd].dropna()

            if len(fwd_vals) < 5:
                continue

            rows.append({
                "group":           group,
                "window":          f"{window}D",
                "n":               len(fwd_vals),
                "avg_return":      round(fwd_vals.mean(), 4),
                "median_return":   round(fwd_vals.median(), 4),
                "win_rate":        round((fwd_vals > 0).mean() * 100, 2),
                "avg_alpha":       round(alpha_vals.mean(), 4),
                "median_alpha":    round(alpha_vals.median(), 4),
                "alpha_win_rate":  round((alpha_vals > 0).mean() * 100, 2),
                "avg_drawdown":    round(dd_vals.mean(), 4),
            })

    return pd.DataFrame(rows)


def format_report(summary: pd.DataFrame, run_date: date) -> list[str]:
    lines = []
    lines += [
        "=" * 70,
        "IMS AUDIT v3 — IMS × MLE OVERLAP ANALYSIS",
        f"Datum reportu : {run_date}",
        "=" * 70,
        "",
        "Definice signálů:",
        "  IMS signal     : score >= 60",
        "  IMS ELITE      : 90 <= score < 95",
        "  MLE signal     : rank_10d <= 50 (TOP50 momentum)",
        "  Overlap        : stejný date + ticker v IMS i MLE",
        "",
        "Skupiny:",
        "  IMS_only       : IMS signal, NENÍ v MLE TOP50",
        "  MLE_only       : MLE TOP50, NENÍ v IMS",
        "  IMS_MLE        : průnik IMS ∩ MLE TOP50",
        "  IMS_ELITE      : IMS score 90-94",
        "  IMS_ELITE_MLE  : IMS ELITE ∩ MLE TOP50",
        "",
    ]

    group_order = GROUPS

    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = summary[summary["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 70)
        lines.append(
            f"  {'Skupina':<20} {'N':>6} {'AvgRet':>8} {'MedRet':>8} "
            f"{'WinRate':>8} {'AvgAlpha':>10} {'MedAlpha':>10} "
            f"{'AlphaWR':>8} {'AvgDD':>8}"
        )
        lines.append(
            f"  {'-'*20} {'-'*6} {'-'*8} {'-'*8} "
            f"{'-'*8} {'-'*10} {'-'*10} "
            f"{'-'*8} {'-'*8}"
        )

        for group in group_order:
            row = sub[sub["group"] == group]
            if row.empty:
                continue
            r = row.iloc[0]
            lines.append(
                f"  {group:<20} {int(r['n']):>6} "
                f"{r['avg_return']:>+7.2f}% {r['median_return']:>+7.2f}% "
                f"{r['win_rate']:>7.1f}% "
                f"{r['avg_alpha']:>+9.2f}% {r['median_alpha']:>+9.2f}% "
                f"{r['alpha_win_rate']:>7.1f}% "
                f"{r['avg_drawdown']:>+7.2f}%"
            )

        lines.append("")

    # Závěr
    lines += [
        "=" * 70,
        "INTERPRETACE",
        "=" * 70,
        "",
        "  Pokud IMS_MLE > IMS_only a MLE_only:",
        "  průnik má additivní hodnotu — oba filtry se doplňují.",
        "",
        "  Pokud IMS_ELITE_MLE > IMS_ELITE:",
        "  MLE TOP50 potvrzení zlepšuje výsledky ELITE skupiny.",
        "  → Kandidát na sekci BEST IDEAS v denním reportu.",
        "",
        "  Pokud průnik není lepší než každý modul zvlášť:",
        "  MLE a IMS měří různé věci — kombinace nepřidává hodnotu.",
        "",
        "OMEZENÍ:",
        "  - Společné dny jsou omezeny překryvem obou archivů.",
        "  - Jeden tržní cyklus 2025-2026.",
        "  - IMS_ELITE_MLE může mít malý N — interpretovat opatrně.",
        "",
        "=" * 70,
    ]

    return lines


# ── Price helpers ─────────────────────────────────────────────────────────────

def _get_price(
    close_map: dict[str, pd.Series],
    ticker: str,
    signal_date: date,
    offset: int,
) -> float | None:
    series = close_map.get(ticker)
    if series is None:
        return None
    signal_ts = pd.Timestamp(signal_date)
    if offset == 0:
        day = series[series.index <= signal_ts]
        return float(day.iloc[-1]) if not day.empty else None
    future = series[series.index > signal_ts]
    if len(future) < offset:
        return None
    return float(future.iloc[offset - 1])


def _get_window_low(
    close_map: dict[str, pd.Series],
    ticker: str,
    signal_date: date,
    window: int,
) -> float | None:
    series = close_map.get(ticker)
    if series is None:
        return None
    signal_ts = pd.Timestamp(signal_date)
    future = series[series.index > signal_ts]
    if len(future) < window:
        return None
    return float(future.iloc[:window].min())
