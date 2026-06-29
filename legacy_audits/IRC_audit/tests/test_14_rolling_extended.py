"""
Industry Rank Calendar Audit Phase 4 — Test 14
audit/tests/test_14_rolling_extended.py

Priorita 1: Rozšířená Rolling Validace

Otázka:
    Je edge MLE+Industry, IMS+Industry a MLE+Persistence stabilní
    napříč různými délkami oken a počty oken?

Okna: 40, 60, 90, 120 obchodních dní
Krok: polovina okna (50% překryt)

Kombinace:
    A) MLE + TOP5 Industry
    B) IMS + TOP10 Industry
    C) MLE + Persistence MED (8-14/20)

Výstup per kombinace:
    - Per okno: start, end, n_best, n_base, avg_return, alpha, win_rate, PASS/FAIL
    - Souhrn: positive_windows / total, avg_edge, worst_edge, best_edge, distribuce

PASS = edge (alpha_best - alpha_base) > 0
"""

from __future__ import annotations

import pandas as pd
import numpy as np

FORWARD_WINDOWS    = [5, 10, 20, 30]
PRIMARY_WINDOW     = 20

ROLLING_CONFIGS = [40, 60, 90, 120]   # délky oken v obchodních dnech
STEP_RATIO      = 0.5                  # 50% překryt

MLE_IND_THRESH  = 5     # TOP5 pro MLE
IMS_IND_THRESH  = 10    # TOP10 pro IMS
PERSIST_LOW     = 7     # <= 7 = LOW
PERSIST_HIGH    = 8     # >= 8 = MED+HIGH


