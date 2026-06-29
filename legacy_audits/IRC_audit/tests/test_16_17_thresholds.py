"""
Industry Rank Calendar Audit Phase 4 — Testy 16 + 17
audit/tests/test_16_17_thresholds.py

Priorita 3: Persistence Threshold Optimization (Test 16)
    Jemnější buckety: 0-4, 5-7, 8-10, 11-13, 14-16, 17-20

Priorita 4: Industry Threshold Optimization (Test 17)
    Thresholdy: TOP3, TOP5, TOP7, TOP10, TOP12, TOP15, TOP20
    Pro MLE i IMS zvlášť.
    Cíl: optimum alpha / počet signálů / win rate.
"""

from __future__ import annotations

import pandas as pd

FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 20


# ── Test 16: Persistence Threshold Optimization ───────────────────────────────

PERSIST_BUCKETS_FINE = [
    ("0-4",   0,  4),
    ("5-7",   5,  7),
    ("8-10",  8, 10),
    ("11-13", 11, 13),
    ("14-16", 14, 16),
    ("17-20", 17, 20),
]


def run_test_16(mle_fwd: pd.DataFrame) -> pd.DataFrame:
    """
    Jemná analýza persistence bucketů pro MLE signály.
    """
    if mle_fwd.empty or "industry_persist" not in mle_fwd.columns:
        return pd.DataFrame()

    rows = []

    for bucket_name, lo, hi in PERSIST_BUCKETS_FINE:
        subset = mle_fwd[
            (mle_fwd["industry_persist"] >= lo) &
            (mle_fwd["industry_persist"] <= hi)
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
            fwd    = usable[col_fwd].dropna()
            alpha  = usable[col_alpha].dropna()
            dd     = usable[col_dd].dropna()

            if len(fwd) < 3:
                continue

            rows.append({
                "bucket":        bucket_name,
                "persist_lo":    lo,
                "window":        f"{window}D",
                "n":             len(fwd),
                "avg_return":    round(float(fwd.mean()), 4),
                "median_return": round(float(fwd.median()), 4),
                "win_rate":      round(float((fwd > 0).mean() * 100), 2),
                "avg_alpha":     round(float(alpha.mean()), 4) if not alpha.empty else None,
                "avg_drawdown":  round(float(dd.mean()), 4) if not dd.empty else None,
            })

    return pd.DataFrame(rows)


# ── Test 17: Industry Threshold Optimization ─────────────────────────────────

IND_THRESHOLDS = [3, 5, 7, 10, 12, 15, 20]


def run_test_17(
    mle_fwd: pd.DataFrame,
    ims_fwd: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Detailní analýza industry thresholdů pro MLE a IMS.
    Pro každý threshold: alpha, return, win_rate, n signálů, delta vs baseline (mimo threshold).
    """
    mle_thresh = _threshold_detail(mle_fwd)
    ims_thresh = _threshold_detail(ims_fwd)
    return mle_thresh, ims_thresh


def _threshold_detail(fwd_df: pd.DataFrame) -> pd.DataFrame:
    if fwd_df.empty or "industry_rank" not in fwd_df.columns:
        return pd.DataFrame()

    rows = []
    col_use   = f"usable_{PRIMARY_WINDOW}d"
    col_fwd   = f"fwd_{PRIMARY_WINDOW}d"
    col_alpha = f"alpha_{PRIMARY_WINDOW}d"
    col_dd    = f"dd_{PRIMARY_WINDOW}d"

    if col_use not in fwd_df.columns:
        return pd.DataFrame()

    usable_all = fwd_df[fwd_df[col_use] == True]

    for threshold in IND_THRESHOLDS:
        top    = usable_all[usable_all["industry_rank"] <= threshold]
        bottom = usable_all[usable_all["industry_rank"] > threshold]

        top_fwd    = top[col_fwd].dropna()
        top_alpha  = top[col_alpha].dropna()
        top_dd     = top[col_dd].dropna()
        bot_fwd    = bottom[col_fwd].dropna()
        bot_alpha  = bottom[col_alpha].dropna()

        if len(top_fwd) < 3:
            continue

        t_alpha = float(top_alpha.mean()) if not top_alpha.empty else None
        b_alpha = float(bot_alpha.mean()) if not bot_alpha.empty else None
        delta   = (t_alpha - b_alpha) if t_alpha is not None and b_alpha is not None else None

        rows.append({
            "threshold":       f"TOP{threshold}",
            "threshold_val":   threshold,
            "n_top":           len(top_fwd),
            "n_bottom":        len(bot_fwd),
            "avg_return_top":  round(float(top_fwd.mean()), 4),
            "median_ret_top":  round(float(top_fwd.median()), 4),
            "win_rate_top":    round(float((top_fwd > 0).mean() * 100), 2),
            "avg_alpha_top":   round(t_alpha, 4) if t_alpha is not None else None,
            "avg_dd_top":      round(float(top_dd.mean()), 4) if not top_dd.empty else None,
            "avg_alpha_base":  round(b_alpha, 4) if b_alpha is not None else None,
            "delta_alpha":     round(delta, 4) if delta is not None else None,
        })

    return pd.DataFrame(rows)


# ── Formátování ───────────────────────────────────────────────────────────────

def format_report(
    test_16:    pd.DataFrame,
    mle_17:     pd.DataFrame,
    ims_17:     pd.DataFrame,
) -> list[str]:
    lines = []

    # ── Test 16 ───────────────────────────────────────────────────────────
    lines.append("=" * 70)
    lines.append("TEST 16 — PERSISTENCE THRESHOLD OPTIMIZATION (MLE)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Kde je skutecne optimum persistence?")
    lines.append("Buckety: 0-4 / 5-7 / 8-10 / 11-13 / 14-16 / 17-20")
    lines.append(f"Primarne okno: {PRIMARY_WINDOW}D")
    lines.append("")

    if test_16.empty or "bucket" not in test_16.columns:
        lines.append("  Nedostatek dat.")
        lines.append("")
    else:
        sub = test_16[test_16["window"] == f"{PRIMARY_WINDOW}D"]
        if sub.empty:
            lines.append("  Zadna data pro 20D okno.")
        else:
            lines.append(
                f"  {'Bucket':<10}  {'N':>6}  {'Avg%':>8}  {'Med%':>8}  "
                f"{'WinRate':>8}  {'Alpha':>8}  {'AvgDD%':>7}"
            )
            lines.append(
                f"  {'-'*10}  {'-'*6}  {'-'*8}  {'-'*8}  "
                f"{'-'*8}  {'-'*8}  {'-'*7}"
            )

            best_alpha  = None
            best_bucket = None

            for _, row in sub.sort_values("persist_lo").iterrows():
                alpha_str = f"{row['avg_alpha']:>+7.2f}%" if row["avg_alpha"] is not None else "     N/A"
                dd_str    = f"{row['avg_drawdown']:>+6.2f}%" if row["avg_drawdown"] is not None else "    N/A"
                lines.append(
                    f"  {row['bucket']:<10}  {int(row['n']):>6}  "
                    f"{row['avg_return']:>+7.2f}%  {row['median_return']:>+7.2f}%  "
                    f"{row['win_rate']:>7.1f}%  {alpha_str}  {dd_str}"
                )
                if row["avg_alpha"] is not None:
                    if best_alpha is None or row["avg_alpha"] > best_alpha:
                        best_alpha  = row["avg_alpha"]
                        best_bucket = row["bucket"]

            lines.append("")
            if best_bucket:
                lines.append(f"  Optimalni bucket: {best_bucket} (alpha {best_alpha:+.2f}%)")

    lines.append("")

    # Všechna okna
    lines.append("  Vsechna okna (Avg return per bucket):")
    if not test_16.empty:
        pivot = test_16.pivot_table(
            index="bucket", columns="window", values="avg_return", aggfunc="mean"
        )
        col_order = [f"{w}D" for w in [5, 10, 20, 30] if f"{w}D" in pivot.columns]
        pivot = pivot[col_order]
        lines.append(f"  {'Bucket':<10}  " + "  ".join(f"{c:>8}" for c in col_order))
        for bucket_name, lo, hi in PERSIST_BUCKETS_FINE:
            if bucket_name in pivot.index:
                vals = "  ".join(
                    f"{pivot.at[bucket_name, c]:>+7.2f}%" if bucket_name in pivot.index and c in pivot.columns else "     N/A"
                    for c in col_order
                )
                lines.append(f"  {bucket_name:<10}  {vals}")
    lines.append("")

    # ── Test 17 ───────────────────────────────────────────────────────────
    lines.append("=" * 70)
    lines.append("TEST 17 — INDUSTRY THRESHOLD OPTIMIZATION")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Jaky threshold je optimalni kompromis alpha / pocet signalu?")
    lines.append(f"Thresholdy: {IND_THRESHOLDS}")
    lines.append(f"Primarne okno: {PRIMARY_WINDOW}D")
    lines.append("")

    for label, df in [("MLE TOP20", mle_17), ("IMS HIGH", ims_17)]:
        lines.append(f"[ {label} ]")
        lines.append("-" * 70)

        if df.empty:
            lines.append("  Nedostatek dat.")
            lines.append("")
            continue

        lines.append(
            f"  {'Threshold':<10}  {'N_top':>6}  {'Avg%':>8}  "
            f"{'Alpha':>8}  {'WinRate':>8}  {'Delta α':>8}  {'Score'}"
        )
        lines.append(
            f"  {'-'*10}  {'-'*6}  {'-'*8}  "
            f"{'-'*8}  {'-'*8}  {'-'*8}  {'-'*8}"
        )

        # Score = alpha × sqrt(n) — kombinuje sílu edge s počtem signálů
        df["score"] = df.apply(
            lambda r: (r["avg_alpha_top"] or 0) * (r["n_top"] ** 0.5)
            if r["avg_alpha_top"] is not None else 0,
            axis=1
        )
        best_score_thresh = df.loc[df["score"].idxmax(), "threshold"] if not df.empty else "N/A"

        for _, row in df.iterrows():
            alpha_str = f"{row['avg_alpha_top']:>+7.2f}%" if row["avg_alpha_top"] is not None else "     N/A"
            delta_str = f"{row['delta_alpha']:>+7.2f}%" if row["delta_alpha"] is not None else "     N/A"
            score_str = f"{row['score']:>7.1f}"
            marker    = " ←" if row["threshold"] == best_score_thresh else ""
            lines.append(
                f"  {row['threshold']:<10}  {int(row['n_top']):>6}  "
                f"{row['avg_return_top']:>+7.2f}%  {alpha_str}  "
                f"{row['win_rate_top']:>7.1f}%  {delta_str}  {score_str}{marker}"
            )

        lines.append("")
        lines.append(f"  Optimalni threshold (alpha × sqrt(n)): {best_score_thresh}")
        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  Score = alpha × sqrt(n) — kompromis mezi sílou a pokrytím")
    lines.append("  Nejvyšší alpha ≠ nejlepší produkční threshold")
    lines.append("  Optimum je tam kde score je nejvyšší")
    lines.append("")

    return lines
