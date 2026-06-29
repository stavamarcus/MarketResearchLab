"""
Industry Rank Calendar Audit — Test 13
audit/tests/test_13_triple.py

Otázka:
    Jak silná je kombinace tří faktorů?
        A) MLE + Industry + Persistence
        B) IMS + Industry + Persistence
        C) MLE + IMS + Industry + Persistence (čtyřnásobná kombinace)

Metodologie:
    Skupiny:
        ALL_THREE    : rank <= TOP_IND AND persist >= PERSIST_MED
        IND_ONLY     : rank <= TOP_IND AND persist < PERSIST_MED
        PERSIST_ONLY : rank > TOP_IND AND persist >= PERSIST_MED
        NONE         : rank > TOP_IND AND persist < PERSIST_MED

    Pro čtyřnásobnou kombinaci (MLE ∩ IMS ∩ Industry ∩ Persist):
        Průnik MLE TOP20 a IMS HIGH signálů se dvěma filtry.

Výstup:
    Forward returns per skupina a window.
    Verdikt: přidává třetí faktor inkrementální edge?
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 20
TOP_IND_RANK    = 10
PERSIST_MED     = 8    # >= 8/20 = dostatečná persistence (MED+HIGH)

PROJECTS_BASE   = Path("C:/Users/stava/Projects")
IMS_ARCHIVE     = PROJECTS_BASE / "InstitutionalMomentumScanner/output/archive/ims_candidates_archive.csv"
MLE_ARCHIVE     = PROJECTS_BASE / "MarketLeadershipEngine/output/archive/rank_matrix_archive.csv"


def run(
    mle_fwd: pd.DataFrame,
    ims_fwd: pd.DataFrame,
    close_map: dict,
    spy_close,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Spustí trojité kombinační testy.

    Returns:
        mle_triple: MLE × Industry × Persistence
        ims_triple: IMS × Industry × Persistence
        quad:       MLE ∩ IMS × Industry × Persistence
    """
    mle_triple = _triple_test(mle_fwd)
    ims_triple = _triple_test(ims_fwd)
    quad       = _quad_test(mle_fwd, ims_fwd, close_map, spy_close)
    return mle_triple, ims_triple, quad


def _group_label(rank: int, persist: int, prefix: str) -> str:
    has_ind     = rank <= TOP_IND_RANK
    has_persist = persist >= PERSIST_MED

    if has_ind and has_persist:
        return f"{prefix}+IND+PERSIST"
    elif has_ind:
        return f"{prefix}+IND_ONLY"
    elif has_persist:
        return f"{prefix}+PERSIST_ONLY"
    else:
        return f"{prefix}+NONE"


def _triple_test(fwd_df: pd.DataFrame) -> pd.DataFrame:
    """Rozdělí signály do 4 skupin podle kombinace Industry + Persistence."""
    if fwd_df.empty:
        return pd.DataFrame()

    # Detekuj prefix z dat
    prefix = "MLE" if "rank_10d" in fwd_df.columns else "IMS"

    df = fwd_df.copy()
    df["group"] = df.apply(
        lambda r: _group_label(int(r["industry_rank"]), int(r["industry_persist"]), prefix),
        axis=1
    )

    rows = []
    group_order = [
        f"{prefix}+IND+PERSIST",
        f"{prefix}+IND_ONLY",
        f"{prefix}+PERSIST_ONLY",
        f"{prefix}+NONE",
    ]

    for group in group_order:
        subset = df[df["group"] == group]
        for w in FORWARD_WINDOWS:
            col_use = f"usable_{w}d"
            if col_use not in subset.columns:
                continue
            usable = subset[subset[col_use] == True]
            fwd    = usable[f"fwd_{w}d"].dropna()
            alpha  = usable[f"alpha_{w}d"].dropna()
            dd     = usable[f"dd_{w}d"].dropna()
            if len(fwd) < 3:
                continue
            rows.append({
                "group":         group,
                "window":        f"{w}D",
                "n":             len(fwd),
                "avg_return":    round(fwd.mean(), 4),
                "median_return": round(fwd.median(), 4),
                "win_rate":      round((fwd > 0).mean() * 100, 2),
                "avg_alpha":     round(alpha.mean(), 4) if not alpha.empty else None,
                "avg_drawdown":  round(dd.mean(), 4) if not dd.empty else None,
            })

    return pd.DataFrame(rows)


