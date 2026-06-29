"""
Audit Test 2 — Leadership Persistence (TOP3 Retention)
audit/tests/top3_retention.py

Otázka:
    Zůstávají zdravé sektory lídry déle?

Výstup:
    top3_retention.csv
    Sloupce: bucket, window, sample_count, retention_rate
"""

from __future__ import annotations

import pandas as pd
from audit.data_loader import AuditData, BUCKET_LABELS, FORWARD_WINDOWS, health_bucket


def run(data: AuditData, lookback: int = 20) -> pd.DataFrame:
    health_df = data.health_for_lookback(lookback)
    rank_df   = data.rank_for_lookback(lookback)

    # Pivot ranků: date → { sector: rank }
    rank_pivot = rank_df.pivot(index="date", columns="sector", values="rank")
    dates_sorted = sorted(rank_pivot.index.tolist())
    date_idx = {d: i for i, d in enumerate(dates_sorted)}

    rows = []

    for window in FORWARD_WINDOWS:
        bucket_total:    dict[str, int] = {label: 0 for label in BUCKET_LABELS}
        bucket_retained: dict[str, int] = {label: 0 for label in BUCKET_LABELS}

        # Filtruj pouze sektory které jsou v TOP3 v daný den
        top3 = health_df[health_df["sector"] != "SPY"].copy()
        # Merge s rank aby byl rank dostupný
        top3 = top3.merge(
            rank_df[["date", "sector", "rank"]],
            on=["date", "sector"], how="left"
        )
        top3 = top3[top3["rank"] <= 3]

        for _, row in top3.iterrows():
            ticker = row["sector"]
            dt     = row["date"]
            h      = int(row["health"])
            bucket = health_bucket(h)

            # Zjisti rank za window dní
            i = date_idx.get(dt)
            if i is None:
                continue
            future_i = i + window
            if future_i >= len(dates_sorted):
                continue  # konec datasetu — vyloučit

            future_date = dates_sorted[future_i]
            if future_date not in rank_pivot.index or ticker not in rank_pivot.columns:
                continue

            future_rank = rank_pivot.loc[future_date, ticker]
            if pd.isna(future_rank):
                continue

            bucket_total[bucket] += 1
            if int(future_rank) <= 3:
                bucket_retained[bucket] += 1

        for label in BUCKET_LABELS:
            n = bucket_total[label]
            if n == 0:
                continue
            rows.append({
                "lookback":       lookback,
                "window":         f"{window}D",
                "bucket":         label,
                "sample_count":   n,
                "retention_rate": round(bucket_retained[label] / n * 100, 1),
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 55)
    lines.append("AUDIT TEST 2 — TOP3 RETENTION RATE")
    lines.append("=" * 55)
    lines.append("")
    lines.append("Otázka: Zůstávají zdravé sektory lídry déle?")
    lines.append("Měří: % sektorů v TOP3 které zůstanou v TOP3 po N dnech")
    lines.append("")

    for lookback in df["lookback"].unique():
        lines.append(f"Lookback {lookback}D")
        lines.append("-" * 55)
        sub = df[df["lookback"] == lookback]

        for window in sub["window"].unique():
            w = sub[sub["window"] == window]
            lines.append(f"\n  Po {window}:")
            lines.append(f"  {'Bucket':<10} {'N':>6} {'Retention':>10}")
            lines.append(f"  {'-'*10} {'-'*6} {'-'*10}")
            for _, r in w.iterrows():
                lines.append(
                    f"  {r['bucket']:<10} {r['sample_count']:>6} "
                    f"{r['retention_rate']:>9.1f}%"
                )
        lines.append("")

    return lines
