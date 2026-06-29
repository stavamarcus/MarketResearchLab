"""
IMS Audit v5 — MLE Early Leadership Detection
==============================================
C:/Users/stava/Projects/InstitutionalMomentumScanner/audit/run_audit_v5_mle_top80.py

Spuštění:
    conda run -n institutional_momentum_scanner --no-capture-output python audit/run_audit_v5_mle_top80.py

Read-only audit. Nesmí měnit:
    - MLE výpočty, report, archiv
    - IMS výpočty, report
    - MIO report

Vstupní data:
    1. MLE archiv:  MarketLeadershipEngine/output/archive/rank_matrix_archive.csv
    2. MDSM cache:  přes IMS data_loader (AccessLayer)
    3. SPY:         přes IMS data_loader (AccessLayer)

Výstupy:
    output/audit/mle_top80_audit_report_YYYY-MM-DD.txt
    output/audit/mle_top80_audit_summary.csv
    output/audit/mle_top80_signals.csv
    output/audit/mle_band_optimization.csv      (Test E)

Rozšíření — Audit v5 Extension:
    Test E — PRE-LEADER Band Optimization.
    Testuje pásma 51-60 / 51-70 / 51-80 / 51-90 / 51-100.
    Původní Testy A-D jsou beze změny.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

# ── Project root (IMS) ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

AUDIT_DIR    = PROJECT_ROOT / "output" / "audit"
PROJECTS_DIR = PROJECT_ROOT.parent
MLE_ARCHIVE  = PROJECTS_DIR / "MarketLeadershipEngine" / "output" / "archive" / "rank_matrix_archive.csv"

# ── Konstanty ─────────────────────────────────────────────────────────────────
TOP80_LO  = 51
TOP80_HI  = 80
TOP50_THR = 50
TOP20_THR = 20

FORWARD_HORIZONS    = [5, 10, 20, 30]
CONVERSION_HORIZONS = [3, 5, 10, 20, 30, 40]

SEP  = "=" * 70
THIN = "-" * 70


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Načtení MLE archivu
# ═══════════════════════════════════════════════════════════════════════════════

def load_mle_archive(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[CHYBA] MLE archiv nenalezen: {path}")
        sys.exit(1)
    df = pd.read_csv(path, dtype={"date": str})
    df["rank_10d"] = pd.to_numeric(df["rank_10d"], errors="coerce")
    df["rank_20d"] = pd.to_numeric(df["rank_20d"], errors="coerce")
    df = df.sort_values(["date", "ticker"]).reset_index(drop=True)
    print(f"[INFO] MLE archiv: {df['date'].nunique()} trading days, {df['ticker'].nunique()} tickers")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Detekce eventů z MLE archivu
# ═══════════════════════════════════════════════════════════════════════════════

def detect_events(
    archive: pd.DataFrame,
    trading_dates: list[str],
    max_horizon: int,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Detekuje tři skupiny signálů z MLE archivu:
      top80_events: první vstup do pásma rank_10d 51–80
      top50_events: první vstup do rank_10d <= 50
      top20_events: snapshot rank_10d <= 20 (každý den)

    Eventy po cutoff (last_date - max_horizon) jsou přeskočeny
    — nemáme dostatečná forward data.
    """
    pivot = archive.pivot(index="date", columns="ticker", values="rank_10d")
    dates_in_archive = sorted(pivot.index.tolist())

    cutoff_idx = len(trading_dates) - max_horizon - 1
    cutoff = trading_dates[cutoff_idx] if cutoff_idx >= 0 else dates_in_archive[-1]

    top80_events: list[dict] = []
    top50_events: list[dict] = []
    top20_events: list[dict] = []

    for i, d in enumerate(dates_in_archive):
        if d > cutoff:
            continue
        prev_d = dates_in_archive[i - 1] if i > 0 else None

        for ticker in pivot.columns:
            r_today = pivot.loc[d, ticker]
            r_prev  = pivot.loc[prev_d, ticker] if prev_d else np.nan

            if pd.isna(r_today):
                continue
            r_today = int(r_today)

            # TOP20 snapshot
            if r_today <= TOP20_THR:
                top20_events.append({"date": d, "ticker": ticker, "rank_10d": r_today})

            # First entry TOP80 band
            if TOP80_LO <= r_today <= TOP80_HI:
                if pd.isna(r_prev) or int(r_prev) > TOP80_HI:
                    top80_events.append({"date": d, "ticker": ticker, "rank_10d": r_today})

            # First entry TOP50
            if r_today <= TOP50_THR:
                if pd.isna(r_prev) or int(r_prev) > TOP50_THR:
                    top50_events.append({"date": d, "ticker": ticker, "rank_10d": r_today})

    print(
        f"[INFO] Eventy: TOP80_ENTRY={len(top80_events)}, "
        f"TOP50_ENTRY={len(top50_events)}, TOP20_SNAP={len(top20_events)}"
    )
    return top80_events, top50_events, top20_events


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Forward returns — přes IMS data_loader interface
# ═══════════════════════════════════════════════════════════════════════════════

