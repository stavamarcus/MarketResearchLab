"""
Industry Rank Calendar Audit Phase 4 — Test 15
audit/tests/test_15_market_regime.py

Priorita 2: Market Regime Analysis

Otázka:
    Ve kterém tržním režimu edge vzniká? Ve kterém mizí?

Metodologie:
    Tržní režim definován pomocí SPY 20D momentum:
        RISK_ON  : SPY 20D return > +2%
        NEUTRAL  : SPY 20D return -2% až +2%
        RISK_OFF : SPY 20D return < -2%

    Per režim vyhodnotit:
        MLE + TOP5 Industry vs MLE_ONLY
        IMS + TOP10 Industry vs IMS_ONLY
        MLE + Persistence MED vs LOW

Výstup:
    Per režim × kombinace: n, avg_return, alpha, win_rate, edge
"""

from __future__ import annotations

import pandas as pd

FORWARD_WINDOWS  = [5, 10, 20, 30]
PRIMARY_WINDOW   = 20

MLE_IND_THRESH   = 5
IMS_IND_THRESH   = 10
PERSIST_MED      = 8

RISK_ON_THRESH   = 2.0    # SPY 20D return > +2% = Risk ON
RISK_OFF_THRESH  = -2.0   # SPY 20D return < -2% = Risk OFF


def _compute_spy_regime(spy_close: pd.Series) -> pd.Series:
    """
    Spočítá tržní režim per obchodní den na základě SPY 20D return.

    Returns:
        pd.Series s index=date (str), values="RISK_ON"/"NEUTRAL"/"RISK_OFF"
    """
    spy = spy_close.copy()
    spy.index = pd.to_datetime(spy.index)
    spy = spy.sort_index()

    # 20D return: dnešní close vs. close před 20 obchodními dny
    spy_ret = spy.pct_change(20) * 100

    regime = spy_ret.apply(
        lambda r: "RISK_ON"  if r > RISK_ON_THRESH else
                  "RISK_OFF" if r < RISK_OFF_THRESH else
                  "NEUTRAL"
    )
    # Index jako string pro merge
    regime.index = regime.index.strftime("%Y-%m-%d")
    return regime


def run(
    mle_fwd:   pd.DataFrame,
    ims_fwd:   pd.DataFrame,
    spy_close: pd.Series,
) -> dict[str, pd.DataFrame]:
    """
    Spustí market regime analýzu.

    Returns:
        dict { combo_name: DataFrame s výsledky per režim }
    """
    regime_map = _compute_spy_regime(spy_close)

    results = {}

    if not mle_fwd.empty:
        results["MLE_IND"]     = _regime_test(mle_fwd, regime_map, "industry_rank",    MLE_IND_THRESH,  "rank",    "MLE+TOP5_IND",    "MLE_ONLY")
        results["MLE_PERSIST"] = _regime_test(mle_fwd, regime_map, "industry_persist", PERSIST_MED,     "persist", "MLE+PERSIST_MED", "MLE+PERSIST_LOW")

    if not ims_fwd.empty:
        results["IMS_IND"]     = _regime_test(ims_fwd, regime_map, "industry_rank",    IMS_IND_THRESH,  "rank",    "IMS+TOP10_IND",   "IMS_ONLY")

    return results


