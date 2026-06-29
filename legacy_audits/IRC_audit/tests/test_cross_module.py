"""
Industry Rank Calendar Audit — Testy 7–10
audit/tests/test_cross_module.py

Test 7: MLE TOP20  vs  MLE TOP20 + TOP10 Industry
Test 8: IMS HIGH   vs  IMS HIGH  + TOP10 Industry
Test 9: MLE TOP20 + Persistence HIGH  vs  MLE TOP20 + Persistence LOW
Test 10: IMS HIGH + Persistence HIGH  vs  IMS HIGH  + Persistence LOW

Metodologie:
    Načte IMS a MLE archivy.
    Pro každý signál přiřadí industry_rank a industry_persist z Industry Rank Calendar archivu.
    Porovná forward returns mezi skupinami.

Závislosti:
    - IMS archive musí mít sloupec industry (od dnešní verze OK)
    - MLE archive musí mít sloupec industry
    - Industry Rank Calendar archive (20D lookback)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FORWARD_WINDOWS    = [5, 10, 20, 30]
PROJECTS_BASE      = Path("C:/Users/stava/Projects")
IMS_ARCHIVE        = PROJECTS_BASE / "InstitutionalMomentumScanner/output/archive/ims_candidates_archive.csv"
MLE_ARCHIVE        = PROJECTS_BASE / "MarketLeadershipEngine/output/archive/rank_matrix_archive.csv"
IND_ARCHIVE        = PROJECTS_BASE / "industry_rank_calendar/output/archive/industry_rank_calendar_archive.csv"
UNIVERSE_CSV       = PROJECTS_BASE / "MDSM-Lite/data/universe/sp500_rank_calendar_universe.csv"

TOP_INDUSTRY_RANK  = 10    # TOP10 industry = tailwind
PERSIST_HIGH       = 12    # >= 12/20 = HIGH persistence
PERSIST_LOW        = 5     # <= 5/20  = LOW persistence


# ── Načtení dat ───────────────────────────────────────────────────────────────

def _load_industry_map() -> dict[tuple[str, str], dict]:
    """
    Vrátí mapping (date_str, industry) → { rank, persist }
    Persist počítán z posledních 20 dní v archivu.
    """
    if not IND_ARCHIVE.exists():
        return {}

    df = pd.read_csv(IND_ARCHIVE, dtype={"date": str, "lookback": str})
    df = df[df["lookback"].astype(str) == "20"].copy()
    df = df[df["status"] == "OK"].copy()
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce").astype("Int64")

    all_dates = sorted(df["date"].unique())

    # Persistence: počet dní v TOP10 za posledních 20D
    persist_map: dict[tuple[str, str], int] = {}
    window = 20
    top_n  = 10

    for i, d in enumerate(all_dates):
        window_dates = all_dates[max(0, i - window + 1): i + 1]
        today_df = df[df["date"] == d]
        for _, row in today_df.iterrows():
            ind = str(row["industry"])
            count = sum(
                1 for wd in window_dates
                if int(df[(df["date"] == wd) & (df["industry"] == ind)]["rank"].iloc[0])
                   <= top_n
                if not df[(df["date"] == wd) & (df["industry"] == ind)].empty
            )
            persist_map[(d, ind)] = count

    # Sestav finální mapping
    result: dict[tuple[str, str], dict] = {}
    for _, row in df.iterrows():
        d   = str(row["date"])
        ind = str(row["industry"])
        r   = int(row["rank"]) if pd.notna(row["rank"]) else 999
        p   = persist_map.get((d, ind), 0)
        result[(d, ind)] = {"rank": r, "persist": p}

    return result


def _load_universe_industry() -> dict[str, str]:
    """ticker → industry z universe CSV."""
    if not UNIVERSE_CSV.exists():
        return {}
    df = pd.read_csv(UNIVERSE_CSV)
    df["ticker"]   = df["ticker"].astype(str).str.strip().str.upper()
    df["industry"] = df["industry"].astype(str).str.strip()
    return dict(zip(df["ticker"], df["industry"]))


def _enrich(df: pd.DataFrame, ind_map: dict, ticker_industry: dict) -> pd.DataFrame:
    """
    Přidá industry, industry_rank, industry_persist do signálového DataFrame.
    Industry se bere z archivu sloupce 'industry' pokud existuje,
    jinak z universe CSV (fallback).
    """
    rows = []
    for _, row in df.iterrows():
        ticker   = str(row.get("ticker", ""))
        date_str = str(row.get("date", ""))

        # Industry: preferuj z archivu, fallback na universe
        industry = str(row.get("industry", "") or "").strip()
        if not industry or industry.lower() in ("nan", "none", ""):
            industry = ticker_industry.get(ticker, "")

        if not industry or industry.lower() in ("nan", "none", ""):
            continue

        ctx = ind_map.get((date_str, industry))
        if ctx is None:
            # Zkus nejbližší dostupné datum
            ctx = {"rank": 999, "persist": 0}

        r = row.to_dict()
        r["industry"]         = industry
        r["industry_rank"]    = ctx["rank"]
        r["industry_persist"] = ctx["persist"]
        rows.append(r)

    return pd.DataFrame(rows).reset_index(drop=True)


def load_cross_signals(verbose: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Načte IMS a MLE signály obohacené o industry kontext.

    Returns:
        ims_df: date, ticker, score, industry, industry_rank, industry_persist
        mle_df: date, ticker, rank_10d, industry, industry_rank, industry_persist
    """
    ind_map         = _load_industry_map()
    ticker_industry = _load_universe_industry()

    if verbose:
        print(f"Industry map: {len(ind_map)} záznamů")
        print(f"Universe industry: {len(ticker_industry)} tickerů")

    # IMS
    ims_df = pd.DataFrame()
    if IMS_ARCHIVE.exists():
        raw = pd.read_csv(IMS_ARCHIVE, dtype={"date": str, "sector": str, "industry": str, "subcategory": str})
        raw = raw[raw["score"] >= 70].copy()  # HIGH + ELITE
        ims_df = _enrich(raw, ind_map, ticker_industry)
        if verbose:
            print(f"IMS HIGH/ELITE signálů po obohacení: {len(ims_df)}")

    # MLE
    mle_df = pd.DataFrame()
    if MLE_ARCHIVE.exists():
        raw = pd.read_csv(MLE_ARCHIVE, dtype={"date": str, "sector": str, "industry": str, "subcategory": str})
        raw = raw[raw["rank_10d"] <= 20].copy()  # TOP20
        mle_df = _enrich(raw, ind_map, ticker_industry)
        if verbose:
            print(f"MLE TOP20 signálů po obohacení: {len(mle_df)}")

    return ims_df, mle_df


