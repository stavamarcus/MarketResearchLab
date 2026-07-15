"""
edge_test_01_mle_irc_signal_validation.py — EDGE-TEST-01.

READ-ONLY signal validation (NE backtest). Testuje edge MLE TOP10 x IRC TOP10
na overlapu 2025-07-09..2026-06-27 (245 IRC obchodnich dni).

MLE ranky: FRESH z DATA-06 (compute_rank_matrix). IRC: z archivu (rank_20d<=10).
Join pres industry (join_rate 1.0 z IRC-RECON-01).

NEDELA: portfolio backtest, Decision Resolver, bot/TWS, API/TWS, MLE archive
overwrite. NEPOUZIVA Sharadar TICKERS industry.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\edge_test_01_mle_irc_signal_validation.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

EDGE definice:
    MLE gate: ticker rank_10d <= 10 (fresh z DATA-06)
    IRC gate: industry rank_20d <= 10 (z archivu)
    join: ticker.industry in IRC_TOP10_industries daneho dne

Skupiny:
    1. universe_baseline
    2. mle_top10
    3. irc_top10_industry (vsechny tickery v TOP10 industries)
    4. mle_top10_x_irc_top10
    5. mle_top25_x_irc_top10
    6. mle_top50_x_irc_top10

Forward windows: 1D, 5D, 10D, 20D
Metriky:
    A) close-to-close: (close[t+h]/close[t] - 1)*100
    B) next-open entry: (close[t+h]/open[t+1] - 1)*100

Vyhrady:
    - t-stat NADHODNOCENY: forward okna se prekryvaji + cross-section
      korelace. Reportovat jako orientacni, ne rigorozni.
    - MLE industry label z universe CSV (musi mit industry sloupec).
    - IRC industry taxonomy z archivu (ne Sharadar).
    - forward return vyzaduje close[t+h]; posledni h dni bez forward -> vynechan.
    - metrika B: open[t+1] musi existovat.
    - known exceptions vylouceni: druhy pruchod bez KLAC/CRWD/HON/APTV/DD/
      NWS/GOOG/FOX/BDX/EXE/PSKY/Q/SNDK.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None

OVERLAP_FROM, OVERLAP_TO = "2025-07-09", "2026-06-27"
WEEKEND_ARTIFACTS = {"2026-05-31", "2026-06-06", "2026-06-13"}
LOOKBACKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
MLE_GATE_LB = 10
IRC_GATE_LB = 20
TOP_N = 10
FORWARD = [1, 5, 10, 20]
START_BUFFER = 45
EXCEPTIONS = {"KLAC", "CRWD", "HON", "APTV", "DD", "NWS", "GOOG", "FOX",
              "BDX", "EXE", "PSKY", "Q", "SNDK"}


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_universe(ucsv):
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    icol = cols.get("industry")
    scol = cols.get("sector")
    instruments = []
    tick2conid, tick2ind, tick2sec = {}, {}, {}
    for _, r in df.iterrows():
        if not is_active(r[acol]):
            continue
        tk = str(r[tcol]).strip().upper()
        ind = str(r[icol]).strip() if icol else ""
        sec = str(r[scol]).strip() if scol else ""
        instruments.append({"conid": int(float(r[ccol])), "ticker": tk,
                            "sector": sec, "industry": ind,
                            "subcategory": ""})
        tick2conid[tk] = str(r[ccol])
        tick2ind[tk] = ind
        tick2sec[tk] = sec
    return instruments, tick2conid, tick2ind, tick2sec


def load_ohlc(view_dir, conid):
    f = view_dir / f"{conid}_D1.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    df.index = pd.to_datetime(df.index).normalize()
    return df.sort_index()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mle-root",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--irc-archive",
                    default=r"C:\Users\stava\Projects\industry_rank_calendar\output\archive\industry_rank_calendar_archive.csv")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas/numpy")
        return 2

    mle_root = Path(args.mle_root)
    sys.path.insert(0, str(mle_root))
    try:
        from src.engines.rank_matrix_engine import compute_rank_matrix
    except ImportError as e:
        print(f"FAIL: MLE engine import: {e}")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    view_dir = Path(args.view_dir)
    instruments, tick2conid, tick2ind, tick2sec = load_universe(Path(args.universe_csv))
    print(f"universe {len(instruments)}")

    # OHLC matice (close + open) v pameti
    close_series, open_series = {}, {}
    for inst in instruments:
        df = load_ohlc(view_dir, tick2conid[inst["ticker"]])
        if df is not None and "close" in df.columns:
            close_series[inst["ticker"]] = df["close"]
            if "open" in df.columns:
                open_series[inst["ticker"]] = df["open"]
    close_matrix = pd.DataFrame(close_series).sort_index()
    open_matrix = pd.DataFrame(open_series).sort_index()
    print(f"close matrix {close_matrix.shape}")

    # IRC archive: TOP10 industries per den (rank_20d<=10)
    idf = pd.read_csv(args.irc_archive, dtype=str, low_memory=False)
    cm = {c.lower(): c for c in idf.columns}
    idf[cm["date"]] = idf[cm["date"]].astype(str).str[:10]
    idf["_lb"] = idf[cm["lookback"]].astype(str).str.replace("d", "", regex=False)
    idf["_rank"] = pd.to_numeric(idf[cm["rank"]], errors="coerce")
    irc20 = idf[(idf["_lb"].isin(["20", "20.0"])) & (idf["_rank"] <= TOP_N)]
    irc_top10_by_date = {}
    for d, grp in irc20.groupby(cm["date"]):
        irc_top10_by_date[d] = set(grp[cm["industry"]].astype(str))

    # obchodni dny: prunik IRC dnu a close_matrix, v overlapu, bez vikend artefaktu
    trading_dates = sorted(
        d for d in irc_top10_by_date
        if OVERLAP_FROM <= d <= OVERLAP_TO and d not in WEEKEND_ARTIFACTS)
    print(f"trading days: {len(trading_dates)}")

    cidx = close_matrix.index
    cidx_str = [str(x.date()) for x in cidx]
    pos_of = {s: i for i, s in enumerate(cidx_str)}

    def fwd_return_cc(tk, tpos, h):
        if tpos + h >= len(cidx):
            return None
        c0 = close_matrix[tk].iloc[tpos] if tk in close_matrix else None
        c1 = close_matrix[tk].iloc[tpos + h] if tk in close_matrix else None
        if c0 is None or c1 is None or pd.isna(c0) or pd.isna(c1) or c0 == 0:
            return None
        return (c1 / c0 - 1) * 100

    def fwd_return_oc(tk, tpos, h):
        # entry open[t+1], exit close[t+h]
        if tpos + h >= len(cidx) or tpos + 1 >= len(cidx):
            return None
        o1 = open_matrix[tk].iloc[tpos + 1] if tk in open_matrix else None
        c1 = close_matrix[tk].iloc[tpos + h] if tk in close_matrix else None
        if o1 is None or c1 is None or pd.isna(o1) or pd.isna(c1) or o1 == 0:
            return None
        return (c1 / o1 - 1) * 100

    # per den: MLE ranky fresh + prirazeni skupin
    # sber: group -> horizon -> metric -> list (ret, ticker, industry, date)
    def new_acc():
        return {g: {h: {"cc": [], "oc": []} for h in FORWARD}
                for g in GROUPS}
    GROUPS = ["universe_baseline", "mle_top10", "irc_top10_industry",
              "mle_top10_x_irc_top10", "mle_top25_x_irc_top10",
              "mle_top50_x_irc_top10"]

    acc = new_acc()
    acc_ex = new_acc()  # bez exceptions
    candidates_per_day = {g: [] for g in GROUPS}
    zero_days = {g: 0 for g in GROUPS}

    for tdate in trading_dates:
        if tdate not in pos_of:
            continue
        tpos = pos_of[tdate]
        run_date = date.fromisoformat(tdate)
        # MLE fresh: 45d slice
        ws = pd.Timestamp(run_date - timedelta(days=START_BUFFER))
        we = pd.Timestamp(run_date)
        cp_slice = {}
        for tk in close_matrix.columns:
            s = close_matrix[tk]
            sub = s[(s.index >= ws) & (s.index <= we)]
            if not sub.empty:
                cp_slice[tk] = sub
        inst_slice = [i for i in instruments if i["ticker"] in cp_slice]
        try:
            rm = compute_rank_matrix(cp_slice, inst_slice, run_date, LOOKBACKS)
        except Exception:
            continue
        rm_idx = rm.set_index("ticker")
        mle_rank = {}
        for tk in rm_idx.index:
            rv = rm_idx.loc[tk, f"rank_{MLE_GATE_LB}d"]
            if not pd.isna(rv):
                mle_rank[tk] = int(rv)

        irc_top10_inds = irc_top10_by_date.get(tdate, set())

        # skupiny clenstvi
        universe_tks = [tk for tk in mle_rank]  # tickery s validnim MLE rank
        mle_t10 = [tk for tk in universe_tks if mle_rank[tk] <= 10]
        mle_t25 = [tk for tk in universe_tks if mle_rank[tk] <= 25]
        mle_t50 = [tk for tk in universe_tks if mle_rank[tk] <= 50]
        irc_tks = [tk for tk in universe_tks
                   if tick2ind.get(tk) in irc_top10_inds]
        m10_irc = [tk for tk in mle_t10 if tick2ind.get(tk) in irc_top10_inds]
        m25_irc = [tk for tk in mle_t25 if tick2ind.get(tk) in irc_top10_inds]
        m50_irc = [tk for tk in mle_t50 if tick2ind.get(tk) in irc_top10_inds]

        group_members = {
            "universe_baseline": universe_tks,
            "mle_top10": mle_t10,
            "irc_top10_industry": irc_tks,
            "mle_top10_x_irc_top10": m10_irc,
            "mle_top25_x_irc_top10": m25_irc,
            "mle_top50_x_irc_top10": m50_irc}

        for g, members in group_members.items():
            candidates_per_day[g].append(len(members))
            if len(members) == 0:
                zero_days[g] += 1
            for tk in members:
                is_ex = tk in EXCEPTIONS
                ind = tick2ind.get(tk, "")
                for h in FORWARD:
                    rcc = fwd_return_cc(tk, tpos, h)
                    roc = fwd_return_oc(tk, tpos, h)
                    if rcc is not None:
                        acc[g][h]["cc"].append((rcc, tk, ind, tdate))
                        if not is_ex:
                            acc_ex[g][h]["cc"].append((rcc, tk, ind, tdate))
                    if roc is not None:
                        acc[g][h]["oc"].append((roc, tk, ind, tdate))
                        if not is_ex:
                            acc_ex[g][h]["oc"].append((roc, tk, ind, tdate))

    # statistiky
    def stats_for(records):
        if not records:
            return None
        rets = np.array([r[0] for r in records])
        n = len(rets)
        mean = float(rets.mean())
        med = float(np.median(rets))
        std = float(rets.std(ddof=1)) if n > 1 else 0.0
        wr = float((rets > 0).mean())
        tstat = float(mean / (std / np.sqrt(n))) if std > 0 and n > 1 else None
        # koncentrace
        by_tk, by_ind = {}, {}
        for r, tk, ind, d in records:
            by_tk[tk] = by_tk.get(tk, 0) + r
            by_ind[ind] = by_ind.get(ind, 0) + r
        top_tk = sorted(by_tk.items(), key=lambda x: -x[1])[:5]
        worst_tk = sorted(by_tk.items(), key=lambda x: x[1])[:5]
        top_ind = sorted(by_ind.items(), key=lambda x: -x[1])[:5]
        # HHI koncentrace (podil sumy top tickeru)
        total_abs = sum(abs(v) for v in by_tk.values()) or 1
        top1_share = abs(top_tk[0][1]) / total_abs if top_tk else 0
        return {"n": n, "mean": round(mean, 4), "median": round(med, 4),
                "std": round(std, 4), "win_rate": round(wr, 4),
                "t_stat": round(tstat, 3) if tstat is not None else None,
                "unique_tickers": len(by_tk),
                "unique_industries": len(by_ind),
                "top1_ticker_share_of_abs": round(top1_share, 4),
                "top_contrib_tickers": [(t, round(v, 2)) for t, v in top_tk],
                "worst_contrib_tickers": [(t, round(v, 2)) for t, v in worst_tk],
                "top_contrib_industries": [(i, round(v, 2)) for i, v in top_ind]}

    def build_result(acc_obj):
        out = {}
        for g in GROUPS:
            out[g] = {"avg_candidates_per_day":
                      round(float(np.mean(candidates_per_day[g])), 2)
                      if candidates_per_day[g] else 0,
                      "days_zero_candidates": zero_days[g],
                      "horizons": {}}
            for h in FORWARD:
                out[g]["horizons"][f"{h}D"] = {
                    "cc": stats_for(acc_obj[g][h]["cc"]),
                    "oc": stats_for(acc_obj[g][h]["oc"])}
        return out

    result_all = build_result(acc)
    result_ex = build_result(acc_ex)

    # EDGE uplift: mle_top10_x_irc_top10 vs mle_top10, vs irc_top10
    def uplift(res, h, metric="cc"):
        edge = res["mle_top10_x_irc_top10"]["horizons"][f"{h}D"][metric]
        mle = res["mle_top10"]["horizons"][f"{h}D"][metric]
        irc = res["irc_top10_industry"]["horizons"][f"{h}D"][metric]
        base = res["universe_baseline"]["horizons"][f"{h}D"][metric]
        return {
            "edge_mean": edge["mean"] if edge else None,
            "mle_mean": mle["mean"] if mle else None,
            "irc_mean": irc["mean"] if irc else None,
            "baseline_mean": base["mean"] if base else None,
            "uplift_vs_mle": round(edge["mean"] - mle["mean"], 4)
            if edge and mle else None,
            "uplift_vs_irc": round(edge["mean"] - irc["mean"], 4)
            if edge and irc else None,
            "uplift_vs_baseline": round(edge["mean"] - base["mean"], 4)
            if edge and base else None}

    uplifts = {f"{h}D": {"all": uplift(result_all, h),
                         "ex": uplift(result_ex, h)} for h in FORWARD}

    # verdikt
    edge_beats_mle = []
    for h in [5, 10, 20]:
        u = uplifts[f"{h}D"]["all"]
        if u["uplift_vs_mle"] is not None:
            edge_beats_mle.append(u["uplift_vs_mle"] > 0)
    edge_beats_mle_ex = []
    for h in [5, 10, 20]:
        u = uplifts[f"{h}D"]["ex"]
        if u["uplift_vs_mle"] is not None:
            edge_beats_mle_ex.append(u["uplift_vs_mle"] > 0)
    # koncentrace check (10D cc)
    edge10 = result_all["mle_top10_x_irc_top10"]["horizons"]["10D"]["cc"]
    concentrated = (edge10 and edge10["top1_ticker_share_of_abs"] > 0.5)

    all_beat = all(edge_beats_mle) if edge_beats_mle else False
    survives_ex = all(edge_beats_mle_ex) if edge_beats_mle_ex else False
    if all_beat and survives_ex and not concentrated:
        verdict = "PASS"
    elif any(edge_beats_mle):
        verdict = "WARN"
    else:
        verdict = "FAIL"

    payload = {"verdict": verdict, "trading_days": len(trading_dates),
               "overlap": [OVERLAP_FROM, OVERLAP_TO],
               "results_all": result_all, "results_ex_exceptions": result_ex,
               "uplifts": uplifts,
               "edge_beats_mle_5_10_20": edge_beats_mle,
               "edge_beats_mle_ex_5_10_20": edge_beats_mle_ex,
               "concentrated_10D": bool(concentrated)}
    _write(payload, mrl, args.out)

    print(f"\n==== EDGE-TEST-01: {verdict} ====")
    print(f"trading_days: {len(trading_dates)}")
    for h in FORWARD:
        u = uplifts[f"{h}D"]["all"]
        print(f"  {h}D cc: edge {u['edge_mean']} | mle {u['mle_mean']} | "
              f"irc {u['irc_mean']} | base {u['baseline_mean']} | "
              f"uplift_vs_mle {u['uplift_vs_mle']}")
    print(f"edge_beats_mle (5/10/20): {edge_beats_mle}")
    print(f"edge_beats_mle_ex: {edge_beats_mle_ex}")
    print(f"concentrated_10D: {concentrated}")
    return 0


def _write(payload, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "EDGE-TEST-01_mle_irc_signal_validation.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    L = ["# EDGE-TEST-01 — MLE x IRC Signal Validation", "",
         f"## Verdikt: {payload['verdict']}", "",
         f"Overlap: {payload['overlap'][0]}..{payload['overlap'][1]} "
         f"({payload['trading_days']} obchodnich dni)", "",
         "MLE ranky fresh z DATA-06. IRC z archivu. Join pres industry.", "",
         "**Vyhrada: t-stat nadhodnoceny (prekryvna okna + cross-section "
         "korelace). Orientacni, ne rigorozni.**", "",
         "## EDGE uplift (close-to-close)", "",
         "| horizon | edge | mle_top10 | irc_top10 | baseline | uplift_vs_mle | uplift_vs_irc |",
         "|---|---|---|---|---|---|---|"]
    for h in FORWARD:
        u = payload["uplifts"][f"{h}D"]["all"]
        L.append(f"| {h}D | {u['edge_mean']} | {u['mle_mean']} | "
                 f"{u['irc_mean']} | {u['baseline_mean']} | "
                 f"{u['uplift_vs_mle']} | {u['uplift_vs_irc']} |")
    L += ["", "## EDGE uplift PO vylouceni exceptions (close-to-close)", "",
          "| horizon | edge_ex | mle_ex | uplift_vs_mle_ex |",
          "|---|---|---|---|"]
    for h in FORWARD:
        u = payload["uplifts"][f"{h}D"]["ex"]
        L.append(f"| {h}D | {u['edge_mean']} | {u['mle_mean']} | "
                 f"{u['uplift_vs_mle']} |")

    L += ["", "## Detailni statistiky per skupina (close-to-close)", ""]
    for g in ["universe_baseline", "mle_top10", "irc_top10_industry",
              "mle_top10_x_irc_top10", "mle_top25_x_irc_top10",
              "mle_top50_x_irc_top10"]:
        gr = payload["results_all"][g]
        L.append(f"### {g}")
        L.append(f"- avg_candidates_per_day: {gr['avg_candidates_per_day']}")
        L.append(f"- days_zero_candidates: {gr['days_zero_candidates']}")
        for h in FORWARD:
            s = gr["horizons"][f"{h}D"]["cc"]
            if s:
                L.append(f"- {h}D: n={s['n']} mean={s['mean']} med={s['median']} "
                         f"wr={s['win_rate']} std={s['std']} t={s['t_stat']} "
                         f"| uniq_tk={s['unique_tickers']} "
                         f"uniq_ind={s['unique_industries']} "
                         f"top1_share={s['top1_ticker_share_of_abs']}")
        # koncentrace detail (10D)
        s10 = gr["horizons"]["10D"]["cc"]
        if s10:
            L.append(f"- 10D top contrib tickers: {s10['top_contrib_tickers']}")
            L.append(f"- 10D worst contrib tickers: {s10['worst_contrib_tickers']}")
            L.append(f"- 10D top contrib industries: {s10['top_contrib_industries']}")
        L.append("")

    L += ["## Klicove otazky", "",
          f"- MLE×IRC > MLE TOP10 only (5/10/20D): "
          f"{payload['edge_beats_mle_5_10_20']}",
          f"- prezije po vylouceni exceptions: "
          f"{payload['edge_beats_mle_ex_5_10_20']}",
          f"- koncentrovany 10D (top1 ticker >50% abs): "
          f"{payload['concentrated_10D']}", "",
          "## PASS/WARN/FAIL", "",
          "- PASS: edge > MLE TOP10 na 5/10/20D, neni koncentrovany, "
          "prezije bez exceptions.",
          "- WARN: edge existuje ale slaby/koncentrovany/nekonzistentni.",
          "- FAIL: edge <= MLE TOP10, IRC filtr nepridava hodnotu.", "",
          "## Vyhrady (souhrn)", "",
          "- t-stat nadhodnoceny (nezavislost porusena).",
          "- signal diagnostic, NE tradable backtest (bez nakladu, slippage).",
          "- metrika B (next-open) je aproximace, ne realny fill.",
          "- MLE ranky fresh z DATA-06 (survivorship: 503 soucasnych).",
          "- overlap 245 dni = kratky sample pro edge inference.", ""]
    (out_dir / "EDGE-TEST-01_mle_irc_signal_validation.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
