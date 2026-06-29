"""
IMS Audit — Return Analysis
audit/tests/return_analysis.py

Zodpovědnost:
    Sekce B: agregovat forward returns per score bucket.
    Vypočítat avg, median, win rate, max drawdown per window a bucket.

Score buckety:
    RADAR   : 60–69
    H70-79  : 70–79
    H80-89  : 80–89
    H90-94  : 90–94
    H95+    : 95+

Výstup:
    pd.DataFrame — jeden řádek per (bucket, window)
    Sloupce:
        bucket, window, n,
        avg_return, median_return, win_rate,
        avg_drawdown, median_drawdown,
        pct_positive, pct_negative

Použití:
    from audit.tests.return_analysis import run
    df = run(forward_df)
"""

from __future__ import annotations

import pandas as pd

# Score buckety: název → (min_inclusive, max_exclusive)
SCORE_BUCKETS: dict[str, tuple[float, float]] = {
    "RADAR":  (60.0, 70.0),
    "H70-79": (70.0, 80.0),
    "H80-89": (80.0, 90.0),
    "H90-94": (90.0, 95.0),
    "H95+":   (95.0, 101.0),
}

FORWARD_WINDOWS = [5, 10, 20, 30]


def run(forward_df: pd.DataFrame) -> pd.DataFrame:
    """
    Agreguje forward returns per score bucket a window.

    Args:
        forward_df: výstup z forward_returns.compute_forward_returns()

    Returns:
        pd.DataFrame s metrikami per (bucket, window)
    """
    rows = []

    for bucket_name, (lo, hi) in SCORE_BUCKETS.items():
        subset = forward_df[
            (forward_df["score"] >= lo) & (forward_df["score"] < hi)
        ].copy()

        if subset.empty:
            continue

        for window in FORWARD_WINDOWS:
            col_fwd = f"fwd_{window}d"
            col_dd  = f"dd_{window}d"
            col_use = f"usable_{window}d"

            if col_use not in subset.columns:
                continue

            usable = subset[subset[col_use] == True]

            if usable.empty:
                continue

            fwd_vals = usable[col_fwd].dropna()
            dd_vals  = usable[col_dd].dropna()

            if len(fwd_vals) < 5:
                # Příliš málo dat — přeskočit
                continue

            rows.append({
                "bucket":          bucket_name,
                "window":          f"{window}D",
                "n":               len(fwd_vals),
                "avg_return":      round(fwd_vals.mean(), 4),
                "median_return":   round(fwd_vals.median(), 4),
                "win_rate":        round((fwd_vals > 0).mean() * 100, 2),
                "avg_drawdown":    round(dd_vals.mean(), 4) if not dd_vals.empty else None,
                "median_drawdown": round(dd_vals.median(), 4) if not dd_vals.empty else None,
                "pct_positive":    round((fwd_vals > 0).mean() * 100, 2),
                "pct_negative":    round((fwd_vals < 0).mean() * 100, 2),
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    """
    Sestaví textový report sekce B.

    Args:
        df: výstup z run()

    Returns:
        list[str] — řádky reportu
    """
    lines = []
    lines.append("=" * 65)
    lines.append("SEKCE B — RETURN ANALYSIS")
    lines.append("=" * 65)
    lines.append("")
    lines.append("Metrika  : forward return od close na signal date")
    lines.append("Drawdown : entry-to-low (nejnižší close v okně / entry - 1)")
    lines.append("")

    bucket_order = list(SCORE_BUCKETS.keys())

    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = df[df["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 65)
        lines.append(
            f"  {'Bucket':<10} {'N':>6} {'Avg%':>8} {'Med%':>8} "
            f"{'WinRate':>8} {'AvgDD%':>8} {'MedDD%':>8}"
        )
        lines.append(
            f"  {'-'*10} {'-'*6} {'-'*8} {'-'*8} "
            f"{'-'*8} {'-'*8} {'-'*8}"
        )

        for bucket in bucket_order:
            row = sub[sub["bucket"] == bucket]
            if row.empty:
                continue
            r = row.iloc[0]

            avg_dd = f"{r['avg_drawdown']:>+7.2f}%" if r["avg_drawdown"] is not None else "     N/A"
            med_dd = f"{r['median_drawdown']:>+7.2f}%" if r["median_drawdown"] is not None else "     N/A"

            lines.append(
                f"  {bucket:<10} {int(r['n']):>6} "
                f"{r['avg_return']:>+7.2f}% {r['median_return']:>+7.2f}% "
                f"{r['win_rate']:>7.1f}% "
                f"{avg_dd} {med_dd}"
            )

        lines.append("")

    # Souhrnná interpretační sekce
    lines.append("-" * 65)
    lines.append("INTERPRETACE")
    lines.append("-" * 65)
    lines.append("  Win rate > 55% = slabý signál")
    lines.append("  Win rate > 60% = střední signál")
    lines.append("  Win rate > 65% = silný signál")
    lines.append("")
    lines.append("  Monotónní vztah score → avg return = IMS má prediktivní hodnotu")
    lines.append("  Plochý nebo inverzní vztah = score není prediktivní pro výnosy")
    lines.append("")

    return lines
