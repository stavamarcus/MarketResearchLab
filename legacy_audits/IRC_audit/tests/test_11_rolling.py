"""
Industry Rank Calendar Audit — Test 11
audit/tests/test_11_rolling.py

Otázka:
    Je edge MLE + TOP10 Industry stabilní napříč různými časovými obdobími?
    Nebo jde o artefakt specifického tržního kontextu v testovaném období?

Metodologie:
    Walk-forward test: rozdělí historii na 6měsíční okna (~126 obchodních dní).
    Pro každé okno zvlášť vyhodnotí:
        MLE+TOP10_IND vs MLE_ONLY
        IMS+TOP10_IND vs IMS_ONLY

    Pokud je edge konzistentní ve všech oknech → stabilní prediktor.
    Pokud edge existuje jen v části oken → tržně podmíněný efekt.

Výstup:
    Per okno: n, avg_return, alpha, win_rate pro obě skupiny
    Souhrn: počet oken kde edge > 0 / celkový počet oken
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

FORWARD_WINDOWS   = [5, 10, 20, 30]
ROLLING_WINDOW_DAYS = 126   # ~6 obchodních měsíců
PRIMARY_WINDOW    = 20
TOP_INDUSTRY_RANK = 10
PROJECTS_BASE     = Path("C:/Users/stava/Projects")


def run(
    mle_fwd:   pd.DataFrame,
    ims_fwd:   pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Spustí rolling validaci pro MLE a IMS.

    Args:
        mle_fwd: forward_df pro MLE signály (z test_cross_module._compute_fwd)
        ims_fwd: forward_df pro IMS signály

    Returns:
        mle_rolling: DataFrame per okno
        ims_rolling: DataFrame per okno
    """
    mle_rolling = _rolling_test(mle_fwd, "MLE+TOP10_IND", "MLE_ONLY", "industry_rank")
    ims_rolling = _rolling_test(ims_fwd, "IMS+TOP10_IND", "IMS_ONLY", "industry_rank")
    return mle_rolling, ims_rolling


def _rolling_test(
    fwd_df:      pd.DataFrame,
    best_label:  str,
    base_label:  str,
    rank_col:    str,
) -> pd.DataFrame:
    """Rozdělí DataFrame na 6měsíční okna a per okno vyhodnotí edge."""
    if fwd_df.empty or "date" not in fwd_df.columns:
        return pd.DataFrame()

    fwd_df = fwd_df.copy()
    fwd_df["date"] = pd.to_datetime(fwd_df["date"])

    all_dates = sorted(fwd_df["date"].unique())
    if len(all_dates) < ROLLING_WINDOW_DAYS:
        return pd.DataFrame()

    rows = []
    step = ROLLING_WINDOW_DAYS // 2   # 50% overlap

    for start_i in range(0, len(all_dates) - ROLLING_WINDOW_DAYS + 1, step):
        end_i     = start_i + ROLLING_WINDOW_DAYS
        window_dates = all_dates[start_i:end_i]
        window_start = window_dates[0].date()
        window_end   = window_dates[-1].date()

        subset = fwd_df[fwd_df["date"].isin(window_dates)].copy()
        if subset.empty:
            continue

        subset["group"] = subset[rank_col].apply(
            lambda r: best_label if r <= TOP_INDUSTRY_RANK else base_label
        )

        col_fwd   = f"fwd_{PRIMARY_WINDOW}d"
        col_alpha = f"alpha_{PRIMARY_WINDOW}d"
        col_use   = f"usable_{PRIMARY_WINDOW}d"

        if col_use not in subset.columns:
            continue

        for group in (best_label, base_label):
            grp = subset[(subset["group"] == group) & (subset[col_use] == True)]
            fwd_vals   = grp[col_fwd].dropna()
            alpha_vals = grp[col_alpha].dropna()
            if len(fwd_vals) < 3:
                continue
            rows.append({
                "window_start": str(window_start),
                "window_end":   str(window_end),
                "group":        group,
                "n":            len(fwd_vals),
                "avg_return":   round(fwd_vals.mean(), 4),
                "avg_alpha":    round(alpha_vals.mean(), 4) if not alpha_vals.empty else None,
                "win_rate":     round((fwd_vals > 0).mean() * 100, 2),
            })

    return pd.DataFrame(rows)


def format_report(mle_rolling: pd.DataFrame, ims_rolling: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST 11 — ROLLING VALIDACE (WALK-FORWARD)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Je edge MLE/IMS + Industry stabilni v case?")
    lines.append(f"Metodologie: {ROLLING_WINDOW_DAYS}-denni okna s 50% prekritem.")
    lines.append(f"Primarne okno: {PRIMARY_WINDOW}D forward return")
    lines.append("")

    for label, df, best_lbl, base_lbl in [
        ("MLE", mle_rolling, "MLE+TOP10_IND", "MLE_ONLY"),
        ("IMS", ims_rolling, "IMS+TOP10_IND", "IMS_ONLY"),
    ]:
        lines.append(f"[ {label} × Industry — rolling ]")
        lines.append("-" * 70)

        if df.empty or "window_start" not in df.columns:
            lines.append("  Nedostatek dat.")
            lines.append("")
            continue

        windows = sorted(df["window_start"].unique())
        edge_positive = 0
        edge_total    = 0

        lines.append(
            f"  {'Okno':<25}  {'Skupina':<16}  {'N':>5}  "
            f"{'Avg%':>7}  {'Alpha':>7}  {'WinR':>6}"
        )
        lines.append(f"  {'-'*25}  {'-'*16}  {'-'*5}  {'-'*7}  {'-'*7}  {'-'*6}")

        for ws in windows:
            window_df = df[df["window_start"] == ws]
            best_row  = window_df[window_df["group"] == best_lbl]
            base_row  = window_df[window_df["group"] == base_lbl]

            if best_row.empty or base_row.empty:
                continue

            b = best_row.iloc[0]
            r = base_row.iloc[0]

            # Konec okna
            we = df[df["window_start"] == ws]["window_end"].iloc[0]

            edge_total += 1
            delta_alpha = (b["avg_alpha"] or 0) - (r["avg_alpha"] or 0)
            if delta_alpha > 0:
                edge_positive += 1

            sign = "✓" if delta_alpha > 0 else "✗"

            for grp_row, grp_lbl in [(b, best_lbl), (r, base_lbl)]:
                alpha_str = f"{grp_row['avg_alpha']:>+6.2f}%" if grp_row["avg_alpha"] is not None else "    N/A"
                prefix = f"  {ws} → {we}" if grp_lbl == best_lbl else f"  {' '*25}"
                lines.append(
                    f"  {ws+' → '+we if grp_lbl == best_lbl else ' '*25:<25}  "
                    f"{grp_lbl:<16}  {int(grp_row['n']):>5}  "
                    f"{grp_row['avg_return']:>+6.2f}%  {alpha_str}  "
                    f"{grp_row['win_rate']:>5.1f}%"
                    f"{'  ' + sign if grp_lbl == best_lbl else ''}"
                )

        lines.append("")
        if edge_total > 0:
            pct = edge_positive / edge_total * 100
            lines.append(f"  Okna s pozitivnim edge: {edge_positive}/{edge_total} ({pct:.0f}%)")
            if pct >= 75:
                lines.append("  VERDIKT: Edge je stabilni — konzistentni ve vetsine oken")
            elif pct >= 50:
                lines.append("  VERDIKT: Edge je castecne stabilni — trfni kontextove zavisly")
            else:
                lines.append("  VERDIKT: Edge neni stabilni — artefakt specifickeho obdobi")
        lines.append("")

    return lines
