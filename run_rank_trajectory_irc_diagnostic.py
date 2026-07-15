"""
run_rank_trajectory_irc_diagnostic.py — RP-0012 post-hoc diagnostika, IRC vrstva

Otázka: v jakém stavu je IRC rank industry v den, kdy MLE×IRC leader
poprvé vypadne z MLE TOP50 (breach) — a liší se post-breach vývoj?

STATUS: DIAGNOSTIKA (exploratorní). Nemění závěr RP-0012. Neoptimalizuje
exit pravidlo. IRC stav při breach JE pozorovatelný bez look-ahead
(na rozdíl od re-entry splitu v základní diagnostice) — případný vzorec
je preregistrovatelný.

Kategorie IRC stavu při breach (rank industry, lookback 20):
    STRONG    <= 10   (selekční zóna intaktní)
    WEAKENING 11–20
    COLLAPSED  > 20
    MISSING   rank nedostupný

Výstupy:
    results/diagnostics/RP-0012_rank_trajectory_irc.csv   (per-breach řádky)
    results/diagnostics/RP-0012_irc_state_table.csv       (agregace)
    konzole: stavová tabulka + IRC delta-5d kvartily

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_rank_trajectory_irc_diagnostic.py

Nález z běhu 2026-07-02 (snapshot dat do 2026-06-30):
    STRONG 72.8 % breachů, post-breach +5.15 % mean
    WEAKENING 17.0 %, +5.90 % (anomálie, neinterpretovat bez CI)
    COLLAPSED 10.3 %, +0.53 % — diskriminátor existuje, ale i nejhorší
    kontext má kladný forward return => kombinovaný exit má záporný prior.
    IRC delta-5d: nemonotónní, bez čitelného signálu.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MLE_TOP, IRC_TOP, IRC_LOOKBACK, HOLD_DAYS, THRESH = 10, 10, 20, 20, 50

ROOT = Path(__file__).resolve().parent
MLE_CSV  = ROOT.parent / "MarketLeadershipEngine" / "output" / "archive" / "rank_matrix_archive.csv"
IRC_CSV  = ROOT.parent / "industry_rank_calendar" / "output" / "archive" / "industry_rank_calendar_archive.csv"
UNIV_CSV = ROOT.parent / "MDSM-Lite" / "data" / "universe" / "sp500_rank_calendar_universe.csv"
PX_DIR   = ROOT.parent / "MDSM-Lite" / "data" / "cache" / "prices"
OUT_DIR  = ROOT / "results" / "diagnostics"


def irc_state(rank) -> str:
    if rank is None or (isinstance(rank, float) and np.isnan(rank)):
        return "MISSING"
    if rank <= 10:
        return "STRONG"
    if rank <= 20:
        return "WEAKENING"
    return "COLLAPSED"


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

    px_cache: dict[str, pd.Series | None] = {}

    def closes(tk: str):
        if tk in px_cache:
            return px_cache[tk]
        c = tk2conid.get(tk)
        s = None
        if c is not None:
            p = PX_DIR / f"{int(c)}_D1.parquet"
            if p.exists():
                df = pd.read_parquet(p)
                df.index = pd.to_datetime(df.index)
                if getattr(df.index, "tz", None) is not None:
                    df.index = df.index.tz_localize(None)
                s = df["close"]
        px_cache[tk] = s
        return s

    rows = []
    n_cand = n_nobreach = 0
    for i, d in enumerate(dates):
        if i + HOLD_DAYS >= len(dates):
            continue
        day = rank_mat.iloc[i]
        for tk in day[day <= MLE_TOP].index:
            ind = tk2ind.get(tk)
            ir_entry = irc_idx.get((d, ind)) if ind is not None else None
            if ir_entry is None or ir_entry > IRC_TOP:
                continue
            path = rank_mat.iloc[i + 1:i + HOLD_DAYS + 1][tk].to_numpy()
            n_cand += 1
            valid = ~np.isnan(path)
            breach_rel = next(
                (k for k in range(len(path)) if valid[k] and path[k] > THRESH),
                None)
            if breach_rel is None:
                n_nobreach += 1
                continue
            gi = i + 1 + breach_rel
            d_breach = dates[gi]
            ir_b = irc_idx.get((d_breach, ind))
            ir_b5 = irc_idx.get((dates[gi - 5], ind)) if gi >= 5 else None
            delta5 = (ir_b - ir_b5) if (ir_b is not None and ir_b5 is not None) else None
            re_rel = next(
                (k for k in range(breach_rel + 1, len(path))
                 if valid[k] and path[k] <= THRESH), None)
            cs = closes(tk)
            pbr = None
            d_end = dates[i + HOLD_DAYS]
            if cs is not None and d_breach in cs.index and d_end in cs.index:
                pbr = float(cs.loc[d_end] / cs.loc[d_breach] - 1.0)
            rows.append({
                "date": d, "ticker": tk, "industry": ind,
                "breach_day": breach_rel + 1,
                "irc_rank_at_breach": ir_b,
                "irc_delta_5d": delta5,          # + = zhoršení ranku
                "irc_state": irc_state(ir_b),
                "reentry_50": re_rel is not None,
                "post_breach_ret": pbr,
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "RP-0012_rank_trajectory_irc.csv", index=False)

    print(f"candidate-days {n_cand} | breach {len(df)} | no-breach {n_nobreach}")
    print(f"IRC missing at breach: {(df['irc_state'] == 'MISSING').sum()}\n")

    tab = []
    for st in ("STRONG", "WEAKENING", "COLLAPSED", "MISSING"):
        sub = df[df["irc_state"] == st]
        if not len(sub):
            continue
        pbr = sub["post_breach_ret"].dropna()
        tab.append({
            "IRC_state_at_breach": st, "N": len(sub),
            "pct": round(100 * len(sub) / len(df), 1),
            "irc_rank_mean": (round(float(sub["irc_rank_at_breach"].mean()), 1)
                              if st != "MISSING" else None),
            "irc_delta5_mean": (round(float(sub["irc_delta_5d"].mean()), 1)
                                if sub["irc_delta_5d"].notna().any() else None),
            "reentry50_pct": round(100 * float(sub["reentry_50"].mean()), 1),
            "post_breach_mean_pct": round(100 * float(pbr.mean()), 2),
            "post_breach_med_pct": round(100 * float(pbr.median()), 2),
            "win_pct": round(100 * float((pbr > 0).mean()), 1),
        })
    t = pd.DataFrame(tab)
    t.to_csv(OUT_DIR / "RP-0012_irc_state_table.csv", index=False)
    print(t.to_string(index=False))

    q = df.dropna(subset=["irc_delta_5d", "post_breach_ret"]).copy()
    q["d5_bucket"] = pd.qcut(q["irc_delta_5d"], 4,
                             labels=["Q1_zlepseni", "Q2", "Q3", "Q4_zhorseni"],
                             duplicates="drop")
    g = q.groupby("d5_bucket", observed=True).agg(
        N=("post_breach_ret", "size"),
        delta5_mean=("irc_delta_5d", "mean"),
        post_breach_mean_pct=("post_breach_ret",
                              lambda s: round(100 * s.mean(), 2)),
        reentry50_pct=("reentry_50", lambda s: round(100 * s.mean(), 1)))
    print("\nIRC 5D zmena (kvartily; + = zhorseni ranku):")
    print(g.to_string())
    print("\nDIAGNOSTIKA — bez inference, bez kriteria. Nemeni zaver RP-0012.")


if __name__ == "__main__":
    main()
