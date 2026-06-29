"""
IMS Audit v2 — Fine Score Bucket Analysis
audit/tests/fine_score_buckets.py

Zodpovědnost:
    Sekce E: forward returns per jemnější score bucket (5-bodové intervaly).
    Odhalí kde přesně začíná edge a zda je přechod 89→90 skutečně zlomový.

Buckety:
    60–64, 65–69, 70–74, 75–79, 80–84, 85–89, 90–94, 95+

Metriky per bucket a window:
    N, avg_return, median_return, win_rate,
    avg_alpha, median_alpha, alpha_win_rate, avg_drawdown
"""

from __future__ import annotations

import pandas as pd

FINE_BUCKETS: dict[str, tuple[float, float]] = {
    "60-64": (60.0, 65.0),
    "65-69": (65.0, 70.0),
    "70-74": (70.0, 75.0),
    "75-79": (75.0, 80.0),
    "80-84": (80.0, 85.0),
    "85-89": (85.0, 90.0),
    "90-94": (90.0, 95.0),
    "95+":   (95.0, 101.0),
}

FORWARD_WINDOWS = [5, 10, 20, 30]


def run(forward_df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for bucket_name, (lo, hi) in FINE_BUCKETS.items():
        subset = forward_df[
            (forward_df["score"] >= lo) & (forward_df["score"] < hi)
        ].copy()

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

            if len(fwd_vals) < 3:
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
                "alpha_win_rate":  round((alpha_vals > 0).mean() * 100, 2) if not alpha_vals.empty else None,
                "avg_drawdown":    round(dd_vals.mean(), 4) if not dd_vals.empty else None,
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 75)
    lines.append("SEKCE E — FINE SCORE BUCKET ANALYSIS")
    lines.append("=" * 75)
    lines.append("")
    lines.append("Buckety po 5 bodech — odhalí přesný zlom v prediktivní síle score.")
    lines.append("POZOR: 95+ má malý N — interpretovat opatrně.")
    lines.append("")

    bucket_order = list(FINE_BUCKETS.keys())

    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = df[df["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 75)
        lines.append(
            f"  {'Bucket':<8} {'N':>6} {'AvgRet':>8} {'MedRet':>8} "
            f"{'WinRate':>8} {'AvgAlpha':>10} {'MedAlpha':>10} "
            f"{'AlphaWR':>8} {'AvgDD':>8}"
        )
        lines.append(
            f"  {'-'*8} {'-'*6} {'-'*8} {'-'*8} "
            f"{'-'*8} {'-'*10} {'-'*10} "
            f"{'-'*8} {'-'*8}"
        )

        for bucket in bucket_order:
            row = sub[sub["bucket"] == bucket]
            if row.empty:
                continue
            r   = row.iloc[0]
            flag = " !" if r["n"] < 30 else ""

            avg_alpha = f"{r['avg_alpha']:>+9.2f}%" if r["avg_alpha"] is not None else "       N/A"
            med_alpha = f"{r['median_alpha']:>+9.2f}%" if r["median_alpha"] is not None else "       N/A"
            awr       = f"{r['alpha_win_rate']:>7.1f}%" if r["alpha_win_rate"] is not None else "     N/A"
            avg_dd    = f"{r['avg_drawdown']:>+7.2f}%" if r["avg_drawdown"] is not None else "     N/A"

            lines.append(
                f"  {bucket:<8} {int(r['n']):>6}{flag} "
                f"{r['avg_return']:>+7.2f}% {r['median_return']:>+7.2f}% "
                f"{r['win_rate']:>7.1f}% "
                f"{avg_alpha} {med_alpha} "
                f"{awr} {avg_dd}"
            )

        lines.append("")

    lines.append("  ! = N < 30, interpretovat opatrně")
    lines.append("")

    return lines
