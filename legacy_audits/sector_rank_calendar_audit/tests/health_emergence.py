"""
Audit Test 7 — Health Is Not Emergence
audit/tests/health_emergence.py

Otázka:
    Predikuje nízký Health budoucí emergence (nástup nového lídra)?

Hypotéza k ověření:
    Health < 30 → následné zlepšení ranku?

Očekávání architekta:
    Health NENÍ emergence predictor.
    Tento test má tuto hypotézu potvrdit daty.

Výstup:
    health_emergence.csv
"""

from __future__ import annotations

import pandas as pd
from audit.data_loader import AuditData, get_forward_return

LOW_HEALTH_THRESHOLD = 30
EMERGENCE_RANK_THRESHOLD = 3  # zlepšení do TOP3 = emergence


def run(data: AuditData, lookback: int = 20) -> pd.DataFrame:
    health_df = data.health_for_lookback(lookback)
    rank_df   = data.rank_for_lookback(lookback)

    rank_pivot   = rank_df.pivot(index="date", columns="sector", values="rank")
    dates_sorted = sorted(rank_pivot.index.tolist())
    date_idx     = {d: i for i, d in enumerate(dates_sorted)}

    rows = []

    # Filtruj záznamy s nízkým Health
    low_health = health_df[
        (health_df["health"] < LOW_HEALTH_THRESHOLD) &
        (health_df["sector"] != "SPY")
    ]

    for _, row in low_health.iterrows():
        ticker = row["sector"]
        dt     = row["date"]
        h      = int(row["health"])
        i      = date_idx.get(dt)
        if i is None:
            continue

        current_rank = None
        if dt in rank_pivot.index and ticker in rank_pivot.columns:
            cr = rank_pivot.loc[dt, ticker]
            current_rank = int(cr) if not pd.isna(cr) else None

        for window in [10, 20, 30]:
            future_i = i + window
            if future_i >= len(dates_sorted):
                continue

            future_date  = dates_sorted[future_i]
            future_rank  = None
            if future_date in rank_pivot.index and ticker in rank_pivot.columns:
                fr = rank_pivot.loc[future_date, ticker]
                future_rank = int(fr) if not pd.isna(fr) else None

            emerged = (future_rank is not None and future_rank <= EMERGENCE_RANK_THRESHOLD
                       and (current_rank is None or current_rank > EMERGENCE_RANK_THRESHOLD))

            fwd = get_forward_return(data.forward_returns, dt, ticker, window)

            rows.append({
                "lookback":      lookback,
                "sector":        ticker,
                "date":          dt,
                "health":        h,
                "current_rank":  current_rank,
                "window":        f"{window}D",
                "future_rank":   future_rank,
                "emerged_top3":  emerged,
                "forward_return": round(fwd, 2) if fwd is not None else None,
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 65)
    lines.append("AUDIT TEST 7 — HEALTH IS NOT EMERGENCE")
    lines.append("=" * 65)
    lines.append("")
    lines.append(f"Otázka: Predikuje Health < {LOW_HEALTH_THRESHOLD} budoucí vzestup sektoru?")
    lines.append("Hypotéza: Health NENÍ emergence predictor.")
    lines.append("")

    for lookback in df["lookback"].unique():
        lines.append(f"Lookback {lookback}D")
        lines.append("-" * 65)
        sub = df[df["lookback"] == lookback]

        lines.append(f"  Celkem Low Health observací (H < {LOW_HEALTH_THRESHOLD}): {sub['date'].nunique()}")
        lines.append("")

        for window in ["10D", "20D", "30D"]:
            w = sub[sub["window"] == window]
            if w.empty:
                continue

            emergence_rate = w["emerged_top3"].mean() * 100
            avg_fwd        = w["forward_return"].dropna().mean()

            lines.append(f"  Po {window}:")
            lines.append(f"    Emergence rate (vzestup do TOP3): {emergence_rate:.1f}%")
            lines.append(f"    Avg forward return:               {avg_fwd:+.2f}%" if avg_fwd is not None else "    Avg forward return: N/A")
            lines.append("")

        lines.append("  Závěr: Pokud emergence rate < 15%, hypotéza potvrzena.")
        lines.append("")

    return lines