def enrich_events(
    events: list[dict],
    close_map: dict,
    spy_close,
    trading_dates: list[str],
    horizons: list[int],
    label: str,
) -> pd.DataFrame:
    """
    Pro každý event vypočítá forward returns, SPY returns, alpha a drawdown.
    Používá stejnou logiku jako IMS forward_returns.py:
      - entry_price  = close na event_date (nebo nejbližší předchozí)
      - forward_price = close N obchodních dní po event_date
      - drawdown     = (min_close v okně / entry_close - 1) * 100
    """
    from audit.data_loader import get_entry_price, get_forward_price, get_window_low
    SPY = "SPY"

    print(f"[INFO] Enrich {label}: {len(events)} eventů...")
    missing = set()
    rows = []

    spy_map = {SPY: spy_close}

    for ev in events:
        ticker     = ev["ticker"]
        entry_date_raw = ev["date"]
        # date může být str nebo date objekt
        if isinstance(entry_date_raw, str):
            entry_date = date.fromisoformat(entry_date_raw)
        else:
            entry_date = entry_date_raw

        entry_price = get_entry_price(close_map, ticker, entry_date)
        spy_entry   = get_entry_price(spy_map, SPY, entry_date)

        if entry_price is None or entry_price <= 0:
            missing.add(ticker)
            continue
        if spy_entry is None or spy_entry <= 0:
            continue

        row = {
            "ticker":      ticker,
            "date":        str(entry_date),
            "rank_10d":    ev["rank_10d"],
        }

        for h in horizons:
            fwd_price = get_forward_price(close_map, ticker, entry_date, h)
            spy_price = get_forward_price(spy_map, SPY, entry_date, h)
            low_price = get_window_low(close_map, ticker, entry_date, h)

            if fwd_price and spy_price and low_price:
                ret   = round((fwd_price / entry_price - 1) * 100, 4)
                spy_r = round((spy_price / spy_entry - 1) * 100, 4)
                alpha = round(ret - spy_r, 4)
                dd    = round((low_price / entry_price - 1) * 100, 4)
            else:
                ret = spy_r = alpha = dd = None

            row[f"ret_{h}d"]   = ret
            row[f"spy_{h}d"]   = spy_r
            row[f"alpha_{h}d"] = alpha
            row[f"dd_{h}d"]    = dd

        rows.append(row)

    if missing:
        print(f"[WARN] {label}: {len(missing)} tickerů bez cache dat")

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Statistiky (Test A + B)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_stats(df: pd.DataFrame, horizons: list[int]) -> dict:
    stats = {}
    for h in horizons:
        ret   = df[f"ret_{h}d"].dropna()   if f"ret_{h}d"   in df.columns else pd.Series(dtype=float)
        dd    = df[f"dd_{h}d"].dropna()    if f"dd_{h}d"    in df.columns else pd.Series(dtype=float)
        alpha = df[f"alpha_{h}d"].dropna() if f"alpha_{h}d" in df.columns else pd.Series(dtype=float)
        n = len(ret)
        stats[h] = {
            "n":              n,
            "avg_ret":        round(ret.mean(),    3) if n > 0 else None,
            "median_ret":     round(ret.median(),  3) if n > 0 else None,
            "win_rate":       round((ret > 0).mean() * 100, 1) if n > 0 else None,
            "avg_dd":         round(dd.mean(),     3) if len(dd) > 0 else None,
            "median_dd":      round(dd.median(),   3) if len(dd) > 0 else None,
            "avg_alpha":      round(alpha.mean(),  3) if len(alpha) > 0 else None,
            "median_alpha":   round(alpha.median(),3) if len(alpha) > 0 else None,
            "alpha_win_rate": round((alpha > 0).mean() * 100, 1) if len(alpha) > 0 else None,
        }
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Test C — Conversion to TOP50
# ═══════════════════════════════════════════════════════════════════════════════

def compute_conversion(
    top80_events: list[dict],
    archive: pd.DataFrame,
    trading_dates: list[str],
    horizons: list[int],
) -> dict:
    pivot = archive.pivot(index="date", columns="ticker", values="rank_10d")
    results = {}

    for h in horizons:
        n_conv = 0
        n_fail = 0
        days_list = []

        for ev in top80_events:
            ticker = ev["ticker"]
            entry  = ev["date"] if isinstance(ev["date"], str) else str(ev["date"])

            if entry not in trading_dates:
                continue
            start_idx = trading_dates.index(entry)
            end_idx   = min(start_idx + h, len(trading_dates) - 1)

            found = False
            for j in range(start_idx + 1, end_idx + 1):
                d = trading_dates[j]
                if d not in pivot.index:
                    continue
                r = pivot.loc[d, ticker] if ticker in pivot.columns else np.nan
                if pd.isna(r):
                    continue
                if int(r) <= TOP50_THR:
                    n_conv += 1
                    days_list.append(j - start_idx)
                    found = True
                    break
            if not found:
                n_fail += 1

        n_total = n_conv + n_fail
        days_s  = pd.Series(days_list, dtype=float)
        results[h] = {
            "n_total":         n_total,
            "n_converted":     n_conv,
            "conversion_rate": round(n_conv / n_total * 100, 1) if n_total > 0 else None,
            "failure_rate":    round(n_fail / n_total * 100, 1) if n_total > 0 else None,
            "avg_days":        round(days_s.mean(),   1) if len(days_s) > 0 else None,
            "median_days":     round(days_s.median(), 1) if len(days_s) > 0 else None,
        }
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Test D — Entry Advantage
# ═══════════════════════════════════════════════════════════════════════════════

def compute_entry_advantage(
    top80_events: list[dict],
    archive: pd.DataFrame,
    close_map: dict,
    spy_close,
    trading_dates: list[str],
    horizons: list[int],
) -> dict:
    """
    Pro tickery které vstoupily do TOP80 a poté do TOP50:
    porovnej return od vstupu do TOP80 vs od vstupu do TOP50.
    Advantage = ret_from_top80_entry - ret_from_top50_entry (kladné = dřívější entry lepší)
    """
    from audit.data_loader import get_entry_price, get_forward_price

    pivot = archive.pivot(index="date", columns="ticker", values="rank_10d")
    SPY = "SPY"
    spy_map = {SPY: spy_close}

    results = {}
    for h in horizons:
        advantages = []
        n_pairs = 0

        for ev80 in top80_events:
            ticker = ev80["ticker"]
            entry80 = ev80["date"] if isinstance(ev80["date"], str) else str(ev80["date"])

            if entry80 not in trading_dates:
                continue
            idx80 = trading_dates.index(entry80)

            # Najdi první vstup do TOP50 po entry80 (max 30D)
            entry50 = None
            for j in range(idx80 + 1, min(idx80 + 31, len(trading_dates))):
                d = trading_dates[j]
                if d not in pivot.index:
                    continue
                r = pivot.loc[d, ticker] if ticker in pivot.columns else np.nan
                if pd.isna(r):
                    continue
                if int(r) <= TOP50_THR:
                    entry50 = d
                    break

            if entry50 is None:
                continue

            idx50 = trading_dates.index(entry50)
            if idx50 + h >= len(trading_dates) or idx80 + h >= len(trading_dates):
                continue

            entry80_date = date.fromisoformat(entry80)
            entry50_date = date.fromisoformat(entry50)

            p80_entry = get_entry_price(close_map, ticker, entry80_date)
            p50_entry = get_entry_price(close_map, ticker, entry50_date)
            p80_fwd   = get_forward_price(close_map, ticker, entry80_date, h)
            p50_fwd   = get_forward_price(close_map, ticker, entry50_date, h)

            if None in (p80_entry, p50_entry, p80_fwd, p50_fwd):
                continue
            if p80_entry <= 0 or p50_entry <= 0:
                continue

            ret80 = (p80_fwd / p80_entry - 1) * 100
            ret50 = (p50_fwd / p50_entry - 1) * 100
            advantages.append(ret80 - ret50)
            n_pairs += 1

        adv = pd.Series(advantages, dtype=float)
        results[h] = {
            "n_pairs":           n_pairs,
            "avg_advantage":     round(adv.mean(),   3) if len(adv) > 0 else None,
            "median_advantage":  round(adv.median(), 3) if len(adv) > 0 else None,
            "win_rate":          round((adv > 0).mean() * 100, 1) if len(adv) > 0 else None,
        }
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 6b. Test E — PRE-LEADER Band Optimization
# ═══════════════════════════════════════════════════════════════════════════════

