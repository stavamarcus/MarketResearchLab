"""
IMS Audit — Relative Performance
audit/tests/relative_performance.py

Zodpovědnost:
    Sekce C: alpha vs SPY per score bucket a window.
    Odpovídá na otázku: generují IMS signály excess return nad trhem?

Metriky:
    avg_alpha       — průměrný excess return vs SPY
    median_alpha    — medián excess return vs SPY
    alpha_win_rate  — % signálů kde ticker > SPY ve stejném okně
    pct_beat_spy    — alias pro alpha_win_rate (explicitnější název v reportu)

Výstup:
    pd.DataFrame — jeden řádek per (bucket, window)
    Sloupce:
        bucket, window, n,
        avg_alpha, median_alpha, alpha_win_rate,
        avg_ticker_return, avg_spy_return

Použití:
    from audit.tests.relative_performance import run
    df = run(forward_df)
"""

from __future__ import annotations

import pandas as pd

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
    Agreguje alpha vs SPY per score bucket a window.

    Args:
        forward_df: výstup z forward_returns.compute_forward_returns()

    Returns:
        pd.DataFrame s alpha metrikami per (bucket, window)
    """
    rows = []

    for bucket_name, (lo, hi) in SCORE_BUCKETS.items():
        subset = forward_df[
            (forward_df["score"] >= lo) & (forward_df["score"] < hi)
        ].copy()

        if subset.empty:
            continue

        for window in FORWARD_WINDOWS:
            col_alpha = f"alpha_{window}d"
            col_fwd   = f"fwd_{window}d"
            col_spy   = f"spy_{window}d"
            col_use   = f"usable_{window}d"

            if col_use not in subset.columns:
                continue

            usable = subset[subset[col_use] == True]
            if usable.empty:
                continue

            alpha_vals  = usable[col_alpha].dropna()
            fwd_vals    = usable[col_fwd].dropna()
            spy_vals    = usable[col_spy].dropna()

            if len(alpha_vals) < 5:
                continue

            rows.append({
                "bucket":            bucket_name,
                "window":            f"{window}D",
                "n":                 len(alpha_vals),
                "avg_alpha":         round(alpha_vals.mean(), 4),
                "median_alpha":      round(alpha_vals.median(), 4),
                "alpha_win_rate":    round((alpha_vals > 0).mean() * 100, 2),
                "avg_ticker_return": round(fwd_vals.mean(), 4),
                "avg_spy_return":    round(spy_vals.mean(), 4),
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    """
    Sestaví textový report sekce C.

    Args:
        df: výstup z run()

    Returns:
        list[str] — řádky reportu
    """
    lines = []
    lines.append("=" * 65)
    lines.append("SEKCE C — RELATIVE PERFORMANCE vs SPY")
    lines.append("=" * 65)
    lines.append("")
    lines.append("Alpha        : ticker return − SPY return (stejné okno)")
    lines.append("Alpha WinRate: % signálů kde ticker překonal SPY")
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
            f"  {'Bucket':<10} {'N':>6} {'AvgAlpha':>10} {'MedAlpha':>10} "
            f"{'AlphaWR':>9} {'AvgTicker':>10} {'AvgSPY':>8}"
        )
        lines.append(
            f"  {'-'*10} {'-'*6} {'-'*10} {'-'*10} "
            f"{'-'*9} {'-'*10} {'-'*8}"
        )

        for bucket in bucket_order:
            row = sub[sub["bucket"] == bucket]
            if row.empty:
                continue
            r = row.iloc[0]

            lines.append(
                f"  {bucket:<10} {int(r['n']):>6} "
                f"{r['avg_alpha']:>+9.2f}% {r['median_alpha']:>+9.2f}% "
                f"{r['alpha_win_rate']:>8.1f}% "
                f"{r['avg_ticker_return']:>+9.2f}% {r['avg_spy_return']:>+7.2f}%"
            )

        lines.append("")

    lines.append("-" * 65)
    lines.append("INTERPRETACE")
    lines.append("-" * 65)
    lines.append("  avg_alpha > 0 = IMS signály v průměru překonávají SPY")
    lines.append("  avg_alpha < 0 = IMS signály zaostávají za SPY")
    lines.append("")
    lines.append("  Důležité: kladný avg return bez kladné alphy = beta exposure,")
    lines.append("  ne skill. Pokud SPY ve stejném období +4% a signály +3%,")
    lines.append("  alpha je záporná i přes kladný absolutní výnos.")
    lines.append("")

    return lines
