"""
run_hold_profile_diagnostic.py — exploratorní diagnostika Edge Lifetime

Otázka: jak se vyvíjí return / alpha MLE×IRC kandidátů s délkou držení
(5–60 obchodních dnů)?

STATUS: DIAGNOSTIKA (exploratorní, deskriptivní).
    - NENÍ experiment. Žádná hypotéza, žádná inference, žádné kritérium.
    - Výběr horizontu z této křivky pro následný test = selekce
      (data snooping) — viz KR Edge Lifetime Hypothesis sekce.
    - Podklad pro budoucí RP Edge Lifetime Characterization.

Metodika:
    - candidate pool: MLE_Rank_10d <= 10 AND IRC(20) rank <= 10
    - COMMON COMPLETABLE SUBSET pro H=60: všechny horizonty na stejné
      množině trades → entries končí ~60 obch. dnů před koncem archivu.
      DŮSLEDEK (kvantifikováno běhemn 2026-07-02): subset NENÍ
      reprezentativní — 20D mean 4.15 % vs 7.23 % na plném vzorku
      (vyřazené entries 04–06/2026 byly silnější).
    - returns close-to-close; alpha vs SPY na stejném okně;
      intra-hold MDD z closes.
    - překryv oken masivní → efektivní N << nominal N; bez clusteringu.

Výstupy: results/diagnostics/RP-0012_hold_profile.csv (+ _trades.csv)

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_hold_profile_diagnostic.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MLE_TOP, IRC_TOP, IRC_LOOKBACK = 10, 10, 20
HORIZONS = [5, 10, 15, 20, 25, 30, 40, 60]
HMAX = max(HORIZONS)
SPY_CONID = 756733

ROOT = Path(__file__).resolve().parent
MLE_CSV  = ROOT.parent / "MarketLeadershipEngine" / "output" / "archive" / "rank_matrix_archive.csv"
IRC_CSV  = ROOT.parent / "industry_rank_calendar" / "output" / "archive" / "industry_rank_calendar_archive.csv"
UNIV_CSV = ROOT.parent / "MDSM-Lite" / "data" / "universe" / "sp500_rank_calendar_universe.csv"
PX_DIR   = ROOT.parent / "MDSM-Lite" / "data" / "cache" / "prices"
OUT_DIR  = ROOT / "results" / "diagnostics"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mle = pd.read_csv(MLE_CSV, usecols=["date", "ticker", "rank_10d"],
                      low_memory=False)
    mle["date"] = pd.to_datetime(mle["date"])
    rank_mat = mle.pivot_table(index="date", columns="ticker",
                               values="rank_10d", aggfunc="first").sort_index()
    dates = list(rank_mat.index)

    irc = pd.read_csv(IRC_CSV, usecols=["date", "lookback", "rank", "industry"])
    irc = irc[irc["lookback"] == IRC_LOOKBACK]
    irc["date"] = pd.to_datetime(irc["date"])
    irc_idx = irc.set_index(["date", "industry"])["rank"].to_dict()

    univ = pd.read_csv(UNIV_CSV)
    tk2ind = univ.set_index("ticker")["industry"].to_dict()
    tk2conid = univ.set_index("ticker")["conid"].to_dict()

    px: dict[str, pd.Series | None] = {}

    def closes(tk: str):
        if tk in px:
            return px[tk]
        c = tk2conid.get(tk)
        s = None
        if c is not None:
            p = PX_DIR / f"{int(c)}_D1.parquet"
            if p.exists():
                d = pd.read_parquet(p)
                d.index = pd.to_datetime(d.index)
                if getattr(d.index, "tz", None) is not None:
                    d.index = d.index.tz_localize(None)
                s = d["close"]
        px[tk] = s
        return s

    spy = pd.read_parquet(PX_DIR / f"{SPY_CONID}_D1.parquet")["close"]
    spy.index = pd.to_datetime(spy.index)

    rows = []
    excl_cal = excl_px = 0
    for i, d in enumerate(dates):
        if i + HMAX >= len(dates):
            excl_cal += 1
            continue
        day = rank_mat.iloc[i]
        for tk in day[day <= MLE_TOP].index:
            ind = tk2ind.get(tk)
            ir = irc_idx.get((d, ind)) if ind else None
            if ir is None or ir > IRC_TOP:
                continue
            cs = closes(tk)
            if cs is None or d not in cs.index:
                excl_px += 1
                continue
            need = [dates[i + h] for h in [0] + HORIZONS]
            if any(x not in cs.index for x in need):
                excl_px += 1
                continue
            e = float(cs.loc[d])
            rec = {"date": d, "ticker": tk}
            for h in HORIZONS:
                dh = dates[i + h]
                r = float(cs.loc[dh]) / e - 1.0
                rec[f"ret_{h}"] = r
                if d in spy.index and dh in spy.index:
                    rec[f"alpha_{h}"] = r - (float(spy.loc[dh]) / float(spy.loc[d]) - 1.0)
                path = np.array([float(cs.loc[dates[i + k]])
                                 for k in range(h + 1)
                                 if dates[i + k] in cs.index])
                peak = np.maximum.accumulate(path)
                rec[f"mdd_{h}"] = float(((path - peak) / peak).min())
            rows.append(rec)

    df = pd.DataFrame(rows)
    print(f"common completable subset (H={HMAX}): N={len(df)}, "
          f"{df['ticker'].nunique()} tickerů | entries "
          f"{df['date'].min().date()} → {df['date'].max().date()}")
    print(f"vyřazeno: kalendář {excl_cal} dnů | price gaps {excl_px}\n")

    out = []
    for h in HORIZONS:
        r = df[f"ret_{h}"]
        a = df[f"alpha_{h}"].dropna()
        m = df[f"mdd_{h}"]
        out.append({
            "hold_d": h,
            "mean_pct": round(100 * r.mean(), 2),
            "median_pct": round(100 * r.median(), 2),
            "per_day_bps": round(10000 * r.mean() / h, 1),
            "alpha_spy_pct": round(100 * a.mean(), 2),
            "alpha_per_day_bps": round(10000 * a.mean() / h, 1),
            "std_pct": round(100 * r.std(), 2),
            "win_pct": round(100 * (r > 0).mean(), 1),
            "med_intra_mdd_pct": round(100 * m.median(), 2),
        })
    t = pd.DataFrame(out)
    print(t.to_string(index=False))
    t.to_csv(OUT_DIR / "RP-0012_hold_profile.csv", index=False)
    df.to_csv(OUT_DIR / "RP-0012_hold_profile_trades.csv", index=False)

    print("\nmarginální alpha (pp za segment):")
    prev, prev_a = 0, 0.0
    for h in HORIZONS:
        a = 100 * df[f"alpha_{h}"].dropna().mean()
        print(f"  {prev:>2}→{h:<3}: {a - prev_a:+.2f}pp "
              f"({(a - prev_a) / (h - prev) * 100:+.1f}bps/den)")
        prev, prev_a = h, a
    print("\nDIAGNOSTIKA — deskriptivní. Výběr horizontu z křivky = selekce.")


if __name__ == "__main__":
    main()
