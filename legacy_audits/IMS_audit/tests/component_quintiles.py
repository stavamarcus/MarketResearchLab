"""
IMS Audit v2 — Component Predictive Power (Quintile Analysis)
audit/tests/component_quintiles.py

Zodpovědnost:
    Sekce G: pro každou scoring komponentu rozděl signály do kvintilů
    a změř forward returns 20D a 30D.

    Otázka: Má každá komponenta samostatně prediktivní hodnotu?
    Pokud Q5 (top kvintil) konzistentně > Q1 (bottom), komponenta je užitečná.
    Pokud je vztah plochý, komponenta nepřispívá k predikci výnosů.

Komponenty:
    rank_improvement_20d
    rank_improvement_40d
    rs_vs_spy_20d
    up_down_volume_ratio_20d
    rank_stability_20d  — pozor: nižší = lepší (invertní logika)

Kvintily:
    Q1 = bottom 20% hodnot komponenty
    Q5 = top 20% hodnot komponenty

Metriky: 20D a 30D
    N, avg_return, median_return, win_rate,
    avg_alpha, median_alpha, alpha_win_rate
"""

from __future__ import annotations

import pandas as pd

COMPONENTS = [
    ("rank_improvement_20d",    True),   # (název, vyšší = lepší?)
    ("rank_improvement_40d",    True),
    ("rs_vs_spy_20d",           True),
    ("up_down_volume_ratio_20d", True),
    ("rank_stability_20d",      False),  # nižší = lepší (stabilnější rank)
]

WINDOWS = [20, 30]