# Varianty testovaných pásem: (label, lo, hi)
PRE_LEADER_BANDS = [
    ("51-60",  51,  60),
    ("51-70",  51,  70),
    ("51-80",  51,  80),   # původní Audit v5
    ("51-90",  51,  90),
    ("51-100", 51, 100),
]


def detect_band_events(
    archive: pd.DataFrame,
    trading_dates: list[str],
    lo: int,
    hi: int,
    max_horizon: int,
) -> list[dict]:
    """
    Detekuje First Entry eventy pro zadané pásmo [lo, hi].
    Podmínka: rank_10d dnes v [lo, hi] A předchozí den > hi (nebo chybí).
    Eventy po cutoff jsou přeskočeny.
    """
    pivot = archive.pivot(index="date", columns="ticker", values="rank_10d")
    dates_in_archive = sorted(pivot.index.tolist())

    cutoff_idx = len(trading_dates) - max_horizon - 1
    cutoff = trading_dates[cutoff_idx] if cutoff_idx >= 0 else dates_in_archive[-1]

    events: list[dict] = []
    for i, d in enumerate(dates_in_archive):
        if d > cutoff:
            continue
        prev_d = dates_in_archive[i - 1] if i > 0 else None

        for ticker in pivot.columns:
            r_today = pivot.loc[d, ticker]
            r_prev  = pivot.loc[prev_d, ticker] if prev_d else np.nan

            if pd.isna(r_today):
                continue
            r_today = int(r_today)

            if lo <= r_today <= hi:
                if pd.isna(r_prev) or int(r_prev) > hi:
                    events.append({"date": d, "ticker": ticker, "rank_10d": r_today})

    return events


def run_test_e(
    archive: pd.DataFrame,
    trading_dates: list[str],
    close_map: dict,
    spy_close,
    top50_events: list[dict],
) -> list[dict]:
    """
    Test E — PRE-LEADER Band Optimization.

    Pro každé pásmo spočítá:
      - forward returns (5D/10D/20D/30D) + alpha + drawdown
      - conversion to TOP50 (3D/5D/10D/20D)
      - entry advantage vs TOP50

    Vrátí list[dict] — jeden dict per pásmo, obsahuje všechny metriky.
    """
    results = []

    for label, lo, hi in PRE_LEADER_BANDS:
        print(f"[TEST E] Pásmo {label} ({lo}–{hi})...")

        # Detekuj eventy pro toto pásmo
        band_events = detect_band_events(archive, trading_dates, lo, hi, max_horizon=40)
        print(f"         Eventy: {len(band_events)}")

        # Forward returns
        df_band = enrich_events(
            band_events, close_map, spy_close, trading_dates, FORWARD_HORIZONS, label
        )
        stats = compute_stats(df_band, FORWARD_HORIZONS)

        # Conversion to TOP50
        conv = compute_conversion(band_events, archive, trading_dates, CONVERSION_HORIZONS)

        # Entry advantage
        adv = compute_entry_advantage(
            band_events, archive, close_map, spy_close, trading_dates, FORWARD_HORIZONS
        )

        results.append({
            "label":      label,
            "lo":         lo,
            "hi":         hi,
            "n_events":   len(band_events),
            "stats":      stats,
            "conv":       conv,
            "advantage":  adv,
        })

    return results


def build_band_comparison_csv(band_results: list[dict]) -> pd.DataFrame:
    """Sestaví summary CSV pro Test E."""
    records = []
    for b in band_results:
        s30  = b["stats"].get(30, {})
        s10  = b["stats"].get(10, {})
        c20  = b["conv"].get(20, {})
        c10  = b["conv"].get(10, {})
        a30  = b["advantage"].get(30, {})
        a10  = b["advantage"].get(10, {})
        records.append({
            "band":              b["label"],
            "n_events":          b["n_events"],
            "ret_30d_avg":       s30.get("avg_ret"),
            "ret_30d_median":    s30.get("median_ret"),
            "win_rate_30d":      s30.get("win_rate"),
            "alpha_30d_avg":     s30.get("avg_alpha"),
            "alpha_wr_30d":      s30.get("alpha_win_rate"),
            "ret_10d_avg":       s10.get("avg_ret"),
            "win_rate_10d":      s10.get("win_rate"),
            "alpha_10d_avg":     s10.get("avg_alpha"),
            "conv_rate_10d":     c10.get("conversion_rate"),
            "conv_rate_20d":     c20.get("conversion_rate"),
            "avg_days_to_top50": c10.get("avg_days"),
            "adv_30d_avg":       a30.get("avg_advantage"),
            "adv_30d_wr":        a30.get("win_rate"),
            "adv_10d_avg":       a10.get("avg_advantage"),
            "adv_10d_wr":        a10.get("win_rate"),
        })
    return pd.DataFrame(records)


