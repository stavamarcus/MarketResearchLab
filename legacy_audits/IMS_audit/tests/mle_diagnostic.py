"""
IMS Audit v4 — MLE_only Diagnostic
audit/tests/mle_diagnostic.py

Cíl:
    Zjistit proč MLE TOP50 poráží IMS × MLE.
    Analyzovat co IMS filtry vyřazují z MLE TOP50.

Testy:
    A — ret_10d distribuce u MLE TOP50
    B — IMS filter breakdown pro MLE TOP50
    C — MLE ∩ IMS vs MLE_only porovnání komponent
    D — Forward returns MLE ∩ IMS vs MLE_only

Výstupy:
    mle_diagnostic_summary.csv
    mle_diagnostic_filter_breakdown.csv
    mle_diagnostic_component_comparison.csv
"""

from __future__ import annotations

from pathlib import Path
from datetime import date

import pandas as pd

PROJECT_ROOT     = Path(__file__).resolve().parents[2]
IMS_ARCHIVE      = PROJECT_ROOT / "output" / "archive" / "ims_candidates_archive.csv"
MLE_ARCHIVE_PATH = Path("C:/Users/stava/Projects/MarketLeadershipEngine/output/archive/rank_matrix_archive.csv")

FORWARD_WINDOWS  = [20, 30]


