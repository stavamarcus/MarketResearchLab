"""
Audit Test 5 — Component Importance
audit/tests/component_importance.py

Otázka:
    Které komponenty Health Score mají skutečnou hodnotu?

Metoda:
    Korelace každé komponenty s:
    - forward return (5D, 10D, 20D)
    - TOP3 retention (20D)

Výstup:
    component_importance.csv
"""

from __future__ import annotations

import pandas as pd
from audit.data_loader import AuditData, FORWARD_WINDOWS, get_forward_return

COMPONENTS = ["avg_rank", "rank_vol", "drop_score", "worst_rank", "top3_days"]


def run(data: AuditData, lookback: int = 20) -> pd.DataFrame:
    health_df = data.health_for_lookback(lookback)
    rank_df   = data.rank_for_lookback(lookback)

    rank_pivot   = rank_df.pivot(index="date", columns="sector", values="rank")
    dates_sorted = sorted(rank_pivot.index.tolist())
    date_idx     = {d: i for i, d in enumerate(dates_sorted)}

    rows = []

    for _, row in health_df.iterrows():
        ticker = row["sector"]
        if ticker == "SPY":
            continue
        dt = row["date"]
        i  = date_idx.get(dt)
        if i is None:
            continue

        base = {comp: row[comp] for comp in COMPONENTS if comp in row}
        base["health"] = row["health"]
        base["sector"] = ticker
        base["date"]   = dt
        base["lookback"] = lookback

        # Forward returns
        for window in [5, 10, 20]:
            fwd = get_forward_return(data.forward_returns, dt, ticker, window)
            spy = get_forward_return(data.forward_returns, dt, "SPY", window)
            base[f"fwd_{window}d"]        = round(fwd, 4) if fwd is not None else None
            base[f"excess_{window}d"]     = round(fwd - spy, 4) if fwd is not None and spy is not None else None

        # TOP3 retention 20D
        future_i = i + 20
        if future_i < len(dates_sorted):
            future_date = dates_sorted[future_i]
            if future_date in rank_pivot.index and ticker in rank_pivot.columns:
                fr = rank_pivot.loc[future_date, ticker]
                base["retained_top3_20d"] = int(fr) <= 3 if not pd.isna(fr) else None
            else:
                base["retained_top3_20d"] = None
        else:
            base["retained_top3_20d"] = None

        rows.append(base)

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 65)
    lines.append("AUDIT TEST 5 — COMPONENT IMPORTANCE")
    lines.append("=" * 65)
    lines.append("")
    lines.append("Metoda: Pearsonova korelace komponenty s forward výsledky")
    lines.append("")

    for lookback in df["lookback"].unique():
        lines.append(f"Lookback {lookback}D")
        lines.append("-" * 65)
        sub = df[df["lookback"] == lookback].copy()

        targets = {
            "fwd_5d":            "Forward Return 5D",
            "fwd_10d":           "Forward Return 10D",
            "fwd_20d":           "Forward Return 20D",
            "excess_20d":        "Excess Return vs SPY 20D",
            "retained_top3_20d": "TOP3 Retention 20D",
        }

        lines.append(f"\n  {'Komponenta':<15} " + " ".join(f"{k:>12}" for k in targets.keys()))
        lines.append(f"  {'-'*15} " + " ".join("-"*12 for _ in targets))

        for comp in COMPONENTS + ["health"]:
            if comp not in sub.columns:
                continue
            corr_vals = []
            for target_col in targets.keys():
                if target_col not in sub.columns:
                    corr_vals.append("N/A")
                    continue
                valid = sub[[comp, target_col]].dropna()
                if len(valid) < 30:
                    corr_vals.append("N/A")
                    continue
                c = valid[comp].corr(valid[target_col])
                corr_vals.append(f"{c:>+.3f}")

            lines.append(f"  {comp:<15} " + " ".join(f"{v:>12}" for v in corr_vals))

        lines.append("")
        lines.append("  Interpretace: |r| > 0.1 = slabý signál, > 0.2 = střední, > 0.3 = silný")
        lines.append("")

    return lines
