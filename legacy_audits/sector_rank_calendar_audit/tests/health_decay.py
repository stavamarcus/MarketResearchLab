"""
Audit Test 3 — Health Decay Analysis
audit/tests/health_decay.py

Otázka:
    Varuje klesající Health před ztrátou leadershipu?

Tři definice decay:
    Decay A: 2 po sobě jdoucí poklesy Health
    Decay B: 3 po sobě jdoucí poklesy Health
    Decay C: pokles > 10 bodů za 5 dní

Výstup:
    health_decay.csv
"""

from __future__ import annotations

import pandas as pd
from audit.data_loader import AuditData, BUCKET_LABELS, FORWARD_WINDOWS, get_forward_return


def _detect_decay_a(health_series: list[int], idx: int) -> bool:
    """2 po sobě jdoucí poklesy."""
    if idx < 2:
        return False
    return health_series[idx] < health_series[idx-1] < health_series[idx-2]


def _detect_decay_b(health_series: list[int], idx: int) -> bool:
    """3 po sobě jdoucí poklesy."""
    if idx < 3:
        return False
    return (health_series[idx] < health_series[idx-1] <
            health_series[idx-2] < health_series[idx-3])


def _detect_decay_c(health_series: list[int], idx: int) -> bool:
    """Pokles > 10 bodů za posledních 5 observací."""
    if idx < 5:
        return False
    return (health_series[idx-5] - health_series[idx]) > 10


def run(data: AuditData, lookback: int = 20) -> pd.DataFrame:
    health_df = data.health_for_lookback(lookback)
    rank_df   = data.rank_for_lookback(lookback)

    rank_pivot = rank_df.pivot(index="date", columns="sector", values="rank")
    dates_sorted = sorted(rank_pivot.index.tolist())
    date_idx = {d: i for i, d in enumerate(dates_sorted)}

    rows = []
    decay_defs = {
        "Decay_A": _detect_decay_a,
        "Decay_B": _detect_decay_b,
        "Decay_C": _detect_decay_c,
    }

    # Per sektor — sestav časovou řadu Health
    for ticker in health_df["sector"].unique():
        if ticker == "SPY":
            continue

        ticker_health = health_df[health_df["sector"] == ticker].sort_values("date")
        health_series = ticker_health["health"].tolist()
        date_series   = ticker_health["date"].tolist()

        for i, (dt, h) in enumerate(zip(date_series, health_series)):
            for decay_name, decay_fn in decay_defs.items():
                if not decay_fn(health_series, i):
                    continue

                # Decay detekován — co se stalo dál?
                date_i = date_idx.get(dt)
                if date_i is None:
                    continue

                for window in [5, 10, 20]:
                    future_i = date_i + window
                    if future_i >= len(dates_sorted):
                        continue

                    future_date = dates_sorted[future_i]

                    # Ztratil sektor TOP3?
                    current_rank = rank_pivot.loc[dt, ticker] if dt in rank_pivot.index and ticker in rank_pivot.columns else None
                    future_rank  = rank_pivot.loc[future_date, ticker] if future_date in rank_pivot.index and ticker in rank_pivot.columns else None

                    was_top3    = int(current_rank) <= 3 if current_rank is not None and not pd.isna(current_rank) else False
                    lost_top3   = (future_rank is not None and not pd.isna(future_rank) and int(future_rank) > 3) if was_top3 else None

                    # Forward return
                    fwd = get_forward_return(data.forward_returns, dt, ticker, window)

                    rows.append({
                        "lookback":      lookback,
                        "decay_pattern": decay_name,
                        "sector":        ticker,
                        "date":          dt,
                        "health_at_decay": h,
                        "window":        f"{window}D",
                        "was_top3":      was_top3,
                        "lost_top3":     lost_top3,
                        "forward_return": round(fwd, 2) if fwd is not None else None,
                    })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 65)
    lines.append("AUDIT TEST 3 — HEALTH DECAY ANALYSIS")
    lines.append("=" * 65)
    lines.append("")
    lines.append("Otázka: Varuje klesající Health před ztrátou leadershipu?")
    lines.append("")
    lines.append("Definice:")
    lines.append("  Decay A: 2 po sobě jdoucí poklesy Health")
    lines.append("  Decay B: 3 po sobě jdoucí poklesy Health")
    lines.append("  Decay C: pokles > 10 bodů za 5 observací")
    lines.append("")

    for lookback in df["lookback"].unique():
        lines.append(f"Lookback {lookback}D")
        lines.append("-" * 65)
        sub = df[df["lookback"] == lookback]

        for decay in ["Decay_A", "Decay_B", "Decay_C"]:
            d = sub[sub["decay_pattern"] == decay]
            if d.empty:
                continue
            lines.append(f"\n  {decay} (N detekováno: {len(d['date'].unique())} events)")

            for window in ["5D", "10D", "20D"]:
                w = d[d["window"] == window]
                if w.empty:
                    continue

                # TOP3 ztráta
                top3_subset = w[w["was_top3"] == True]
                if not top3_subset.empty:
                    loss_rate = top3_subset["lost_top3"].mean() * 100
                    n_top3    = len(top3_subset)
                else:
                    loss_rate = None
                    n_top3    = 0

                # Forward return
                fwd_vals = w["forward_return"].dropna()
                avg_fwd  = fwd_vals.mean() if not fwd_vals.empty else None

                loss_str = f"{loss_rate:.1f}%" if loss_rate is not None else "N/A"
                fwd_str  = f"{avg_fwd:+.2f}%" if avg_fwd is not None else "N/A"

                lines.append(
                    f"    {window}: TOP3 loss rate={loss_str} (n={n_top3})  "
                    f"avg fwd return={fwd_str}"
                )
        lines.append("")

    return lines
