"""
run_rank_trajectory_diagnostic.py — RP-0012 post-hoc diagnostika

Co se děje s MLE×IRC leadery po PRVNÍM výpadku z TOP50 uvnitř 20D okna?

STATUS: DIAGNOSTIKA (exploratorní, post-hoc).
    - NENÍ experiment. Žádná hypotéza, žádný bootstrap, žádné kritérium.
    - NEMĚNÍ primární závěr RP-0012 (H1a NOT SUPPORTED zůstává).
    - NEPOUŽÍVAT k optimalizaci exit pravidla.
    - Výstup = podklad pro případnou preregistraci RP-0013.

Definice (shodné s LeadershipLossEdge_v1, kde relevantní):
    candidate-day: MLE_Rank_10d <= 10 AND IRC(lookback 20) rank <= 10
                   (industry z sp500_rank_calendar_universe, IBKR taxonomy)
    okno:          D+1 .. D+20 lokálních obchodních dnů (globální kalendář
                   = průnik dostupných dat MLE archivu)
    breach:        první den k, kdy rank_10d(k) > 50
    worst rank:    max(rank) od breach do konce okna; missing rank po
                   breach => bucket D (nelze odlišit od >250 spolehlivě —
                   reportováno odděleně)
    re-entry:      první den po breach s rank <= 50 (samostatně <=25, <=10)
    returny:       close-to-close, uvnitř okna:
                   post_breach_ret  = close(D+20)/close(breach) - 1
                   post_reentry_ret = close(D+20)/close(re-entry50) - 1

Datové zdroje (přímé čtení — diagnostika, ne experiment; CACHE_ONLY
pravidlo experimentů se na diagnostické scripty nevztahuje, data se
POUZE čtou):
    MLE:  MarketLeadershipEngine/output/archive/rank_matrix_archive.csv
    IRC:  industry_rank_calendar/output/archive/industry_rank_calendar_archive.csv
    UNIV: MDSM-Lite/data/universe/sp500_rank_calendar_universe.csv
    PX:   MDSM-Lite/data/cache/prices/{conid}_D1.parquet

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_rank_trajectory_diagnostic.py
Výstup: konzole + results/diagnostics/RP-0012_rank_trajectory.csv (+ summary.md)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ── parametry (převzato z RP-0012; diagnostika, nic se nezamyká) ────────
MLE_TOP      = 10
IRC_TOP      = 10
IRC_LOOKBACK = 20
HOLD_DAYS    = 20
THRESH       = 50
REENTRY_LEVELS = (50, 25, 10)
BUCKETS = [("A_51-100", 51, 100), ("B_101-150", 101, 150),
           ("C_151-250", 151, 250), ("D_gt250", 251, 10**9)]

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

    px_cache: dict[str, pd.Series] = {}

    def closes(tk: str) -> pd.Series | None:
        if tk in px_cache:
            return px_cache[tk]
        conid = tk2conid.get(tk)
        s = None
        if conid is not None:
            p = PX_DIR / f"{int(conid)}_D1.parquet"
            if p.exists():
                df = pd.read_parquet(p)
                df.index = pd.to_datetime(df.index)
                if getattr(df.index, "tz", None) is not None:
                    df.index = df.index.tz_localize(None)
                s = df["close"]
        px_cache[tk] = s
        return s

    rows = []
    n_candidates = 0
    n_no_breach = 0
    for i, d in enumerate(dates):
        if i + HOLD_DAYS >= len(dates):
            continue
        day = rank_mat.iloc[i]
        leaders = day[day <= MLE_TOP].index
        for tk in leaders:
            ind = tk2ind.get(tk)
            ir = irc_idx.get((d, ind)) if ind is not None else None
            if ir is None or ir > IRC_TOP:
                continue
            path = rank_mat.iloc[i + 1:i + HOLD_DAYS + 1][tk].to_numpy()
            n_candidates += 1
            valid = ~np.isnan(path)
            breach_rel = None
            for k in range(len(path)):
                if valid[k] and path[k] > THRESH:
                    breach_rel = k  # 0-based v D+1..D+20
                    break
            if breach_rel is None:
                n_no_breach += 1
                continue
            post = path[breach_rel:]
            post_missing = bool(np.isnan(post).any())
            worst = float(np.nanmax(post))
            if post_missing:
                bucket = "D_gt250"   # missing => konzervativně D, flag níže
            else:
                bucket = next(b for b, lo, hi in BUCKETS if lo <= worst <= hi)

            rec = {"date": d, "ticker": tk,
                   "breach_day": breach_rel + 1,       # dny od entry
                   "worst_rank_after": worst,
                   "post_missing_rank": post_missing,
                   "bucket": bucket}

            # re-entry pro každou úroveň
            for lvl in REENTRY_LEVELS:
                re_rel = None
                for k in range(breach_rel + 1, len(path)):
                    if valid[k] and path[k] <= lvl:
                        re_rel = k
                        break
                rec[f"reentry_{lvl}"] = re_rel is not None
                rec[f"days_to_reentry_{lvl}"] = (
                    (re_rel - breach_rel) if re_rel is not None else None)

            # returny uvnitř okna (close-to-close)
            cs = closes(tk)
            rec["post_breach_ret"] = None
            rec["post_reentry50_ret"] = None
            if cs is not None:
                d_breach = dates[i + 1 + breach_rel]
                d_end = dates[i + HOLD_DAYS]
                if d_breach in cs.index and d_end in cs.index:
                    rec["post_breach_ret"] = float(
                        cs.loc[d_end] / cs.loc[d_breach] - 1.0)
                if rec["reentry_50"]:
                    d_re = dates[i + 1 + breach_rel + rec["days_to_reentry_50"]]
                    if d_re in cs.index and d_end in cs.index:
                        rec["post_reentry50_ret"] = float(
                            cs.loc[d_end] / cs.loc[d_re] - 1.0)
            rows.append(rec)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "RP-0012_rank_trajectory.csv", index=False)

    # ── report ──
    lines = []
    lines.append("# RP-0012 — Rank Trajectory Diagnostika (post-hoc, exploratorní)")
    lines.append("")
    lines.append(f"candidate-days: {n_candidates} | bez breachu TOP{THRESH}: "
                 f"{n_no_breach} ({100 * n_no_breach / n_candidates:.2f} %) | "
                 f"s breachem: {len(df)}")
    lines.append(f"post-breach missing rank (bucket D konzervativně): "
                 f"{int(df['post_missing_rank'].sum())}")
    lines.append("")
    lines.append("| bucket | N | %vzorku | reentry50 % | reentry25 % | reentry10 % "
                 "| med d→re50 | post-breach ret mean/med % | "
                 "ret s re-entry mean % | ret bez re-entry mean % |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for b, _, _ in BUCKETS:
        sub = df[df["bucket"] == b]
        if not len(sub):
            lines.append(f"| {b} | 0 | 0 | – | – | – | – | – | – | – |")
            continue
        r50 = 100 * sub["reentry_50"].mean()
        r25 = 100 * sub["reentry_25"].mean()
        r10 = 100 * sub["reentry_10"].mean()
        med_d = sub.loc[sub["reentry_50"], "days_to_reentry_50"].median()
        pbr = sub["post_breach_ret"].dropna()
        with_re = sub.loc[sub["reentry_50"], "post_breach_ret"].dropna()
        no_re = sub.loc[~sub["reentry_50"], "post_breach_ret"].dropna()
        lines.append(
            f"| {b} | {len(sub)} | {100 * len(sub) / len(df):.1f} "
            f"| {r50:.1f} | {r25:.1f} | {r10:.1f} "
            f"| {med_d if med_d == med_d else '–'} "
            f"| {100 * pbr.mean():.2f} / {100 * pbr.median():.2f} "
            f"| {100 * with_re.mean():.2f} (N={len(with_re)}) "
            f"| {100 * no_re.mean():.2f} (N={len(no_re)}) |")
    lines.append("")
    re50 = df.loc[df["reentry_50"], "post_reentry50_ret"].dropna()
    lines.append(f"post-RE-ENTRY(50) return do konce okna: mean "
                 f"{100 * re50.mean():.2f} % | median {100 * re50.median():.2f} % "
                 f"| N={len(re50)}")
    lines.append("")
    lines.append("POZNÁMKY: exploratorní; returny podmíněné breachem/re-entry "
                 "trpí look-ahead selekcí (podmínka definována zpětně) — "
                 "NEINTERPRETOVAT jako obchodovatelný edge; pouze podklad "
                 "pro preregistraci RP-0013.")
    report = "\n".join(lines)
    (OUT_DIR / "RP-0012_rank_trajectory_summary.md").write_text(
        report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
