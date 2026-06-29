"""
Audit Test 6 — Health Regime Stability
audit/tests/regime_stability.py

Otázka:
    Jak dlouho přetrvávají silné Health režimy?

Definice režimu:
    Souvislé období kdy Health zůstává nad prahem (90, 80, 70).

Výstup:
    health_regime_stability.csv
"""

from __future__ import annotations

import pandas as pd
from audit.data_loader import AuditData

THRESHOLDS = [90, 80, 70]


def run(data: AuditData, lookback: int = 20) -> pd.DataFrame:
    health_df = data.health_for_lookback(lookback)
    rows = []

    for ticker in health_df["sector"].unique():
        if ticker == "SPY":
            continue

        ticker_df = health_df[health_df["sector"] == ticker].sort_values("date")
        dates     = ticker_df["date"].tolist()
        healths   = ticker_df["health"].tolist()

        for threshold in THRESHOLDS:
            regime_start = None
            regime_len   = 0

            for i, (dt, h) in enumerate(zip(dates, healths)):
                if h >= threshold:
                    if regime_start is None:
                        regime_start = dt
                        regime_len   = 1
                    else:
                        regime_len += 1
                else:
                    if regime_start is not None and regime_len > 0:
                        rows.append({
                            "lookback":   lookback,
                            "sector":     ticker,
                            "threshold":  threshold,
                            "start_date": regime_start,
                            "end_date":   dates[i - 1],
                            "duration":   regime_len,
                        })
                    regime_start = None
                    regime_len   = 0

            if regime_start is not None and regime_len > 0:
                rows.append({
                    "lookback":   lookback,
                    "sector":     ticker,
                    "threshold":  threshold,
                    "start_date": regime_start,
                    "end_date":   dates[-1],
                    "duration":   regime_len,
                })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 60)
    lines.append("AUDIT TEST 6 — HEALTH REGIME STABILITY")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Definice: Režim = souvislé období Health >= prahu")
    lines.append("")

    for lookback in df["lookback"].unique():
        lines.append(f"Lookback {lookback}D")
        lines.append("-" * 60)
        sub = df[df["lookback"] == lookback]

        for threshold in THRESHOLDS:
            t = sub[sub["threshold"] == threshold]
            if t.empty:
                continue

            lines.append(f"\n  Health >= {threshold}")
            summary = t.groupby("sector")["duration"].agg(
                count="count", avg="mean", median="median", max="max"
            ).round(1).sort_values("avg", ascending=False)

            lines.append(f"  {'Sector':<6} {'Regimes':>8} {'Avg':>7} {'Median':>8} {'Max':>6}")
            lines.append(f"  {'-'*6} {'-'*8} {'-'*7} {'-'*8} {'-'*6}")
            for sector, row in summary.iterrows():
                lines.append(
                    f"  {sector:<6} {int(row['count']):>8} "
                    f"{row['avg']:>6.1f}d {row['median']:>7.1f}d "
                    f"{int(row['max']):>5}d"
                )
        lines.append("")

    return lines
