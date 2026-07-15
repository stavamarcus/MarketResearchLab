"""
mle_recon01b_rank_diagnostics.py — MLE-RECON-01B targeted rank diagnostics.

READ-ONLY. Vysvetli rozpor ret_exact vysoky vs rank_exact nizky z
MLE-RECON-01. Analyzuje 2 dny (clean + contaminated), lookback 10.

NEDELA: MLE archive overwrite, IRC recon, backtest, API/TWS, zmenu dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\mle_recon01b_rank_diagnostics.py

Testy:
    1. archive vs recon ranked ticker count + intersection
    2. rank_diff distribuce (konstantni posun vs chaos)
    3. ret exact but rank mismatch count
    4. clean re-ranking: vyhod known exceptions, prepocti rank jen mezi
       clean tickery -> pokud sedi, rank mismatch = amplification efekt

Exception tickery (z PRICE-RECON + MLE-RECON):
    KLAC,CRWD,HON,APTV,DD (corporate action),
    NWS,GOOG,FOX (alias), BDX (manual review)
Insufficient history: EXE,PSKY,Q,SNDK

Edge cases:
    - clean re-ranking pouziva Sharadar recon ret i archiv ret zvlast,
      prepocita rank JEN mezi clean tickery (dense rank, sestupne).
    - engine import z MLE (sys.path).
    - lookback 10 primarni.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

LOOKBACKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
GATE_LB = 10
CORP_ACTION = {"KLAC", "CRWD", "HON", "APTV", "DD"}
ALIAS = {"NWS", "GOOG", "FOX"}
MANUAL = {"BDX"}
INSUFFICIENT = {"EXE", "PSKY", "Q", "SNDK"}
EXCEPTIONS = CORP_ACTION | ALIAS | MANUAL | INSUFFICIENT
CLEAN_DAY = "2026-03-20"
CONTAM_DAY = "2026-06-12"  # KLAC split


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_universe(ucsv):
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    out = []
    for _, r in df.iterrows():
        if not is_active(r[acol]):
            continue
        out.append({"conid": int(float(r[ccol])),
                    "ticker": str(r[tcol]).strip().upper(),
                    "sector": "", "industry": "", "subcategory": ""})
    return out


def load_close(view_dir, conid):
    f = view_dir / f"{conid}_D1.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    if "close" not in df.columns:
        return None
    df.index = pd.to_datetime(df.index).normalize()
    return df["close"].sort_index()


def dense_rank_desc(ret_map):
    """Prirad rank (1=nejvyssi ret) jen mezi tickery s ne-None ret."""
    valid = {t: r for t, r in ret_map.items() if r is not None
             and not pd.isna(r)}
    ordered = sorted(valid, key=lambda t: valid[t], reverse=True)
    return {t: i + 1 for i, t in enumerate(ordered)}


def analyze_day(tdate, compute_rank_matrix, close_prices, instruments,
                adf_idx, arch_dates_set):
    out = {"date": tdate}
    if tdate not in arch_dates_set:
        out["error"] = "den neni v archivu"
        return out
    run_date = date.fromisoformat(tdate)
    rm = compute_rank_matrix(close_prices=close_prices,
                             instruments=instruments,
                             target_date=run_date, lookbacks=LOOKBACKS)
    rm_idx = rm.set_index("ticker")
    rcol, retcol = f"rank_{GATE_LB}d", f"ret_{GATE_LB}d"

    # archiv tickery pro tento den
    try:
        arch_day = adf_idx.xs(tdate, level="date")
    except KeyError:
        out["error"] = "den neni v archivu (xs)"
        return out

    # ranked counts
    recon_ranked = {t: rm_idx.loc[t, rcol] for t in rm_idx.index
                    if not pd.isna(rm_idx.loc[t, rcol])}
    arch_ranked = {t: arch_day.loc[t, rcol] for t in arch_day.index
                   if rcol in arch_day.columns
                   and not pd.isna(arch_day.loc[t, rcol])}
    out["archive_ranked_count"] = len(arch_ranked)
    out["recon_ranked_count"] = len(recon_ranked)
    inter = set(arch_ranked) & set(recon_ranked)
    out["intersection_count"] = len(inter)
    out["archive_only_ranked"] = sorted(set(arch_ranked) - set(recon_ranked))[:20]
    out["recon_only_ranked"] = sorted(set(recon_ranked) - set(arch_ranked))[:20]

    # rank_diff distribuce (na intersekci)
    diffs = []
    ret_exact_rank_mism = 0
    ret_mism_rank_mism = 0
    rows = []
    for t in inter:
        ar = int(arch_ranked[t]); rr = int(recon_ranked[t])
        aret = arch_day.loc[t, retcol] if retcol in arch_day.columns else None
        rret = rm_idx.loc[t, retcol]
        rank_diff = rr - ar
        diffs.append(rank_diff)
        ret_diff = (abs(float(aret) - float(rret))
                    if aret is not None and not pd.isna(aret)
                    and not pd.isna(rret) else None)
        if rank_diff != 0:
            if ret_diff is not None and ret_diff <= 0.0001:
                ret_exact_rank_mism += 1
            elif ret_diff is not None and ret_diff > 0.01:
                ret_mism_rank_mism += 1
        cat = "clean"
        if t in CORP_ACTION:
            cat = "corporate_action_cache_artifact"
        elif t in ALIAS:
            cat = "identity_alias_class_mismatch"
        elif t in MANUAL:
            cat = "needs_manual_review_BDX"
        elif t in INSUFFICIENT:
            cat = "insufficient_history"
        rows.append({"ticker": t, "arch_ret": None if aret is None or pd.isna(aret) else round(float(aret),2),
                     "recon_ret": None if pd.isna(rret) else round(float(rret),2),
                     "ret_diff": None if ret_diff is None else round(ret_diff,4),
                     "arch_rank": ar, "recon_rank": rr,
                     "rank_diff": rank_diff, "category": cat})
    out["ret_exact_but_rank_mismatch"] = ret_exact_rank_mism
    out["ret_mismatch_and_rank_mismatch"] = ret_mism_rank_mism
    # rank_diff distribuce
    if diffs:
        sdiffs = pd.Series(diffs)
        out["rank_diff_distribution"] = {
            "min": int(sdiffs.min()), "max": int(sdiffs.max()),
            "mean": round(float(sdiffs.mean()), 2),
            "abs_le_1": int((sdiffs.abs() <= 1).sum()),
            "abs_le_5": int((sdiffs.abs() <= 5).sum()),
            "abs_gt_50": int((sdiffs.abs() > 50).sum()),
            "zero": int((sdiffs == 0).sum())}
    # top 50 rank_diff
    rows.sort(key=lambda r: abs(r["rank_diff"]), reverse=True)
    out["top_50_rank_diff"] = rows[:50]

    # ── CLEAN RE-RANKING: vyhod exceptions, prepocti rank jen clean ──
    arch_ret_clean = {t: arch_day.loc[t, retcol] for t in arch_day.index
                      if t not in EXCEPTIONS and retcol in arch_day.columns
                      and not pd.isna(arch_day.loc[t, retcol])}
    recon_ret_clean = {t: rm_idx.loc[t, retcol] for t in rm_idx.index
                       if t not in EXCEPTIONS
                       and not pd.isna(rm_idx.loc[t, retcol])}
    arch_clean_rank = dense_rank_desc(arch_ret_clean)
    recon_clean_rank = dense_rank_desc(recon_ret_clean)
    clean_inter = set(arch_clean_rank) & set(recon_clean_rank)
    clean_match = sum(1 for t in clean_inter
                      if arch_clean_rank[t] == recon_clean_rank[t])
    clean_mismatch_rows = [
        {"ticker": t, "arch_clean_rank": arch_clean_rank[t],
         "recon_clean_rank": recon_clean_rank[t],
         "diff": recon_clean_rank[t] - arch_clean_rank[t]}
        for t in clean_inter if arch_clean_rank[t] != recon_clean_rank[t]]
    clean_mismatch_rows.sort(key=lambda r: abs(r["diff"]), reverse=True)
    out["clean_reranking"] = {
        "clean_ticker_count": len(clean_inter),
        "clean_rank_match": clean_match,
        "clean_rank_mismatch": len(clean_inter) - clean_match,
        "clean_match_rate": round(clean_match / len(clean_inter), 4)
        if clean_inter else None,
        "top_clean_mismatch": clean_mismatch_rows[:30]}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mle-root",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--mle-archive",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive\rank_matrix_archive.csv")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--clean-day", default=CLEAN_DAY)
    ap.add_argument("--contam-day", default=CONTAM_DAY)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
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
    instruments = load_universe(Path(args.universe_csv))
    close_prices = {}
    for inst in instruments:
        s = load_close(view_dir, inst["conid"])
        if s is not None and not s.empty:
            close_prices[inst["ticker"]] = s
    print(f"universe {len(instruments)}, close_prices {len(close_prices)}")

    adf = pd.read_csv(args.mle_archive, dtype={"date": str}, low_memory=False)
    adf["ticker"] = adf["ticker"].astype(str).str.upper()
    adf_idx = adf.set_index(["date", "ticker"])
    arch_dates = set(adf["date"].unique())

    results = {}
    for label, day in [("clean_day", args.clean_day),
                       ("contaminated_day", args.contam_day)]:
        print(f"analyza {label}: {day}")
        results[label] = analyze_day(day, compute_rank_matrix, close_prices,
                                     instruments, adf_idx, arch_dates)

    _write(results, mrl, args.out)

    for label, r in results.items():
        print(f"\n== {label} ({r['date']}) ==")
        if r.get("error"):
            print(f"  ERROR: {r['error']}"); continue
        print(f"  ranked: archive {r['archive_ranked_count']} "
              f"recon {r['recon_ranked_count']} "
              f"intersection {r['intersection_count']}")
        print(f"  ret_exact_but_rank_mismatch: {r['ret_exact_but_rank_mismatch']}")
        cr = r["clean_reranking"]
        print(f"  clean_reranking: {cr['clean_ticker_count']} tickeru, "
              f"match {cr['clean_rank_match']}, "
              f"mismatch {cr['clean_rank_mismatch']}, "
              f"rate {cr['clean_match_rate']}")
    return 0


def _write(results, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-RECON-01B_rank_diagnostics.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")
    L = ["# MLE-RECON-01B — Rank Diagnostics", ""]
    for label, r in results.items():
        L.append(f"## {label} ({r.get('date')})")
        if r.get("error"):
            L.append(f"- ERROR: {r['error']}"); L.append(""); continue
        L += [f"- archive_ranked_count: {r['archive_ranked_count']}",
              f"- recon_ranked_count: {r['recon_ranked_count']}",
              f"- intersection_count: {r['intersection_count']}",
              f"- archive_only_ranked: {r['archive_only_ranked']}",
              f"- recon_only_ranked: {r['recon_only_ranked']}",
              f"- ret_exact_but_rank_mismatch: {r['ret_exact_but_rank_mismatch']}",
              f"- ret_mismatch_and_rank_mismatch: {r['ret_mismatch_and_rank_mismatch']}",
              f"- rank_diff_distribution: {r.get('rank_diff_distribution')}", ""]
        cr = r["clean_reranking"]
        L += ["### Clean re-ranking (bez exceptions)",
              f"- clean_ticker_count: {cr['clean_ticker_count']}",
              f"- clean_rank_match: {cr['clean_rank_match']}",
              f"- clean_rank_mismatch: {cr['clean_rank_mismatch']}",
              f"- clean_match_rate: {cr['clean_match_rate']}", ""]
        if cr["top_clean_mismatch"]:
            L.append("- top clean mismatch:")
            for m in cr["top_clean_mismatch"][:15]:
                L.append(f"  - {m['ticker']}: arch={m['arch_clean_rank']} "
                         f"recon={m['recon_clean_rank']} diff={m['diff']}")
        L += ["", "### Top 15 rank_diff (s exceptions)", ""]
        for m in r.get("top_50_rank_diff", [])[:15]:
            L.append(f"- {m['ticker']}: arch_rank={m['arch_rank']} "
                     f"recon_rank={m['recon_rank']} diff={m['rank_diff']} "
                     f"arch_ret={m['arch_ret']} recon_ret={m['recon_ret']} "
                     f"[{m['category']}]")
        L.append("")
    L += ["## Interpretace", "",
          "- clean_match_rate ~1.0 -> rank mismatch = amplification efekt",
          "  exception tickeru (ne bug).",
          "- clean_match_rate nizky -> bug v universe/rank/porovnani.",
          "- ranked counts nesedi -> ranking universe / NaN / missing price.",
          "- ret sedi ale rank ne i po clean -> comparator bug.", ""]
    (out_dir / "MLE-RECON-01B_rank_diagnostics.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
