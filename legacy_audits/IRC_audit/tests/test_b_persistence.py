"""
Industry Rank Calendar Audit — Test B
audit/tests/test_b_persistence.py

Otázka:
    Dosahují akcie z industry s vysokou persistence lepších forward returns?
    Persistence = počet dní v TOP10 za posledních 20D.

Buckety:
    HIGH   : persist >= 15/20  (75%+)
    MED    : persist 10–14/20  (50–70%)
    LOW    : persist 5–9/20    (25–45%)
    NONE   : persist 0–4/20    (0–20%)

Hypotéza:
    H0: persistence nepredikuje forward returns
    H1: vyšší persistence → konzistentnější forward returns

Interpretace:
    HIGH persistence = industry stabilně vede → silnější tailwind
    NONE persistence = industry nikdy nebyla v TOP10 → slabý/žádný tailwind
"""

from __future__ import annotations

import pandas as pd

FORWARD_WINDOWS = [5, 10, 20, 30]

PERSIST_BUCKETS: dict[str, tuple[int, int]] = {
    "HIGH (15-20)": (15, 20),
    "MED  (10-14)": (10, 14),
    "LOW  (5-9)":   (5, 9),
    "NONE (0-4)":   (0, 4),
}


def run(forward_df: pd.DataFrame) -> pd.DataFrame:
    """
    Agreguje forward returns per persistence bucket.
    """
    rows = []

    for bucket_name, (lo, hi) in PERSIST_BUCKETS.items():
        subset = forward_df[
            (forward_df["industry_persist"] >= lo) &
            (forward_df["industry_persist"] <= hi)
        ].copy()

        if subset.empty:
            continue

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

            if len(fwd_vals) < 10:
                continue

            rows.append({
                "bucket":        bucket_name,
                "window":        f"{window}D",
                "n":             len(fwd_vals),
                "avg_return":    round(fwd_vals.mean(), 4),
                "median_return": round(fwd_vals.median(), 4),
                "win_rate":      round((fwd_vals > 0).mean() * 100, 2),
                "avg_alpha":     round(alpha_vals.mean(), 4) if not alpha_vals.empty else None,
                "avg_drawdown":  round(dd_vals.mean(), 4) if not dd_vals.empty else None,
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST B — INDUSTRY PERSISTENCE EFFECT")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Ma persistence industry v TOP10 vliv na forward returns?")
    lines.append("Persistence = pocet dni v TOP10 za poslednich 20 obchodnich dni")
    lines.append("")

    bucket_order = list(PERSIST_BUCKETS.keys())

    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = df[df["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 70)
        lines.append(
            f"  {'Bucket':<16}  {'N':>6}  {'Avg%':>8}  {'Med%':>8}  "
            f"{'WinRate':>8}  {'AvgAlpha':>9}  {'AvgDD%':>8}"
        )
        lines.append(
            f"  {'-'*16}  {'-'*6}  {'-'*8}  {'-'*8}  "
            f"{'-'*8}  {'-'*9}  {'-'*8}"
        )

        for bucket in bucket_order:
            row = sub[sub["bucket"] == bucket]
            if row.empty:
                continue
            r = row.iloc[0]

            alpha_str = f"{r['avg_alpha']:>+8.2f}%" if r["avg_alpha"] is not None else "      N/A"
            dd_str    = f"{r['avg_drawdown']:>+7.2f}%" if r["avg_drawdown"] is not None else "     N/A"

            lines.append(
                f"  {bucket:<16}  {int(r['n']):>6}  "
                f"{r['avg_return']:>+7.2f}%  {r['median_return']:>+7.2f}%  "
                f"{r['win_rate']:>7.1f}%  {alpha_str}  {dd_str}"
            )

        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  HIGH persistence → lepsi returns = persistence ma prediktivni hodnotu")
    lines.append("  Plochý trend = persistence neni dalsi informace nad samotnym rankem")
    lines.append("")

    return lines