def run(forward_df: pd.DataFrame) -> pd.DataFrame:
    """
    Rozdělí signály do kvintilů per komponenta a změří forward returns.

    Args:
        forward_df: výstup z compute_forward_returns() s komponentami z archivu

    Returns:
        pd.DataFrame — jeden řádek per (component, quintile, window)
    """
    rows = []

    for comp, higher_is_better in COMPONENTS:
        if comp not in forward_df.columns:
            continue

        # Přiřaď kvintily na základě hodnoty komponenty
        valid = forward_df[forward_df[comp].notna()].copy()
        if len(valid) < 50:
            continue

        valid["quintile"] = pd.qcut(
            valid[comp],
            q=5,
            labels=["Q1", "Q2", "Q3", "Q4", "Q5"],
            duplicates="drop",
        )

        for quintile in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
            subset = valid[valid["quintile"] == quintile]

            for window in WINDOWS:
                col_fwd   = f"fwd_{window}d"
                col_alpha = f"alpha_{window}d"
                col_use   = f"usable_{window}d"

                if col_use not in subset.columns:
                    continue

                usable = subset[subset[col_use] == True]
                if usable.empty:
                    continue

                fwd_vals   = usable[col_fwd].dropna()
                alpha_vals = usable[col_alpha].dropna()

                if len(fwd_vals) < 5:
                    continue

                rows.append({
                    "component":       comp,
                    "higher_is_better": higher_is_better,
                    "quintile":        quintile,
                    "window":          f"{window}D",
                    "n":               len(fwd_vals),
                    "avg_return":      round(fwd_vals.mean(), 4),
                    "median_return":   round(fwd_vals.median(), 4),
                    "win_rate":        round((fwd_vals > 0).mean() * 100, 2),
                    "avg_alpha":       round(alpha_vals.mean(), 4) if not alpha_vals.empty else None,
                    "median_alpha":    round(alpha_vals.median(), 4) if not alpha_vals.empty else None,
                    "alpha_win_rate":  round((alpha_vals > 0).mean() * 100, 2) if not alpha_vals.empty else None,
                })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 75)
    lines.append("SEKCE G — COMPONENT PREDICTIVE POWER (QUINTILE ANALYSIS)")
    lines.append("=" * 75)
    lines.append("")
    lines.append("Každá komponenta rozdělena do 5 kvintilů.")
    lines.append("Q1 = nejnižší hodnoty, Q5 = nejvyšší hodnoty komponenty.")
    lines.append("Výjimka: rank_stability — Q1 = nejstabilnější (nižší = lepší).")
    lines.append("")
    lines.append("Pokud Q5 >> Q1 → komponenta má prediktivní hodnotu.")
    lines.append("Pokud Q5 ≈ Q1 → komponenta nepřispívá k předpovědi výnosů.")
    lines.append("")

    comp_order = [c for c, _ in COMPONENTS]

    for comp in comp_order:
        sub = df[df["component"] == comp]
        if sub.empty:
            continue

        higher = df[df["component"] == comp]["higher_is_better"].iloc[0]
        note   = "(vyšší hodnota = lepší)" if higher else "(nižší hodnota = lepší — invertní)"

        lines.append(f"Komponenta: {comp}  {note}")
        lines.append("-" * 75)

        for window in WINDOWS:
            w_str = f"{window}D"
            w_sub = sub[sub["window"] == w_str]
            if w_sub.empty:
                continue

            lines.append(f"  Forward {w_str}:")
            lines.append(
                f"  {'Kvintil':<8} {'N':>6} {'AvgRet':>8} {'MedRet':>8} "
                f"{'WinRate':>8} {'AvgAlpha':>10} {'MedAlpha':>10} {'AlphaWR':>8}"
            )
            lines.append(
                f"  {'-'*8} {'-'*6} {'-'*8} {'-'*8} "
                f"{'-'*8} {'-'*10} {'-'*10} {'-'*8}"
            )

            for q in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
                row = w_sub[w_sub["quintile"] == q]
                if row.empty:
                    continue
                r = row.iloc[0]

                avg_alpha = f"{r['avg_alpha']:>+9.2f}%" if r["avg_alpha"] is not None else "       N/A"
                med_alpha = f"{r['median_alpha']:>+9.2f}%" if r["median_alpha"] is not None else "       N/A"
                awr       = f"{r['alpha_win_rate']:>7.1f}%" if r["alpha_win_rate"] is not None else "     N/A"

                lines.append(
                    f"  {q:<8} {int(r['n']):>6} "
                    f"{r['avg_return']:>+7.2f}% {r['median_return']:>+7.2f}% "
                    f"{r['win_rate']:>7.1f}% "
                    f"{avg_alpha} {med_alpha} {awr}"
                )

            # Q5 vs Q1 delta
            q1 = w_sub[w_sub["quintile"] == "Q1"]
            q5 = w_sub[w_sub["quintile"] == "Q5"]
            if not q1.empty and not q5.empty:
                delta_ret   = q5.iloc[0]["avg_return"]   - q1.iloc[0]["avg_return"]
                delta_alpha = q5.iloc[0]["avg_alpha"]     - q1.iloc[0]["avg_alpha"] \
                              if q5.iloc[0]["avg_alpha"] is not None \
                              and q1.iloc[0]["avg_alpha"] is not None else None
                delta_wr    = q5.iloc[0]["win_rate"]     - q1.iloc[0]["win_rate"]

                alpha_str = f"  AvgAlpha delta: {delta_alpha:+.2f}%" if delta_alpha is not None else ""
                lines.append(
                    f"\n  Q5 vs Q1 delta:"
                    f"  AvgReturn: {delta_ret:+.2f}%"
                    f"  WinRate: {delta_wr:+.1f}%"
                    f"{alpha_str}"
                )

            lines.append("")

        lines.append("")

    lines.append("  Interpretace Q5 vs Q1 delta:")
    lines.append("  AvgReturn delta > +1%  = komponenta má slabou prediktivní sílu")
    lines.append("  AvgReturn delta > +2%  = střední prediktivní síla")
    lines.append("  AvgReturn delta > +4%  = silná prediktivní síla")
    lines.append("")

    return lines
