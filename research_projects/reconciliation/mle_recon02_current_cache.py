"""
mle_recon02_current_cache.py — MLE-RECON-02 current-cache return reconciliation.

READ-ONLY. Hlavni reference = SOUCASNA MDSM cache (ne stary archiv).
Porovna MLE returns/ranky pocitane ze soucasne MDSM cache vs z DATA-06,
oboje pres STEJNY MLE engine. Archiv jen sekundarni audit.

NEDELA: IRC, backtest, MLE archive overwrite, API/TWS, zmenu dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\mle_recon02_current_cache.py

Metoda:
    Pro kazdy den v range:
      compute_rank_matrix(MDSM_cache_prices, ...)  -> ranky_mdsm
      compute_rank_matrix(DATA06_prices, ...)      -> ranky_data06
    Porovnat ret_Nd, rank_Nd, TOP10 overlap.
    Sekundarne: vs archiv, rozdil = archive_compute_mismatch pokud
      computed_mdsm == computed_data06 ale arch_ret se lisi.

Pouziva stejny universe/order, lookbacks [1..10,20], 45d okno jako MLE.

Edge cases / predpoklady:
    - MDSM cache range OMEZENY (~503 dni). Pro dny, kde MDSM cache nema
      45d okno, ticker vypadne z MDSM compute -> porovnava se jen prunik
      tickeru pritomnych v OBOU (mdsm i data06) compute.
    - 45d okno: run_date - 45 kalendarnich dni (jako MLE start_buffer).
      Engine dostane oriznute okno -> shodne s MLE original chovanim.
    - tie-break: universe order (dict order).
    - engine import z MLE.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

RANGE_FROM, RANGE_TO = "2025-07-09", "2026-07-04"
LOOKBACKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
GATE_LB = 10
START_BUFFER = 45
RET_EXACT, RET_MICRO = 0.0001, 0.01

CORP_ACTION = {"KLAC", "CRWD", "HON", "APTV", "DD"}
ALIAS = {"NWS", "GOOG", "FOX"}
MANUAL = {"BDX"}
INSUFFICIENT = {"EXE", "PSKY", "Q", "SNDK"}


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def category(tk):
    if tk in CORP_ACTION:
        return "corporate_action_cache_artifact"
    if tk in ALIAS:
        return "identity_alias_class_mismatch"
    if tk in MANUAL:
        return "needs_manual_review_or_unmapped_adjustment_artifact"
    if tk in INSUFFICIENT:
        return "insufficient_history_not_in_archive"
    return "clean"


def load_universe(ucsv):
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    instruments = []
    tick2conid = {}
    for _, r in df.iterrows():
        if not is_active(r[acol]):
            continue
        tk = str(r[tcol]).strip().upper()
        instruments.append({"conid": int(float(r[ccol])), "ticker": tk,
                            "sector": "", "industry": "", "subcategory": ""})
        tick2conid[tk] = str(r[ccol])
    return instruments, tick2conid


def load_series(dir_path, conid):
    f = dir_path / f"{conid}_D1.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    if "close" not in df.columns:
        return None
    df.index = pd.to_datetime(df.index).normalize()
    return df["close"].sort_index()


def build_close_prices(dir_path, instruments, tick2conid):
    cp = {}
    for inst in instruments:
        s = load_series(dir_path, tick2conid[inst["ticker"]])
        if s is not None and not s.empty:
            cp[inst["ticker"]] = s
    return cp


def slice_window(cp, run_date):
    ws = pd.Timestamp(run_date - timedelta(days=START_BUFFER))
    we = pd.Timestamp(run_date)
    out = {}
    for tk, s in cp.items():
        sub = s[(s.index >= ws) & (s.index <= we)]
        if not sub.empty:
            out[tk] = sub
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mle-root",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--mdsm-prices",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\cache\prices")
    ap.add_argument("--mle-archive",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive\rank_matrix_archive.csv")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--range-from", default=RANGE_FROM)
    ap.add_argument("--range-to", default=RANGE_TO)
    ap.add_argument("--max-days", type=int, default=0)
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
    instruments, tick2conid = load_universe(Path(args.universe_csv))
    print(f"universe {len(instruments)}")

    cp_mdsm = build_close_prices(Path(args.mdsm_prices), instruments, tick2conid)
    cp_data06 = build_close_prices(Path(args.view_dir), instruments, tick2conid)
    print(f"MDSM close_prices {len(cp_mdsm)}, DATA-06 {len(cp_data06)}")

    # archiv (sekundarni audit)
    adf = pd.read_csv(args.mle_archive, dtype={"date": str}, low_memory=False)
    adf["ticker"] = adf["ticker"].astype(str).str.upper()
    adf = adf[(adf["date"] >= args.range_from) & (adf["date"] <= args.range_to)]
    adf_idx = adf.set_index(["date", "ticker"])
    arch_dates = sorted(adf["date"].unique())
    if args.max_days > 0:
        arch_dates = arch_dates[:args.max_days]
    print(f"dni: {len(arch_dates)}")

    stats = {"n_dates": len(arch_dates), "range": [args.range_from, args.range_to],
             "per_lookback": {lb: {"compared": 0, "ret_exact": 0,
                                   "ret_micro": 0, "ret_mismatch": 0,
                                   "rank_exact": 0, "rank_total": 0}
                              for lb in LOOKBACKS},
             "top10_overlap_sum": 0.0, "top10_overlap_days": 0,
             "mdsm_only_ranked_total": 0, "data06_only_ranked_total": 0,
             "archive_audit": {"archive_compute_mismatch": 0,
                               "arch_matches_mdsm": 0,
                               "arch_matches_data06": 0,
                               "arch_matches_neither": 0},
             "top_mismatches": []}
    mism = []

    for tdate in arch_dates:
        run_date = date.fromisoformat(tdate)
        m_slice = slice_window(cp_mdsm, run_date)
        d_slice = slice_window(cp_data06, run_date)
        m_inst = [i for i in instruments if i["ticker"] in m_slice]
        d_inst = [i for i in instruments if i["ticker"] in d_slice]
        if not m_slice or not d_slice:
            continue
        try:
            rm_m = compute_rank_matrix(m_slice, m_inst, run_date, LOOKBACKS)
            rm_d = compute_rank_matrix(d_slice, d_inst, run_date, LOOKBACKS)
        except Exception as e:  # noqa: BLE001
            stats.setdefault("compute_errors", []).append(
                {"date": tdate, "error": str(e)})
            continue
        rm_m_idx = rm_m.set_index("ticker")
        rm_d_idx = rm_d.set_index("ticker")

        for lb in LOOKBACKS:
            rcol, retcol = f"rank_{lb}d", f"ret_{lb}d"
            # prunik tickeru s ne-NaN rank v OBOU
            m_ranked = {t for t in rm_m_idx.index
                        if not pd.isna(rm_m_idx.loc[t, rcol])}
            d_ranked = {t for t in rm_d_idx.index
                        if not pd.isna(rm_d_idx.loc[t, rcol])}
            common = m_ranked & d_ranked
            if lb == GATE_LB:
                stats["mdsm_only_ranked_total"] += len(m_ranked - d_ranked)
                stats["data06_only_ranked_total"] += len(d_ranked - m_ranked)

            pl = stats["per_lookback"][lb]
            for tk in common:
                m_ret = rm_m_idx.loc[tk, retcol]
                d_ret = rm_d_idx.loc[tk, retcol]
                m_rank = rm_m_idx.loc[tk, rcol]
                d_rank = rm_d_idx.loc[tk, rcol]
                if pd.isna(m_ret) or pd.isna(d_ret):
                    continue
                pl["compared"] += 1
                rdiff = abs(float(m_ret) - float(d_ret))
                if rdiff <= RET_EXACT:
                    pl["ret_exact"] += 1
                elif rdiff <= RET_MICRO:
                    pl["ret_micro"] += 1
                else:
                    pl["ret_mismatch"] += 1
                pl["rank_total"] += 1
                rank_ok = int(m_rank) == int(d_rank)
                if rank_ok:
                    pl["rank_exact"] += 1
                elif lb == GATE_LB:
                    mism.append({"date": tdate, "ticker": tk,
                                 "mdsm_rank": int(m_rank),
                                 "data06_rank": int(d_rank),
                                 "mdsm_ret": round(float(m_ret), 2),
                                 "data06_ret": round(float(d_ret), 2),
                                 "category": category(tk)})

                # archive audit (gate lookback)
                if lb == GATE_LB:
                    try:
                        a_ret = float(adf_idx.loc[(tdate, tk), retcol])
                        m_eq = abs(a_ret - float(m_ret)) <= RET_MICRO
                        d_eq = abs(a_ret - float(d_ret)) <= RET_MICRO
                        md_eq = rdiff <= RET_MICRO
                        aud = stats["archive_audit"]
                        if md_eq and not m_eq and not d_eq:
                            aud["archive_compute_mismatch"] += 1
                        elif m_eq and d_eq:
                            aud["arch_matches_mdsm"] += 1
                            aud["arch_matches_data06"] += 1
                        elif m_eq:
                            aud["arch_matches_mdsm"] += 1
                        elif d_eq:
                            aud["arch_matches_data06"] += 1
                        else:
                            aud["arch_matches_neither"] += 1
                    except (KeyError, TypeError, ValueError):
                        pass

            # TOP10 overlap (gate)
            if lb == GATE_LB and common:
                m_top10 = {t for t in common
                           if int(rm_m_idx.loc[t, rcol]) <= 10}
                d_top10 = {t for t in common
                           if int(rm_d_idx.loc[t, rcol]) <= 10}
                if m_top10:
                    stats["top10_overlap_sum"] += \
                        len(m_top10 & d_top10) / len(m_top10)
                    stats["top10_overlap_days"] += 1

    # finalizace rates
    for lb, pl in stats["per_lookback"].items():
        n = pl["compared"] or 1
        pl["ret_exact_rate"] = round(pl["ret_exact"] / n, 6)
        pl["ret_micro_rate"] = round(pl["ret_micro"] / n, 6)
        pl["ret_mismatch_rate"] = round(pl["ret_mismatch"] / n, 6)
        rt = pl["rank_total"] or 1
        pl["rank_exact_rate"] = round(pl["rank_exact"] / rt, 6)
    if stats["top10_overlap_days"]:
        stats["top10_overlap_rate"] = round(
            stats["top10_overlap_sum"] / stats["top10_overlap_days"], 4)
    mism.sort(key=lambda m: abs(m["mdsm_ret"] - m["data06_ret"]), reverse=True)
    catcount = {}
    for m in mism:
        catcount[m["category"]] = catcount.get(m["category"], 0) + 1
    stats["gate10_mismatch_by_category"] = catcount
    stats["top_mismatches"] = mism[:30]
    stats["gate10_mismatch_total"] = len(mism)

    # verdikt (gate10, DATA-06 vs MDSM current cache)
    g = stats["per_lookback"][GATE_LB]
    g_ret_ok = g["ret_exact_rate"] + g["ret_micro_rate"]
    clean_mism = catcount.get("clean", 0)
    if g_ret_ok >= 0.999 and g["rank_exact_rate"] >= 0.99 and clean_mism <= 5:
        verdict = "PASS"
    elif g["rank_exact_rate"] >= 0.98:
        verdict = "WARN"
    else:
        verdict = "FAIL"
    stats["verdict"] = verdict

    _write(stats, mrl, args.out)

    print(f"\n==== MLE-RECON-02: {verdict} ====")
    print(f"top10_overlap_rate: {stats.get('top10_overlap_rate')}")
    print(f"mdsm_only_ranked: {stats['mdsm_only_ranked_total']}, "
          f"data06_only_ranked: {stats['data06_only_ranked_total']}")
    for lb in [1, 5, 10, 20]:
        pl = stats["per_lookback"][lb]
        print(f"  L{lb}: ret_exact {pl['ret_exact_rate']} "
              f"micro {pl['ret_micro_rate']} mismatch {pl['ret_mismatch_rate']} "
              f"| rank_exact {pl['rank_exact_rate']}")
    print(f"gate10 mismatch_by_category: {catcount}")
    print(f"archive_audit: {stats['archive_audit']}")
    return 0


def _write(stats, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-RECON-02_current_cache_return_reconciliation.json").write_text(
        json.dumps(stats, indent=2, default=str), encoding="utf-8")
    L = ["# MLE-RECON-02 — Current-Cache Return Reconciliation", "",
         f"## Verdikt: {stats['verdict']}", "",
         f"Range: {stats['range'][0]} .. {stats['range'][1]} "
         f"({stats['n_dates']} dni)", "",
         "Hlavni reference: SOUCASNA MDSM cache vs DATA-06 (stejny MLE engine).",
         "Archiv jen sekundarni audit.", "",
         f"- top10_overlap_rate: {stats.get('top10_overlap_rate')}",
         f"- mdsm_only_ranked_total: {stats['mdsm_only_ranked_total']}",
         f"- data06_only_ranked_total: {stats['data06_only_ranked_total']}", "",
         "## Per-lookback (MDSM current vs DATA-06)", "",
         "| lookback | compared | ret_exact | ret_micro | ret_mismatch | rank_exact |",
         "|---|---|---|---|---|---|"]
    for lb in LOOKBACKS:
        pl = stats["per_lookback"][lb]
        L.append(f"| {lb}d | {pl['compared']} | {pl['ret_exact_rate']} | "
                 f"{pl['ret_micro_rate']} | {pl['ret_mismatch_rate']} | "
                 f"{pl['rank_exact_rate']} |")
    L += ["", "## Gate (lookback 10)", "",
          f"- mismatch_total: {stats['gate10_mismatch_total']}",
          f"- mismatch_by_category: {stats['gate10_mismatch_by_category']}", "",
          "### Top mismatches (DATA-06 vs MDSM current)", ""]
    for m in stats["top_mismatches"][:20]:
        L.append(f"- {m['date']} {m['ticker']}: mdsm_rank={m['mdsm_rank']} "
                 f"data06_rank={m['data06_rank']} mdsm_ret={m['mdsm_ret']} "
                 f"data06_ret={m['data06_ret']} [{m['category']}]")
    aud = stats["archive_audit"]
    L += ["", "## Archive audit (sekundarni)", "",
          f"- archive_compute_mismatch (computed_mdsm==data06, arch se lisi): "
          f"{aud['archive_compute_mismatch']}",
          f"- arch_matches_mdsm: {aud['arch_matches_mdsm']}",
          f"- arch_matches_data06: {aud['arch_matches_data06']}",
          f"- arch_matches_neither: {aud['arch_matches_neither']}", "",
          "## Interpretace", "",
          "- ret/rank DATA-06 vs MDSM current cache vysoke -> Sharadar view",
          "  reprodukuje soucasnou MDSM cache (cenova kompatibilita).",
          "- archive_compute_mismatch > 0 -> archiv zastaraly vuci re-adjusted",
          "  cache (ocekavane, ne chyba recon).", "",
          "## Vyhrady", "",
          "- MDSM cache range omezeny; dny bez 45d okna v cache preskoceny.",
          "- porovnava se prunik tickeru ranked v OBOU compute.",
          "- 45d okno, tie-break universe order, engine z MLE.", ""]
    (out_dir / "MLE-RECON-02_current_cache_return_reconciliation.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
