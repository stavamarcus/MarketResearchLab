"""
Cross-Module Audit
market_breadth/audit/cross_module_audit.py

Účel:
    Výzkumný audit vztahů mezi Market Breadth Evolution a ostatními moduly.
    Standalone skript — bez MRC, bez thresholdů, bez MIO integrace.

Vstupní soubory:
    market_breadth/output/breadth_history.csv
    MarketLeadershipEngine/output/archive/rank_matrix_archive.csv
    InstitutionalMomentumScanner/output/archive/ims_candidates_archive.csv
    industry_rank_calendar/output/archive/industry_rank_calendar_archive.csv

Výstupní soubory (market_breadth/audit/output/):
    audit_summary.txt
    breadth_distribution.csv
    breadth_change_events.csv
    irc_lookback_comparison.csv
    breadth_vs_mle.csv
    breadth_vs_ims.csv
    breadth_vs_irc.csv
    breadth_vs_ims_corr.csv

Společný průnik: 2025-07-09 → 2026-06-26 (244 dní)

Spuštění:
    conda activate market_breadth
    cd C:\\Users\\stava\\Projects\\market_breadth
    python audit\\cross_module_audit.py
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Konfigurace cest
# ---------------------------------------------------------------------------

PROJECTS = Path(r"C:\Users\stava\Projects")

BREADTH_CSV  = PROJECTS / "market_breadth" / "output" / "breadth_history.csv"
MLE_CSV      = PROJECTS / "MarketLeadershipEngine" / "output" / "archive" / "rank_matrix_archive.csv"
IMS_CSV      = PROJECTS / "InstitutionalMomentumScanner" / "output" / "archive" / "ims_candidates_archive.csv"
IRC_CSV      = PROJECTS / "industry_rank_calendar" / "output" / "archive" / "industry_rank_calendar_archive.csv"

OUTPUT_DIR   = Path(__file__).resolve().parent / "output"

# Společný průnik (zjištěno diagnostikou)
INTERSECTION_START = "2025-07-09"
INTERSECTION_END   = "2026-06-26"

# IRC lookbacky k analýze
IRC_LOOKBACKS = [5, 10, 20, 30]

# Počet top/bottom industry pro analýzu
IRC_TOP_N = 7

# Počet top MLE tickerů (rank_10d)
MLE_TOP_N = 20

# IMS skupiny
IMS_ELITE_MIN = 90
IMS_HIGH_MIN  = 70


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("CROSS-MODULE AUDIT")
    print("=" * 60)
    print(f"Průnik: {INTERSECTION_START} → {INTERSECTION_END}")
    print()

    # 1. Načti a ořízni data
    breadth, mle, ims, irc = _load_data()

    # 2. Audit 1 — Breadth distribuce a události
    breadth_dist   = _audit_breadth_distribution(breadth)
    breadth_events = _audit_breadth_change_events(breadth)

    # 3. Audit 2 — IRC lookback srovnání
    irc_comparison = _audit_irc_lookbacks(irc, breadth)

    # 4. Audit 3 — Breadth vs MLE
    breadth_vs_mle = _audit_breadth_vs_mle(breadth, mle)

    # 5. Audit 4 — Breadth vs IMS
    breadth_vs_ims = _audit_breadth_vs_ims(breadth, ims)

    # 6. Audit 5 — Breadth vs IRC
    breadth_vs_irc = _audit_breadth_vs_irc(breadth, irc)

    # 7. Ulož CSV výstupy
    _save_outputs(
        breadth_dist, breadth_events,
        irc_comparison,
        breadth_vs_mle, breadth_vs_ims, breadth_vs_irc,
    )

    # 8. Sestav audit_summary.txt
    _write_summary(
        breadth, mle, ims, irc,
        breadth_dist, breadth_events,
        irc_comparison,
        breadth_vs_mle, breadth_vs_ims, breadth_vs_irc,
    )

    print()
    print(f"Výstupy uloženy do: {OUTPUT_DIR}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Načtení dat
# ---------------------------------------------------------------------------

def _load_data():
    print("Načítám data...")

    breadth = pd.read_csv(BREADTH_CSV, parse_dates=["date"])
    breadth = breadth[
        (breadth["date"] >= INTERSECTION_START) &
        (breadth["date"] <= INTERSECTION_END)
    ].copy()
    breadth = breadth[breadth["above_ma50_pct"].notna()].reset_index(drop=True)
    print(f"  Breadth: {len(breadth)} dní")

    mle = pd.read_csv(MLE_CSV, parse_dates=["date"], low_memory=False)
    mle = mle[
        (mle["date"] >= INTERSECTION_START) &
        (mle["date"] <= INTERSECTION_END)
    ].copy()
    print(f"  MLE: {len(mle)} řádků, {mle['date'].nunique()} dní")

    ims = pd.read_csv(IMS_CSV, parse_dates=["date"])
    ims = ims[
        (ims["date"] >= INTERSECTION_START) &
        (ims["date"] <= INTERSECTION_END)
    ].copy()
    print(f"  IMS: {len(ims)} řádků, {ims['date'].nunique()} dní")

    irc = pd.read_csv(IRC_CSV, parse_dates=["date"])
    irc = irc[
        (irc["date"] >= INTERSECTION_START) &
        (irc["date"] <= INTERSECTION_END)
    ].copy()
    print(f"  IRC: {len(irc)} řádků, {irc['date'].nunique()} dní, lookbacky: {sorted(irc['lookback'].unique())}")
    print()

    return breadth, mle, ims, irc


# ---------------------------------------------------------------------------
# Audit 1 — Breadth distribuce
# ---------------------------------------------------------------------------

def _audit_breadth_distribution(breadth: pd.DataFrame) -> pd.DataFrame:
    """
    Základní statistiky breadth metrik za celé období průniku.
    Otázky: Jaké jsou typické hodnoty? Kde jsou extrémní body?
    """
    print("Audit 1: Breadth distribuce...")

    metrics = ["above_ma50_pct", "above_ma100_pct", "above_ma200_pct",
               "advance_decline_net", "new_highs", "new_lows", "mcclellan"]

    rows = []
    for m in metrics:
        if m not in breadth.columns:
            continue
        s = breadth[m].dropna()
        if len(s) == 0:
            continue
        rows.append({
            "metric":   m,
            "count":    len(s),
            "mean":     round(s.mean(), 2),
            "median":   round(s.median(), 2),
            "std":      round(s.std(), 2),
            "min":      round(s.min(), 2),
            "p10":      round(s.quantile(0.10), 2),
            "p25":      round(s.quantile(0.25), 2),
            "p75":      round(s.quantile(0.75), 2),
            "p90":      round(s.quantile(0.90), 2),
            "max":      round(s.max(), 2),
        })

    # Evolution distribuce (1D/5D/10D/20D změny)
    evo_cols = [c for c in breadth.columns if "_change_pp" in c]
    for m in evo_cols:
        s = breadth[m].dropna()
        if len(s) == 0:
            continue
        rows.append({
            "metric":   m,
            "count":    len(s),
            "mean":     round(s.mean(), 2),
            "median":   round(s.median(), 2),
            "std":      round(s.std(), 2),
            "min":      round(s.min(), 2),
            "p10":      round(s.quantile(0.10), 2),
            "p25":      round(s.quantile(0.25), 2),
            "p75":      round(s.quantile(0.75), 2),
            "p90":      round(s.quantile(0.90), 2),
            "max":      round(s.max(), 2),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Audit 1b — Breadth change events
# ---------------------------------------------------------------------------

def _audit_breadth_change_events(breadth: pd.DataFrame) -> pd.DataFrame:
    """
    Identifikuje významné pohyby v breadth.
    Otázky:
      - Jak rychle se mění breadth při korekcích?
      - Jak dlouho trvá zotavení?
      - Jak často nastává prudký breakdown?
    """
    print("Audit 1b: Breadth change events...")

    rows = []
    for _, row in breadth.iterrows():
        for ma in [50, 100, 200]:
            pct_col  = f"above_ma{ma}_pct"
            c1d      = f"above_ma{ma}_1d_change_pp"
            c5d      = f"above_ma{ma}_5d_change_pp"
            c10d     = f"above_ma{ma}_10d_change_pp"
            c20d     = f"above_ma{ma}_20d_change_pp"

            if pct_col not in breadth.columns:
                continue

            pct  = row.get(pct_col)
            d1   = row.get(c1d)
            d5   = row.get(c5d)
            d10  = row.get(c10d)
            d20  = row.get(c20d)

            if pd.isna(pct):
                continue

            # Klasifikuj rychlost změny za 5D
            if pd.notna(d5):
                if d5 <= -10:
                    event_5d = "crash"        # >= 10 pp pokles za 5D
                elif d5 <= -5:
                    event_5d = "sharp_down"   # 5-10 pp pokles
                elif d5 <= -2:
                    event_5d = "down"
                elif d5 >= 10:
                    event_5d = "surge"
                elif d5 >= 5:
                    event_5d = "sharp_up"
                elif d5 >= 2:
                    event_5d = "up"
                else:
                    event_5d = "flat"
            else:
                event_5d = None

            rows.append({
                "date":      row["date"],
                "ma":        ma,
                "pct":       pct,
                "1d_pp":     d1,
                "5d_pp":     d5,
                "10d_pp":    d10,
                "20d_pp":    d20,
                "event_5d":  event_5d,
            })

    df = pd.DataFrame(rows)

    # Statistiky podle event_5d
    if "event_5d" in df.columns:
        summary = df.groupby(["ma", "event_5d"]).agg(
            count=("date", "count"),
            avg_pct=("pct", "mean"),
            avg_1d=("1d_pp", "mean"),
            avg_10d=("10d_pp", "mean"),
            avg_20d=("20d_pp", "mean"),
        ).round(2).reset_index()
        return summary

    return df


# ---------------------------------------------------------------------------
# Audit 2 — IRC lookback srovnání
# ---------------------------------------------------------------------------

def _audit_irc_lookbacks(irc: pd.DataFrame, breadth: pd.DataFrame) -> pd.DataFrame:
    """
    Porovnává stabilitu a chování IRC pro různé lookbacky (5/10/20/30D)
    v kontextu breadth stavu.
    Otázky:
      - Liší se žebříčky industrie podle lookbacku?
      - Jsou některé lookbacky stabilnější při slabém breadth?
    """
    print("Audit 2: IRC lookback srovnání...")

    # Přidej breadth kontext ke každému IRC datu
    breadth_daily = breadth[["date", "above_ma200_pct", "above_ma200_5d_change_pp",
                              "above_ma200_20d_change_pp"]].copy()

    rows = []
    for lb in IRC_LOOKBACKS:
        irc_lb = irc[irc["lookback"] == lb].copy()
        irc_lb = irc_lb.merge(breadth_daily, on="date", how="inner")

        # Top 7 industrie per den
        top7 = irc_lb[irc_lb["rank"] <= IRC_TOP_N]

        # Korelace: rank 1 industrie median_return vs breadth
        rank1 = irc_lb[irc_lb["rank"] == 1][["date", "median_return", "above_ma200_pct",
                                               "above_ma200_20d_change_pp"]].copy()

        corr_pct  = rank1["median_return"].corr(rank1["above_ma200_pct"])
        corr_evo  = rank1["median_return"].corr(rank1["above_ma200_20d_change_pp"])

        # Stabilita top7 — průměrný advance_ratio top industrie
        top7_adv  = top7.groupby("date")["advance_ratio"].mean()

        # Breadth kvartily → průměrný advance_ratio top industrie
        irc_lb["breadth_q"] = pd.qcut(irc_lb["above_ma200_pct"], q=4,
                                       labels=["Q1_weak", "Q2", "Q3", "Q4_strong"])
        by_q = irc_lb[irc_lb["rank"] <= IRC_TOP_N].groupby("breadth_q").agg(
            avg_median_return=("median_return", "mean"),
            avg_advance_ratio=("advance_ratio", "mean"),
            n_days=("date", "nunique"),
        ).round(2)

        for q_label, q_row in by_q.iterrows():
            rows.append({
                "lookback":             lb,
                "breadth_quartile":     q_label,
                "avg_top7_ret":         q_row["avg_median_return"],
                "avg_top7_adv_ratio":   q_row["avg_advance_ratio"],
                "n_days":               q_row["n_days"],
                "corr_ret_vs_breadth_pct": round(corr_pct, 3),
                "corr_ret_vs_breadth_evo": round(corr_evo, 3),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Audit 3 — Breadth vs MLE
# ---------------------------------------------------------------------------

def _audit_breadth_vs_mle(breadth: pd.DataFrame, mle: pd.DataFrame) -> pd.DataFrame:
    """
    Otázky:
      - Mizí MLE edge (rank_10d TOP20) při slabém breadth?
      - Začíná breadth slábnout dříve než MLE?
      - Funguje MLE při breadth zhoršení ale ještě ne kolapsu?
    """
    print("Audit 3: Breadth vs MLE...")

    # Denní agregát MLE: počet TOP20, průměrný return TOP20
    mle_daily = mle.copy()
    mle_daily["is_top20"] = mle_daily["rank_10d"] <= MLE_TOP_N

    mle_agg = mle_daily.groupby("date").agg(
        top20_count=("is_top20", "sum"),
        top20_avg_ret_10d=("ret_10d", lambda x: x[mle_daily.loc[x.index, "is_top20"]].mean()),
        universe_size=("ticker", "count"),
    ).reset_index()

    # Merge s breadth
    merged = mle_agg.merge(
        breadth[["date", "above_ma50_pct", "above_ma100_pct", "above_ma200_pct",
                 "above_ma200_1d_change_pp", "above_ma200_5d_change_pp",
                 "above_ma200_10d_change_pp", "above_ma200_20d_change_pp",
                 "advance_decline_net", "new_highs", "new_lows"]],
        on="date", how="inner"
    )

    # Breadth kvartily podle MA200
    merged["breadth_q200"] = pd.qcut(merged["above_ma200_pct"], q=4,
                                      labels=["Q1_weak", "Q2", "Q3", "Q4_strong"])

    # Výsledek: průměrný MLE return TOP20 podle breadth kvartilu
    by_q = merged.groupby("breadth_q200").agg(
        n_days=("date", "count"),
        avg_top20_ret_10d=("top20_avg_ret_10d", "mean"),
        avg_top20_count=("top20_count", "mean"),
        avg_breadth_ma200=("above_ma200_pct", "mean"),
        avg_nh=("new_highs", "mean"),
        avg_nl=("new_lows", "mean"),
    ).round(2).reset_index()

    # Korelace: MLE top20 return vs breadth evoluce
    corr_rows = []
    for col in ["above_ma50_pct", "above_ma200_pct",
                "above_ma200_5d_change_pp", "above_ma200_20d_change_pp",
                "advance_decline_net"]:
        if col in merged.columns:
            c = merged["top20_avg_ret_10d"].corr(merged[col])
            corr_rows.append({"breadth_signal": col, "corr_with_mle_top20_ret": round(c, 3)})

    corr_df = pd.DataFrame(corr_rows)

    # Kombinovaný výstup
    by_q["type"] = "by_breadth_quartile"
    corr_df["type"] = "correlation"
    result = pd.concat([
        by_q.rename(columns={"breadth_q200": "label"}),
        corr_df.rename(columns={"breadth_signal": "label", "corr_with_mle_top20_ret": "avg_top20_ret_10d"}),
    ], ignore_index=True)

    return result


# ---------------------------------------------------------------------------
# Audit 4 — Breadth vs IMS
# ---------------------------------------------------------------------------

def _audit_breadth_vs_ims(breadth: pd.DataFrame, ims: pd.DataFrame) -> pd.DataFrame:
    """
    Otázky:
      - Jak reaguje počet IMS HIGH/ELITE signálů na breadth?
      - Při jakém breadth stavu se objevují nejkvalitnější IMS signály?
    """
    print("Audit 4: Breadth vs IMS...")

    # IMS ELITE = score >= 90, HIGH = 70-89
    ims = ims.copy()
    ims["is_elite"] = ims["score"] >= IMS_ELITE_MIN
    ims["is_high"]  = (ims["score"] >= IMS_HIGH_MIN) & (ims["score"] < IMS_ELITE_MIN)

    ims_daily = ims.groupby("date").agg(
        elite_count=("is_elite", "sum"),
        high_count=("is_high", "sum"),
        total_count=("ticker", "count"),
        avg_score=("score", "mean"),
        avg_rs_vs_spy=("rs_vs_spy_20d", "mean"),
    ).reset_index()

    merged = ims_daily.merge(
        breadth[["date", "above_ma50_pct", "above_ma100_pct", "above_ma200_pct",
                 "above_ma200_1d_change_pp", "above_ma200_5d_change_pp",
                 "above_ma200_20d_change_pp", "advance_decline_net",
                 "new_highs", "new_lows"]],
        on="date", how="inner"
    )

    # Breadth kvartily
    merged["breadth_q200"] = pd.qcut(merged["above_ma200_pct"], q=4,
                                      labels=["Q1_weak", "Q2", "Q3", "Q4_strong"])

    by_q = merged.groupby("breadth_q200").agg(
        n_days=("date", "count"),
        avg_elite_count=("elite_count", "mean"),
        avg_high_count=("high_count", "mean"),
        avg_total_ims=("total_count", "mean"),
        avg_score=("avg_score", "mean"),
        avg_breadth_ma200=("above_ma200_pct", "mean"),
    ).round(2).reset_index()

    # Korelace
    corr_rows = []
    for col in ["above_ma50_pct", "above_ma200_pct",
                "above_ma200_5d_change_pp", "above_ma200_20d_change_pp",
                "advance_decline_net", "new_highs"]:
        if col in merged.columns:
            c_elite = merged["elite_count"].corr(merged[col])
            c_total = merged["total_count"].corr(merged[col])
            corr_rows.append({
                "breadth_signal":    col,
                "corr_elite_count":  round(c_elite, 3),
                "corr_total_count":  round(c_total, 3),
            })

    corr_df = pd.DataFrame(corr_rows)

    return by_q, corr_df


# ---------------------------------------------------------------------------
# Audit 5 — Breadth vs IRC
# ---------------------------------------------------------------------------

def _audit_breadth_vs_irc(breadth: pd.DataFrame, irc: pd.DataFrame) -> pd.DataFrame:
    """
    Otázky:
      - Jak se mění síla TOP industrie podle breadth stavu?
      - Existuje narrow leadership (top industries drží) i při slabém breadth?
      - Který lookback nejlépe koreluje se změnami breadth?
    """
    print("Audit 5: Breadth vs IRC...")

    breadth_slim = breadth[["date", "above_ma50_pct", "above_ma200_pct",
                             "above_ma200_5d_change_pp", "above_ma200_20d_change_pp"]].copy()

    rows = []
    for lb in IRC_LOOKBACKS:
        irc_lb = irc[irc["lookback"] == lb].copy()

        # Top industrie per den
        top    = irc_lb[irc_lb["rank"] <= IRC_TOP_N]
        top_agg = top.groupby("date").agg(
            top7_avg_ret=("median_return", "mean"),
            top7_avg_adv=("advance_ratio", "mean"),
            top7_min_ret=("median_return", "min"),
        ).reset_index()

        # Bottom industrie (rank >= 53) — narrow leadership check
        bottom = irc_lb[irc_lb["rank"] >= 53]
        bot_agg = bottom.groupby("date").agg(
            bot7_avg_ret=("median_return", "mean"),
        ).reset_index()

        merged = top_agg.merge(bot_agg, on="date", how="left")
        merged = merged.merge(breadth_slim, on="date", how="inner")

        # Spread: top vs bottom
        merged["top_bot_spread"] = merged["top7_avg_ret"] - merged["bot7_avg_ret"]

        # Breadth kvartily
        merged["breadth_q"] = pd.qcut(merged["above_ma200_pct"], q=4,
                                       labels=["Q1_weak", "Q2", "Q3", "Q4_strong"])

        by_q = merged.groupby("breadth_q").agg(
            n_days=("date", "count"),
            avg_top7_ret=("top7_avg_ret", "mean"),
            avg_top7_adv=("top7_avg_adv", "mean"),
            avg_spread=("top_bot_spread", "mean"),
            avg_breadth=("above_ma200_pct", "mean"),
        ).round(2).reset_index()

        by_q["lookback"] = lb

        # Korelace top7_avg_ret vs breadth signály
        for col in ["above_ma200_pct", "above_ma200_5d_change_pp", "above_ma200_20d_change_pp"]:
            c = merged["top7_avg_ret"].corr(merged[col])
            by_q[f"corr_vs_{col}"] = round(c, 3)

        rows.append(by_q)

    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# Uložení výstupů
# ---------------------------------------------------------------------------

def _save_outputs(
    breadth_dist, breadth_events,
    irc_comparison,
    breadth_vs_mle, breadth_vs_ims, breadth_vs_irc,
) -> None:
    breadth_dist.to_csv(OUTPUT_DIR / "breadth_distribution.csv", index=False)
    print(f"  Uloženo: breadth_distribution.csv ({len(breadth_dist)} řádků)")

    breadth_events.to_csv(OUTPUT_DIR / "breadth_change_events.csv", index=False)
    print(f"  Uloženo: breadth_change_events.csv ({len(breadth_events)} řádků)")

    irc_comparison.to_csv(OUTPUT_DIR / "irc_lookback_comparison.csv", index=False)
    print(f"  Uloženo: irc_lookback_comparison.csv ({len(irc_comparison)} řádků)")

    breadth_vs_mle.to_csv(OUTPUT_DIR / "breadth_vs_mle.csv", index=False)
    print(f"  Uloženo: breadth_vs_mle.csv ({len(breadth_vs_mle)} řádků)")

    ims_by_q, ims_corr = breadth_vs_ims
    ims_by_q.to_csv(OUTPUT_DIR / "breadth_vs_ims.csv", index=False)
    ims_corr.to_csv(OUTPUT_DIR / "breadth_vs_ims_corr.csv", index=False)
    print(f"  Uloženo: breadth_vs_ims.csv + breadth_vs_ims_corr.csv")

    breadth_vs_irc.to_csv(OUTPUT_DIR / "breadth_vs_irc.csv", index=False)
    print(f"  Uloženo: breadth_vs_irc.csv ({len(breadth_vs_irc)} řádků)")


# ---------------------------------------------------------------------------
# Textový souhrn
# ---------------------------------------------------------------------------

def _write_summary(
    breadth, mle, ims, irc,
    breadth_dist, breadth_events,
    irc_comparison,
    breadth_vs_mle, breadth_vs_ims, breadth_vs_irc,
) -> None:

    ims_by_q, ims_corr = breadth_vs_ims
    lines = []
    sep  = "=" * 60
    line = "-" * 60

    lines += [
        "", sep,
        "  CROSS-MODULE AUDIT — VÝSLEDKY",
        f"  Průnik: {INTERSECTION_START} → {INTERSECTION_END}",
        f"  Dní: {len(breadth)}",
        sep, "",
    ]

    # --- Breadth distribuce ---
    lines += [line, "[ 1. BREADTH DISTRIBUCE ]", ""]
    for _, r in breadth_dist[breadth_dist["metric"].isin(
            ["above_ma50_pct", "above_ma100_pct", "above_ma200_pct"])].iterrows():
        lines.append(
            f"  {r['metric']:30s}  "
            f"med={r['median']:5.1f}%  "
            f"std={r['std']:4.1f}  "
            f"p10={r['p10']:5.1f}  "
            f"p90={r['p90']:5.1f}"
        )
    lines.append("")

    # Evolution distribuce
    lines.append("  Evolution (pp) — MA200:")
    for _, r in breadth_dist[breadth_dist["metric"].str.contains("ma200.*change")].iterrows():
        lines.append(
            f"  {r['metric']:40s}  "
            f"med={r['median']:+5.1f}  "
            f"p10={r['p10']:+6.1f}  "
            f"p90={r['p90']:+6.1f}"
        )
    lines.append("")

    # --- Breadth change events ---
    lines += [line, "[ 2. BREADTH CHANGE EVENTS (MA200, klasifikace 5D pohybu) ]", ""]
    events_200 = breadth_events[breadth_events["ma"] == 200] if "ma" in breadth_events.columns else pd.DataFrame()
    if not events_200.empty:
        for _, r in events_200.iterrows():
            lines.append(
                f"  {str(r.get('event_5d','')):<12s}  "
                f"n={int(r.get('count', 0)):4d}  "
                f"avg_pct={r.get('avg_pct', float('nan')):5.1f}%  "
                f"avg_10d={r.get('avg_10d', float('nan')):+5.1f}pp  "
                f"avg_20d={r.get('avg_20d', float('nan')):+5.1f}pp"
            )
    lines.append("")

    # --- IRC lookback srovnání ---
    lines += [line, "[ 3. IRC LOOKBACK SROVNÁNÍ (TOP7, podle breadth kvartilu) ]", ""]
    if not irc_comparison.empty:
        for lb in IRC_LOOKBACKS:
            lb_df = irc_comparison[irc_comparison["lookback"] == lb]
            if lb_df.empty:
                continue
            lines.append(f"  Lookback {lb}D:")
            corr_pct = lb_df["corr_ret_vs_breadth_pct"].iloc[0] if "corr_ret_vs_breadth_pct" in lb_df.columns else float("nan")
            corr_evo = lb_df["corr_ret_vs_breadth_evo"].iloc[0] if "corr_ret_vs_breadth_evo" in lb_df.columns else float("nan")
            lines.append(f"    Korelace (top7_ret vs breadth_pct): {corr_pct:+.3f}")
            lines.append(f"    Korelace (top7_ret vs breadth_20D_evo): {corr_evo:+.3f}")
            for _, r in lb_df.iterrows():
                lines.append(
                    f"    {str(r.get('breadth_quartile','')):<12s}  "
                    f"avg_ret={r.get('avg_top7_ret', float('nan')):+5.1f}%  "
                    f"avg_adv={r.get('avg_top7_adv_ratio', float('nan')):5.1f}%  "
                    f"n={int(r.get('n_days', 0)):3d}d"
                )
            lines.append("")

    # --- Breadth vs MLE ---
    lines += [line, "[ 4. BREADTH vs MLE (TOP20 rank_10d) ]", ""]
    mle_q = breadth_vs_mle[breadth_vs_mle["type"] == "by_breadth_quartile"] if "type" in breadth_vs_mle.columns else breadth_vs_mle
    mle_c = breadth_vs_mle[breadth_vs_mle["type"] == "correlation"] if "type" in breadth_vs_mle.columns else pd.DataFrame()

    if not mle_q.empty:
        lines.append("  Průměrný 10D return MLE TOP20 podle breadth kvartilu (MA200):")
        for _, r in mle_q.iterrows():
            ret = r.get("avg_top20_ret_10d", float("nan"))
            cnt = r.get("avg_top20_count", float("nan"))
            n   = r.get("n_days", 0)
            brd = r.get("avg_breadth_ma200", float("nan"))
            lines.append(
                f"    {str(r.get('label','')):<12s}  "
                f"avg_ret_10d={ret:+5.1f}%  "
                f"avg_top20_n={cnt:4.1f}  "
                f"avg_breadth={brd:4.1f}%  "
                f"n={int(n):3d}d"
            )
    lines.append("")

    if not mle_c.empty:
        lines.append("  Korelace MLE TOP20 return vs breadth signály:")
        for _, r in mle_c.iterrows():
            lines.append(f"    {str(r.get('label','')):<40s}  corr={r.get('avg_top20_ret_10d', float('nan')):+.3f}")
    lines.append("")

    # --- Breadth vs IMS ---
    lines += [line, "[ 5. BREADTH vs IMS (ELITE score>=90) ]", ""]
    if not ims_by_q.empty:
        lines.append("  Průměrný počet IMS ELITE signálů podle breadth kvartilu (MA200):")
        for _, r in ims_by_q.iterrows():
            lines.append(
                f"    {str(r.get('breadth_q200','')):<12s}  "
                f"elite={r.get('avg_elite_count', float('nan')):4.1f}/d  "
                f"high={r.get('avg_high_count', float('nan')):5.1f}/d  "
                f"avg_score={r.get('avg_score', float('nan')):4.1f}  "
                f"breadth={r.get('avg_breadth_ma200', float('nan')):4.1f}%  "
                f"n={int(r.get('n_days', 0)):3d}d"
            )
    lines.append("")

    if not ims_corr.empty:
        lines.append("  Korelace IMS ELITE count vs breadth signály:")
        for _, r in ims_corr.iterrows():
            lines.append(
                f"    {str(r.get('breadth_signal','')):<40s}  "
                f"elite={r.get('corr_elite_count', float('nan')):+.3f}  "
                f"total={r.get('corr_total_count', float('nan')):+.3f}"
            )
    lines.append("")

    # --- Breadth vs IRC ---
    lines += [line, "[ 6. BREADTH vs IRC (TOP7 industrie, spread top vs bottom) ]", ""]
    if not breadth_vs_irc.empty:
        for lb in IRC_LOOKBACKS:
            lb_df = breadth_vs_irc[breadth_vs_irc["lookback"] == lb]
            if lb_df.empty:
                continue
            lines.append(f"  Lookback {lb}D:")
            for _, r in lb_df.iterrows():
                lines.append(
                    f"    {str(r.get('breadth_q','')):<12s}  "
                    f"top7_ret={r.get('avg_top7_ret', float('nan')):+5.1f}%  "
                    f"spread={r.get('avg_spread', float('nan')):+5.1f}pp  "
                    f"adv={r.get('avg_top7_adv', float('nan')):5.1f}%  "
                    f"n={int(r.get('n_days', 0)):3d}d"
                )
            # Korelace
            corr_cols = [c for c in lb_df.columns if c.startswith("corr_vs_")]
            for cc in corr_cols:
                val = lb_df[cc].iloc[0]
                lines.append(f"    korelace {cc}: {val:+.3f}")
            lines.append("")

    lines += [sep, "  Výstupy uloženy do: audit/output/", sep, ""]

    summary_path = OUTPUT_DIR / "audit_summary.txt"
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Uloženo: audit_summary.txt")


if __name__ == "__main__":
    main()