def build_test_e_report(band_results: list[dict], spy_available: bool) -> list[str]:
    """Sestaví sekci Test E pro textový report."""
    L = []

    L += [
        "", SEP,
        "  TEST E — PRE-LEADER BAND OPTIMIZATION".center(70),
        THIN,
        "  Testovaná pásma: 51-60 / 51-70 / 51-80 / 51-90 / 51-100",
        "  Definice: First Entry — ticker vstoupí do pásma z hodnoty > hi.",
        "",
    ]

    # ── Forward Returns per pásmo ─────────────────────────────────────────────
    L += ["  E.1 FORWARD RETURNS", THIN,
          f"  {'Band':<8} {'H':>4} {'N':>5} {'Avg%':>7} {'Med%':>7} {'WR%':>6} {'AvgDD%':>8}",
          f"  {'-'*50}"]

    for b in band_results:
        first = True
        for h in FORWARD_HORIZONS:
            s = b["stats"].get(h, {})
            band_lbl = b["label"] if first else ""
            L.append(
                f"  {band_lbl:<8} {h:>3}D {_n(s.get('n')):>5} "
                f"{_f(s.get('avg_ret')):>7} {_f(s.get('median_ret')):>7} "
                f"{_pct(s.get('win_rate')):>6} {_f(s.get('avg_dd')):>8}"
            )
            first = False
        L.append("")

    # ── Alpha per pásmo ───────────────────────────────────────────────────────
    if spy_available:
        L += ["  E.2 ALPHA vs SPY", THIN,
              f"  {'Band':<8} {'H':>4} {'AvgAlpha%':>10} {'MedAlpha%':>11} {'AlphaWR%':>9}",
              f"  {'-'*47}"]
        for b in band_results:
            first = True
            for h in FORWARD_HORIZONS:
                s = b["stats"].get(h, {})
                band_lbl = b["label"] if first else ""
                L.append(
                    f"  {band_lbl:<8} {h:>3}D "
                    f"{_f(s.get('avg_alpha')):>10} "
                    f"{_f(s.get('median_alpha')):>11} "
                    f"{_pct(s.get('alpha_win_rate')):>9}"
                )
                first = False
            L.append("")

    # ── Conversion per pásmo ──────────────────────────────────────────────────
    L += ["  E.3 CONVERSION → TOP50", THIN,
          f"  {'Band':<8} {'H':>4} {'ConvRate':>9} {'FailRate':>9} {'AvgDays':>8} {'MedDays':>8}",
          f"  {'-'*52}"]
    for b in band_results:
        first = True
        for h in CONVERSION_HORIZONS:
            c = b["conv"].get(h, {})
            band_lbl = b["label"] if first else ""
            L.append(
                f"  {band_lbl:<8} {h:>3}D "
                f"{_pct(c.get('conversion_rate')):>9} "
                f"{_pct(c.get('failure_rate')):>9} "
                f"{_f(c.get('avg_days'), '.1f'):>8} "
                f"{_f(c.get('median_days'), '.1f'):>8}"
            )
            first = False
        L.append("")

    # ── Entry Advantage per pásmo ─────────────────────────────────────────────
    L += ["  E.4 ENTRY ADVANTAGE (vs čekání na TOP50)", THIN,
          f"  {'Band':<8} {'H':>4} {'N_pairs':>8} {'AvgAdv%':>9} {'MedAdv%':>9} {'WR%':>7}",
          f"  {'-'*50}"]
    for b in band_results:
        first = True
        for h in FORWARD_HORIZONS:
            a = b["advantage"].get(h, {})
            band_lbl = b["label"] if first else ""
            L.append(
                f"  {band_lbl:<8} {h:>3}D "
                f"{_n(a.get('n_pairs')):>8} "
                f"{_f(a.get('avg_advantage')):>9} "
                f"{_f(a.get('median_advantage')):>9} "
                f"{_pct(a.get('win_rate')):>7}"
            )
            first = False
        L.append("")

    # ── Souhrnná tabulka ──────────────────────────────────────────────────────
    L += [
        SEP,
        "  PRE-LEADER BAND COMPARISON (souhrnná tabulka)".center(70),
        THIN,
        f"  {'Band':<8} {'N':>5} {'30D Avg%':>9} {'30D Alpha':>10} {'30D WR%':>8} "
        f"{'Conv20D':>8} {'Adv30D%':>8} {'AAdvWR':>7}  Verdict",
        f"  {'-'*82}",
    ]

    for b in band_results:
        s30 = b["stats"].get(30, {})
        c20 = b["conv"].get(20, {})
        a30 = b["advantage"].get(30, {})

        avg_r  = s30.get("avg_ret")
        wr_r   = s30.get("win_rate")
        alpha  = s30.get("avg_alpha")
        aw_r   = s30.get("alpha_win_rate")
        conv20 = c20.get("conversion_rate")
        adv30  = a30.get("avg_advantage")
        adv_wr = a30.get("win_rate")

        # Verdict — ordinální hodnocení, ne binární počítání
        # Kritéria rozlišující pásma:
        #   standalone edge (avg_ret 30D + WR)
        #   conversion 30D (ne 20D — dle Conversion Horizon Analysis)
        #   entry advantage 30D
        #   alpha 30D (záporná u všech, ale méně záporná = lepší)
        conv30 = b["conv"].get(30, {}).get("conversion_rate") or 0

        # Skóre pro ordinální řazení (vyšší = lepší)
        score = (
            (avg_r  or 0) * 1.5 +   # standalone return (váha 1.5)
            (wr_r   or 0) * 0.5 +   # win rate
            conv30         * 0.3 +   # conversion 30D
            (adv30  or 0) * 2.0 +   # entry advantage (nejdůležitější pro praxi)
            (adv_wr or 0) * 0.5 +   # advantage win rate
            (alpha  or 0) * 1.0      # alpha (záporná u všech, ale penalizuje)
        )
        b["_score"] = score  # uložíme pro ordinální řazení

    # Přiřaď verdikty ordinálně podle skóre
    sorted_by_score = sorted(band_results, key=lambda b: b.get("_score", 0), reverse=True)
    verdict_map = {}
    for rank_i, b in enumerate(sorted_by_score):
        if rank_i == 0:
            verdict_map[b["label"]] = "BEST"
        elif rank_i == 1:
            verdict_map[b["label"]] = "STRONG"
        elif rank_i == 2:
            verdict_map[b["label"]] = "GOOD"
        else:
            verdict_map[b["label"]] = "WEAK"

    # Sestavení tabulky v původním pořadí pásem
    for b in band_results:
        s30  = b["stats"].get(30, {})
        c20  = b["conv"].get(20, {})
        a30  = b["advantage"].get(30, {})
        avg_r  = s30.get("avg_ret")
        alpha  = s30.get("avg_alpha")
        wr_r   = s30.get("win_rate")
        conv20 = c20.get("conversion_rate")
        adv30  = a30.get("avg_advantage")
        adv_wr = a30.get("win_rate")
        verdict = verdict_map.get(b["label"], "—")

        L.append(
            f"  {b['label']:<8} {b['n_events']:>5} "
            f"{_f(avg_r):>9} "
            f"{_f(alpha):>10} "
            f"{_pct(wr_r):>8} "
            f"{_pct(conv20):>8} "
            f"{_f(adv30):>8} "
            f"{_pct(adv_wr):>7}  {verdict}"
        )

    L.append("")

    # ── Interpretace Test E ───────────────────────────────────────────────────
    L += [SEP, "  TEST E — INTERPRETACE", THIN, ""]

    # Najdi nejlepší pásmo per kritérium
    def _best(key_fn, band_results):
        valid = [(b["label"], key_fn(b)) for b in band_results if key_fn(b) is not None]
        if not valid:
            return "N/A", None
        return max(valid, key=lambda x: x[1])

    best_edge_lbl,  best_edge_v  = _best(lambda b: b["stats"].get(30, {}).get("avg_ret"),       band_results)
    best_wr_lbl,    best_wr_v    = _best(lambda b: b["stats"].get(30, {}).get("win_rate"),       band_results)
    best_conv_lbl,  best_conv_v  = _best(lambda b: b["conv"].get(20, {}).get("conversion_rate"), band_results)
    best_adv_lbl,   best_adv_v   = _best(lambda b: b["advantage"].get(30, {}).get("avg_advantage"), band_results)
    best_alpha_lbl, best_alpha_v = _best(lambda b: b["stats"].get(30, {}).get("avg_alpha"),      band_results)

    # Q1 — nejlepší standalone edge
    q1 = (f"Pásmo {best_edge_lbl} (30D avg={_f(best_edge_v)}%, WR={_pct(best_wr_v)}). "
          f"Pozor: širší pásmo = více eventů = regrese k průměru.")

    # Q2 — nejlepší conversion
    q2 = f"Pásmo {best_conv_lbl} (20D conversion rate={_pct(best_conv_v)})."

    # Q3 — největší entry advantage
    q3 = f"Pásmo {best_adv_lbl} (30D avg advantage={_f(best_adv_v)}%)."

    # Q4 — nejlepší kompromis
    # Skóre: normalizuj každé kritérium (0-1) a zprůměruj
    def _score(b):
        s30  = b["stats"].get(30, {})
        c20  = b["conv"].get(20, {})
        a30  = b["advantage"].get(30, {})
        vals = [
            s30.get("avg_ret")          or 0,
            s30.get("win_rate")         or 0,
            s30.get("avg_alpha")        or 0,
            c20.get("conversion_rate")  or 0,
            a30.get("avg_advantage")    or 0,
            a30.get("win_rate")         or 0,
        ]
        return sum(vals)

    scored = sorted(band_results, key=_score, reverse=True)
    best_compromise = scored[0]["label"]
    second = scored[1]["label"] if len(scored) > 1 else "N/A"
    q4 = (f"Pásmo {best_compromise} — nejlepší součet skóre across all criteria. "
          f"Druhé v pořadí: {second}.")

    # Q5 — doporučení pro architekta
    q5 = (f"Pokud by se implementovala sekce MLE PRE-LEADERS, audit doporučuje "
          f"pásmo {best_compromise}. "
          f"Důvod: nejlepší kompromis mezi počtem signálů, standalone edge, "
          f"conversion rate a entry advantage.")

    L += [
        f"  1. Které pásmo má nejlepší standalone edge?",
        f"     {q1}", "",
        f"  2. Které pásmo má nejlepší conversion do TOP50?",
        f"     {q2}", "",
        f"  3. Které pásmo poskytuje největší entry advantage?",
        f"     {q3}", "",
        f"  4. Nejlepší kompromis (N / kvalita / časnost)?",
        f"     {q4}", "",
        f"  5. Doporučení pro architekta:",
        f"     {q5}",
        "", SEP, "",
    ]

    return L


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Summary CSV
# ═══════════════════════════════════════════════════════════════════════════════

