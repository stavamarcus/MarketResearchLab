"""
Audit Test 4 — Leadership Cycle Analysis
audit/tests/leadership_cycles.py

Otázka:
    Jak dlouho trvá sektorový leadership?

Definice Leadership Cycle:
    Souvislé období kdy sektor zůstává v TOP3.

Výstup:
    leadership_cycles.csv
"""

from __future__ import annotations

import pandas as pd
from audit.data_loader import AuditData


def run(data: AuditData, lookback: int = 20) -> pd.DataFrame:
    rank_df = data.rank_for_lookback(lookback)

    # Pivot: date × sector → rank
    pivot = rank_df[rank_df["sector"] != "SPY"].pivot(
        index="date", columns="sector", values="rank"
    ).sort_index()

    dates = sorted(pivot.index.tolist())
    rows  = []

    for ticker in pivot.columns:
        series    = pivot[ticker].reindex(dates)
        in_top3   = (series <= 3)

        cycle_start = None
        cycle_len   = 0

        for i, dt in enumerate(dates):
            if in_top3.iloc[i]:
                if cycle_start is None:
                    cycle_start = dt
                    cycle_len   = 1
                else:
                    cycle_len += 1
            else:
                if cycle_start is not None and cycle_len > 0:
                    rows.append({
                        "lookback":    lookback,
                        "sector":      ticker,
                        "start_date":  cycle_start,
                        "end_date":    dates[i - 1],
                        "duration_td": cycle_len,  # trading days
                    })
                cycle_start = None
                cycle_len   = 0

        # Uzavři poslední cyklus pokud stále probíhá
        if cycle_start is not None and cycle_len > 0:
            rows.append({
                "lookback":    lookback,
                "sector":      ticker,
                "start_date":  cycle_start,
                "end_date":    dates[-1],
                "duration_td": cycle_len,
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 60)
    lines.append("AUDIT TEST 4 — LEADERSHIP CYCLE ANALYSIS")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Definice: Cycle = souvislé období v TOP3 (obchodní dny)")
    lines.append("")

    for lookback in df["lookback"].unique():
        lines.append(f"Lookback {lookback}D")
        lines.append("-" * 60)
        sub = df[df["lookback"] == lookback]

        # Summary per sektor
        summary = sub.groupby("sector")["duration_td"].agg(
            cycles="count",
            avg_duration="mean",
            median_duration="median",
            max_duration="max",
            min_duration="min",
        ).round(1).sort_values("avg_duration", ascending=False)

        lines.append(f"\n  {'Sector':<6} {'Cycles':>7} {'Avg':>7} {'Median':>8} {'Max':>6} {'Min':>6}")
        lines.append(f"  {'-'*6} {'-'*7} {'-'*7} {'-'*8} {'-'*6} {'-'*6}")
        for sector, row in summary.iterrows():
            lines.append(
                f"  {sector:<6} {int(row['cycles']):>7} "
                f"{row['avg_duration']:>6.1f}d {row['median_duration']:>7.1f}d "
                f"{int(row['max_duration']):>5}d {int(row['min_duration']):>5}d"
            )

        # Celkové statistiky
        lines.append(f"\n  Celkem cyklů: {len(sub)}")
        lines.append(f"  Průměrná délka: {sub['duration_td'].mean():.1f} dní")
        lines.append(f"  Medián délky: {sub['duration_td'].median():.1f} dní")
        lines.append(f"  Nejdelší cyklus: {sub['duration_td'].max()} dní "
                     f"({sub.loc[sub['duration_td'].idxmax(), 'sector']} "
                     f"{sub.loc[sub['duration_td'].idxmax(), 'start_date']})")
        lines.append("")

    return lines