def load_mle_diagnostic_data(verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Načte a propojí MLE archiv s IMS archivem.

    Returns:
        (mle_df, ims_df) — propojené DataFramy
    """
    # ── MLE ──────────────────────────────────────────────────────────
    mle = pd.read_csv(MLE_ARCHIVE_PATH, dtype={"date": str})
    mle["date"] = pd.to_datetime(mle["date"]).dt.date
    mle_top50 = mle[mle["rank_10d"] <= 50].copy()

    # ── IMS ──────────────────────────────────────────────────────────
    ims = pd.read_csv(IMS_ARCHIVE, dtype={"date": str})
    ims["date"] = pd.to_datetime(ims["date"]).dt.date

    # Společné dny
    common_dates = set(mle_top50["date"].unique()) & set(ims["date"].unique())
    mle_top50 = mle_top50[mle_top50["date"].isin(common_dates)].copy()
    ims        = ims[ims["date"].isin(common_dates)].copy()

    # Přidej příznak "in_ims" k MLE TOP50
    ims_keys = set(zip(ims["date"], ims["ticker"]))
    mle_top50["in_ims"]    = mle_top50.apply(lambda r: (r["date"], r["ticker"]) in ims_keys, axis=1)
    mle_top50["ims_score"] = mle_top50.apply(
        lambda r: _get_ims_score(ims, r["date"], r["ticker"]), axis=1
    )

    if verbose:
        n_total     = len(mle_top50)
        n_in_ims    = mle_top50["in_ims"].sum()
        n_mle_only  = n_total - n_in_ims
        print(f"MLE TOP50 celkem  : {n_total} řádků ({mle_top50['date'].nunique()} dní)")
        print(f"  v IMS (≥60)     : {n_in_ims} ({100*n_in_ims/n_total:.1f}%)")
        print(f"  MLE_only        : {n_mle_only} ({100*n_mle_only/n_total:.1f}%)")

    return mle_top50, ims


def run_test_a(mle_top50: pd.DataFrame) -> pd.DataFrame:
    """
    Test A: ret_10d distribuce u MLE TOP50 celkem a per skupina.
    """
    rows = []

    for group_name, subset in [
        ("MLE_TOP50_all",  mle_top50),
        ("MLE_in_IMS",     mle_top50[mle_top50["in_ims"] == True]),
        ("MLE_only",       mle_top50[mle_top50["in_ims"] == False]),
    ]:
        if "ret_10d" not in subset.columns or subset.empty:
            continue
        vals = subset["ret_10d"].dropna()
        if vals.empty:
            continue
        rows.append({
            "group":      group_name,
            "n":          len(vals),
            "avg_ret10d": round(vals.mean(), 2),
            "med_ret10d": round(vals.median(), 2),
            "p25_ret10d": round(vals.quantile(0.25), 2),
            "p75_ret10d": round(vals.quantile(0.75), 2),
            "min_ret10d": round(vals.min(), 2),
            "max_ret10d": round(vals.max(), 2),
        })

    return pd.DataFrame(rows)


def run_test_b(mle_top50: pd.DataFrame) -> pd.DataFrame:
    """
    Test B: IMS filter breakdown pro MLE TOP50.
    Kolik MLE TOP50 tickerů by prošlo / neprošlo každým IMS filtrem.
    Pozn.: EMA200, volume, negative extreme nejsou přímo v MLE archivu.
    Používáme dostupné proxy: ret_10d jako momentum proxy.
    """
    rows = []
    total = len(mle_top50)

    # Skupiny
    in_ims   = mle_top50[mle_top50["in_ims"] == True]
    mle_only = mle_top50[mle_top50["in_ims"] == False]

    # Ret_10d distribuce per skupina
    for group_name, subset in [("MLE_in_IMS", in_ims), ("MLE_only", mle_only)]:
        if subset.empty:
            continue
        n = len(subset)

        # Dostupné rank metriky z MLE archivu
        rank_cols = [c for c in ["rank_1d", "rank_5d", "rank_10d", "rank_20d"] if c in subset.columns]

        row = {
            "group": group_name,
            "n": n,
            "pct_of_top50": round(100 * n / total, 1),
        }

        for col in rank_cols:
            vals = subset[col].dropna()
            row[f"avg_{col}"] = round(vals.mean(), 1)
            row[f"med_{col}"] = round(vals.median(), 1)

        if "ret_10d" in subset.columns:
            vals = subset["ret_10d"].dropna()
            row["avg_ret10d"] = round(vals.mean(), 2)
            row["med_ret10d"] = round(vals.median(), 2)

        if "ret_20d" in subset.columns:
            vals = subset["ret_20d"].dropna()
            row["avg_ret20d"] = round(vals.mean(), 2)
            row["med_ret20d"] = round(vals.median(), 2)

        rows.append(row)

    return pd.DataFrame(rows)


def run_test_c(
    mle_top50:  pd.DataFrame,
    ims_df:     pd.DataFrame,
) -> pd.DataFrame:
    """
    Test C: Porovnání IMS komponent pro MLE_in_IMS vs MLE_only.
    MLE_only tickery — jaké mají IMS score? (většina bude pod 60, ale IMS
    archiv má jen ≥60. Porovnáme tedy co máme k dispozici.)
    """
    rows = []

    comp_cols = [
        "rs_vs_spy_20d",
        "up_down_volume_ratio_20d",
        "rank_stability_20d",
        "rank_improvement_20d",
        "rank_improvement_40d",
    ]

    # MLE_in_IMS — vezmi IMS data pro tyto tickery
    in_ims_keys  = mle_top50[mle_top50["in_ims"] == True][["date", "ticker"]]
    ims_in_mle   = ims_df.merge(in_ims_keys, on=["date", "ticker"], how="inner")

    # IMS tickery MIMO MLE TOP50 — pro srovnání
    mle_keys     = set(zip(mle_top50["date"], mle_top50["ticker"]))
    ims_not_mle  = ims_df[~ims_df.apply(lambda r: (r["date"], r["ticker"]) in mle_keys, axis=1)]

    for group_name, subset in [
        ("IMS_in_MLE_TOP50", ims_in_mle),
        ("IMS_not_in_MLE",   ims_not_mle),
    ]:
        if subset.empty:
            continue
        row = {"group": group_name, "n": len(subset)}

        if "score" in subset.columns:
            row["avg_score"] = round(subset["score"].mean(), 1)
            row["med_score"] = round(subset["score"].median(), 1)

        for col in comp_cols:
            if col in subset.columns:
                vals = subset[col].dropna()
                if not vals.empty:
                    row[f"avg_{col}"] = round(vals.mean(), 3)
                    row[f"med_{col}"] = round(vals.median(), 3)

        rows.append(row)

    return pd.DataFrame(rows)


def run_test_d(
    mle_top50:  pd.DataFrame,
    close_map:  dict[str, pd.Series],
    spy_close:  pd.Series,
) -> pd.DataFrame:
    """
    Test D: Forward 20D/30D returns pro MLE_in_IMS vs MLE_only.
    """
    rows = []

    for _, row in mle_top50.iterrows():
        ticker = row["ticker"]
        dt     = row["date"]
        group  = "MLE_in_IMS" if row["in_ims"] else "MLE_only"

        entry = _get_price(close_map, ticker, dt, 0)
        spy_e = _get_price({"SPY": spy_close}, "SPY", dt, 0)

        if entry is None or spy_e is None or entry <= 0 or spy_e <= 0:
            continue

        rec = {"date": dt, "ticker": ticker, "group": group, "ret_10d_mle": row.get("ret_10d")}

        for window in FORWARD_WINDOWS:
            fwd = _get_price(close_map, ticker, dt, window)
            sf  = _get_price({"SPY": spy_close}, "SPY", dt, window)
            low = _get_window_low(close_map, ticker, dt, window)

            if fwd is not None and sf is not None and low is not None:
                fwd_ret  = (fwd / entry - 1) * 100
                spy_ret  = (sf  / spy_e  - 1) * 100
                rec[f"fwd_{window}d"]   = round(fwd_ret, 4)
                rec[f"alpha_{window}d"] = round(fwd_ret - spy_ret, 4)
                rec[f"dd_{window}d"]    = round((low / entry - 1) * 100, 4)
                rec[f"ok_{window}d"]    = True
            else:
                rec[f"fwd_{window}d"]   = None
                rec[f"alpha_{window}d"] = None
                rec[f"dd_{window}d"]    = None
                rec[f"ok_{window}d"]    = False

        rows.append(rec)

    return pd.DataFrame(rows)


def aggregate_test_d(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group in ["MLE_in_IMS", "MLE_only"]:
        sub = results[results["group"] == group]
        for window in FORWARD_WINDOWS:
            col_fwd = f"fwd_{window}d"
            col_alp = f"alpha_{window}d"
            col_dd  = f"dd_{window}d"
            col_ok  = f"ok_{window}d"
            if col_ok not in sub.columns:
                continue
            usable    = sub[sub[col_ok] == True]
            fwd_vals  = usable[col_fwd].dropna()
            alp_vals  = usable[col_alp].dropna()
            dd_vals   = usable[col_dd].dropna()
            if len(fwd_vals) < 5:
                continue
            rows.append({
                "group":         group,
                "window":        f"{window}D",
                "n":             len(fwd_vals),
                "avg_return":    round(fwd_vals.mean(), 4),
                "median_return": round(fwd_vals.median(), 4),
                "win_rate":      round((fwd_vals > 0).mean() * 100, 2),
                "avg_alpha":     round(alp_vals.mean(), 4),
                "median_alpha":  round(alp_vals.median(), 4),
                "alpha_win_rate": round((alp_vals > 0).mean() * 100, 2),
                "avg_drawdown":  round(dd_vals.mean(), 4),
            })
    return pd.DataFrame(rows)


def format_report(
    test_a: pd.DataFrame,
    test_b: pd.DataFrame,
    test_c: pd.DataFrame,
    test_d_agg: pd.DataFrame,
    run_date: date,
) -> list[str]:
    lines = []
    lines += [
        "=" * 70,
        "IMS AUDIT v4 — MLE_only DIAGNOSTIC",
        f"Datum reportu : {run_date}",
        "=" * 70,
        "",
        "Hypotéza: MLE TOP50 zachycuje čisté 10D price momentum.",
        "IMS filtry část nejsilnějších momentum tahů vyřadí.",
        "",
    ]

    # Test A
    lines += ["=" * 70, "TEST A — ret_10d DISTRIBUCE U MLE TOP50", "=" * 70, ""]
    lines.append(f"  {'Skupina':<22} {'N':>6} {'Avg':>8} {'Med':>8} {'P25':>8} {'P75':>8} {'Max':>8}")
    lines.append(f"  {'-'*22} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for _, r in test_a.iterrows():
        lines.append(
            f"  {r['group']:<22} {int(r['n']):>6} "
            f"{r['avg_ret10d']:>+7.1f}% {r['med_ret10d']:>+7.1f}% "
            f"{r['p25_ret10d']:>+7.1f}% {r['p75_ret10d']:>+7.1f}% "
            f"{r['max_ret10d']:>+7.1f}%"
        )
    lines += ["", "  Interpretace: MLE_only má vyšší ret_10d než MLE_in_IMS?", ""]

    # Test B
    lines += ["=" * 70, "TEST B — RANK PROFIL: MLE_in_IMS vs MLE_only", "=" * 70, ""]
    for _, r in test_b.iterrows():
        lines.append(f"  {r['group']} (N={int(r['n'])}, {r['pct_of_top50']:.1f}% TOP50)")
        for col in ["avg_ret10d", "med_ret10d", "avg_ret20d", "med_ret20d",
                    "avg_rank_1d", "avg_rank_5d", "avg_rank_10d", "avg_rank_20d"]:
            if col in r and not pd.isna(r[col]):
                lines.append(f"    {col:<25}: {r[col]:>8.2f}")
        lines.append("")

    # Test C
    lines += ["=" * 70, "TEST C — IMS KOMPONENTY: v MLE TOP50 vs mimo MLE TOP50", "=" * 70, ""]
    comp_labels = {
        "avg_score":                    "Avg IMS score",
        "avg_rs_vs_spy_20d":            "Avg RS vs SPY 20D",
        "avg_up_down_volume_ratio_20d":  "Avg UD Volume Ratio",
        "avg_rank_stability_20d":        "Avg Rank Stability (nižší=lepší)",
        "avg_rank_improvement_20d":      "Avg Rank Improvement 20D",
    }
    for _, r in test_c.iterrows():
        lines.append(f"  {r['group']} (N={int(r['n'])})")
        for col, label in comp_labels.items():
            if col in r and not pd.isna(r.get(col, float("nan"))):
                lines.append(f"    {label:<35}: {r[col]:>8.2f}")
        lines.append("")
    lines.append("  Interpretace: IMS_in_MLE_TOP50 má vyšší score a RS než IMS_not_in_MLE?")
    lines.append("")

    # Test D
    lines += ["=" * 70, "TEST D — FORWARD RETURNS: MLE_in_IMS vs MLE_only", "=" * 70, ""]
    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = test_d_agg[test_d_agg["window"] == w_str]
        if sub.empty:
            continue
        lines.append(f"  Forward {w_str}:")
        lines.append(f"  {'Skupina':<15} {'N':>6} {'AvgRet':>8} {'MedRet':>8} {'WinRate':>8} {'AvgAlpha':>10} {'AvgDD':>8}")
        lines.append(f"  {'-'*15} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*8}")
        for _, r in sub.iterrows():
            lines.append(
                f"  {r['group']:<15} {int(r['n']):>6} "
                f"{r['avg_return']:>+7.2f}% {r['median_return']:>+7.2f}% "
                f"{r['win_rate']:>7.1f}% {r['avg_alpha']:>+9.2f}% "
                f"{r['avg_drawdown']:>+7.2f}%"
            )
        lines.append("")

    lines += [
        "=" * 70,
        "ZÁVĚR",
        "=" * 70,
        "",
        "  Pokud MLE_only má výrazně vyšší ret_10d než MLE_in_IMS:",
        "  IMS filtry vyřazují nejmomentumnější tickery → IMS je konzervativní.",
        "",
        "  Pokud MLE_only má lepší forward 20D/30D i po vstupu:",
        "  momentum bez quality filtrů předčí momentum s filtry.",
        "  → Zvážit uvolnění IMS filtrů pro 'pure momentum' bucket.",
        "",
        "  Pokud MLE_in_IMS má podobné nebo lepší forward returns:",
        "  IMS filtry přidávají quality bez ztráty edge.",
        "  → Průnik je správný přístup, jen špatně definovaný v Audit v3.",
        "",
        "OMEZENÍ:",
        "  - Jeden tržní cyklus 2025-2026.",
        "  - IMS archiv neobsahuje filter_data pro MLE_only tickery.",
        "    Filter breakdown (EMA200, volume) nelze přesně rekonstruovat.",
        "",
        "=" * 70,
    ]

    return lines


# ── Price helpers ─────────────────────────────────────────────────────────────

def _get_price(close_map, ticker, signal_date, offset):
    series = close_map.get(ticker)
    if series is None:
        return None
    ts = pd.Timestamp(signal_date)
    if offset == 0:
        day = series[series.index <= ts]
        return float(day.iloc[-1]) if not day.empty else None
    future = series[series.index > ts]
    if len(future) < offset:
        return None
    return float(future.iloc[offset - 1])


def _get_window_low(close_map, ticker, signal_date, window):
    series = close_map.get(ticker)
    if series is None:
        return None
    ts = pd.Timestamp(signal_date)
    future = series[series.index > ts]
    if len(future) < window:
        return None
    return float(future.iloc[:window].min())


def _get_ims_score(ims_df, dt, ticker):
    row = ims_df[(ims_df["date"] == dt) & (ims_df["ticker"] == ticker)]
    if row.empty:
        return None
    return float(row["score"].iloc[0])
