"""
Industry Rank Calendar Audit — Test 12
audit/tests/test_12_threshold.py

Otázka:
    Jaký threshold industry ranku je optimální?
    TOP3, TOP5, TOP10 nebo TOP15?

Metodologie:
    Pro MLE TOP20 signály vyhodnotí forward returns pro různé thresholdy.
    Hledá threshold kde je edge maximální a kde začíná klesat.

Výstup:
    Per threshold (TOP3/TOP5/TOP10/TOP15): n, avg_return, alpha, win_rate
    Doporučení: optimální threshold
"""

from __future__ import annotations

import pandas as pd

FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 20
THRESHOLDS      = [3, 5, 10, 15, 20]


def run(mle_fwd: pd.DataFrame, ims_fwd: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Vyhodnotí forward returns pro různé thresholdy industry ranku.

    Returns:
        mle_thresh: DataFrame s výsledky per threshold pro MLE
        ims_thresh: DataFrame s výsledky per threshold pro IMS
    """
    mle_thresh = _threshold_test(mle_fwd)
    ims_thresh = _threshold_test(ims_fwd)
    return mle_thresh, ims_thresh


def _threshold_test(fwd_df: pd.DataFrame) -> pd.DataFrame:
    """Per threshold vyhodnotí avg_return, alpha, win_rate."""
    if fwd_df.empty or "industry_rank" not in fwd_df.columns:
        return pd.DataFrame()

    rows = []

    for threshold in THRESHOLDS:
        subset = fwd_df[fwd_df["industry_rank"] <= threshold].copy()
        baseline = fwd_df[fwd_df["industry_rank"] > threshold].copy()

        for window in FORWARD_WINDOWS:
            col_fwd   = f"fwd_{window}d"
            col_alpha = f"alpha_{window}d"
            col_use   = f"usable_{window}d"

            if col_use not in subset.columns:
                continue

            # TOP group
            top_usable = subset[subset[col_use] == True]
            fwd_vals   = top_usable[col_fwd].dropna()
            alpha_vals = top_usable[col_alpha].dropna()

            if len(fwd_vals) < 3:
                continue

            # Baseline (mimo threshold)
            base_usable   = baseline[baseline[col_use] == True]
            base_fwd_vals = base_usable[col_fwd].dropna()
            base_alpha    = base_usable[col_alpha].dropna()

            rows.append({
                "threshold":       f"TOP{threshold}",
                "window":          f"{window}D",
                "n_top":           len(fwd_vals),
                "n_base":          len(base_fwd_vals),
                "avg_return_top":  round(fwd_vals.mean(), 4),
                "avg_alpha_top":   round(alpha_vals.mean(), 4) if not alpha_vals.empty else None,
                "win_rate_top":    round((fwd_vals > 0).mean() * 100, 2),
                "avg_return_base": round(base_fwd_vals.mean(), 4) if not base_fwd_vals.empty else None,
                "avg_alpha_base":  round(base_alpha.mean(), 4) if not base_alpha.empty else None,
                "delta_return":    round(fwd_vals.mean() - base_fwd_vals.mean(), 4) if not base_fwd_vals.empty else None,
                "delta_alpha":     round(alpha_vals.mean() - base_alpha.mean(), 4) if not alpha_vals.empty and not base_alpha.empty else None,
            })

    return pd.DataFrame(rows)


def format_report(mle_thresh: pd.DataFrame, ims_thresh: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST 12 — OPTIMALIZACE PRAHU INDUSTRY RANKU")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Jaky threshold industry ranku je optimalni?")
    lines.append("Porovnani: TOP3 vs TOP5 vs TOP10 vs TOP15 vs TOP20")
    lines.append(f"Primarne okno: {PRIMARY_WINDOW}D")
    lines.append("")

    for label, df in [("MLE TOP20", mle_thresh), ("IMS HIGH", ims_thresh)]:
        lines.append(f"[ {label} × Industry threshold ]")
        lines.append("-" * 70)

        if df.empty or "threshold" not in df.columns:
            lines.append("  Nedostatek dat.")
            lines.append("")
            continue

        w_str = f"{PRIMARY_WINDOW}D"
        sub   = df[df["window"] == w_str]

        if sub.empty:
            lines.append(f"  Zadna data pro {PRIMARY_WINDOW}D okno.")
            lines.append("")
            continue

        lines.append(
            f"  {'Threshold':<10}  {'N(top)':>7}  {'Avg%':>8}  "
            f"{'Alpha':>8}  {'WinRate':>8}  {'Delta α':>8}"
        )
        lines.append(
            f"  {'-'*10}  {'-'*7}  {'-'*8}  "
            f"{'-'*8}  {'-'*8}  {'-'*8}"
        )

        best_alpha = None
        best_thresh = None

        for _, row in sub.iterrows():
            alpha_str = f"{row['avg_alpha_top']:>+7.2f}%" if row["avg_alpha_top"] is not None else "     N/A"
            delta_str = f"{row['delta_alpha']:>+7.2f}%" if row["delta_alpha"] is not None else "     N/A"
            lines.append(
                f"  {row['threshold']:<10}  {int(row['n_top']):>7}  "
                f"{row['avg_return_top']:>+7.2f}%  {alpha_str}  "
                f"{row['win_rate_top']:>7.1f}%  {delta_str}"
            )

            if row["avg_alpha_top"] is not None:
                if best_alpha is None or row["avg_alpha_top"] > best_alpha:
                    best_alpha  = row["avg_alpha_top"]
                    best_thresh = row["threshold"]

        lines.append("")
        if best_thresh:
            lines.append(f"  Optimalni threshold (max alpha): {best_thresh} (alpha={best_alpha:+.2f}%)")
        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  Pokud alpha monot. klesa TOP3→TOP20 = uzsi filtr je lepsi")
    lines.append("  Pokud alpha ma lokalni maximum = existuje optimalni threshold")
    lines.append("  Pokud alpha roste s thresholdem = sirsi filtr je lepsi")
    lines.append("")

    return lines