def build_summary_csv(
    stats80: dict, stats50: dict, stats20: dict,
    conv: dict, advantage: dict,
    horizons: list[int], conv_horizons: list[int],
) -> pd.DataFrame:
    records = []

    for label, st in [("TOP80_ENTRY", stats80), ("TOP50_ENTRY", stats50), ("TOP20_SNAPSHOT", stats20)]:
        for h in horizons:
            s = st.get(h, {})
            records.append({"group": label, "horizon": h, **s})

    for h in conv_horizons:
        c = conv.get(h, {})
        records.append({"group": "CONVERSION", "horizon": h, **c})

    for h in horizons:
        a = advantage.get(h, {})
        records.append({"group": "ENTRY_ADVANTAGE", "horizon": h, **a})

    return pd.DataFrame(records)


def _build_conversion_horizon_analysis(
    cr_vals: dict,
    c10: dict, c20: dict, c30: dict, c40: dict,
) -> list[str]:
    """
    Sestaví sekci Conversion Horizon Analysis — analýza křivky konverze.

    Odpovídá na otázky:
      1. Při jakém horizontu se conversion rate prakticky stabilizuje?
      2. Má smysl používat 20D / 30D / jiný horizont pro produkční report?
      3. Doporučení jednoho horizontu.
    """
    L = [
        SEP,
        "  CONVERSION HORIZON ANALYSIS".center(70),
        THIN,
        "",
        "  Konverzní křivka — jak rychle PRE-LEADERS vstupují do TOP50:",
        "",
        f"  {'Horizon':>8}  {'ConvRate':>9}  {'Delta vs prev':>14}  {'AvgDays':>8}",
        f"  {'-'*45}",
    ]

    horizons_ordered = [3, 5, 10, 20, 30, 40]
    prev_cr = None
    stable_horizon = None  # první horizont kde delta < 3 pp

    conv_lookup = {
        3: c10.get("conversion_rate") if False else cr_vals.get(3),  # použij cr_vals
        5: cr_vals.get(5),
        10: cr_vals.get(10),
        20: cr_vals.get(20),
        30: cr_vals.get(30),
        40: cr_vals.get(40),
    }
    avg_days_lookup = {
        10: c10.get("avg_days"),
        20: c20.get("avg_days"),
        30: c30.get("avg_days"),
        40: c40.get("avg_days"),
    }

    for h in horizons_ordered:
        cr = conv_lookup.get(h)
        avg_d = avg_days_lookup.get(h)

        if cr is not None and prev_cr is not None:
            delta = cr - prev_cr
            delta_str = f"{delta:+.1f} pp"
            if stable_horizon is None and delta < 3.0:
                stable_horizon = h
        elif prev_cr is None:
            delta_str = "  —"
        else:
            delta_str = "  N/A"

        avg_d_str = _f(avg_d, ".1f") if avg_d is not None else "  N/A"

        L.append(
            f"  {str(h)+'D':>8}  {_pct(cr):>9}  {delta_str:>14}  {avg_d_str:>8}"
        )
        if cr is not None:
            prev_cr = cr

    L.append("")

    # ── Interpretace ─────────────────────────────────────────────────────────
    L += ["  INTERPRETACE — CONVERSION HORIZON", THIN, ""]

    # Q1 — stabilizace
    cr20 = conv_lookup.get(20)
    cr30 = conv_lookup.get(30)
    cr40 = conv_lookup.get(40)

    if stable_horizon is not None:
        q1 = (f"Křivka se začíná stabilizovat při {stable_horizon}D "
              f"(přírůstek < 3 pp oproti předchozímu horizontu).")
    elif cr30 is not None and cr20 is not None and (cr30 - cr20) < 3:
        q1 = "Křivka se stabilizuje mezi 20D a 30D."
        stable_horizon = 30
    else:
        q1 = "Křivka nezaznamenala zřejmou stabilizaci v testovaném rozsahu (3–40D)."

    # Q2 — srovnání 20D / 30D / jiný
    if cr20 is not None and cr30 is not None and cr40 is not None:
        delta_20_30 = cr30 - cr20
        delta_30_40 = cr40 - cr30
        if delta_20_30 >= 3 and delta_30_40 < 3:
            q2 = (f"30D je přirozenější hranice: přírůstek 20D→30D je {delta_20_30:.1f} pp, "
                  f"ale 30D→40D pouze {delta_30_40:.1f} pp. "
                  f"20D podhodnocuje skutečnou konverzi.")
        elif delta_20_30 < 3:
            q2 = (f"20D je dostatečný: přírůstek 20D→30D je pouze {delta_20_30:.1f} pp. "
                  f"Vyšší horizonty nepřidávají podstatnou informaci.")
        else:
            q2 = (f"Přírůstky jsou stále významné i při 30D→40D ({delta_30_40:.1f} pp). "
                  f"Křivka se nestabilizovala — zvažte 40D jako referenční horizont.")
    else:
        q2 = "Nelze vyhodnotit — chybí data pro 20D, 30D nebo 40D."

    # Q3 — doporučení jednoho horizontu
    if stable_horizon == 20:
        rec_h = 20
        rec_reason = (f"20D je dostatečný — křivka se stabilizuje před tímto horizontem. "
                      f"Conversion rate {_pct(cr20)} zachycuje podstatnou část konverzí.")
    elif stable_horizon == 30 or (cr20 is not None and cr30 is not None and (cr30 - cr20) >= 3):
        rec_h = 30
        rec_reason = (f"30D lépe zachycuje skutečnou konverzi než 20D "
                      f"(+{_f(cr30 - cr20 if cr30 and cr20 else None, '.1f')} pp) "
                      f"a zároveň je dostatečně blízko k obchodnímu horizontu swing tradingu. "
                      f"Doporučená formulace: \"Reached TOP50 within 30 trading days\".")
    else:
        rec_h = 20
        rec_reason = "Data neukázala jasný důvod pro změnu oproti 20D. Ponechat 20D."

    L += [
        f"  1. Při jakém horizontu se conversion rate prakticky stabilizuje?",
        f"     {q1}", "",
        f"  2. Má smysl používat 20D / 30D / jiný horizont?",
        f"     {q2}", "",
        f"  3. Doporučení pro produkční report:",
        f"     Doporučený horizont: {rec_h}D",
        f"     Důvod: {rec_reason}",
        "", SEP, "",
    ]

    return L


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Report
# ═══════════════════════════════════════════════════════════════════════════════

