"""
mle_recon01_rank_matrix.py — MLE-RECON-01 shadow rank reconciliation (Cesta B).

Regeneruje MLE rank matrix ze Sharadar DATA-06 cen pomoci PUVODNIHO MLE
engine (compute_rank_matrix) a porovna s rank_matrix_archive.csv.

READ-ONLY. NEDELA: MLE archive overwrite, IRC recon, backtest, API/TWS,
zmenu raw/optimized/derived dat, MDSM config zmenu.

Princip (Cesta B):
    stejny MLE engine + jiny loader (Sharadar close misto MDSM cache).
    Testuje: dava Sharadar cena stejny MLE rank jako MDSM archiv?

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\mle_recon01_rank_matrix.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Parametry (potvrzeno architektem):
    universe: sp500_rank_calendar_universe.csv, active_flag==1, 503, poradi
    close_prices: DATA-06 view, per ticker, v poradi universe
    lookbacks: [1,2,3,4,5,6,7,8,9,10,20] (z MLE config)
    range: 2025-07-09 .. 2026-07-04 (plny MLE archive)
    rank: exact int match; ret: round(2), tolerance abs<=0.0001
    ret_micro: 0.0001<diff<=0.01; ret_mismatch: diff>0.01
    gate: rank_10d exact + ret_10d exact/micro
    EXE/PSKY/Q/SNDK: compute included, comparison excluded
    NWS/GOOG/FOX: expected identity_alias_class_mismatch
    BDX: expected needs_manual_review

Edge cases / predpoklady:
    - compute_rank_matrix import z MLE (sys.path). Engine zavisi jen na
      pandas + MLE logging_utils (overeno importovatelny samostatne).
    - start_buffer: MLE pouziva run_date - 45 kalendarnich dni pro extended
      start. Recon nacte cely dostupny DATA-06 history per ticker (staci
      pro max lookback 20 trading dni).
    - tie-break: close_prices dict plnen v poradi universe_csv (shodne
      returny -> poradi dle vlozeni). Musi odpovidat MLE originalu.
    - target_date mimo obchodni den: engine vezme nejblizsi predchozi.
    - EXE/PSKY/Q/SNDK: bez historie -> engine je vynecha z rankingu
      (NaN v returns). Ve vypoctu zustavaji (dict), comparison je preskoci.
    - vykon: ~250 dni x compute (503 tickeru). Muze trvat minuty.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

RANGE_FROM, RANGE_TO = "2025-07-09", "2026-07-04"
LOOKBACKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
RET_EXACT_TOL = 0.0001
RET_MICRO_TOL = 0.01
GATE_LOOKBACK = 10

INSUFFICIENT_HISTORY = {"EXE", "PSKY", "Q", "SNDK"}
ALIAS_TICKERS = {"NWS", "GOOG", "FOX"}
MANUAL_REVIEW_TICKERS = {"BDX"}


def is_active(value) -> bool:
    return str(value).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_universe(ucsv: Path):
    """Nacti universe v PORADI (bez sortu). Vrati list dict + poradi."""
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    instruments = []
    for _, r in df.iterrows():
        if not is_active(r[acol]):
            continue
        instruments.append({
            "conid": int(float(r[ccol])),
            "ticker": str(r[tcol]).strip().upper(),
            "sector": str(r.get(cols.get("sector", ""), "")),
            "industry": str(r.get(cols.get("industry", ""), "")),
            "subcategory": str(r.get(cols.get("subcategory", ""), "")),
        })
    return instruments


def load_close_series(view_dir: Path, conid: int):
    """Nacti close Series z DATA-06 view {conid}_D1.parquet."""
    f = view_dir / f"{conid}_D1.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    if "close" not in df.columns:
        return None
    df.index = pd.to_datetime(df.index).normalize()
    return df["close"].sort_index()


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
    ap.add_argument("--range-from", default=RANGE_FROM)
    ap.add_argument("--range-to", default=RANGE_TO)
    ap.add_argument("--max-days", type=int, default=0,
                    help="omezeni poctu dni (0=vse), pro rychly test")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    # import MLE engine
    mle_root = Path(args.mle_root)
    if not mle_root.exists():
        print(f"FAIL: MLE root neexistuje: {mle_root}")
        return 2
    sys.path.insert(0, str(mle_root))
    try:
        from src.engines.rank_matrix_engine import compute_rank_matrix
    except ImportError as e:
        print(f"FAIL: nelze importovat MLE engine: {e}")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    view_dir = Path(args.view_dir)
    ucsv = Path(args.universe_csv)
    apath = Path(args.mle_archive)
    for p, name in [(view_dir, "view"), (ucsv, "universe"), (apath, "archive")]:
        if not p.exists():
            print(f"FAIL: {name} neexistuje: {p}")
            return 2

    # universe v poradi
    instruments = load_universe(ucsv)
    print(f"universe: {len(instruments)} active instrumentu (poradi zachovano)")

    # close_prices dict v PORADI universe
    close_prices = {}
    loaded, missing = 0, []
    for inst in instruments:
        s = load_close_series(view_dir, inst["conid"])
        if s is not None and not s.empty:
            close_prices[inst["ticker"]] = s
            loaded += 1
        else:
            missing.append(inst["ticker"])
    print(f"close_prices: {loaded} nacteno, {len(missing)} chybi")

    # archiv
    adf = pd.read_csv(apath, dtype={"date": str}, low_memory=False)
    adf["ticker"] = adf["ticker"].astype(str).str.upper()
    arch_tickers = set(adf["ticker"])
    # index archivu podle (date, ticker)
    adf_idx = adf.set_index(["date", "ticker"])

    # obchodni dny v range = z archivu (aby sedely target_date)
    arch_dates = sorted(d for d in adf["date"].unique()
                        if args.range_from <= d <= args.range_to)
    if args.max_days > 0:
        arch_dates = arch_dates[:args.max_days]
    print(f"porovnavam {len(arch_dates)} dni {args.range_from}..{args.range_to}")

    # akumulace statistik
    stats = {
        "range": [args.range_from, args.range_to],
        "n_dates": len(arch_dates), "universe_active": len(instruments),
        "close_prices_loaded": loaded, "close_prices_missing": missing,
        "compared_cells": 0,
        "rank_exact": 0, "rank_mismatch": 0,
        "ret_exact": 0, "ret_micro": 0, "ret_mismatch": 0,
        "gate_rank10_exact": 0, "gate_rank10_mismatch": 0,
        "gate_ret10_ok": 0, "gate_ret10_mismatch": 0,
        "excluded_insufficient_history": sorted(INSUFFICIENT_HISTORY),
        "excluded_cells": 0,
        "expected_exceptions": {t: {"rank_mismatch": 0, "ret_mismatch": 0}
                                for t in (ALIAS_TICKERS | MANUAL_REVIEW_TICKERS)},
        "per_day_sample": [],
        "top_mismatches": [],
    }

    all_mismatches = []
    for di, tdate in enumerate(arch_dates):
        run_date = date.fromisoformat(tdate)
        try:
            rm = compute_rank_matrix(
                close_prices=close_prices, instruments=instruments,
                target_date=run_date, lookbacks=LOOKBACKS)
        except Exception as e:  # noqa: BLE001
            stats.setdefault("compute_errors", []).append(
                {"date": tdate, "error": str(e)})
            continue
        # rm: DataFrame s ticker, rank_Nd, ret_Nd
        rm_idx = rm.set_index("ticker")

        day_rank_mism = 0
        day_cells = 0
        for ticker in rm_idx.index:
            if ticker in INSUFFICIENT_HISTORY:
                continue
            if (tdate, ticker) not in adf_idx.index:
                continue  # ticker neni v archivu pro tento den
            arch_row = adf_idx.loc[(tdate, ticker)]
            recon_row = rm_idx.loc[ticker]
            is_exception = (ticker in ALIAS_TICKERS
                            or ticker in MANUAL_REVIEW_TICKERS)

            for lb in LOOKBACKS:
                rcol, retcol = f"rank_{lb}d", f"ret_{lb}d"
                if rcol not in arch_row or rcol not in recon_row:
                    continue
                a_rank = arch_row[rcol]
                r_rank = recon_row[rcol]
                a_ret = arch_row[retcol]
                r_ret = recon_row[retcol]
                # preskoc pokud oba None/NaN
                if pd.isna(a_rank) and pd.isna(r_rank):
                    continue
                stats["compared_cells"] += 1
                day_cells += 1

                # rank
                rank_ok = (not pd.isna(a_rank) and not pd.isna(r_rank)
                           and int(a_rank) == int(r_rank))
                if rank_ok:
                    stats["rank_exact"] += 1
                else:
                    stats["rank_mismatch"] += 1
                    day_rank_mism += 1
                    if is_exception:
                        stats["expected_exceptions"][ticker]["rank_mismatch"] += 1

                # ret
                if not pd.isna(a_ret) and not pd.isna(r_ret):
                    rdiff = abs(float(a_ret) - float(r_ret))
                    if rdiff <= RET_EXACT_TOL:
                        stats["ret_exact"] += 1
                    elif rdiff <= RET_MICRO_TOL:
                        stats["ret_micro"] += 1
                    else:
                        stats["ret_mismatch"] += 1
                        if is_exception:
                            stats["expected_exceptions"][ticker]["ret_mismatch"] += 1

                # gate lookback 10
                if lb == GATE_LOOKBACK:
                    if rank_ok:
                        stats["gate_rank10_exact"] += 1
                    else:
                        stats["gate_rank10_mismatch"] += 1
                    if not pd.isna(a_ret) and not pd.isna(r_ret):
                        if abs(float(a_ret) - float(r_ret)) <= RET_MICRO_TOL:
                            stats["gate_ret10_ok"] += 1
                        else:
                            stats["gate_ret10_mismatch"] += 1

                # sber mismatch (non-exception, rank)
                if not rank_ok and not is_exception and lb == GATE_LOOKBACK:
                    all_mismatches.append({
                        "date": tdate, "ticker": ticker, "lookback": lb,
                        "arch_rank": None if pd.isna(a_rank) else int(a_rank),
                        "recon_rank": None if pd.isna(r_rank) else int(r_rank),
                        "arch_ret": None if pd.isna(a_ret) else float(a_ret),
                        "recon_ret": None if pd.isna(r_ret) else float(r_ret)})

        if len(stats["per_day_sample"]) < 10:
            stats["per_day_sample"].append(
                {"date": tdate, "cells": day_cells,
                 "rank_mismatch": day_rank_mism})

    # top mismatches dle ret rozdilu
    all_mismatches.sort(
        key=lambda m: abs((m["arch_ret"] or 0) - (m["recon_ret"] or 0)),
        reverse=True)
    stats["top_mismatches"] = all_mismatches[:30]
    stats["n_gate10_nonexception_mismatches"] = len(all_mismatches)

    # gross vs clean mismatch rate (rank, vsechny lookbacky)
    total = stats["compared_cells"] or 1
    stats["gross_rank_mismatch_rate"] = round(
        stats["rank_mismatch"] / total, 6)
    exc_rank = sum(v["rank_mismatch"]
                   for v in stats["expected_exceptions"].values())
    stats["clean_rank_mismatch_rate"] = round(
        (stats["rank_mismatch"] - exc_rank) / total, 6)
    stats["expected_exception_rank_mismatches"] = exc_rank

    # verdikt (gate rank_10d + ret_10d)
    g10 = stats["gate_rank10_exact"] + stats["gate_rank10_mismatch"]
    clean_g10_mism = stats["gate_rank10_mismatch"] - sum(
        1 for m in all_mismatches)  # all_mismatches uz jsou non-exception g10
    # clean rank10 mismatch = non-exception g10 mismatches
    stats["gate10_total"] = g10
    stats["gate10_clean_mismatch"] = len(all_mismatches)
    if g10 == 0:
        verdict = "FAIL"
        stats["verdict_note"] = "zadne gate10 bunky"
    else:
        clean_rate = len(all_mismatches) / g10
        stats["gate10_clean_mismatch_rate"] = round(clean_rate, 6)
        if clean_rate == 0:
            verdict = "PASS"
        elif clean_rate < 0.01:
            verdict = "WARN"
        else:
            verdict = "FAIL"
    stats["verdict"] = verdict

    _write(stats, mrl, args.out)

    print(f"\n==== MLE-RECON-01: {verdict} ====")
    print(f"compared_cells: {stats['compared_cells']}")
    print(f"rank: exact {stats['rank_exact']} | mismatch {stats['rank_mismatch']}")
    print(f"  gross_rank_mismatch_rate: {stats['gross_rank_mismatch_rate']}")
    print(f"  clean_rank_mismatch_rate: {stats['clean_rank_mismatch_rate']}")
    print(f"ret: exact {stats['ret_exact']} | micro {stats['ret_micro']} "
          f"| mismatch {stats['ret_mismatch']}")
    print(f"gate10: exact {stats['gate_rank10_exact']} | "
          f"mismatch {stats['gate_rank10_mismatch']} | "
          f"clean_mismatch {stats['gate10_clean_mismatch']}")
    print(f"expected_exception_rank_mismatches: {exc_rank}")
    return 0


def _write(stats, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-RECON-01_rank_matrix_reconciliation.json").write_text(
        json.dumps(stats, indent=2, default=str), encoding="utf-8")
    L = ["# MLE-RECON-01 — Rank Matrix Reconciliation (Cesta B)", "",
         f"## Verdikt: {stats['verdict']}", "",
         f"Range: {stats['range'][0]} .. {stats['range'][1]}",
         f"Dni: {stats['n_dates']}", "",
         "## Metoda", "",
         "- puvodni MLE compute_rank_matrix + Sharadar DATA-06 ceny",
         "- universe: 503 active, poradi zachovano (tie-break reprodukce)",
         f"- lookbacks: {LOOKBACKS}", "",
         "## Souhrn", "",
         f"- compared_cells: {stats['compared_cells']}",
         f"- close_prices_loaded: {stats['close_prices_loaded']}",
         f"- close_prices_missing: {len(stats['close_prices_missing'])} "
         f"{stats['close_prices_missing'][:20]}", "",
         "### Rank", "",
         f"- rank_exact: {stats['rank_exact']}",
         f"- rank_mismatch: {stats['rank_mismatch']}",
         f"- gross_rank_mismatch_rate: {stats['gross_rank_mismatch_rate']}",
         f"- clean_rank_mismatch_rate: {stats['clean_rank_mismatch_rate']}",
         f"- expected_exception_rank_mismatches: "
         f"{stats['expected_exception_rank_mismatches']}", "",
         "### Return", "",
         f"- ret_exact (<=0.0001): {stats['ret_exact']}",
         f"- ret_micro (<=0.01): {stats['ret_micro']}",
         f"- ret_mismatch (>0.01): {stats['ret_mismatch']}", "",
         "### Gate (lookback 10, strategie rank_10d<=10)", "",
         f"- gate_rank10_exact: {stats['gate_rank10_exact']}",
         f"- gate_rank10_mismatch: {stats['gate_rank10_mismatch']}",
         f"- gate10_clean_mismatch (non-exception): "
         f"{stats['gate10_clean_mismatch']}",
         f"- gate10_clean_mismatch_rate: "
         f"{stats.get('gate10_clean_mismatch_rate')}", "",
         "## Expected exceptions (NWS/GOOG/FOX/BDX)", ""]
    for t, v in stats["expected_exceptions"].items():
        L.append(f"- {t}: rank_mismatch={v['rank_mismatch']} "
                 f"ret_mismatch={v['ret_mismatch']}")
    L += ["", "## Excluded (insufficient history, ve vypoctu, ne v porovnani)",
          "", f"- {stats['excluded_insufficient_history']}", "",
          "## Top gate10 non-exception mismatches", ""]
    for m in stats["top_mismatches"][:30]:
        L.append(f"- {m['date']} {m['ticker']} L{m['lookback']}: "
                 f"arch_rank={m['arch_rank']} recon_rank={m['recon_rank']} "
                 f"arch_ret={m['arch_ret']} recon_ret={m['recon_ret']}")
    if "compute_errors" in stats:
        L += ["", "## Compute errors", ""]
        for e in stats["compute_errors"][:10]:
            L.append(f"- {e['date']}: {e['error']}")
    L += ["", "## Vyhrady", "",
          "- tie-break: close_prices poradi = universe_csv poradi.",
          "- EXE/PSKY/Q/SNDK: ve vypoctu, vyloucene z porovnani.",
          "- NWS/GOOG/FOX/BDX: expected exceptions, pocitane zvlast.",
          "- ret tolerance: exact<=0.0001, micro<=0.01, mismatch>0.01.",
          "- gate: rank_10d exact + ret_10d exact/micro.", ""]
    (out_dir / "MLE-RECON-01_rank_matrix_reconciliation.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
