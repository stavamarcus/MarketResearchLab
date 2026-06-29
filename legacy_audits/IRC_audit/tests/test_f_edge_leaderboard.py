"""
Industry Rank Calendar Audit — Test F
audit/tests/test_f_edge_leaderboard.py

Zodpovědnost:
    Sestavit souhrnný žebříček všech hypotéz seřazený podle síly edge.
    Edge = avg_alpha (20D) nejsilnější skupiny vs. nejslabší skupiny.

    Výstup: tabulka hypotéz s edge, win rate a hodnocením (1–5 hvězd).

    Toto není nový výpočet — pouze agreguje výsledky testů A–E.
"""

from __future__ import annotations

import pandas as pd

STAR_THRESHOLDS = [
    (3.0, "⭐⭐⭐⭐⭐"),
    (2.0, "⭐⭐⭐⭐"),
    (1.0, "⭐⭐⭐"),
    (0.5, "⭐⭐"),
    (0.0, "⭐"),
]

PRIMARY_WINDOW = "20D"


def _stars(edge: float) -> str:
    for threshold, rating in STAR_THRESHOLDS:
        if edge >= threshold:
            return rating
    return "⭐"


def build_leaderboard(
    test_a: pd.DataFrame,  # rank buckets
    test_b: pd.DataFrame,  # persistence
    test_c: pd.DataFrame,  # tailwind
    test_d: pd.DataFrame,  # new entrant
    test_e: pd.DataFrame,  # breadth
) -> pd.DataFrame:
    """
    Sestaví edge leaderboard z výsledků testů A–E.

    Pro každou hypotézu vezme avg_alpha (20D) nejsilnější skupiny.
    Edge = rozdíl avg_alpha mezi nejsilnější a nejslabší skupinou.
    """
    rows = []

    def _extract(df, window, best_group_col, best_val, worst_val=None):
        """Vezme alpha pro best a worst skupinu v daném okně."""
        if df.empty or window not in df["window"].values:
            return None, None
        sub = df[df["window"] == window]

        best_row  = sub[sub[best_group_col] == best_val]
        worst_row = sub[sub[best_group_col] == worst_val] if worst_val else None

        best_alpha  = float(best_row.iloc[0]["avg_alpha"])  if not best_row.empty  and best_row.iloc[0]["avg_alpha"]  is not None else None
        worst_alpha = float(worst_row.iloc[0]["avg_alpha"]) if worst_row is not None and not worst_row.empty and worst_row.iloc[0]["avg_alpha"] is not None else None
        best_wr     = float(best_row.iloc[0]["win_rate"])   if not best_row.empty else None

        return best_alpha, worst_alpha, best_wr

    # Test A — Top industry rank (R1-5 vs R31+)
    a_best, a_worst, a_wr = _extract(test_a, PRIMARY_WINDOW, "bucket", "R1-5", "R31+")
    if a_best is not None:
        edge = (a_best - a_worst) if a_worst is not None else a_best
        rows.append({
            "hypoteza":       "Industry R1-5 vs R31+",
            "nejlepsi_grup":  "R1-5",
            "nejhorsi_grup":  "R31+",
            "edge_alpha_20D": round(edge, 2),
            "alpha_best_20D": round(a_best, 2),
            "win_rate":       round(a_wr, 1) if a_wr else None,
            "hodnoceni":      _stars(edge),
        })

    # Test A — TOP10 vs zbytek (R1-10 vs R31+)
    a_top10 = test_a[test_a["bucket"].isin(["R1-5", "R6-10"]) & (test_a["window"] == PRIMARY_WINDOW)]
    a_bad   = test_a[(test_a["bucket"] == "R31+") & (test_a["window"] == PRIMARY_WINDOW)]
    if not a_top10.empty and not a_bad.empty:
        best_alpha  = float(a_top10["avg_alpha"].mean())
        worst_alpha = float(a_bad.iloc[0]["avg_alpha"]) if a_bad.iloc[0]["avg_alpha"] is not None else 0
        edge = best_alpha - worst_alpha
        rows.append({
            "hypoteza":       "Industry TOP10 vs R31+",
            "nejlepsi_grup":  "R1-10",
            "nejhorsi_grup":  "R31+",
            "edge_alpha_20D": round(edge, 2),
            "alpha_best_20D": round(best_alpha, 2),
            "win_rate":       None,
            "hodnoceni":      _stars(edge),
        })

    # Test B — Persistence HIGH vs NONE
    b_best, b_worst, b_wr = _extract(test_b, PRIMARY_WINDOW, "bucket", "HIGH (15-20)", "NONE (0-4)")
    if b_best is not None:
        edge = (b_best - b_worst) if b_worst is not None else b_best
        rows.append({
            "hypoteza":       "Persistence HIGH vs NONE",
            "nejlepsi_grup":  "15-20/20",
            "nejhorsi_grup":  "0-4/20",
            "edge_alpha_20D": round(edge, 2),
            "alpha_best_20D": round(b_best, 2),
            "win_rate":       round(b_wr, 1) if b_wr else None,
            "hodnoceni":      _stars(edge),
        })

    # Test C — Tailwind vs Headwind (IMS/MLE kandidáti)
    if not test_c.empty and "group" in test_c.columns:
        c_tw = test_c[(test_c["group"] == "TAILWIND") & (test_c["window"] == PRIMARY_WINDOW)]
        c_hw = test_c[(test_c["group"] == "HEADWIND") & (test_c["window"] == PRIMARY_WINDOW)]
        if not c_tw.empty and not c_hw.empty:
            tw_alpha = float(c_tw.iloc[0]["avg_alpha"]) if c_tw.iloc[0]["avg_alpha"] is not None else 0
            hw_alpha = float(c_hw.iloc[0]["avg_alpha"]) if c_hw.iloc[0]["avg_alpha"] is not None else 0
            edge = tw_alpha - hw_alpha
            tw_wr = float(c_tw.iloc[0]["win_rate"]) if c_tw.iloc[0]["win_rate"] is not None else None
            rows.append({
                "hypoteza":       "IMS/MLE + Tailwind vs Headwind",
                "nejlepsi_grup":  "TAILWIND (R1-10)",
                "nejhorsi_grup":  "HEADWIND (R11+)",
                "edge_alpha_20D": round(edge, 2),
                "alpha_best_20D": round(tw_alpha, 2),
                "win_rate":       round(tw_wr, 1) if tw_wr else None,
                "hodnoceni":      _stars(edge),
            })

    # Test D — New Entrant vs Established
    d_new  = test_d[(test_d["group"] == "NEW_ENTRANT")  & (test_d["window"] == PRIMARY_WINDOW)]
    d_est  = test_d[(test_d["group"] == "ESTABLISHED")  & (test_d["window"] == PRIMARY_WINDOW)]
    if not d_new.empty and not d_est.empty:
        new_alpha = float(d_new.iloc[0]["avg_alpha"]) if d_new.iloc[0]["avg_alpha"] is not None else 0
        est_alpha = float(d_est.iloc[0]["avg_alpha"]) if d_est.iloc[0]["avg_alpha"] is not None else 0
        edge = new_alpha - est_alpha
        new_wr = float(d_new.iloc[0]["win_rate"]) if d_new.iloc[0]["win_rate"] is not None else None
        rows.append({
            "hypoteza":       "New Entrant vs Established",
            "nejlepsi_grup":  "NEW_ENTRANT",
            "nejhorsi_grup":  "ESTABLISHED",
            "edge_alpha_20D": round(edge, 2),
            "alpha_best_20D": round(new_alpha, 2),
            "win_rate":       round(new_wr, 1) if new_wr else None,
            "hodnoceni":      _stars(max(edge, 0)),
        })

    # Test E — Breadth BROAD90 vs NARROW
    e_best, e_worst, e_wr = _extract(test_e, PRIMARY_WINDOW, "bucket", "BROAD90 (90-100%)", "NARROW  (<50%)")
    if e_best is not None:
        edge = (e_best - e_worst) if e_worst is not None else e_best
        rows.append({
            "hypoteza":       "Breadth Adv%>=90 vs <50%",
            "nejlepsi_grup":  "Adv% >= 90%",
            "nejhorsi_grup":  "Adv% < 50%",
            "edge_alpha_20D": round(edge, 2),
            "alpha_best_20D": round(e_best, 2),
            "win_rate":       round(e_wr, 1) if e_wr else None,
            "hodnoceni":      _stars(edge),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("edge_alpha_20D", ascending=False).reset_index(drop=True)

    return df


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST F — EDGE LEADERBOARD")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Souhrn vsech hypotez serazeny podle sily edge (20D alpha).")
    lines.append("Edge = avg_alpha nejlepsi skupiny minus nejhorsi skupiny (20D).")
    lines.append("")

    if df.empty:
        lines.append("  Nedostatek dat pro sestaveni leaderboardu.")
        lines.append("")
        return lines

    lines.append(
        f"  {'#':<3}  {'Hypoteza':<35}  {'Edge α':>8}  {'Best α':>8}  {'WinRate':>8}  {'Rating'}"
    )
    lines.append(
        f"  {'-'*3}  {'-'*35}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*12}"
    )

    for i, (_, row) in enumerate(df.iterrows(), 1):
        edge_str = f"{row['edge_alpha_20D']:>+7.2f}%"
        best_str = f"{row['alpha_best_20D']:>+7.2f}%"
        wr_str   = f"{row['win_rate']:>7.1f}%" if row["win_rate"] is not None else "     N/A"
        lines.append(
            f"  {i:<3}  {row['hypoteza']:<35}  {edge_str}  {best_str}  {wr_str}  {row['hodnoceni']}"
        )

    lines.append("")
    lines.append("-" * 70)
    lines.append("LEGENDA:")
    lines.append("  Edge α  = avg_alpha(best) - avg_alpha(worst) za 20D okno")
    lines.append("  Best α  = avg_alpha nejlepsi skupiny vs SPY za 20D okno")
    lines.append("  WinRate = % obchodu s kladnym returnem pro nejlepsi skupinu")
    lines.append("")
    lines.append("  ⭐⭐⭐⭐⭐ = edge > 3%   — velmi silny prediktor")
    lines.append("  ⭐⭐⭐⭐   = edge 2-3%  — silny prediktor")
    lines.append("  ⭐⭐⭐     = edge 1-2%  — stredni prediktor")
    lines.append("  ⭐⭐       = edge 0.5-1% — slaby prediktor")
    lines.append("  ⭐         = edge < 0.5% — zanedbatelny")
    lines.append("")

    return lines
