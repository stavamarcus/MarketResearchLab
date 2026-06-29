"""
Industry Rank Calendar Audit — Test A
audit/tests/test_a_rank_buckets.py

Otázka:
    Dosahují akcie z TOP industry (R1–R5) lepších forward returns
    než akcie z slabších industry skupin?

Metodologie:
    - Každý ticker-den je zařazen do bucketu podle industry_rank
    - Buckety: R1-5, R6-10, R11-20, R21-30, R31+
    - Per bucket: avg return, median return, win rate, alpha vs SPY, drawdown
    - Použit 20D forward window jako primární (odpovídá 20D lookbacku industry rank)

Hypotéza:
    H0: industry rank nepredikuje forward returns
    H1: nižší rank (silnější industry) → vyšší forward returns

Interpretace:
    Monotónní sestupný trend avg_return R1-5 → R31+ = industry rank má prediktivní hodnotu
    Plochý nebo inverzní trend = rank není prediktivní
"""

from __future__ import annotations

import pandas as pd

FORWARD_WINDOWS = [5, 10, 20, 30]

RANK_BUCKETS: dict[str, tuple[int, int]] = {
    "R1-5":  (1, 5),
    "R6-10": (6, 10),
    "R11-20": (11, 20),
    "R21-30": (21, 30),
    "R31+":  (31, 999),
}


def run(forward_df: pd.DataFrame) -> pd.DataFrame:
    """
    Agreguje forward returns per industry rank bucket.

    Args:
        forward_df: výstup z forward_returns.compute_forward_returns()

    Returns:
        pd.DataFrame: bucket, window, n, avg_return, median_return,
                      win_rate, avg_alpha, median_alpha, avg_drawdown
    """
    rows = []

    for bucket_name, (lo, hi) in RANK_BUCKETS.items():
        subset = forward_df[
            (forward_df["industry_rank"] >= lo) &
            (forward_df["industry_rank"] <= hi)
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
                "bucket":          bucket_name,
                "window":          f"{window}D",
                "n":               len(fwd_vals),
                "avg_return":      round(fwd_vals.mean(), 4),
                "median_return":   round(fwd_vals.median(), 4),
                "win_rate":        round((fwd_vals > 0).mean() * 100, 2),
                "avg_alpha":       round(alpha_vals.mean(), 4) if not alpha_vals.empty else None,
                "median_alpha":    round(alpha_vals.median(), 4) if not alpha_vals.empty else None,
                "avg_drawdown":    round(dd_vals.mean(), 4) if not dd_vals.empty else None,
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST A — INDUSTRY RANK BUCKET EFFECT")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Maji akcie z TOP industry (R1-5) lepsi forward returns?")
    lines.append("Buckety: R1-5 | R6-10 | R11-20 | R21-30 | R31+")
    lines.append("Alpha: excess return vs SPY ve stejnem okne")
    lines.append("")

    bucket_order = list(RANK_BUCKETS.keys())

    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = df[df["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 70)
        lines.append(
            f"  {'Bucket':<10}  {'N':>6}  {'Avg%':>8}  {'Med%':>8}  "
            f"{'WinRate':>8}  {'AvgAlpha':>9}  {'AvgDD%':>8}"
        )
        lines.append(
            f"  {'-'*10}  {'-'*6}  {'-'*8}  {'-'*8}  "
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
                f"  {bucket:<10}  {int(r['n']):>6}  "
                f"{r['avg_return']:>+7.2f}%  {r['median_return']:>+7.2f}%  "
                f"{r['win_rate']:>7.1f}%  {alpha_str}  {dd_str}"
            )

        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  Monotonni pokles avg_return/alpha R1-5 → R31+ = rank ma prediktivni hodnotu")
    lines.append("  Plochý nebo inverzni trend = rank neni prediktivni")
    lines.append("")

    return lines