def _regime_test(
    fwd_df:      pd.DataFrame,
    regime_map:  pd.Series,
    filter_col:  str,
    threshold:   int,
    filter_type: str,
    best_label:  str,
    base_label:  str,
) -> pd.DataFrame:
    df = fwd_df.copy()
    df["date_str"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["regime"]   = df["date_str"].map(regime_map).fillna("NEUTRAL")

    if filter_type == "rank":
        df["group"] = df[filter_col].apply(lambda v: best_label if v <= threshold else base_label)
    else:
        df["group"] = df[filter_col].apply(lambda v: best_label if v >= threshold else base_label)

    rows = []
    regimes = ["RISK_ON", "NEUTRAL", "RISK_OFF"]

    for regime in regimes:
        for group in (best_label, base_label):
            subset = df[(df["regime"] == regime) & (df["group"] == group)]
            col_use = f"usable_{PRIMARY_WINDOW}d"
            if col_use not in subset.columns:
                continue
            usable = subset[subset[col_use] == True]
            fwd    = usable[f"fwd_{PRIMARY_WINDOW}d"].dropna()
            alpha  = usable[f"alpha_{PRIMARY_WINDOW}d"].dropna()
            dd     = usable[f"dd_{PRIMARY_WINDOW}d"].dropna()
            if len(fwd) < 3:
                continue
            rows.append({
                "regime":       regime,
                "group":        group,
                "n":            len(fwd),
                "avg_return":   round(float(fwd.mean()), 4),
                "avg_alpha":    round(float(alpha.mean()), 4) if not alpha.empty else None,
                "win_rate":     round(float((fwd > 0).mean() * 100), 2),
                "avg_drawdown": round(float(dd.mean()), 4) if not dd.empty else None,
            })

    return pd.DataFrame(rows)


def format_report(results: dict[str, pd.DataFrame]) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("TEST 15 — MARKET REGIME ANALYSIS")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Ve kterem trhu edge vznika? Ve kterem mizi?")
    lines.append(f"Rezim: SPY 20D return > +{RISK_ON_THRESH}% = RISK_ON")
    lines.append(f"       SPY 20D return < {RISK_OFF_THRESH}% = RISK_OFF")
    lines.append(f"       jinak = NEUTRAL")
    lines.append(f"Primarne okno: {PRIMARY_WINDOW}D")
    lines.append("")

    configs = [
        ("MLE_IND",     "MLE + TOP5 Industry",        "MLE+TOP5_IND",    "MLE_ONLY"),
        ("IMS_IND",     "IMS + TOP10 Industry",       "IMS+TOP10_IND",   "IMS_ONLY"),
        ("MLE_PERSIST", "MLE + Persistence MED/HIGH", "MLE+PERSIST_MED", "MLE+PERSIST_LOW"),
    ]

    for key, title, best_lbl, base_lbl in configs:
        df = results.get(key, pd.DataFrame())
        lines.append(f"[ {title} ]")
        lines.append("-" * 70)

        if df.empty or "regime" not in df.columns:
            lines.append("  Nedostatek dat.")
            lines.append("")
            continue

        lines.append(
            f"  {'Rezim':<10}  {'Skupina':<20}  {'N':>5}  "
            f"{'Avg%':>7}  {'Alpha':>7}  {'WinRate':>7}"
        )
        lines.append(
            f"  {'-'*10}  {'-'*20}  {'-'*5}  "
            f"{'-'*7}  {'-'*7}  {'-'*7}"
        )

        for regime in ["RISK_ON", "NEUTRAL", "RISK_OFF"]:
            sub = df[df["regime"] == regime]
            if sub.empty:
                continue
            for group in (best_lbl, base_lbl):
                row = sub[sub["group"] == group]
                if row.empty:
                    continue
                r = row.iloc[0]
                alpha_str = f"{r['avg_alpha']:>+6.2f}%" if r["avg_alpha"] is not None else "    N/A"
                lines.append(
                    f"  {regime:<10}  {group:<20}  {int(r['n']):>5}  "
                    f"{r['avg_return']:>+6.2f}%  {alpha_str}  {r['win_rate']:>6.1f}%"
                )

            # Delta per regime
            best_row = sub[sub["group"] == best_lbl]
            base_row = sub[sub["group"] == base_lbl]
            if not best_row.empty and not base_row.empty:
                d_a = (best_row.iloc[0]["avg_alpha"] or 0) - (base_row.iloc[0]["avg_alpha"] or 0)
                pass_str = "✓ PASS" if d_a > 0 else "✗ FAIL"
                lines.append(
                    f"  {'':<10}  {'DELTA':<20}  {'':>5}  "
                    f"{'':>7}  {'+' if d_a >= 0 else ''}{d_a:>6.2f}%  {pass_str}"
                )
            lines.append("")

        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  Edge silny v RISK_ON i NEUTRAL = robustni pro produkci")
    lines.append("  Edge pouze v RISK_ON = pozor v bear markets")
    lines.append("  Edge mizí v RISK_OFF = normalni pro momentum strategie")
    lines.append("")

    return lines
