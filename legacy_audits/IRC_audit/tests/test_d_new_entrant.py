"""
Industry Rank Calendar Audit — Test D
audit/tests/test_d_new_entrant.py

Otázka:
    Mají akcie z industry které právě vstoupily do TOP10 lepší forward returns
    než akcie z industry které jsou v TOP10 stabilně?

    New Entrant = industry vstoupila do TOP10 dnes, ale včera v TOP10 nebyla.

Hypotéza:
    H0: nový vstup do TOP10 nepredikuje forward returns
    H1: nový vstup signalizuje rotaci kapitálu → vyšší forward returns

Interpretace:
    NEW_ENTRANT > ESTABLISHED = hledat nové rotace, ne jen stabilní leadery
    NEW_ENTRANT < ESTABLISHED = stabilita je cennější než rychlost vstupu
    NEW_ENTRANT ≈ ESTABLISHED = vstup samotný nemá prediktivní hodnotu
"""

from __future__ import annotations

import pandas as pd

FORWARD_WINDOWS = [5, 10, 20, 30]


def run(forward_df: pd.DataFrame) -> pd.DataFrame:
    """
    Porovná forward returns: New Entrant vs. Established (stabilní v TOP10).
    Established = v TOP10 a is_new_entrant = False.
    """
    rows = []

    groups = {
        "NEW_ENTRANT":  forward_df[forward_df["is_new_entrant"] == True],
        "ESTABLISHED":  forward_df[
            (forward_df["industry_rank"] <= 10) &
            (forward_df["is_new_entrant"] == False)
        ],
        "OUTSIDE_TOP10": forward_df[forward_df["industry_rank"] > 10],
    }

    for group_name, subset in groups.items():
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

            if len(fwd_vals) < 5:
                continue

            rows.append({
                "group":         group_name,
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
    lines.append("TEST D — NEW ENTRANT EFFECT")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Maji akcie z industry ktera prave vstoupila do TOP10")
    lines.append("        lepsi returns nez akcie z ustalenych TOP10 industry?")
    lines.append("")
    lines.append("NEW_ENTRANT   = industry vstoupila do TOP10 dnes (vcera nebyla)")
    lines.append("ESTABLISHED   = industry je v TOP10 a neni NEW_ENTRANT")
    lines.append("OUTSIDE_TOP10 = industry neni v TOP10")
    lines.append("")

    group_order = ["NEW_ENTRANT", "ESTABLISHED", "OUTSIDE_TOP10"]

    for window in FORWARD_WINDOWS:
        w_str = f"{window}D"
        sub   = df[df["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 70)
        lines.append(
            f"  {'Skupina':<14}  {'N':>6}  {'Avg%':>8}  {'Med%':>8}  "
            f"{'WinRate':>8}  {'AvgAlpha':>9}  {'AvgDD%':>8}"
        )
        lines.append(
            f"  {'-'*14}  {'-'*6}  {'-'*8}  {'-'*8}  "
            f"{'-'*8}  {'-'*9}  {'-'*8}"
        )

        for group in group_order:
            row = sub[sub["group"] == group]
            if row.empty:
                continue
            r = row.iloc[0]
            alpha_str = f"{r['avg_alpha']:>+8.2f}%" if r["avg_alpha"] is not None else "      N/A"
            dd_str    = f"{r['avg_drawdown']:>+7.2f}%" if r["avg_drawdown"] is not None else "     N/A"
            lines.append(
                f"  {group:<14}  {int(r['n']):>6}  "
                f"{r['avg_return']:>+7.2f}%  {r['median_return']:>+7.2f}%  "
                f"{r['win_rate']:>7.1f}%  {alpha_str}  {dd_str}"
            )

        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  NEW_ENTRANT > ESTABLISHED = hledat nove rotace (momentum vstupu)")
    lines.append("  NEW_ENTRANT < ESTABLISHED = stabilita lepsim prediktorem")
    lines.append("  NEW_ENTRANT ≈ ESTABLISHED = vstup sam o sobe nema prediktivni hodnotu")
    lines.append("")

    return lines
