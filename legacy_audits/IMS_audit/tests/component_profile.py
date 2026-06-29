"""
IMS Audit v2 — Component Profile by Bucket
audit/tests/component_profile.py

Zodpovědnost:
    Sekce F: průměr a medián každé scoring komponenty per score bucket.
    Odhalí čím se H90-94 liší od ostatních bucketů na úrovni vstupních metrik.

Komponenty:
    rank_improvement_20d    — zlepšení ranku za 20D (kladné = vzestup)
    rank_improvement_40d    — zlepšení ranku za 40D
    rs_vs_spy_20d           — excess return vs SPY za 20D (%)
    up_down_volume_ratio_20d — up/down volume ratio za 20D (>1.5 = akumulace)
    rank_stability_20d      — std ranku za 20D (nižší = stabilnější)

Buckety: stejné jako Fine Score Bucket Analysis (5-bodové intervaly)
"""

from __future__ import annotations

import pandas as pd

FINE_BUCKETS: dict[str, tuple[float, float]] = {
    "60-64": (60.0, 65.0),
    "65-69": (65.0, 70.0),
    "70-74": (70.0, 75.0),
    "75-79": (75.0, 80.0),
    "80-84": (80.0, 85.0),
    "85-89": (85.0, 90.0),
    "90-94": (90.0, 95.0),
    "95+":   (95.0, 101.0),
}

COMPONENTS = [
    "rank_improvement_20d",
    "rank_improvement_40d",
    "rs_vs_spy_20d",
    "up_down_volume_ratio_20d",
    "rank_stability_20d",
]


def run(forward_df: pd.DataFrame) -> pd.DataFrame:
    """
    Vypočítá průměr a medián každé komponenty per score bucket.

    Args:
        forward_df: výstup z compute_forward_returns() — musí obsahovat
                    sloupce komponent z archivu

    Returns:
        pd.DataFrame — jeden řádek per (bucket, component)
    """
    rows = []

    for bucket_name, (lo, hi) in FINE_BUCKETS.items():
        subset = forward_df[
            (forward_df["score"] >= lo) & (forward_df["score"] < hi)
        ].copy()

        n = len(subset)

        for comp in COMPONENTS:
            if comp not in subset.columns:
                continue

            vals = subset[comp].dropna()
            if vals.empty:
                continue

            rows.append({
                "bucket":   bucket_name,
                "n":        n,
                "component": comp,
                "avg":      round(vals.mean(), 4),
                "median":   round(vals.median(), 4),
                "p25":      round(vals.quantile(0.25), 4),
                "p75":      round(vals.quantile(0.75), 4),
                "std":      round(vals.std(), 4),
            })

    return pd.DataFrame(rows)


def format_report(df: pd.DataFrame) -> list[str]:
    lines = []
    lines.append("=" * 75)
    lines.append("SEKCE F — COMPONENT PROFILE BY BUCKET")
    lines.append("=" * 75)
    lines.append("")
    lines.append("Průměr a medián každé scoring komponenty per score bucket.")
    lines.append("Odhalí co odlišuje H90-94 od ostatních bucketů.")
    lines.append("")

    bucket_order = list(FINE_BUCKETS.keys())

    for comp in COMPONENTS:
        sub = df[df["component"] == comp]
        if sub.empty:
            continue

        lines.append(f"Komponenta: {comp}")
        lines.append("-" * 75)
        lines.append(
            f"  {'Bucket':<8} {'N':>6} {'Avg':>10} {'Median':>10} "
            f"{'P25':>10} {'P75':>10} {'Std':>10}"
        )
        lines.append(
            f"  {'-'*8} {'-'*6} {'-'*10} {'-'*10} "
            f"{'-'*10} {'-'*10} {'-'*10}"
        )

        for bucket in bucket_order:
            row = sub[sub["bucket"] == bucket]
            if row.empty:
                continue
            r    = row.iloc[0]
            flag = " !" if r["n"] < 30 else ""
            lines.append(
                f"  {bucket:<8} {int(r['n']):>6}{flag} "
                f"{r['avg']:>10.3f} {r['median']:>10.3f} "
                f"{r['p25']:>10.3f} {r['p75']:>10.3f} "
                f"{r['std']:>10.3f}"
            )

        lines.append("")

    lines.append("  Interpretace:")
    lines.append("  rank_improvement: vyšší = silnější momentum vzestup")
    lines.append("  rs_vs_spy_20d:    vyšší = silnější outperformance vs trh")
    lines.append("  up_down_vol:      vyšší = silnější akumulace (>1.5 = signifikantní)")
    lines.append("  rank_stability:   nižší = konzistentnější zlepšování (méně volatilní rank)")
    lines.append("")
    lines.append("  ! = N < 30, interpretovat opatrně")
    lines.append("")

    return lines