# ── Forward returns ───────────────────────────────────────────────────────────

def _compute_fwd(df: pd.DataFrame, close_map: dict, spy_close: pd.Series) -> pd.DataFrame:
    """Vypočítá forward returns pro signální DataFrame."""
    from audit.data_loader import get_entry_price, get_forward_price, get_window_low
    spy_map = {"SPY": spy_close}
    rows    = []

    for _, signal in df.iterrows():
        ticker      = signal["ticker"]
        signal_date = pd.Timestamp(signal["date"]).date()

        entry = get_entry_price(close_map, ticker, signal_date)
        if entry is None or entry <= 0:
            continue
        spy_e = get_entry_price(spy_map, "SPY", signal_date)
        if spy_e is None or spy_e <= 0:
            continue

        row = {
            "date":             signal_date,
            "ticker":           ticker,
            "industry":         signal.get("industry", ""),
            "industry_rank":    signal.get("industry_rank", 999),
            "industry_persist": signal.get("industry_persist", 0),
        }

        # IMS score nebo MLE rank_10d
        if "score" in signal:
            row["score"]    = signal.get("score")
        if "rank_10d" in signal:
            row["rank_10d"] = signal.get("rank_10d")

        for w in FORWARD_WINDOWS:
            fwd = get_forward_price(close_map, ticker, signal_date, w)
            spy = get_forward_price(spy_map, "SPY", signal_date, w)
            low = get_window_low(close_map, ticker, signal_date, w)
            if fwd and spy and low:
                fwd_ret = (fwd / entry - 1) * 100
                spy_ret = (spy / spy_e - 1) * 100
                row[f"fwd_{w}d"]    = round(fwd_ret, 4)
                row[f"alpha_{w}d"]  = round(fwd_ret - spy_ret, 4)
                row[f"dd_{w}d"]     = round((low / entry - 1) * 100, 4)
                row[f"usable_{w}d"] = True
            else:
                row[f"fwd_{w}d"]    = None
                row[f"alpha_{w}d"]  = None
                row[f"dd_{w}d"]     = None
                row[f"usable_{w}d"] = False

        rows.append(row)

    return pd.DataFrame(rows)


