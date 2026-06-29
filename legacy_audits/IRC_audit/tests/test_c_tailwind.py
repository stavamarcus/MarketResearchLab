"""
Industry Rank Calendar Audit — Test C
audit/tests/test_c_tailwind.py

Otázka:
    Mají IMS/MLE kandidáti z TOP10 industry lepší forward returns
    než kandidáti z slabších industry skupin?

    Jinými slovy: přidává "vítr v zádech" od industry edge na TOP signálech?

Metodologie:
    - Načte IMS a MLE archivy
    - Každému tickeru přiřadí industry rank z Industry Rank Calendar archivu
    - Rozdělí na skupiny:
        TAILWIND  : industry_rank R1-10
        HEADWIND  : industry_rank R11+
    - Porovná forward returns a alpha per skupina

Hypotéza:
    H0: industry tailwind nepřidává alpha na IMS/MLE kandidátech
    H1: IMS/MLE kandidáti s tailwindem (R1-10) dosahují vyšší alpha než bez tailwindu

Interpretace:
    Pokud TAILWIND > HEADWIND o >1% alpha → industry kontext má smysl jako filtr
    Pokud rozdíl je zanedbatelný → industry rank nefunguje jako filtr, jen jako popis
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FORWARD_WINDOWS = [5, 10, 20, 30]

PROJECTS_BASE  = Path("C:/Users/stava/Projects")
IMS_ARCHIVE    = PROJECTS_BASE / "InstitutionalMomentumScanner/output/archive/ims_candidates_archive.csv"
MLE_ARCHIVE    = PROJECTS_BASE / "MarketLeadershipEngine/output/archive/rank_matrix_archive.csv"
IND_ARCHIVE    = PROJECTS_BASE / "industry_rank_calendar/output/archive/industry_rank_calendar_archive.csv"

TAILWIND_THRESHOLD = 10   # R1-10 = tailwind


def load_candidate_signals(verbose: bool = True) -> pd.DataFrame:
    """
    Načte IMS HIGH/ELITE a MLE TOP20 signály a přiřadí jim industry rank.
    Vrátí DataFrame: date, ticker, source, industry, industry_rank
    """
    rows = []

    # IMS signály (HIGH + ELITE)
    if IMS_ARCHIVE.exists():
        ims = pd.read_csv(IMS_ARCHIVE, dtype={"date": str})
        ims["date"] = pd.to_datetime(ims["date"]).dt.date
        ims_filtered = ims[ims["score"] >= 70].copy()
        for _, row in ims_filtered.iterrows():
            rows.append({
                "date":     row["date"],
                "ticker":   str(row["ticker"]),
                "source":   "IMS",
                "industry": str(row.get("industry", "") or ""),
            })
        if verbose:
            print(f"IMS signálů (HIGH/ELITE): {len(ims_filtered)}")

    # MLE TOP20 signály
    if MLE_ARCHIVE.exists():
        mle = pd.read_csv(MLE_ARCHIVE, dtype={"date": str, "sector": str, "industry": str, "subcategory": str})
        mle["date"] = pd.to_datetime(mle["date"]).dt.date
        mle_filtered = mle[mle["rank_10d"] <= 20].copy()
        for _, row in mle_filtered.iterrows():
            rows.append({
                "date":     row["date"],
                "ticker":   str(row["ticker"]),
                "source":   "MLE",
                "industry": str(row.get("industry", "") or ""),
            })
        if verbose:
            print(f"MLE TOP20 signálů: {len(mle_filtered)}")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df[df["industry"].str.lower().notna()].copy()
    df = df[~df["industry"].isin(["", "nan", "none"])].copy()

    # Přiřaď industry rank z IND_ARCHIVE (20D lookback)
    if IND_ARCHIVE.exists():
        ind = pd.read_csv(IND_ARCHIVE, dtype={"date": str, "lookback": str})
        ind = ind[ind["lookback"].astype(str) == "20"].copy()
        ind["date"] = pd.to_datetime(ind["date"]).dt.date
        ind = ind[ind["status"] == "OK"].copy()

        # date × industry → rank
        ind_map = {}
        for _, row in ind.iterrows():
            ind_map[(row["date"], row["industry"])] = int(row["rank"])

        df["industry_rank"] = df.apply(
            lambda r: ind_map.get((r["date"], r["industry"])),
            axis=1
        )
    else:
        df["industry_rank"] = None

    # Filtruj řádky bez industry_rank
    df = df[df["industry_rank"].notna()].copy()
    df["industry_rank"] = df["industry_rank"].astype(int)

    if verbose:
        print(f"Signálů s industry rank: {len(df)}")
        tailwind = (df["industry_rank"] <= TAILWIND_THRESHOLD).sum()
        headwind = (df["industry_rank"] > TAILWIND_THRESHOLD).sum()
        print(f"  TAILWIND (R1-{TAILWIND_THRESHOLD}): {tailwind}")
        print(f"  HEADWIND (R{TAILWIND_THRESHOLD+1}+): {headwind}")

    return df.reset_index(drop=True)


def run(
    candidate_df: pd.DataFrame,
    close_map: dict,
    spy_close,
) -> pd.DataFrame:
    """
    Vypočítá forward returns pro IMS/MLE kandidáty rozdělené na tailwind/headwind.

    Args:
        candidate_df: výstup z load_candidate_signals()
        close_map:    dict[ticker, pd.Series] z data_loader
        spy_close:    pd.Series SPY

    Returns:
        pd.DataFrame s forward returns a tailwind/headwind skupinou
    """
    from audit.data_loader import get_entry_price, get_forward_price, get_window_low

    spy_map = {"SPY": spy_close}
    rows    = []

    for _, signal in candidate_df.iterrows():
        ticker      = signal["ticker"]
        signal_date = signal["date"]
        ind_rank    = signal["industry_rank"]
        group       = "TAILWIND" if ind_rank <= TAILWIND_THRESHOLD else "HEADWIND"

        entry_price = get_entry_price(close_map, ticker, signal_date)
        if entry_price is None or entry_price <= 0:
            continue

        spy_entry = get_entry_price(spy_map, "SPY", signal_date)
        if spy_entry is None or spy_entry <= 0:
            continue

        row = {
            "date":          signal_date,
            "ticker":        ticker,
            "source":        signal["source"],
            "industry":      signal["industry"],
            "industry_rank": ind_rank,
            "group":         group,
            "entry_price":   round(entry_price, 4),
        }

        for window in FORWARD_WINDOWS:
            fwd_price = get_forward_price(close_map, ticker, signal_date, window)
            spy_price = get_forward_price(spy_map, "SPY", signal_date, window)
            low_price = get_window_low(close_map, ticker, signal_date, window)

            if fwd_price and spy_price and low_price:
                fwd_ret  = (fwd_price / entry_price - 1) * 100
                spy_ret  = (spy_price / spy_entry - 1) * 100
                row[f"fwd_{window}d"]    = round(fwd_ret, 4)
                row[f"alpha_{window}d"]  = round(fwd_ret - spy_ret, 4)
                row[f"dd_{window}d"]     = round((low_price / entry_price - 1) * 100, 4)
                row[f"usable_{window}d"] = True
            else:
                row[f"fwd_{window}d"]    = None
                row[f"alpha_{window}d"]  = None
                row[f"dd_{window}d"]     = None
                row[f"usable_{window}d"] = False

        rows.append(row)

    return pd.DataFrame(rows)


def aggregate(forward_df: pd.DataFrame) -> pd.DataFrame:
    """Agreguje forward returns per group (TAILWIND/HEADWIND) a window."""
    rows = []

    for group in ("TAILWIND", "HEADWIND"):
        subset = forward_df[forward_df["group"] == group].copy()
        if subset.empty:
            continue

        for window in FORWARD_WINDOWS:
            col_fwd   = f"fwd_{window}d"
            col_alpha = f"alpha_{window}d"
            col_dd    = f"dd_{window}d"
            col_use   = f"usable_{window}d"

            if col_use not in subset.columns:
                continue

            usable = subset[subset[col_use] == True]
            if usable.empty:
                continue

            fwd_vals   = usable[col_fwd].dropna()
            alpha_vals = usable[col_alpha].dropna()
            dd_vals    = usable[col_dd].dropna()

            if len(fwd_vals) < 1:
                continue

            rows.append({
                "group":         group,
                "window":        f"{window}D",
                "n":             len(fwd_vals),
                "avg_return":    round(fwd_vals.mean(), 4),
                "median_return": round(fwd_vals.median(), 4),
                "win_rate":      round((fwd_vals > 0).mean() * 100, 2),
                "avg_alpha":     round(alpha_vals.mean(), 4) if not alpha_vals.empty else None,
                "avg_drawdown":  round(dd_vals.mean(), 4) if not dd_vals.empty else None,
            })

    return pd.DataFrame(rows)


def format_report(agg_df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST C — INDUSTRY TAILWIND EFFECT (IMS + MLE KANDIDATI)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Prida 'vitr v zadech' (industry R1-10) edge na TOP signalech?")
    lines.append(f"TAILWIND = industry_rank R1-{TAILWIND_THRESHOLD}")
    lines.append(f"HEADWIND = industry_rank R{TAILWIND_THRESHOLD+1}+")
    lines.append("Zdroje  : IMS HIGH/ELITE + MLE TOP20")
    lines.append("")

    if agg_df.empty or "window" not in agg_df.columns:
        lines.append("  Nedostatek dat pro Test C (malo kandidatu s industry_rank).")
        lines.append("")
        return lines

    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = agg_df[agg_df["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 70)
        lines.append(
            f"  {'Skupina':<12}  {'N':>6}  {'Avg%':>8}  {'Med%':>8}  "
            f"{'WinRate':>8}  {'AvgAlpha':>9}  {'AvgDD%':>8}"
        )
        lines.append(
            f"  {'-'*12}  {'-'*6}  {'-'*8}  {'-'*8}  "
            f"{'-'*8}  {'-'*9}  {'-'*8}"
        )

        for group in ("TAILWIND", "HEADWIND"):
            row = sub[sub["group"] == group]
            if row.empty:
                continue
            r = row.iloc[0]

            alpha_str = f"{r['avg_alpha']:>+8.2f}%" if r["avg_alpha"] is not None else "      N/A"
            dd_str    = f"{r['avg_drawdown']:>+7.2f}%" if r["avg_drawdown"] is not None else "     N/A"

            lines.append(
                f"  {group:<12}  {int(r['n']):>6}  "
                f"{r['avg_return']:>+7.2f}%  {r['median_return']:>+7.2f}%  "
                f"{r['win_rate']:>7.1f}%  {alpha_str}  {dd_str}"
            )

        # Delta TAILWIND - HEADWIND
        tw = sub[sub["group"] == "TAILWIND"]
        hw = sub[sub["group"] == "HEADWIND"]
        if not tw.empty and not hw.empty:
            delta_ret   = tw.iloc[0]["avg_return"] - hw.iloc[0]["avg_return"]
            delta_alpha = (tw.iloc[0]["avg_alpha"] or 0) - (hw.iloc[0]["avg_alpha"] or 0)
            sign = "+" if delta_ret >= 0 else ""
            lines.append(
                f"  {'DELTA':12}  {'':>6}  {sign}{delta_ret:>7.2f}%  {'':>8}  "
                f"{'':>8}  {'+' if delta_alpha >= 0 else ''}{delta_alpha:>8.2f}%"
            )

        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  DELTA avg_return > +1% = tailwind prida measurable edge")
    lines.append("  DELTA avg_alpha  > +1% = prida alpha nad SPY")
    lines.append("  DELTA blizko 0  = industry rank nema vliv na vysledky signalu")
    lines.append("")

    return lines
