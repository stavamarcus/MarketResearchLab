"""
Industry Rank Calendar Audit — Test E
audit/tests/test_e_breadth.py

Otázka:
    Záleží na šířce pohybu (Adv%) uvnitř industry?
    Mají akcie z industry kde 90%+ členů roste lepší returns?

Buckety:
    BROAD90   : advance_ratio >= 90%
    BROAD75   : advance_ratio 75–89%
    MED50     : advance_ratio 50–74%
    NARROW    : advance_ratio < 50%

Hypotéza:
    H0: šířka pohybu (Adv%) nepredikuje forward returns
    H1: vyšší Adv% → lepší forward returns (celá industry táhne společně)

Interpretace:
    BROAD90 >> NARROW = breadth je silný prediktor, filtruj jen na Adv% >= 75%
    Plochý trend = breadth není dalším faktorem, rank stačí
"""

from __future__ import annotations

import pandas as pd

FORWARD_WINDOWS = [5, 10, 20, 30]

BREADTH_BUCKETS: dict[str, tuple[float, float]] = {
    "BROAD90 (90-100%)": (90.0, 100.1),
    "BROAD75 (75-89%)":  (75.0, 90.0),
    "MED50   (50-74%)":  (50.0, 75.0),
    "NARROW  (<50%)":    (0.0,  50.0),
}


def run(forward_df: pd.DataFrame) -> pd.DataFrame:
    if "advance_ratio" not in forward_df.columns:
        return pd.DataFrame()

    rows = []

    for bucket_name, (lo, hi) in BREADTH_BUCKETS.items():
        subset = forward_df[
            (forward_df["advance_ratio"] >= lo) &
            (forward_df["advance_ratio"] < hi)
        ].copy()

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

            if len(fwd_vals) < 10:
                continue

            rows.append({
                "bucket":        bucket_name,
                "window":        f"{window}D",
                "n":             len(fwd_vals),
                "avg_return":    round(fwd_vals.mean(), 4),
                "median_return": round(fwd_vals.median(), 4),
                "win_rate":      round((fwd_vals > 0).mean() * 100, 2),
                "avg_alpha":     round(alpha_vals.mean(), 4) if not alpha_vals.empty else None,
                "avg_drawdown":  round(dd_vals.mean(), 4) if not dd_vals.empty else None,
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST E — BREADTH (ADV%) EFFECT")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Zalezi na sirce pohybu uvnitr industry (Adv%)?")
    lines.append("Adv% = procento clenu industry s kladnym returnem")
    lines.append("")

    bucket_order = list(BREADTH_BUCKETS.keys())

    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = df[df["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 70)
        lines.append(
            f"  {'Bucket':<20}  {'N':>6}  {'Avg%':>8}  {'Med%':>8}  "
            f"{'WinRate':>8}  {'AvgAlpha':>9}  {'AvgDD%':>8}"
        )
        lines.append(
            f"  {'-'*20}  {'-'*6}  {'-'*8}  {'-'*8}  "
            f"{'-'*8}  {'-'*9}  {'-'*8}"
        )

        for bucket in bucket_order:
            row = sub[sub["bucket"] == bucket]
            if row.empty:
                continue
            r = row.iloc[0]
            alpha_str = f"{r['avg_alpha']:>+8.2f}%" if r["avg_alpha"] is not None else "      N/A"
            dd_str    = f"{r['avg_drawdown']:>+7.2f}%" if r["avg_drawdown"] is not None else "     N/A"
            lines.append(
                f"  {bucket:<20}  {int(r['n']):>6}  "
                f"{r['avg_return']:>+7.2f}%  {r['median_return']:>+7.2f}%  "
                f"{r['win_rate']:>7.1f}%  {alpha_str}  {dd_str}"
            )

        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  Monotonni pokles BROAD90 → NARROW = breadth je prediktor")
    lines.append("  Plochý trend = sirka pohybu nema prediktivni hodnotu")
    lines.append("")

    return lines
