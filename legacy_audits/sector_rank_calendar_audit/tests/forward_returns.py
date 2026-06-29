"""
Audit Test 1 — Forward Return Analysis
audit/tests/forward_returns.py

Otázka:
    Produkují sektory s vyšším Health lepší budoucí výnosy?

Výstup:
    forward_returns.csv
    Sloupce: bucket, window, sample_count, avg_return, median_return,
             win_rate, avg_excess_return, median_excess_return
"""

from __future__ import annotations

import pandas as pd
from audit.data_loader import AuditData, HEALTH_BUCKETS, BUCKET_LABELS, FORWARD_WINDOWS, health_bucket, get_forward_return


def run(data: AuditData, lookback: int = 20) -> pd.DataFrame:
    """
    Spustí Forward Return Analysis.

    Args:
        data:     AuditData
        lookback: 20 nebo 30

    Returns:
        DataFrame s výsledky per bucket a window
    """
    health_df = data.health_for_lookback(lookback)
    rows = []

    for window in FORWARD_WINDOWS:
        bucket_data: dict[str, list] = {label: [] for label in BUCKET_LABELS}
        spy_data:    dict[str, list] = {label: [] for label in BUCKET_LABELS}

        for _, row in health_df.iterrows():
            ticker = row["sector"]
            dt     = row["date"]
            h      = int(row["health"])
            bucket = health_bucket(h)

            # True forward return z close prices
            fwd = get_forward_return(data.forward_returns, dt, ticker, window)
            if fwd is None:
                continue

            # SPY forward return pro excess return výpočet
            spy_fwd = get_forward_return(data.forward_returns, dt, "SPY", window)

            bucket_data[bucket].append(fwd)
            if spy_fwd is not None:
                spy_data[bucket].append(fwd - spy_fwd)

        for label in BUCKET_LABELS:
            vals        = bucket_data[label]
            excess_vals = spy_data[label]

            if not vals:
                continue

            s = pd.Series(vals)
            rows.append({
                "lookback":             lookback,
                "window":               f"{window}D",
                "bucket":               label,
                "sample_count":         len(vals),
                "avg_return":           round(s.mean(), 2),
                "median_return":        round(s.median(), 2),
                "win_rate":             round((s > 0).mean() * 100, 1),
                "avg_excess_return":    round(pd.Series(excess_vals).mean(), 2) if excess_vals else None,
                "median_excess_return": round(pd.Series(excess_vals).median(), 2) if excess_vals else None,
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 65)
    lines.append("AUDIT TEST 1 — FORWARD RETURN ANALYSIS")
    lines.append("=" * 65)
    lines.append("")
    lines.append("Otázka: Produkují sektory s vyšším Health lepší budoucí výnosy?")
    lines.append("")

    for lookback in df["lookback"].unique():
        lines.append(f"Lookback {lookback}D")
        lines.append("-" * 65)
        sub = df[df["lookback"] == lookback]

        for window in sub["window"].unique():
            w = sub[sub["window"] == window]
            lines.append(f"\n  Forward {window}:")
            lines.append(f"  {'Bucket':<10} {'N':>6} {'AvgRet':>8} {'MedRet':>8} {'WinRate':>8} {'AvgExcess':>10}")
            lines.append(f"  {'-'*10} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
            for _, r in w.iterrows():
                exc = f"{r['avg_excess_return']:>+8.2f}%" if r["avg_excess_return"] is not None else "     N/A"
                lines.append(
                    f"  {r['bucket']:<10} {r['sample_count']:>6} "
                    f"{r['avg_return']:>+7.2f}% {r['median_return']:>+7.2f}% "
                    f"{r['win_rate']:>7.1f}% {exc}"
                )
        lines.append("")

    return lines
