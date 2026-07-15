"""
mle_recon01d_archive_intersection.py — MLE-RECON-01D.

READ-ONLY. Archive-ranked intersection reconciliation. Pro kazdy
date/lookback pouzije POUZE tickery, ktere archiv skutecne rankoval,
a na te mnozine prepocita recon rank z recon ret.

NEDELA: MLE archive overwrite, IRC, backtest, API/TWS, zmenu dat.
NEPREPISUJE puvodni MLE-RECON-01.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\mle_recon01d_archive_intersection.py

Metoda:
    ret = round(((close_now/close_past)-1)*100, 2)  [identicky s MLE engine]
    recon rank = poradi dle ret (sestupne) JEN mezi archive_set tickery
    tie-break: universe order z MLE universe CSV (jako MLE engine dict order)

Dva rezimy:
    A) archive_ranked_raw: vsechny archive-ranked tickery vc. exceptions
    B) exception_neutral_clean: bez KLAC/CRWD/HON/APTV/DD/NWS/GOOG/FOX/BDX

Edge cases / predpoklady:
    - recon rank se POCITA zde (ne z compute_rank_matrix), aby ranking
      universe = archive_set. Vzorec identicky s MLE engine.
    - tie-break: pri shodnem ret poradi dle universe order (MLE engine
      pouziva dict insertion order = universe order). REPLIKACE tohoto
      je nutna pro shodu rank.
    - close_past: target_idx - lookback v OBCHODNICH dnech z DATA-06 serie
      daneho tickeru. MLE engine pouziva SPOLECNY price_matrix index
      (prunik/union vsech tickeru). ZDE POZOR: pokud pocitam past_idx
      per ticker z jeho vlastni serie, muze se lisit od MLE spolecneho
      indexu pri chybejicich dnech. -> pouzivam SPOLECNY obchodni kalendar
      z archive dat (vsechny archive dates) pro konzistenci.
    - EXE/PSKY/Q/SNDK: nejsou v archivu -> automaticky mimo archive_set.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

RANGE_FROM, RANGE_TO = "2025-07-09", "2026-07-04"
LOOKBACKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
GATE_LB = 10
RET_EXACT, RET_MICRO = 0.0001, 0.01

CORP_ACTION = {"KLAC", "CRWD", "HON", "APTV", "DD"}
ALIAS = {"NWS", "GOOG", "FOX"}
MANUAL = {"BDX"}
INSUFFICIENT = {"EXE", "PSKY", "Q", "SNDK"}
CLEAN_EXCLUDE = CORP_ACTION | ALIAS | MANUAL


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def category(ticker):
    if ticker in CORP_ACTION:
        return "corporate_action_cache_artifact"
    if ticker in ALIAS:
        return "identity_alias_class_mismatch"
    if ticker in MANUAL:
        return "needs_manual_review_or_unmapped_adjustment_artifact"
    if ticker in INSUFFICIENT:
        return "insufficient_history_not_in_archive"
    return "clean"


def load_universe_order(ucsv):
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    order = {}
    tick2conid = {}
    idx = 0
    for _, r in df.iterrows():
        if not is_active(r[acol]):
            continue
        tk = str(r[tcol]).strip().upper()
        order[tk] = idx
        tick2conid[tk] = str(r[ccol])
        idx += 1
    return order, tick2conid


def load_close_matrix(view_dir, tick2conid, order):
    """Nacti close vsech tickeru do jednoho DataFrame (date x ticker).
    Sloupce v poradi universe (order)."""
    series = {}
    for tk in sorted(order, key=lambda t: order[t]):
        conid = tick2conid.get(tk)
        if not conid:
            continue
        f = view_dir / f"{conid}_D1.parquet"
        if not f.exists():
            continue
        df = pd.read_parquet(f)
        if "close" not in df.columns:
            continue
        df.index = pd.to_datetime(df.index).normalize()
        series[tk] = df["close"].sort_index()
    matrix = pd.DataFrame(series)  # union index
    matrix = matrix.sort_index()
    return matrix


def recon_rank_on_set(matrix, tdate_ts, lookback, archive_set, order):
    """Spocti recon ret + rank JEN mezi archive_set tickery.
    Vraci dict ticker -> (ret, rank). Rank dle ret sestupne, tie-break
    universe order."""
    idx = matrix.index
    avail = idx[idx <= tdate_ts]
    if len(avail) == 0:
        return {}
    target_ts = avail[-1]
    tpos = idx.get_loc(target_ts)
    ppos = tpos - lookback
    if ppos < 0:
        return {}
    past_ts = idx[ppos]
    now = matrix.loc[target_ts]
    past = matrix.loc[past_ts]

    rets = {}
    for tk in archive_set:
        if tk not in matrix.columns:
            continue
        cn, cp = now.get(tk), past.get(tk)
        if pd.isna(cn) or pd.isna(cp) or cp == 0:
            continue
        rets[tk] = round(((cn / cp) - 1) * 100, 2)
    # rank: sestupne dle ret, tie-break universe order (nizsi order = driv)
    ordered = sorted(rets, key=lambda t: (-rets[t], order.get(t, 1e9)))
    return {tk: (rets[tk], i + 1) for i, tk in enumerate(ordered)}


def analyze(matrix, order, adf, mode_exclude):
    """Projdi archiv, per date/lookback prepocti recon rank na archive_set.
    mode_exclude: set tickeru k vylouceni (clean rezim) nebo prazdny."""
    stats = {"compared_cells": 0, "ret_exact": 0, "ret_micro": 0,
             "ret_mismatch": 0, "rank_exact": 0, "rank_mismatch": 0,
             "gate10_rank_exact": 0, "gate10_rank_total": 0,
             "archive_ranked_counts": [], "recon_missing": 0,
             "top10_overlap_sum": 0, "top10_overlap_days": 0,
             "mismatches": []}
    # archiv indexovan
    for tdate, grp in adf.groupby("date"):
        tdate_ts = pd.Timestamp(tdate)
        for lb in LOOKBACKS:
            rcol, retcol = f"rank_{lb}d", f"ret_{lb}d"
            if rcol not in grp.columns:
                continue
            sub = grp[grp[rcol].notna() & grp[retcol].notna()]
            arch_set = set(sub["ticker"])
            if mode_exclude:
                arch_set = arch_set - mode_exclude
            if not arch_set:
                continue
            # recon rank na arch_set
            recon = recon_rank_on_set(matrix, tdate_ts, lb, arch_set, order)
            # v clean rezimu: prepocti i ARCHIV rank jen mezi arch_set
            if mode_exclude:
                arch_ret = {r["ticker"]: r[retcol] for _, r in sub.iterrows()
                            if r["ticker"] in arch_set}
                arch_ordered = sorted(
                    arch_ret, key=lambda t: (-float(arch_ret[t]),
                                             order.get(t, 1e9)))
                arch_rank = {t: i + 1 for i, t in enumerate(arch_ordered)}
            else:
                arch_rank = {r["ticker"]: int(r[rcol])
                             for _, r in sub.iterrows()
                             if r["ticker"] in arch_set}
                arch_ret = {r["ticker"]: float(r[retcol])
                            for _, r in sub.iterrows()
                            if r["ticker"] in arch_set}

            if lb == GATE_LB:
                stats["archive_ranked_counts"].append(len(arch_set))

            # TOP10 overlap (gate lookback)
            if lb == GATE_LB:
                arch_top10 = {t for t, r in arch_rank.items() if r <= 10}
                recon_top10 = {t for t, (_, r) in recon.items() if r <= 10}
                if arch_top10:
                    stats["top10_overlap_sum"] += len(
                        arch_top10 & recon_top10) / max(len(arch_top10), 1)
                    stats["top10_overlap_days"] += 1

            for tk in arch_set:
                if tk not in recon:
                    stats["recon_missing"] += 1
                    continue
                r_ret, r_rank = recon[tk]
                a_rank = arch_rank.get(tk)
                a_ret = arch_ret.get(tk)
                if a_rank is None or a_ret is None:
                    continue
                stats["compared_cells"] += 1
                # ret
                rdiff = abs(float(a_ret) - r_ret)
                if rdiff <= RET_EXACT:
                    stats["ret_exact"] += 1
                elif rdiff <= RET_MICRO:
                    stats["ret_micro"] += 1
                else:
                    stats["ret_mismatch"] += 1
                # rank
                rank_ok = int(a_rank) == int(r_rank)
                if rank_ok:
                    stats["rank_exact"] += 1
                else:
                    stats["rank_mismatch"] += 1
                if lb == GATE_LB:
                    stats["gate10_rank_total"] += 1
                    if rank_ok:
                        stats["gate10_rank_exact"] += 1
                    if not rank_ok:
                        stats["mismatches"].append({
                            "date": tdate, "ticker": tk, "lookback": lb,
                            "arch_rank": int(a_rank), "recon_rank": int(r_rank),
                            "arch_ret": round(float(a_ret), 2),
                            "recon_ret": r_ret,
                            "category": category(tk)})
    # finalizace
    n = stats["compared_cells"] or 1
    stats["ret_exact_rate"] = round(stats["ret_exact"] / n, 6)
    stats["ret_micro_rate"] = round(stats["ret_micro"] / n, 6)
    stats["ret_mismatch_rate"] = round(stats["ret_mismatch"] / n, 6)
    stats["rank_exact_rate"] = round(stats["rank_exact"] / n, 6)
    g = stats["gate10_rank_total"] or 1
    stats["gate10_rank_exact_rate"] = round(stats["gate10_rank_exact"] / g, 6)
    if stats["archive_ranked_counts"]:
        s = pd.Series(stats["archive_ranked_counts"])
        stats["archive_ranked_min"] = int(s.min())
        stats["archive_ranked_median"] = int(s.median())
        stats["archive_ranked_max"] = int(s.max())
    if stats["top10_overlap_days"]:
        stats["top10_overlap_rate"] = round(
            stats["top10_overlap_sum"] / stats["top10_overlap_days"], 4)
    # top mismatch dle ret rozdilu
    stats["mismatches"].sort(
        key=lambda m: abs(m["arch_ret"] - m["recon_ret"]), reverse=True)
    # kategorizace mismatch
    catcount = {}
    for m in stats["mismatches"]:
        catcount[m["category"]] = catcount.get(m["category"], 0) + 1
    stats["mismatch_by_category"] = catcount
    stats["top_mismatches"] = stats["mismatches"][:30]
    del stats["mismatches"]  # uklid (velke)
    del stats["archive_ranked_counts"]
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--mle-archive",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive\rank_matrix_archive.csv")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--range-from", default=RANGE_FROM)
    ap.add_argument("--range-to", default=RANGE_TO)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    order, tick2conid = load_universe_order(Path(args.universe_csv))
    print(f"universe: {len(order)} active")

    matrix = load_close_matrix(Path(args.view_dir), tick2conid, order)
    print(f"close matrix: {matrix.shape[0]} dni x {matrix.shape[1]} tickeru")

    adf = pd.read_csv(args.mle_archive, dtype={"date": str}, low_memory=False)
    adf["ticker"] = adf["ticker"].astype(str).str.upper()
    adf = adf[(adf["date"] >= args.range_from) & (adf["date"] <= args.range_to)]
    print(f"archiv: {len(adf)} radku, {adf['date'].nunique()} dni")

    print("rezim A: archive_ranked_raw ...")
    raw = analyze(matrix, order, adf, set())
    print("rezim B: exception_neutral_clean ...")
    clean = analyze(matrix, order, adf, CLEAN_EXCLUDE)

    # verdikt (clean rezim)
    clean_ret_ok = clean["ret_exact_rate"] + clean["ret_micro_rate"]
    clean_unknown = clean.get("mismatch_by_category", {}).get("clean", 0)
    if clean_ret_ok >= 0.995 and clean["gate10_rank_exact_rate"] >= 0.99 \
            and clean_unknown <= 5:
        verdict = "PASS"
    elif clean["gate10_rank_exact_rate"] >= 0.95:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    result = {"verdict": verdict, "range": [args.range_from, args.range_to],
              "archive_ranked_raw": raw, "exception_neutral_clean": clean}
    _write(result, mrl, args.out)

    print(f"\n==== MLE-RECON-01D: {verdict} ====")
    for label, s in [("RAW", raw), ("CLEAN", clean)]:
        print(f"[{label}] cells {s['compared_cells']} | "
              f"ret_exact {s['ret_exact_rate']} micro {s['ret_micro_rate']} "
              f"mismatch {s['ret_mismatch_rate']}")
        print(f"       rank_exact {s['rank_exact_rate']} | "
              f"gate10_rank_exact {s['gate10_rank_exact_rate']} | "
              f"top10_overlap {s.get('top10_overlap_rate')}")
        print(f"       mismatch_by_category: {s.get('mismatch_by_category')}")
    return 0


def _write(result, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-RECON-01D_archive_ranked_intersection.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")
    L = ["# MLE-RECON-01D — Archive-Ranked Intersection", "",
         f"## Verdikt: {result['verdict']}", "",
         f"Range: {result['range'][0]} .. {result['range'][1]}", "",
         "Metoda: recon rank prepocitan JEN mezi archive-ranked tickery",
         "per date/lookback. Tie-break: universe order.", ""]
    for label, key in [("A) archive_ranked_raw", "archive_ranked_raw"),
                       ("B) exception_neutral_clean", "exception_neutral_clean")]:
        s = result[key]
        L += [f"## {label}", "",
              f"- compared_cells: {s['compared_cells']}",
              f"- archive_ranked: min={s.get('archive_ranked_min')} "
              f"median={s.get('archive_ranked_median')} "
              f"max={s.get('archive_ranked_max')}",
              f"- recon_missing: {s['recon_missing']}",
              f"- ret_exact_rate: {s['ret_exact_rate']}",
              f"- ret_micro_rate: {s['ret_micro_rate']}",
              f"- ret_mismatch_rate: {s['ret_mismatch_rate']}",
              f"- rank_exact_rate: {s['rank_exact_rate']}",
              f"- gate10_rank_exact_rate: {s['gate10_rank_exact_rate']}",
              f"- top10_overlap_rate: {s.get('top10_overlap_rate')}",
              f"- mismatch_by_category: {s.get('mismatch_by_category')}", "",
              "### Top mismatches (gate10)", ""]
        for m in s.get("top_mismatches", [])[:20]:
            L.append(f"- {m['date']} {m['ticker']} L{m['lookback']}: "
                     f"arch_rank={m['arch_rank']} recon_rank={m['recon_rank']} "
                     f"arch_ret={m['arch_ret']} recon_ret={m['recon_ret']} "
                     f"[{m['category']}]")
        L.append("")
    L += ["## Interpretace", "",
          "- CLEAN gate10_rank_exact vysoky + ret_exact/micro >=99.5% ->",
          "  MLE rank logika + Sharadar ceny sedi mimo znale artefakty.",
          "- zbytkove clean mismatchy (kategorie 'clean') = nevysvetlene,",
          "  nutna dalsi analyza.", "",
          "## Vyhrady", "",
          "- recon rank pocitan zde (ne compute_rank_matrix), vzorec",
          "  identicky s MLE engine, ranking universe = archive_set.",
          "- tie-break: universe order (replikace MLE dict order).",
          "- close_past: spolecny index z DATA-06 union (ne per-ticker).",
          "  Muze se lisit od MLE price_matrix pri chybejicich dnech.", ""]
    (out_dir / "MLE-RECON-01D_archive_ranked_intersection.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
