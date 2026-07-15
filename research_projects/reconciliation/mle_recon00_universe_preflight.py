"""
mle_recon00_universe_preflight.py — MLE-RECON-00 universe preflight.

READ-ONLY. Overi, ze MLE universe CSV lze presne pouzit pro Cestu B
MLE reconciliation. NEPISE MLE-RECON-01.

NEDELA: MLE-RECON-01, IRC recon, backtest, API/TWS, zmenu dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\mle_recon00_universe_preflight.py

Kontroly:
    1. universe CSV: columns, row_count, active_flag counts, duplicates,
       missing, poradi (bez sortu)
    2. DATA-06 coverage: active conid s {conid}_D1.parquet, missing
    3. archive coverage: unique tickers, date range, rows/date,
       archive vs universe vs view rozdily
    4. order check: order_index dle poradi v CSV (bez abecedniho sortu)
    5. alias/BDX vyjimky z PRICE-RECON (reportovat, neblokovat)

Edge cases:
    - active_flag hodnoty neznamy predem (1/0 vs true/false) -> skript
      reportuje unique hodnoty; active = hodnota v {1,"1",True,"true","Y"}.
    - MLE load_universe filtruje active_flag==1 (viz mle_universe_loader).
      Preflight replikuje: active = _is_active(value).
    - poradi: read_csv BEZ sort, order_index = poradi radku.
    - DATA-06 view filename {conid}_D1.parquet.
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

# alias/BDX vyjimky z PRICE-RECON-01C
ALIAS_CONIDS = {"129348130": "NWS->NWSA", "208813720": "GOOG->GOOGL",
                "356858007": "FOX->FOXA"}
MANUAL_REVIEW_CONIDS = {"4886": "BDX boundary 2026-02-10"}


def is_active(value) -> bool:
    """Replikuje MLE mle_universe_loader active_flag filtr (==1)."""
    s = str(value).strip().lower()
    return s in ("1", "1.0", "true", "yes", "y")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--mle-archive",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive\rank_matrix_archive.csv")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    report = {"checks": {}, "verdict": None, "warnings": [], "fails": []}

    # ── 1. universe CSV ──
    ucsv = Path(args.universe_csv)
    if not ucsv.exists():
        print(f"FAIL: universe_csv neexistuje: {ucsv}")
        return 2
    udf = pd.read_csv(ucsv, dtype=str)  # bez sortu, zachova poradi
    ucheck = {"columns": list(udf.columns), "row_count": len(udf)}
    # active_flag
    acol = next((c for c in udf.columns if c.lower() == "active_flag"), None)
    ccol = next((c for c in udf.columns if c.lower() == "conid"), None)
    tcol = next((c for c in udf.columns if c.lower() == "ticker"), None)
    if not (acol and ccol and tcol):
        report["fails"].append(
            f"universe chybi sloupce (conid/ticker/active_flag); "
            f"ma: {list(udf.columns)}")
        ucheck["required_columns_present"] = False
    else:
        ucheck["required_columns_present"] = True
        ucheck["active_flag_values"] = udf[acol].value_counts().to_dict()
        udf["_active"] = udf[acol].apply(is_active)
        active = udf[udf["_active"]]
        ucheck["active_count"] = len(active)
        ucheck["inactive_count"] = len(udf) - len(active)
        # duplicates
        ucheck["duplicate_conid"] = int(udf[ccol].duplicated().sum())
        ucheck["duplicate_ticker"] = int(udf[tcol].duplicated().sum())
        ucheck["missing_conid"] = int(udf[ccol].isna().sum())
        ucheck["missing_ticker"] = int(udf[tcol].isna().sum())
        # order preserved (poradi radku = order_index)
        ucheck["order_preserved"] = True  # read_csv bez sortu
        ucheck["first_5_order"] = [
            {"order": i, "conid": str(r[ccol]), "ticker": str(r[tcol])}
            for i, (_, r) in enumerate(active.head(5).iterrows())]
    report["checks"]["universe"] = ucheck

    if not ucheck.get("required_columns_present"):
        report["verdict"] = "FAIL"
        _write(report, mrl, args.out)
        print("FAIL: universe chybi povinne sloupce")
        return 0

    active_conids = set(active[ccol].astype(str))
    active_tickers = set(active[tcol].astype(str).str.upper())

    # ── 2. DATA-06 coverage ──
    vdir = Path(args.view_dir)
    vcheck = {}
    if not vdir.exists():
        report["fails"].append(f"DATA-06 view neexistuje: {vdir}")
        vcheck["view_exists"] = False
    else:
        vcheck["view_exists"] = True
        view_conids = set()
        for f in vdir.glob("*_D1.parquet"):
            stem = f.stem
            cid = stem.rsplit("_", 1)[0] if "_" in stem else stem
            view_conids.add(cid)
        vcheck["view_files"] = len(view_conids)
        covered = active_conids & view_conids
        missing = active_conids - view_conids
        vcheck["active_covered_in_view"] = len(covered)
        vcheck["active_missing_in_view"] = len(missing)
        vcheck["missing_conids"] = sorted(missing)[:50]
        # ticker pro missing
        miss_rows = active[active[ccol].astype(str).isin(missing)]
        vcheck["missing_sample"] = [
            {"conid": str(r[ccol]), "ticker": str(r[tcol])}
            for _, r in miss_rows.head(20).iterrows()]
    report["checks"]["data06_coverage"] = vcheck

    # ── 3. archive coverage ──
    acheck = {}
    apath = Path(args.mle_archive)
    if not apath.exists():
        report["fails"].append(f"MLE archive neexistuje: {apath}")
        acheck["archive_exists"] = False
    else:
        acheck["archive_exists"] = True
        adf = pd.read_csv(apath, dtype={"date": str})
        atcol = next((c for c in adf.columns if c.lower() == "ticker"), None)
        adcol = next((c for c in adf.columns if c.lower() == "date"), None)
        arch_tickers = set(adf[atcol].astype(str).str.upper())
        acheck["archive_rows"] = len(adf)
        acheck["archive_unique_tickers"] = len(arch_tickers)
        acheck["archive_date_min"] = str(adf[adcol].min())
        acheck["archive_date_max"] = str(adf[adcol].max())
        rpd = adf.groupby(adcol).size()
        acheck["rows_per_date_min"] = int(rpd.min())
        acheck["rows_per_date_median"] = int(rpd.median())
        acheck["rows_per_date_max"] = int(rpd.max())
        # rozdily
        arch_not_universe = arch_tickers - active_tickers
        universe_not_arch = active_tickers - arch_tickers
        acheck["archive_tickers_not_in_active_universe"] = \
            sorted(arch_not_universe)[:30]
        acheck["n_archive_not_universe"] = len(arch_not_universe)
        acheck["active_universe_not_in_archive"] = \
            sorted(universe_not_arch)[:30]
        acheck["n_active_not_archive"] = len(universe_not_arch)
        # archive tickers vs view (pres ticker->conid z universe)
        if vcheck.get("view_exists"):
            tick2conid = dict(zip(active[tcol].astype(str).str.upper(),
                                  active[ccol].astype(str)))
            arch_view_missing = []
            for t in arch_tickers:
                cid = tick2conid.get(t)
                if cid and cid not in view_conids:
                    arch_view_missing.append(t)
            acheck["archive_tickers_not_in_view"] = \
                sorted(arch_view_missing)[:30]
            acheck["n_archive_not_in_view"] = len(arch_view_missing)
    report["checks"]["archive_coverage"] = acheck

    # ── 5. alias/BDX vyjimky ──
    excheck = {"alias_in_universe": {}, "manual_review_in_universe": {}}
    for cid, desc in ALIAS_CONIDS.items():
        excheck["alias_in_universe"][cid] = {
            "desc": desc, "in_active_universe": cid in active_conids}
    for cid, desc in MANUAL_REVIEW_CONIDS.items():
        excheck["manual_review_in_universe"][cid] = {
            "desc": desc, "in_active_universe": cid in active_conids}
    report["checks"]["exceptions"] = excheck

    # ── verdikt ──
    if report["fails"]:
        verdict = "FAIL"
    else:
        miss = vcheck.get("active_missing_in_view", 0)
        # WARN pokud nejaky active chybi v view nebo alias/BDX pritomny
        alias_present = any(v["in_active_universe"]
                            for v in excheck["alias_in_universe"].values())
        mr_present = any(v["in_active_universe"]
                         for v in excheck["manual_review_in_universe"].values())
        if miss > 0.05 * ucheck.get("active_count", 1):
            verdict = "FAIL"
            report["fails"].append(
                f"{miss} active conid chybi v DATA-06 (>5%)")
        elif miss > 0 or alias_present or mr_present \
                or acheck.get("n_active_not_archive", 0) > 0 \
                or acheck.get("n_archive_not_universe", 0) > 0:
            verdict = "WARN"
        else:
            verdict = "PASS"
    report["verdict"] = verdict

    _write(report, mrl, args.out)

    print(f"==== MLE-RECON-00: {verdict} ====")
    print(f"universe: {ucheck.get('row_count')} rows, "
          f"active {ucheck.get('active_count')}, "
          f"dup_conid {ucheck.get('duplicate_conid')}, "
          f"dup_ticker {ucheck.get('duplicate_ticker')}")
    print(f"DATA-06 coverage: {vcheck.get('active_covered_in_view')} "
          f"covered, {vcheck.get('active_missing_in_view')} missing")
    if acheck.get("archive_exists"):
        print(f"archive: {acheck.get('archive_unique_tickers')} tickers, "
              f"{acheck.get('archive_date_min')}..{acheck.get('archive_date_max')}, "
              f"rows/date {acheck.get('rows_per_date_min')}-"
              f"{acheck.get('rows_per_date_max')}")
        print(f"  archive_not_universe: {acheck.get('n_archive_not_universe')}, "
              f"active_not_archive: {acheck.get('n_active_not_archive')}, "
              f"archive_not_view: {acheck.get('n_archive_not_in_view')}")
    if report["fails"]:
        print("FAILS:", report["fails"])
    return 0


def _write(report, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-RECON-00_universe_preflight.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    c = report["checks"]
    u = c.get("universe", {})
    v = c.get("data06_coverage", {})
    a = c.get("archive_coverage", {})
    e = c.get("exceptions", {})
    L = ["# MLE-RECON-00 — Universe Preflight", "",
         f"## Verdikt: {report['verdict']}", ""]
    if report["fails"]:
        L += ["### FAILS", ""] + [f"- {x}" for x in report["fails"]] + [""]
    L += ["## 1. Universe CSV", "",
          f"- columns: {u.get('columns')}",
          f"- row_count: {u.get('row_count')}",
          f"- active_flag_values: {u.get('active_flag_values')}",
          f"- active_count: {u.get('active_count')}",
          f"- inactive_count: {u.get('inactive_count')}",
          f"- duplicate_conid: {u.get('duplicate_conid')}",
          f"- duplicate_ticker: {u.get('duplicate_ticker')}",
          f"- missing_conid: {u.get('missing_conid')}",
          f"- missing_ticker: {u.get('missing_ticker')}",
          f"- order_preserved: {u.get('order_preserved')} (read_csv bez sortu)",
          f"- first_5_order: {u.get('first_5_order')}", "",
          "## 2. DATA-06 coverage", "",
          f"- view_files: {v.get('view_files')}",
          f"- active_covered_in_view: {v.get('active_covered_in_view')}",
          f"- active_missing_in_view: {v.get('active_missing_in_view')}",
          f"- missing_sample: {v.get('missing_sample')}", "",
          "## 3. Archive coverage", ""]
    if a.get("archive_exists"):
        L += [f"- archive_rows: {a.get('archive_rows')}",
              f"- unique_tickers: {a.get('archive_unique_tickers')}",
              f"- date_range: {a.get('archive_date_min')}..{a.get('archive_date_max')}",
              f"- rows_per_date: min={a.get('rows_per_date_min')} "
              f"median={a.get('rows_per_date_median')} "
              f"max={a.get('rows_per_date_max')}",
              f"- archive_tickers_not_in_active_universe "
              f"({a.get('n_archive_not_universe')}): "
              f"{a.get('archive_tickers_not_in_active_universe')}",
              f"- active_universe_not_in_archive "
              f"({a.get('n_active_not_archive')}): "
              f"{a.get('active_universe_not_in_archive')}",
              f"- archive_tickers_not_in_view "
              f"({a.get('n_archive_not_in_view')}): "
              f"{a.get('archive_tickers_not_in_view')}", ""]
    else:
        L += ["- archive NEEXISTUJE", ""]
    L += ["## 4. Order check", "",
          "- order_index = poradi radku v universe_csv (read_csv bez sortu).",
          "- MLE-RECON-01 MUSI plnit close_prices dict v tomto poradi",
          "  (tie-break pri shodnem returnu zavisi na poradi).", "",
          "## 5. Alias / manual-review vyjimky (z PRICE-RECON-01C)", ""]
    for cid, info in e.get("alias_in_universe", {}).items():
        L.append(f"- alias {cid} ({info['desc']}): "
                 f"in_active_universe={info['in_active_universe']}")
    for cid, info in e.get("manual_review_in_universe", {}).items():
        L.append(f"- manual_review {cid} ({info['desc']}): "
                 f"in_active_universe={info['in_active_universe']}")
    L += ["", "## Vyhrady", "",
          "- active_flag filtr: hodnota v {1,true,yes,y} (replikuje MLE).",
          "- coverage FAIL prah: >5% active conid chybi v DATA-06.",
          "- alias/BDX se reportuji, NEblokuji preflight.", ""]
    (out_dir / "MLE-RECON-00_universe_preflight.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