def run(
    mle_fwd: pd.DataFrame,
    ims_fwd: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """
    Spustí rozšířenou rolling validaci pro všechny kombinace a délky oken.

    Returns:
        dict { combo_name: DataFrame s výsledky per okno }
    """
    results = {}

    if not mle_fwd.empty:
        results["MLE_IND"]     = _rolling_combo(mle_fwd, "industry_rank",    MLE_IND_THRESH,  "rank",    "MLE+TOP5_IND",    "MLE_ONLY")
        results["MLE_PERSIST"] = _rolling_combo(mle_fwd, "industry_persist", PERSIST_HIGH,    "persist", "MLE+PERSIST_MED", "MLE+PERSIST_LOW")

    if not ims_fwd.empty:
        results["IMS_IND"]     = _rolling_combo(ims_fwd, "industry_rank",    IMS_IND_THRESH,  "rank",    "IMS+TOP10_IND",   "IMS_ONLY")

    return results


def _rolling_combo(
    fwd_df:     pd.DataFrame,
    filter_col: str,
    threshold:  int,
    filter_type: str,    # "rank" nebo "persist"
    best_label: str,
    base_label: str,
) -> pd.DataFrame:
    """
    Pro každou délku okna a každé okno vyhodnotí edge dané kombinace.
    filter_type="rank"    → best = filter_col <= threshold
    filter_type="persist" → best = filter_col >= threshold
    """
    if fwd_df.empty or "date" not in fwd_df.columns:
        return pd.DataFrame()

    df = fwd_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    all_dates  = sorted(df["date"].unique())

    rows = []

    for window_size in ROLLING_CONFIGS:
        if len(all_dates) < window_size:
            continue

        step = max(1, int(window_size * STEP_RATIO))

        for start_i in range(0, len(all_dates) - window_size + 1, step):
            end_i        = start_i + window_size
            window_dates = all_dates[start_i:end_i]
            subset       = df[df["date"].isin(window_dates)].copy()

            if subset.empty:
                continue

            if filter_type == "rank":
                subset["group"] = subset[filter_col].apply(
                    lambda v: best_label if v <= threshold else base_label
                )
            else:  # persist
                subset["group"] = subset[filter_col].apply(
                    lambda v: best_label if v >= threshold else base_label
                )

            col_fwd   = f"fwd_{PRIMARY_WINDOW}d"
            col_alpha = f"alpha_{PRIMARY_WINDOW}d"
            col_use   = f"usable_{PRIMARY_WINDOW}d"

            if col_use not in subset.columns:
                continue

            best_data = subset[(subset["group"] == best_label) & (subset[col_use] == True)]
            base_data = subset[(subset["group"] == base_label) & (subset[col_use] == True)]

            if len(best_data) < 3 or len(base_data) < 3:
                continue

            best_fwd   = best_data[col_fwd].dropna()
            best_alpha = best_data[col_alpha].dropna()
            base_fwd   = base_data[col_fwd].dropna()
            base_alpha = base_data[col_alpha].dropna()

            if best_fwd.empty or base_fwd.empty:
                continue

            b_alpha = best_alpha.mean() if not best_alpha.empty else 0
            r_alpha = base_alpha.mean() if not base_alpha.empty else 0
            edge    = b_alpha - r_alpha

            rows.append({
                "window_size":  window_size,
                "window_start": str(window_dates[0].date()),
                "window_end":   str(window_dates[-1].date()),
                "n_best":       len(best_fwd),
                "n_base":       len(base_fwd),
                "avg_ret_best": round(float(best_fwd.mean()), 4),
                "avg_ret_base": round(float(base_fwd.mean()), 4),
                "alpha_best":   round(b_alpha, 4),
                "alpha_base":   round(r_alpha, 4),
                "edge":         round(edge, 4),
                "wr_best":      round(float((best_fwd > 0).mean() * 100), 2),
                "wr_base":      round(float((base_fwd > 0).mean() * 100), 2),
                "pass":         edge > 0,
            })

    return pd.DataFrame(rows)


def _summarize(df: pd.DataFrame, best_label: str, base_label: str) -> list[str]:
    """Sestaví souhrn per window_size."""
    lines = []
    if df.empty or "window_size" not in df.columns:
        lines.append("  Nedostatek dat.")
        return lines

    for ws in sorted(df["window_size"].unique()):
        sub = df[df["window_size"] == ws]
        n_pass  = sub["pass"].sum()
        n_total = len(sub)
        pct     = n_pass / n_total * 100 if n_total > 0 else 0
        edges   = sub["edge"].dropna()

        if edges.empty:
            continue

        verdict = (
            "STABILNI"         if pct >= 75 else
            "CASTECNE STABILNI" if pct >= 50 else
            "NESTABILNI"
        )

        lines.append(f"  Okno {ws:>3}D | {n_pass}/{n_total} PASS ({pct:.0f}%) | "
                     f"avg edge: {edges.mean():>+6.2f}% | "
                     f"best: {edges.max():>+6.2f}% | "
                     f"worst: {edges.min():>+6.2f}% | "
                     f"{verdict}")

    return lines


def format_report(results: dict[str, pd.DataFrame]) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST 14 — ROZSIRENA ROLLING VALIDACE")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Je edge stabilni v ruznych delkach oken?")
    lines.append(f"Okna: {ROLLING_CONFIGS} obchodnich dni, 50% prekryt")
    lines.append(f"Primarne okno: {PRIMARY_WINDOW}D forward return")
    lines.append(f"PASS = edge (alpha_best - alpha_base) > 0")
    lines.append("")

    configs = [
        ("MLE_IND",     "MLE + TOP5 Industry",      "MLE+TOP5_IND",    "MLE_ONLY"),
        ("IMS_IND",     "IMS + TOP10 Industry",     "IMS+TOP10_IND",   "IMS_ONLY"),
        ("MLE_PERSIST", "MLE + Persistence MED/HIGH", "MLE+PERSIST_MED", "MLE+PERSIST_LOW"),
    ]

    for key, title, best_lbl, base_lbl in configs:
        df = results.get(key, pd.DataFrame())
        lines.append(f"[ {title} ]")
        lines.append("-" * 70)

        if df.empty:
            lines.append("  Nedostatek dat.")
            lines.append("")
            continue

        lines += _summarize(df, best_lbl, base_lbl)
        lines.append("")

        # Detail per okno pro nejdelší window_size
        max_ws  = df["window_size"].max()
        sub_max = df[df["window_size"] == max_ws]

        if not sub_max.empty:
            lines.append(f"  Detail oken ({max_ws}D):")
            lines.append(
                f"    {'Okno':<23}  {'N_best':>6}  {'N_base':>6}  "
                f"{'Edge α':>8}  {'WR_best':>7}  {'PASS'}"
            )
            lines.append(
                f"    {'-'*23}  {'-'*6}  {'-'*6}  "
                f"{'-'*8}  {'-'*7}  {'-'*4}"
            )
            for _, row in sub_max.iterrows():
                pass_str = "✓" if row["pass"] else "✗"
                lines.append(
                    f"    {row['window_start']} → {row['window_end']}  "
                    f"{int(row['n_best']):>6}  {int(row['n_base']):>6}  "
                    f"{row['edge']:>+7.2f}%  {row['wr_best']:>6.1f}%  {pass_str}"
                )
            lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  >= 75% PASS = stabilni edge")
    lines.append("  50-74% PASS = castecne stabilni, trzni kontext zavisly")
    lines.append("  < 50% PASS  = nestabilni, nepouzivat jako filtr")
    lines.append("")

    return lines