def _f(v, fmt=".2f", suf="") -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "  N/A"
    return f"{v:{fmt}}{suf}"

def _pct(v) -> str: return _f(v, ".1f", "%")
def _n(v)   -> str: return _f(v, ".0f") if v is not None else "  N/A"


def build_report(
    run_date: str,
    archive_range: tuple[str, str],
    trading_days: int,
    n_top80: int, n_top50: int, n_top20: int,
    stats80: dict, stats50: dict, stats20: dict,
    conv: dict, advantage: dict,
    horizons: list[int], conv_horizons: list[int],
    spy_available: bool,
    test_e_lines: list[str] | None = None,
) -> list[str]:
    L = []

    L += [
        "", SEP,
        "  MLE AUDIT v5 — EARLY LEADERSHIP DETECTION".center(70),
        f"  Run date: {run_date}".center(70),
        SEP,
        f"  Archive : {archive_range[0]} → {archive_range[1]}  ({trading_days} trading days)",
        f"  Eventy  : TOP80_ENTRY={n_top80}  TOP50_ENTRY={n_top50}  TOP20_SNAP={n_top20}",
        f"  SPY alpha: {'ANO' if spy_available else 'NE (SPY nedostupný)'}",
        THIN,
    ]

    # ── Test A ────────────────────────────────────────────────────────────────
    L += ["", "  TEST A — FORWARD RETURNS", THIN,
          f"  {'H':>4} {'Group':<20} {'N':>5} {'Avg%':>7} {'Med%':>7} {'WR%':>6} {'AvgDD%':>8} {'MedDD%':>8}",
          f"  {'-'*65}"]

    groups = [("TOP80 ENTRY", stats80), ("TOP50 ENTRY", stats50), ("TOP20 SNAP", stats20)]
    for h in horizons:
        for label, st in groups:
            s = st.get(h, {})
            L.append(
                f"  {h:>3}D {label:<20} {_n(s.get('n')):>5} "
                f"{_f(s.get('avg_ret')):>7} {_f(s.get('median_ret')):>7} "
                f"{_pct(s.get('win_rate')):>6} "
                f"{_f(s.get('avg_dd')):>8} {_f(s.get('median_dd')):>8}"
            )
        L.append("")

    # ── Test B ────────────────────────────────────────────────────────────────
    L += ["  TEST B — ALPHA vs SPY", THIN]
    if not spy_available:
        L.append("  N/A — SPY data nedostupná.")
    else:
        L += [f"  {'H':>4} {'Group':<20} {'AvgAlpha%':>10} {'MedAlpha%':>11} {'AlphaWR%':>9}",
              f"  {'-'*58}"]
        for h in horizons:
            for label, st in groups:
                s = st.get(h, {})
                L.append(
                    f"  {h:>3}D {label:<20} "
                    f"{_f(s.get('avg_alpha')):>10} "
                    f"{_f(s.get('median_alpha')):>11} "
                    f"{_pct(s.get('alpha_win_rate')):>9}"
                )
            L.append("")

    # ── Test C ────────────────────────────────────────────────────────────────
    L += ["  TEST C — CONVERSION TOP80 → TOP50", THIN,
          f"  {'H':>4} {'N_total':>8} {'Conv':>7} {'ConvRate':>9} {'FailRate':>9} {'AvgD':>6} {'MedD':>6}",
          f"  {'-'*60}"]
    for h in conv_horizons:
        c = conv.get(h, {})
        L.append(
            f"  {h:>3}D {_n(c.get('n_total')):>8} "
            f"{_n(c.get('n_converted')):>7} "
            f"{_pct(c.get('conversion_rate')):>9} "
            f"{_pct(c.get('failure_rate')):>9} "
            f"{_f(c.get('avg_days'), '.1f'):>6} "
            f"{_f(c.get('median_days'), '.1f'):>6}"
        )
    L.append("")

    # ── Test D ────────────────────────────────────────────────────────────────
    L += ["  TEST D — ENTRY ADVANTAGE (TOP80 vs TOP50 start)", THIN,
          f"  {'H':>4} {'N_pairs':>8} {'AvgAdv%':>9} {'MedAdv%':>9} {'WR%':>7}",
          f"  {'-'*45}"]
    for h in horizons:
        a = advantage.get(h, {})
        L.append(
            f"  {h:>3}D {_n(a.get('n_pairs')):>8} "
            f"{_f(a.get('avg_advantage')):>9} "
            f"{_f(a.get('median_advantage')):>9} "
            f"{_pct(a.get('win_rate')):>7}"
        )
    L.append("")

    # ── Interpretace ──────────────────────────────────────────────────────────
    L += [SEP, "  INTERPRETACE", THIN, ""]

    s80_30 = stats80.get(30, {})
    s50_30 = stats50.get(30, {})
    c10    = conv.get(10, {})
    c20    = conv.get(20, {})
    a10    = advantage.get(10, {})
    a30    = advantage.get(30, {})

    # Q1
    avg80 = s80_30.get("avg_ret"); wr80 = s80_30.get("win_rate")
    if avg80 is not None and wr80 is not None:
        if avg80 > 0 and wr80 > 55:   q1 = f"POZITIVNÍ EDGE  (avg={avg80:.2f}%, WR={wr80:.1f}%)"
        elif avg80 > 0 and wr80 >= 50: q1 = f"SLABÝ EDGE  (avg={avg80:.2f}%, WR={wr80:.1f}%)"
        else:                           q1 = f"BEZ EDGE  (avg={avg80:.2f}%, WR={wr80:.1f}%)"
    else:
        q1 = "chybí data (forward returns nedostupné — zkontroluj MDSM cache)"

    # Q2
    avg50 = s50_30.get("avg_ret"); wr50 = s50_30.get("win_rate")
    if avg80 is not None and avg50 is not None:
        diff = avg80 - avg50
        if diff > 0.5 and (wr80 or 0) > (wr50 or 0):
            q2 = f"ANO — TOP80 lepší o {diff:.2f}% avg 30D return"
        elif diff < -0.5:
            q2 = f"NE — TOP50 lepší o {abs(diff):.2f}% avg 30D return"
        else:
            q2 = f"NEPRŮKAZNÉ — rozdíl {diff:+.2f}% (TOP80 vs TOP50 avg 30D)"
    else:
        q2 = "nelze vyhodnotit"

    # Q3 — konverzní křivka
    c3   = conv.get(3,  {})
    c5   = conv.get(5,  {})
    c10  = conv.get(10, {})
    c20  = conv.get(20, {})
    c30  = conv.get(30, {})
    c40  = conv.get(40, {})

    cr_vals = {
        3:  c3.get("conversion_rate"),
        5:  c5.get("conversion_rate"),
        10: c10.get("conversion_rate"),
        20: c20.get("conversion_rate"),
        30: c30.get("conversion_rate"),
        40: c40.get("conversion_rate"),
    }
    q3 = "  ".join(f"{h}D:{_pct(v)}" for h, v in cr_vals.items())

    # Q4 — avg days
    q4 = (f"10D horizon: avg={_f(c10.get('avg_days'),'.1f')} dní, "
          f"median={_f(c10.get('median_days'),'.1f')} dní  |  "
          f"20D horizon: avg={_f(c20.get('avg_days'),'.1f')} dní  |  "
          f"30D horizon: avg={_f(c30.get('avg_days'),'.1f')} dní")

    # Q5
    av10 = a10.get('avg_advantage'); wr_a10 = a10.get('win_rate')
    av30 = a30.get('avg_advantage'); wr_a30 = a30.get('win_rate')
    q5 = (f"10D: avg advantage={_f(av10)}%, WR={_pct(wr_a10)}, N={_n(a10.get('n_pairs'))}  |  "
          f"30D: avg advantage={_f(av30)}%, WR={_pct(wr_a30)}, N={_n(a30.get('n_pairs'))}")

    # Q6 — kritéria
    cr10 = c10.get("conversion_rate")
    edge_ok = (avg80 or 0) > 0 and (wr80 or 0) > 50
    conv_ok = (cr10 or 0) > 40
    adv_ok  = (av10 or 0) > 0
    met = sum([edge_ok, conv_ok, adv_ok])
    if met == 3:
        q6 = "ANO — všechna 3 kritéria splněna"
    elif met == 2:
        q6 = "PRAVDĚPODOBNĚ — 2/3 kritérií splněna. Doporučen sběr dalších dat."
    elif met == 1:
        q6 = "NEPRAVDĚPODOBNĚ — 1/3 kritérií splněna."
    else:
        q6 = "NE — žádné kritérium nesplněno."

    # ── Conversion Horizon Analysis ───────────────────────────────────────────
    # Zjisti při kterém horizontu se křivka stabilizuje
    # Kritérium stabilizace: přírůstek conversion rate < 3 procentní body
    conv_curve_lines = _build_conversion_horizon_analysis(cr_vals, c10, c20, c30, c40)

    L += [
        f"  1. Má First Entry TOP80 Band edge?",
        f"     {q1}", "",
        f"  2. Je TOP80 lepší než First Entry TOP50?",
        f"     {q2}", "",
        f"  3. Jak často se TOP80 kandidáti dostanou do TOP50?",
        f"     {q3}", "",
        f"  4. Kolik dní průměrně trvá conversion do TOP50?",
        f"     {q4}", "",
        f"  5. Má dřívější entry praktickou výhodu?",
        f"     {q5}", "",
        f"  6. Má smysl přidat MLE PRE-LEADERS sekci?",
        f"     {q6}",
        f"     Kritéria: edge={'OK' if edge_ok else '--'}  conv_10D>40%={'OK' if conv_ok else '--'}  entry_advantage={'OK' if adv_ok else '--'}",
        "", SEP, "",
    ]
    L += conv_curve_lines

    # ── Test E (pokud byl spuštěn) ────────────────────────────────────────────
    if test_e_lines:
        L += test_e_lines

    return L


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    run_date = date.today()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    print(SEP)
    print("  IMS AUDIT v5 — MLE EARLY LEADERSHIP DETECTION".center(70))
    print(SEP)
    print(f"  Run date   : {run_date}")
    print(f"  MLE archive: {MLE_ARCHIVE}")
    print()

    # ── 1. MLE archiv ─────────────────────────────────────────────────────────
    archive = load_mle_archive(MLE_ARCHIVE)
    trading_dates = sorted(archive["date"].unique().tolist())

    # ── 2. Eventy ─────────────────────────────────────────────────────────────
    top80_events, top50_events, top20_events = detect_events(
        archive, trading_dates, max_horizon=40
    )

    # ── 3. Close prices přes IMS data_loader ──────────────────────────────────
    # data_loader.py se stará o AccessLayer, conid lookup, SPY atd.
    # Tickery v MLE archivu jsou SP500 — jsou v IMS universe.
    # Pokud ticker není v IMS universe (velmi vzácné), data_loader ho přeskočí.
    print("\nNačítám close prices přes IMS data_loader...")

    # Upravíme archive path na IMS archiv dočasně — data_loader načítá
    # tickers z IMS archivu. Pro MLE potřebujeme jiný ticker set.
    # Řešení: vytvoříme minimální "signals" DataFrame s MLE tickery
    # a předáme přes data_loader internal API (přímý volání _init_access_layer).

    from audit.data_loader import _init_access_layer, _fetch_all_tickers, _fetch_ticker
    from audit.data_loader import SPY_CONID, SPY_TICKER

    layer, universe_map = _init_access_layer(verbose=True)

    signal_start_str = trading_dates[0]
    signal_end_str   = trading_dates[-1]
    from datetime import date as date_cls
    fetch_start = date_cls.fromisoformat(signal_start_str)
    fetch_end   = date_cls.fromisoformat(signal_end_str)

    all_tickers = sorted(archive["ticker"].unique().tolist())
    print(f"[INFO] Načítám close prices: {len(all_tickers)} tickerů...")

    close_map = _fetch_all_tickers(
        layer, all_tickers, universe_map, fetch_start, fetch_end, verbose=True
    )
    spy_close = _fetch_ticker(layer, SPY_CONID, SPY_TICKER, fetch_start, fetch_end, verbose=True)

    spy_available = spy_close is not None
    if not spy_available:
        print("[WARN] SPY data nedostupná. Alpha výpočty budou prázdné.")

    print(f"[INFO] Close prices načteny: {len(close_map)}/{len(all_tickers)}")

    # ── 4. Enrich events s forward returns ────────────────────────────────────
    print("\nPočítám forward returns...")
    df80 = enrich_events(top80_events, close_map, spy_close, trading_dates, FORWARD_HORIZONS, "TOP80")
    df50 = enrich_events(top50_events, close_map, spy_close, trading_dates, FORWARD_HORIZONS, "TOP50")
    df20 = enrich_events(top20_events, close_map, spy_close, trading_dates, FORWARD_HORIZONS, "TOP20")

    # ── 5. Statistiky ─────────────────────────────────────────────────────────
    stats80 = compute_stats(df80, FORWARD_HORIZONS)
    stats50 = compute_stats(df50, FORWARD_HORIZONS)
    stats20 = compute_stats(df20, FORWARD_HORIZONS)

    # ── 6. Test C — Conversion ────────────────────────────────────────────────
    print("Test C: Conversion...")
    conv = compute_conversion(top80_events, archive, trading_dates, CONVERSION_HORIZONS)

    # ── 7. Test D — Entry Advantage ───────────────────────────────────────────
    print("Test D: Entry Advantage...")
    advantage = compute_entry_advantage(
        top80_events, archive, close_map, spy_close, trading_dates, FORWARD_HORIZONS
    )

    # ── 7b. Test E — PRE-LEADER Band Optimization ─────────────────────────────
    print("\nTest E: PRE-LEADER Band Optimization...")
    band_results = run_test_e(
        archive, trading_dates, close_map, spy_close, top50_events
    )
    test_e_lines = build_test_e_report(band_results, spy_available)

    # ── 8. Report ─────────────────────────────────────────────────────────────
    lines = build_report(
        run_date=str(run_date),
        archive_range=(trading_dates[0], trading_dates[-1]),
        trading_days=len(trading_dates),
        n_top80=len(top80_events), n_top50=len(top50_events), n_top20=len(top20_events),
        stats80=stats80, stats50=stats50, stats20=stats20,
        conv=conv, advantage=advantage,
        horizons=FORWARD_HORIZONS, conv_horizons=CONVERSION_HORIZONS,
        spy_available=spy_available,
        test_e_lines=test_e_lines,
    )
    report_text = "\n".join(lines)
    print(report_text)

    report_path = AUDIT_DIR / f"mle_top80_audit_report_{run_date}.txt"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"[INFO] Report: {report_path}")

    # ── 9. CSV výstupy ────────────────────────────────────────────────────────
    summary = build_summary_csv(
        stats80, stats50, stats20, conv, advantage,
        FORWARD_HORIZONS, CONVERSION_HORIZONS
    )
    summary.to_csv(AUDIT_DIR / "mle_top80_audit_summary.csv", index=False)

    df80["group"] = "TOP80_ENTRY"
    df50["group"] = "TOP50_ENTRY"
    signals_df = pd.concat([df80, df50], ignore_index=True)
    signals_df.to_csv(AUDIT_DIR / "mle_top80_signals.csv", index=False)

    print(f"[INFO] Summary CSV: {AUDIT_DIR / 'mle_top80_audit_summary.csv'}")
    print(f"[INFO] Signals CSV: {AUDIT_DIR / 'mle_top80_signals.csv'}")

    band_csv = build_band_comparison_csv(band_results)
    band_csv.to_csv(AUDIT_DIR / "mle_band_optimization.csv", index=False)
    print(f"[INFO] Band optimization CSV: {AUDIT_DIR / 'mle_band_optimization.csv'}")

    print("[INFO] Audit v5 dokončen.")


if __name__ == "__main__":
    main()
