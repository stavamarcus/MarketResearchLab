"""
Lead/Lag Audit
market_breadth/audit/lag_audit.py

Účel:
    Výzkumný audit časového zpoždění mezi pohyby Market Breadth
    a reakcemi ostatních modulů (MLE, IMS, IRC).

    Hlavní část:  Event-based Lead/Lag
    Doplněk:      Cross-correlation

Vstupní soubory:
    market_breadth/output/breadth_history.csv
    MarketLeadershipEngine/output/archive/rank_matrix_archive.csv
    InstitutionalMomentumScanner/output/archive/ims_candidates_archive.csv
    industry_rank_calendar/output/archive/industry_rank_calendar_archive.csv

Výstupní soubory (market_breadth/audit/output/):
    lag_audit_summary.txt
    lag_events.csv
    lag_event_mle.csv
    lag_event_ims.csv
    lag_event_irc.csv
    lag_crosscorr.csv

Společný průnik: 2025-07-09 → 2026-06-26 (244 dní)

Spuštění:
    conda activate market_breadth
    cd C:\\Users\\stava\\Projects\\market_breadth
    python audit\\lag_audit.py
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Konfigurace cest
# ---------------------------------------------------------------------------

PROJECTS     = Path(r"C:\Users\stava\Projects")
BREADTH_CSV  = PROJECTS / "market_breadth" / "output" / "breadth_history.csv"
MLE_CSV      = PROJECTS / "MarketLeadershipEngine" / "output" / "archive" / "rank_matrix_archive.csv"
IMS_CSV      = PROJECTS / "InstitutionalMomentumScanner" / "output" / "archive" / "ims_candidates_archive.csv"
IRC_CSV      = PROJECTS / "industry_rank_calendar" / "output" / "archive" / "industry_rank_calendar_archive.csv"

OUTPUT_DIR   = Path(__file__).resolve().parent / "output"

# ---------------------------------------------------------------------------
# Parametry
# ---------------------------------------------------------------------------

INTERSECTION_START = "2025-07-09"
INTERSECTION_END   = "2026-06-26"

# Event thresholdy — MA50 jako primární (více událostí), MA200 jako sekundární
EVENTS = [
    # (sloupec, threshold, směr, label)
    ("above_ma50_5d_change_pp",  -5,  "down", "MA50_5D_dn5"),
    ("above_ma50_5d_change_pp",  -8,  "down", "MA50_5D_dn8"),
    ("above_ma50_5d_change_pp",  +5,  "up",   "MA50_5D_up5"),
    ("above_ma50_5d_change_pp",  +8,  "up",   "MA50_5D_up8"),
    ("above_ma200_5d_change_pp", -5,  "down", "MA200_5D_dn5"),
    ("above_ma200_5d_change_pp", -8,  "down", "MA200_5D_dn8"),
    ("above_ma200_5d_change_pp", +5,  "up",   "MA200_5D_up5"),
    ("above_ma200_5d_change_pp", +8,  "up",   "MA200_5D_up8"),
]

# Horizonty pro forward analýzu (v obchodních dnech)
FORWARD_HORIZONS = [1, 3, 5, 10]

# IRC lookbacky
IRC_LOOKBACKS = [5, 10, 20, 30]

# TOP N pro MLE
MLE_TOP_N = 20

# Cross-correlation lag rozsah
LAG_RANGE = range(-20, 21)

# Minimální N pro spolehlivý výsledek
MIN_N_RELIABLE = 15


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("LEAD/LAG AUDIT")
    print("=" * 60)
    print(f"Průnik: {INTERSECTION_START} → {INTERSECTION_END}")
    print()

    # 1. Načti data
    breadth, mle_daily, ims_daily, irc_daily = _load_data()

    # 2. Identifikuj události
    events_df = _detect_events(breadth)
    events_df.to_csv(OUTPUT_DIR / "lag_events.csv", index=False)
    print(f"  Uloženo: lag_events.csv ({len(events_df)} událostí)")

    # 3. Event-based forward analýza
    lag_mle = _event_forward_analysis(events_df, mle_daily, "mle")
    lag_ims = _event_forward_analysis(events_df, ims_daily, "ims")
    lag_irc = _event_forward_analysis(events_df, irc_daily, "irc")

    lag_mle.to_csv(OUTPUT_DIR / "lag_event_mle.csv", index=False)
    lag_ims.to_csv(OUTPUT_DIR / "lag_event_ims.csv", index=False)
    lag_irc.to_csv(OUTPUT_DIR / "lag_event_irc.csv", index=False)
    print(f"  Uloženo: lag_event_mle.csv, lag_event_ims.csv, lag_event_irc.csv")

    # 4. Cross-correlation
    crosscorr = _cross_correlation(breadth, mle_daily, ims_daily, irc_daily)
    crosscorr.to_csv(OUTPUT_DIR / "lag_crosscorr.csv", index=False)
    print(f"  Uloženo: lag_crosscorr.csv ({len(crosscorr)} řádků)")

    # 5. Summary
    _write_summary(breadth, events_df, lag_mle, lag_ims, lag_irc, crosscorr)
    print(f"  Uloženo: lag_audit_summary.txt")

    print()
    print(f"Výstupy uloženy do: {OUTPUT_DIR}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Načtení a příprava denních signálů
# ---------------------------------------------------------------------------

def _load_data():
    print("Načítám data...")

    # Breadth
    breadth = pd.read_csv(BREADTH_CSV, parse_dates=["date"])
    breadth = breadth[
        (breadth["date"] >= INTERSECTION_START) &
        (breadth["date"] <= INTERSECTION_END) &
        breadth["above_ma50_pct"].notna()
    ].reset_index(drop=True)
    print(f"  Breadth: {len(breadth)} dní")

    # MLE — denní agregát: avg ret_10d TOP20
    mle = pd.read_csv(MLE_CSV, parse_dates=["date"], low_memory=False)
    mle = mle[(mle["date"] >= INTERSECTION_START) & (mle["date"] <= INTERSECTION_END)]
    mle["is_top20"] = mle["rank_10d"] <= MLE_TOP_N
    mle_daily = mle.groupby("date").apply(
        lambda x: pd.Series({
            "mle_top20_ret10d": x.loc[x["is_top20"], "ret_10d"].mean(),
            "mle_top20_count":  x["is_top20"].sum(),
        })
    ).reset_index()
    print(f"  MLE: {len(mle_daily)} dní")

    # IMS — denní agregát
    ims = pd.read_csv(IMS_CSV, parse_dates=["date"])
    ims = ims[(ims["date"] >= INTERSECTION_START) & (ims["date"] <= INTERSECTION_END)]
    ims_daily = ims.groupby("date").agg(
        ims_elite_count=("score", lambda x: (x >= 90).sum()),
        ims_high_count=("score",  lambda x: ((x >= 70) & (x < 90)).sum()),
        ims_total=("ticker", "count"),
        ims_avg_score=("score", "mean"),
    ).reset_index()
    print(f"  IMS: {len(ims_daily)} dní")

    # IRC — denní agregát pro každý lookback
    irc = pd.read_csv(IRC_CSV, parse_dates=["date"])
    irc = irc[(irc["date"] >= INTERSECTION_START) & (irc["date"] <= INTERSECTION_END)]
    irc_parts = []
    for lb in IRC_LOOKBACKS:
        top7 = irc[(irc["lookback"] == lb) & (irc["rank"] <= 7)]
        agg = top7.groupby("date").agg(
            top7_ret=("median_return", "mean"),
            top7_adv=("advance_ratio", "mean"),
        ).reset_index()
        agg["lookback"] = lb
        irc_parts.append(agg)
    irc_daily = pd.concat(irc_parts, ignore_index=True)
    print(f"  IRC: {len(irc_daily)} řádků ({irc_daily['date'].nunique()} dní × {len(IRC_LOOKBACKS)} lookbacky)")
    print()

    return breadth, mle_daily, ims_daily, irc_daily


# ---------------------------------------------------------------------------
# Detekce událostí
# ---------------------------------------------------------------------------

def _detect_events(breadth: pd.DataFrame) -> pd.DataFrame:
    """
    Identifikuje dny kde breadth splňuje event podmínky.
    Přidá kontext (breadth hodnoty v den události).
    """
    rows = []
    for col, thresh, direction, label in EVENTS:
        if col not in breadth.columns:
            continue
        s = breadth[col].dropna()
        if direction == "down":
            mask = breadth[col] <= thresh
        else:
            mask = breadth[col] >= thresh

        event_days = breadth[mask].copy()
        for _, row in event_days.iterrows():
            rows.append({
                "event_label":        label,
                "event_col":          col,
                "threshold":          thresh,
                "direction":          direction,
                "date":               row["date"],
                "above_ma50_pct":     row.get("above_ma50_pct"),
                "above_ma200_pct":    row.get("above_ma200_pct"),
                "breadth_5d_pp_ma50": row.get("above_ma50_5d_change_pp"),
                "breadth_5d_pp_ma200":row.get("above_ma200_5d_change_pp"),
            })

    df = pd.DataFrame(rows).sort_values(["event_label", "date"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Event-based forward analýza
# ---------------------------------------------------------------------------

def _event_forward_analysis(
    events_df: pd.DataFrame,
    module_daily: pd.DataFrame,
    module_name: str,
) -> pd.DataFrame:
    """
    Pro každý event typ zjistí průměrné hodnoty modulového signálu
    v horizontech +1/+3/+5/+10 dní po události.

    Porovnává s baseline (průměr celého období bez event dnů).
    """
    # Příprava: pro IRC zpracuj každý lookback zvlášť
    if module_name == "irc":
        parts = []
        for lb in IRC_LOOKBACKS:
            sub = module_daily[module_daily["lookback"] == lb][["date", "top7_ret", "top7_adv"]].copy()
            result = _compute_forward(events_df, sub, ["top7_ret", "top7_adv"], module_name, lb)
            result["lookback"] = lb
            parts.append(result)
        return pd.concat(parts, ignore_index=True)
    else:
        if module_name == "mle":
            signal_cols = ["mle_top20_ret10d"]
        else:
            signal_cols = ["ims_elite_count", "ims_high_count", "ims_total", "ims_avg_score"]
        return _compute_forward(events_df, module_daily, signal_cols, module_name)


def _compute_forward(
    events_df: pd.DataFrame,
    module_daily: pd.DataFrame,
    signal_cols: list[str],
    module_name: str,
    lookback: int | None = None,
) -> pd.DataFrame:
    """
    Jádro event-based analýzy.
    Pro každý event typ a horizont spočítá:
    - avg signálu v daném horizontu
    - baseline (avg mimo event dny)
    - delta = avg - baseline
    - N událostí
    """
    # Baseline — průměr celého období
    baseline = {col: module_daily[col].mean() for col in signal_cols if col in module_daily.columns}

    # Index datumů pro efektivní lookup
    module_daily = module_daily.sort_values("date").reset_index(drop=True)
    date_index = {d: i for i, d in enumerate(module_daily["date"])}

    rows = []
    for event_label, group in events_df.groupby("event_label"):
        event_dates = sorted(group["date"].tolist())
        n_events = len(event_dates)

        for horizon in FORWARD_HORIZONS:
            forward_values: dict[str, list] = {col: [] for col in signal_cols if col in module_daily.columns}

            for event_date in event_dates:
                if event_date not in date_index:
                    continue
                idx = date_index[event_date]
                target_idx = idx + horizon
                if target_idx >= len(module_daily):
                    continue
                target_row = module_daily.iloc[target_idx]
                for col in forward_values:
                    val = target_row.get(col)
                    if pd.notna(val):
                        forward_values[col].append(float(val))

            for col in forward_values:
                vals = forward_values[col]
                if not vals:
                    continue
                avg_val  = np.mean(vals)
                base_val = baseline.get(col, np.nan)
                delta    = avg_val - base_val if pd.notna(base_val) else np.nan

                row = {
                    "module":       module_name,
                    "event_label":  event_label,
                    "direction":    group["direction"].iloc[0],
                    "horizon_days": horizon,
                    "signal":       col,
                    "n_events":     n_events,
                    "n_valid":      len(vals),
                    "avg_value":    round(avg_val, 3),
                    "baseline":     round(base_val, 3) if pd.notna(base_val) else None,
                    "delta_vs_baseline": round(delta, 3) if pd.notna(delta) else None,
                    "reliable":     n_events >= MIN_N_RELIABLE,
                }
                if lookback is not None:
                    row["lookback"] = lookback
                rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Cross-correlation
# ---------------------------------------------------------------------------

def _cross_correlation(
    breadth: pd.DataFrame,
    mle_daily: pd.DataFrame,
    ims_daily: pd.DataFrame,
    irc_daily: pd.DataFrame,
) -> pd.DataFrame:
    """
    Spočítá Pearsonovu korelaci breadth signálu vs modulový signál
    pro lag = -20..+20 obchodních dní.

    lag > 0: breadth VEDE modul (breadth se změní dříve)
    lag < 0: modul VEDE breadth
    """
    # Breadth signál: above_ma50_pct a above_ma200_pct
    breadth_sig = breadth[["date", "above_ma50_pct", "above_ma200_pct"]].copy()

    # Připrav modulové signály
    module_signals = []

    # MLE
    mle_m = mle_daily[["date", "mle_top20_ret10d"]].copy()
    mle_m.columns = ["date", "signal"]
    module_signals.append(("mle", "mle_top20_ret10d", mle_m))

    # IMS
    for col in ["ims_elite_count", "ims_total"]:
        ims_m = ims_daily[["date", col]].copy()
        ims_m.columns = ["date", "signal"]
        module_signals.append(("ims", col, ims_m))

    # IRC — každý lookback
    for lb in IRC_LOOKBACKS:
        irc_m = irc_daily[irc_daily["lookback"] == lb][["date", "top7_ret"]].copy()
        irc_m.columns = ["date", "signal"]
        module_signals.append((f"irc_{lb}d", "top7_ret", irc_m))

    rows = []
    for breadth_col in ["above_ma50_pct", "above_ma200_pct"]:
        b = breadth_sig[["date", breadth_col]].dropna().copy()
        b = b.sort_values("date").reset_index(drop=True)

        for module_name, signal_name, module_df in module_signals:
            m = module_df.dropna().sort_values("date").reset_index(drop=True)

            # Merge na společné datumy
            merged = b.merge(m, on="date", how="inner")
            merged.columns = ["date", "breadth", "module_signal"]

            for lag in LAG_RANGE:
                # Posun: kladný lag = breadth(t) vs modul(t+lag)
                # = breadth předbíhá modul o lag dní
                if lag == 0:
                    b_series = merged["breadth"]
                    m_series = merged["module_signal"]
                elif lag > 0:
                    b_series = merged["breadth"].iloc[:-lag].reset_index(drop=True)
                    m_series = merged["module_signal"].iloc[lag:].reset_index(drop=True)
                else:
                    abs_lag = abs(lag)
                    b_series = merged["breadth"].iloc[abs_lag:].reset_index(drop=True)
                    m_series = merged["module_signal"].iloc[:-abs_lag].reset_index(drop=True)

                if len(b_series) < 10:
                    continue

                corr = b_series.corr(m_series)
                rows.append({
                    "breadth_signal": breadth_col,
                    "module":         module_name,
                    "signal":         signal_name,
                    "lag_days":       lag,
                    "lag_meaning":    "breadth_leads" if lag > 0 else ("module_leads" if lag < 0 else "simultaneous"),
                    "correlation":    round(corr, 4) if pd.notna(corr) else None,
                    "n":              len(b_series),
                })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Textový souhrn
# ---------------------------------------------------------------------------

def _write_summary(
    breadth: pd.DataFrame,
    events_df: pd.DataFrame,
    lag_mle: pd.DataFrame,
    lag_ims: pd.DataFrame,
    lag_irc: pd.DataFrame,
    crosscorr: pd.DataFrame,
) -> None:

    sep  = "=" * 60
    line = "-" * 60
    lines = []

    lines += [
        "", sep,
        "  LEAD/LAG AUDIT — VÝSLEDKY",
        f"  Průnik: {INTERSECTION_START} → {INTERSECTION_END}",
        f"  Dní: {len(breadth)}",
        sep, "",
    ]

    # LIMITATIONS
    lines += [
        line,
        "[ LIMITATIONS ]",
        "",
        "  Lead/Lag analýza byla provedena na přibližně 244 obchodních",
        "  dnech (2025-07-09 → 2026-06-26).",
        "",
        "  Historické období obsahuje převážně bull a neutrální tržní",
        "  prostředí. Extrémní RISK_OFF podmínky jsou zastoupeny minimálně.",
        "",
        "  Výsledky deterioračních scénářů (down events) jsou založeny",
        "  na malém počtu významných událostí a je nutné je interpretovat",
        "  s odpovídající opatrností.",
        "",
        f"  Výsledky označené 'reliable=False' mají N < {MIN_N_RELIABLE} událostí",
        "  a jsou pouze orientační.",
        "",
    ]

    # Event counts
    lines += [line, "[ POČTY UDÁLOSTÍ ]", ""]
    event_counts = events_df.groupby("event_label").agg(
        n=("date", "count"),
        direction=("direction", "first"),
    ).reset_index()
    for _, r in event_counts.iterrows():
        reliable = "✓" if r["n"] >= MIN_N_RELIABLE else "! malý vzorek"
        lines.append(f"  {r['event_label']:<20s}  n={r['n']:3d}  {reliable}")
    lines.append("")

    # Event-based: MLE
    lines += [line, "[ EVENT-BASED: BREADTH → MLE (mle_top20_ret10d) ]", ""]
    lines.append("  Baseline (průměr celého období): viz lag_event_mle.csv")
    lines.append("  delta = avg po události - baseline")
    lines.append("")
    _format_event_table(lines, lag_mle, "mle_top20_ret10d", "%", reliable_only=False)

    # Event-based: IMS
    lines += [line, "[ EVENT-BASED: BREADTH → IMS (elite_count) ]", ""]
    _format_event_table(lines, lag_ims, "ims_elite_count", "cnt", reliable_only=False)

    lines += ["", "  IMS total count:", ""]
    _format_event_table(lines, lag_ims, "ims_total", "cnt", reliable_only=False)

    # Event-based: IRC
    lines += [line, "[ EVENT-BASED: BREADTH → IRC (top7_ret, lookback 20D) ]", ""]
    lag_irc_20 = lag_irc[lag_irc["lookback"] == 20]
    _format_event_table(lines, lag_irc_20, "top7_ret", "%", reliable_only=False)

    lines += ["", "  IRC lookback srovnání (horizont +5D, event MA50_5D_dn5):"]
    for lb in IRC_LOOKBACKS:
        sub = lag_irc[
            (lag_irc["lookback"] == lb) &
            (lag_irc["signal"] == "top7_ret") &
            (lag_irc["event_label"] == "MA50_5D_dn5") &
            (lag_irc["horizon_days"] == 5)
        ]
        if sub.empty:
            continue
        r = sub.iloc[0]
        lines.append(
            f"    IRC {lb:2d}D  avg={r['avg_value']:+.2f}%  "
            f"delta={r['delta_vs_baseline']:+.2f}%  "
            f"n={r['n_events']}"
        )
    lines.append("")

    # Cross-correlation — peak lags
    lines += [line, "[ CROSS-CORRELATION — PEAK LAG (breadth vede nebo sleduje?) ]", ""]
    lines.append("  lag > 0: breadth vede modul")
    lines.append("  lag < 0: modul vede breadth")
    lines.append("  Pouze MA50 breadth signál, nejvyšší absolutní korelace:")
    lines.append("")

    cc_ma50 = crosscorr[crosscorr["breadth_signal"] == "above_ma50_pct"]
    for module in cc_ma50["module"].unique():
        sub = cc_ma50[cc_ma50["module"] == module].dropna(subset=["correlation"])
        if sub.empty:
            continue
        peak = sub.loc[sub["correlation"].abs().idxmax()]
        lines.append(
            f"  {module:<15s}  peak_lag={int(peak['lag_days']):+3d}d  "
            f"corr={peak['correlation']:+.3f}  "
            f"({peak['lag_meaning']})"
        )
    lines.append("")
    lines.append("  Plné výsledky viz lag_crosscorr.csv")
    lines.append("")

    lines += [sep, "  Výstupy uloženy do: audit/output/", sep, ""]

    (OUTPUT_DIR / "lag_audit_summary.txt").write_text("\n".join(lines), encoding="utf-8")


def _format_event_table(
    lines: list,
    df: pd.DataFrame,
    signal: str,
    unit: str,
    reliable_only: bool = False,
) -> None:
    """Formátuje event-based výsledky pro daný signál do textové tabulky."""
    sub = df[df["signal"] == signal].copy()
    if reliable_only:
        sub = sub[sub["reliable"] == True]
    if sub.empty:
        lines.append("  (žádná data)")
        return

    for event_label in sorted(sub["event_label"].unique()):
        ev = sub[sub["event_label"] == event_label]
        n = ev["n_events"].iloc[0]
        reliable = "" if ev["reliable"].iloc[0] else " [!]"
        lines.append(f"  {event_label} (n={n}){reliable}:")
        for _, r in ev.sort_values("horizon_days").iterrows():
            delta_str = f"{r['delta_vs_baseline']:+.2f}" if pd.notna(r.get("delta_vs_baseline")) else " N/A"
            lines.append(
                f"    +{int(r['horizon_days']):2d}D  "
                f"avg={r['avg_value']:+7.2f}{unit}  "
                f"delta={delta_str}{unit}  "
                f"n_valid={int(r['n_valid'])}"
            )
        lines.append("")


if __name__ == "__main__":
    main()