def _quad_test(
    mle_fwd: pd.DataFrame,
    ims_fwd: pd.DataFrame,
    close_map: dict,
    spy_close,
) -> pd.DataFrame:
    """
    Čtyřnásobná kombinace: průnik MLE TOP20 ∩ IMS HIGH s Industry + Persist filtry.
    Signál musí být v obou archivech ve stejný den.
    """
    if mle_fwd.empty or ims_fwd.empty:
        return pd.DataFrame()

    # Průnik: ticker-date v obou archivech
    mle_keys = set(zip(mle_fwd["date"].astype(str), mle_fwd["ticker"]))
    ims_keys = set(zip(ims_fwd["date"].astype(str), ims_fwd["ticker"]))
    common   = mle_keys & ims_keys

    if not common:
        return pd.DataFrame()

    # Vezmi MLE data pro průnik (má industry_rank a persist)
    mle_copy = mle_fwd.copy()
    mle_copy["key"] = list(zip(mle_copy["date"].astype(str), mle_copy["ticker"]))
    overlap = mle_copy[mle_copy["key"].isin(common)].copy()

    if overlap.empty:
        return pd.DataFrame()

    overlap["group"] = overlap.apply(
        lambda r: _group_label(int(r["industry_rank"]), int(r["industry_persist"]), "QUAD"),
        axis=1
    )

    rows = []
    group_order = [
        "QUAD+IND+PERSIST",
        "QUAD+IND_ONLY",
        "QUAD+PERSIST_ONLY",
        "QUAD+NONE",
    ]

    for group in group_order:
        subset = overlap[overlap["group"] == group]
        for w in FORWARD_WINDOWS:
            col_use = f"usable_{w}d"
            if col_use not in subset.columns:
                continue
            usable = subset[subset[col_use] == True]
            fwd    = usable[f"fwd_{w}d"].dropna()
            alpha  = usable[f"alpha_{w}d"].dropna()
            dd     = usable[f"dd_{w}d"].dropna()
            if len(fwd) < 2:
                continue
            rows.append({
                "group":         group,
                "window":        f"{w}D",
                "n":             len(fwd),
                "avg_return":    round(fwd.mean(), 4),
                "median_return": round(fwd.median(), 4),
                "win_rate":      round((fwd > 0).mean() * 100, 2),
                "avg_alpha":     round(alpha.mean(), 4) if not alpha.empty else None,
                "avg_drawdown":  round(dd.mean(), 4) if not dd.empty else None,
            })

    return pd.DataFrame(rows)


def format_report(mle_triple: pd.DataFrame, ims_triple: pd.DataFrame, quad: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST 13 — TROJITE A CTYRNASOBNE KOMBINACE")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Prida treti faktor inkrementalni edge?")
    lines.append(f"Industry filtr : rank <= TOP{TOP_IND_RANK}")
    lines.append(f"Persist filtr  : >= {PERSIST_MED}/20 dni v TOP10")
    lines.append("")

    configs = [
        ("MLE × Industry × Persistence", mle_triple,
         ["MLE+IND+PERSIST", "MLE+IND_ONLY", "MLE+PERSIST_ONLY", "MLE+NONE"]),
        ("IMS × Industry × Persistence", ims_triple,
         ["IMS+IND+PERSIST", "IMS+IND_ONLY", "IMS+PERSIST_ONLY", "IMS+NONE"]),
        ("MLE ∩ IMS × Industry × Persistence", quad,
         ["QUAD+IND+PERSIST", "QUAD+IND_ONLY", "QUAD+PERSIST_ONLY", "QUAD+NONE"]),
    ]

    for title, df, group_order in configs:
        lines.append(f"[ {title} ]")
        lines.append("-" * 70)

        if df.empty or "window" not in df.columns:
            lines.append("  Nedostatek dat.")
            lines.append("")
            continue

        w_str = f"{PRIMARY_WINDOW}D"
        sub   = df[df["window"] == w_str]

        if sub.empty:
            lines.append(f"  Zadna data pro {PRIMARY_WINDOW}D okno.")
            lines.append("")
            continue

        lines.append(
            f"  {'Skupina':<24}  {'N':>5}  {'Avg%':>8}  {'Med%':>8}  "
            f"{'WinRate':>8}  {'Alpha':>8}  {'AvgDD%':>7}"
        )
        lines.append(
            f"  {'-'*24}  {'-'*5}  {'-'*8}  {'-'*8}  "
            f"{'-'*8}  {'-'*8}  {'-'*7}"
        )

        for group in group_order:
            row = sub[sub["group"] == group]
            if row.empty:
                continue
            r = row.iloc[0]
            alpha_str = f"{r['avg_alpha']:>+7.2f}%" if r["avg_alpha"] is not None else "     N/A"
            dd_str    = f"{r['avg_drawdown']:>+6.2f}%" if r["avg_drawdown"] is not None else "    N/A"
            lines.append(
                f"  {group:<24}  {int(r['n']):>5}  "
                f"{r['avg_return']:>+7.2f}%  {r['median_return']:>+7.2f}%  "
                f"{r['win_rate']:>7.1f}%  {alpha_str}  {dd_str}"
            )

        # Delta: ALL_THREE vs NONE
        best_grp  = sub[sub["group"] == group_order[0]]
        worst_grp = sub[sub["group"] == group_order[-1]]
        if not best_grp.empty and not worst_grp.empty:
            d_ret   = best_grp.iloc[0]["avg_return"] - worst_grp.iloc[0]["avg_return"]
            d_alpha = (best_grp.iloc[0]["avg_alpha"] or 0) - (worst_grp.iloc[0]["avg_alpha"] or 0)
            lines.append(
                f"  {'DELTA (best vs NONE)':<24}  {'':>5}  "
                f"{'+' if d_ret >= 0 else ''}{d_ret:>7.2f}%  {'':>8}  "
                f"{'':>8}  {'+' if d_alpha >= 0 else ''}{d_alpha:>7.2f}%"
            )

        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  +IND+PERSIST >> +IND_ONLY a +PERSIST_ONLY = synergicky efekt")
    lines.append("  +IND+PERSIST ≈ max(+IND_ONLY, +PERSIST_ONLY) = aditivni efekt")
    lines.append("  +IND+PERSIST ≈ NONE = faktory se navzajem rusí")
    lines.append("")

    return lines