def _agg(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Agreguje forward returns per group a window."""
    rows = []
    for group in df[group_col].unique():
        subset = df[df[group_col] == group]
        for w in FORWARD_WINDOWS:
            col_use = f"usable_{w}d"
            if col_use not in subset.columns:
                continue
            usable = subset[subset[col_use] == True]
            fwd    = usable[f"fwd_{w}d"].dropna()
            alpha  = usable[f"alpha_{w}d"].dropna()
            dd     = usable[f"dd_{w}d"].dropna()
            if len(fwd) < 3:
                continue
            rows.append({
                "group":         group,
                "window":        f"{w}D",
                "n":             len(fwd),
                "avg_return":    round(fwd.mean(), 4),
                "median_return": round(fwd.median(), 4),
                "win_rate":      round((fwd > 0).mean() * 100, 2),
                "avg_alpha":     round(alpha.mean(), 4) if not alpha.empty else None,
                "avg_drawdown":  round(dd.mean(), 4) if not dd.empty else None,
            })
    return pd.DataFrame(rows)


def compute_fwd(df: pd.DataFrame, close_map: dict, spy_close: pd.Series) -> pd.DataFrame:
    """Veřejný wrapper pro _compute_fwd — používán testy 11–13."""
    return _compute_fwd(df, close_map, spy_close)
    """Agreguje forward returns per group a window."""
    rows = []
    for group in df[group_col].unique():
        subset = df[df[group_col] == group]
        for w in FORWARD_WINDOWS:
            col_use = f"usable_{w}d"
            if col_use not in subset.columns:
                continue
            usable = subset[subset[col_use] == True]
            fwd    = usable[f"fwd_{w}d"].dropna()
            alpha  = usable[f"alpha_{w}d"].dropna()
            dd     = usable[f"dd_{w}d"].dropna()
            if len(fwd) < 3:
                continue
            rows.append({
                "group":         group,
                "window":        f"{w}D",
                "n":             len(fwd),
                "avg_return":    round(fwd.mean(), 4),
                "median_return": round(fwd.median(), 4),
                "win_rate":      round((fwd > 0).mean() * 100, 2),
                "avg_alpha":     round(alpha.mean(), 4) if not alpha.empty else None,
                "avg_drawdown":  round(dd.mean(), 4) if not dd.empty else None,
            })
    return pd.DataFrame(rows)


# ── Testy ─────────────────────────────────────────────────────────────────────

def run_test_7(mle_df: pd.DataFrame, close_map: dict, spy_close: pd.Series) -> pd.DataFrame:
    """Test 7: MLE TOP20 vs MLE TOP20 + TOP10 Industry."""
    if mle_df.empty:
        return pd.DataFrame()
    df = _compute_fwd(mle_df, close_map, spy_close)
    if df.empty:
        return pd.DataFrame()
    df["group"] = df["industry_rank"].apply(
        lambda r: "MLE+TOP10_IND" if r <= TOP_INDUSTRY_RANK else "MLE_ONLY"
    )
    return _agg(df, "group")


def run_test_8(ims_df: pd.DataFrame, close_map: dict, spy_close: pd.Series) -> pd.DataFrame:
    """Test 8: IMS HIGH vs IMS HIGH + TOP10 Industry."""
    if ims_df.empty:
        return pd.DataFrame()
    df = _compute_fwd(ims_df, close_map, spy_close)
    if df.empty:
        return pd.DataFrame()
    df["group"] = df["industry_rank"].apply(
        lambda r: "IMS+TOP10_IND" if r <= TOP_INDUSTRY_RANK else "IMS_ONLY"
    )
    return _agg(df, "group")


def run_test_9(mle_df: pd.DataFrame, close_map: dict, spy_close: pd.Series) -> pd.DataFrame:
    """Test 9: MLE TOP20 + Persistence HIGH vs MLE TOP20 + Persistence LOW."""
    if mle_df.empty:
        return pd.DataFrame()
    df = _compute_fwd(mle_df, close_map, spy_close)
    if df.empty:
        return pd.DataFrame()

    def group_persist(p):
        if p >= PERSIST_HIGH:
            return "MLE+PERSIST_HIGH"
        elif p <= PERSIST_LOW:
            return "MLE+PERSIST_LOW"
        else:
            return "MLE+PERSIST_MED"

    df["group"] = df["industry_persist"].apply(group_persist)
    return _agg(df, "group")


def run_test_10(ims_df: pd.DataFrame, close_map: dict, spy_close: pd.Series) -> pd.DataFrame:
    """Test 10: IMS HIGH + Persistence HIGH vs IMS HIGH + Persistence LOW."""
    if ims_df.empty:
        return pd.DataFrame()
    df = _compute_fwd(ims_df, close_map, spy_close)
    if df.empty:
        return pd.DataFrame()

    def group_persist(p):
        if p >= PERSIST_HIGH:
            return "IMS+PERSIST_HIGH"
        elif p <= PERSIST_LOW:
            return "IMS+PERSIST_LOW"
        else:
            return "IMS+PERSIST_MED"

    df["group"] = df["industry_persist"].apply(group_persist)
    return _agg(df, "group")


# ── Formátování reportu ───────────────────────────────────────────────────────

def _fmt_test(title: str, question: str, df: pd.DataFrame, group_order: list[str]) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append(title)
    lines.append("=" * 70)
    lines.append("")
    lines.append(question)
    lines.append("")

    if df.empty or "window" not in df.columns:
        lines.append("  Nedostatek dat.")
        lines.append("")
        return lines

    for w in FORWARD_WINDOWS:
        w_str = f"{w}D"
        sub   = df[df["window"] == w_str]
        if sub.empty:
            continue

        lines.append(f"Forward {w_str}")
        lines.append("-" * 70)
        lines.append(
            f"  {'Skupina':<20}  {'N':>6}  {'Avg%':>8}  {'Med%':>8}  "
            f"{'WinRate':>8}  {'AvgAlpha':>9}  {'AvgDD%':>8}"
        )
        lines.append(
            f"  {'-'*20}  {'-'*6}  {'-'*8}  {'-'*8}  "
            f"{'-'*8}  {'-'*9}  {'-'*8}"
        )

        for group in group_order:
            row = sub[sub["group"] == group]
            if row.empty:
                continue
            r = row.iloc[0]
            alpha_str = f"{r['avg_alpha']:>+8.2f}%" if r["avg_alpha"] is not None else "      N/A"
            dd_str    = f"{r['avg_drawdown']:>+7.2f}%" if r["avg_drawdown"] is not None else "     N/A"
            lines.append(
                f"  {group:<20}  {int(r['n']):>6}  "
                f"{r['avg_return']:>+7.2f}%  {r['median_return']:>+7.2f}%  "
                f"{r['win_rate']:>7.1f}%  {alpha_str}  {dd_str}"
            )

        # Delta
        if len(group_order) >= 2:
            best  = sub[sub["group"] == group_order[0]]
            worst = sub[sub["group"] == group_order[-1]]
            if not best.empty and not worst.empty:
                d_ret   = best.iloc[0]["avg_return"] - worst.iloc[0]["avg_return"]
                d_alpha = (best.iloc[0]["avg_alpha"] or 0) - (worst.iloc[0]["avg_alpha"] or 0)
                lines.append(
                    f"  {'DELTA':<20}  {'':>6}  "
                    f"{'+' if d_ret >= 0 else ''}{d_ret:>7.2f}%  {'':>8}  "
                    f"{'':>8}  {'+' if d_alpha >= 0 else ''}{d_alpha:>8.2f}%"
                )

        lines.append("")

    return lines


def format_report(t7, t8, t9, t10) -> list[str]:
    lines = []

    lines += _fmt_test(
        "TEST 7 — MLE TOP20 × INDUSTRY",
        "Hypoteza: MLE TOP20 + TOP10 Industry > MLE TOP20 bez industry filtru",
        t7,
        ["MLE+TOP10_IND", "MLE_ONLY"],
    )

    lines += _fmt_test(
        "TEST 8 — IMS HIGH × INDUSTRY",
        "Hypoteza: IMS HIGH + TOP10 Industry > IMS HIGH bez industry filtru",
        t8,
        ["IMS+TOP10_IND", "IMS_ONLY"],
    )

    lines += _fmt_test(
        "TEST 9 — MLE TOP20 × PERSISTENCE",
        "Hypoteza: MLE TOP20 + Persistence HIGH > MLE TOP20 + Persistence LOW",
        t9,
        ["MLE+PERSIST_HIGH", "MLE+PERSIST_MED", "MLE+PERSIST_LOW"],
    )

    lines += _fmt_test(
        "TEST 10 — IMS HIGH × PERSISTENCE",
        "Hypoteza: IMS HIGH + Persistence HIGH > IMS HIGH + Persistence LOW",
        t10,
        ["IMS+PERSIST_HIGH", "IMS+PERSIST_MED", "IMS+PERSIST_LOW"],
    )

    return lines
