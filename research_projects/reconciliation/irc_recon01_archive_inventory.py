"""
irc_recon01_archive_inventory.py — IRC-RECON-01 archive inventory.

READ-ONLY. Overi IRC archive vrstvu pred EDGE testem MLE TOP10 x IRC TOP10.

NEDELA: backtest, portfolio engine, Decision Resolver, bot/TWS, MLE
archive overwrite. NEPOUZIVA Sharadar TICKERS industry.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\irc_recon01_archive_inventory.py

Kontroly (dle zadani):
    1. IRC archive schema (columns)
    2. date range
    3. rows per date
    4. industry/subcategory coverage
    5. duplicate industry/date rows
    6. missing dates (vs MLE archive trading dates)
    7. rank_20d availability
    8. TOP10 industry count per date (rank_20d <= 10)
    9. IRC <-> MLE join pres industry/subcategory metadata
    10. universe/taxonomy mismatch pred EDGE testem

Overlap: 2025-07-09 .. 2026-06-27 (MLE inter IRC).
Hlavni IRC gate: rank_20d <= 10.

Edge cases / predpoklady:
    - IRC archive schema NENI predem jisty -> skript vypise columns.
      Ocekavane (z inventory): date, lookback, rank, industry, sector,
      median_return, mean_return, member_count, advance_ratio,
      top_1..3_ticker/return, status.
    - lookback sloupec: IRC ma 'lookback' (dlouhy format) NEBO rank_20d
      (siroky). Skript detekuje oboje.
    - MLE archive pro missing-dates + join test (industry/subcategory).
    - industry_rank_calendar projekt NENI v sandboxu; cte jen CSV.
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

OVERLAP_FROM, OVERLAP_TO = "2025-07-09", "2026-06-27"
IRC_GATE_LOOKBACK = 20
TOP_N = 10


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--irc-archive",
                    default=r"C:\Users\stava\Projects\industry_rank_calendar\output\archive\industry_rank_calendar_archive.csv")
    ap.add_argument("--mle-archive",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive\rank_matrix_archive.csv")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--overlap-from", default=OVERLAP_FROM)
    ap.add_argument("--overlap-to", default=OVERLAP_TO)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    irc_path = Path(args.irc_archive)
    if not irc_path.exists():
        print(f"FAIL: IRC archive neexistuje: {irc_path}")
        return 2

    idf = pd.read_csv(irc_path, dtype=str, low_memory=False)
    report = {"schema": {}, "date": {}, "rows_per_date": {},
              "taxonomy": {}, "duplicates": {}, "missing_dates": {},
              "rank20d": {}, "top10": {}, "mle_join": {},
              "mismatch_risks": [], "warnings": []}

    # ── 1. schema ──
    cols = list(idf.columns)
    report["schema"]["columns"] = cols
    report["schema"]["row_count"] = len(idf)
    colmap = {c.lower(): c for c in cols}
    dcol = colmap.get("date")
    icol = colmap.get("industry")
    scol = colmap.get("sector")
    subcol = colmap.get("subcategory")
    lbcol = colmap.get("lookback")
    rankcol = colmap.get("rank")
    if dcol is None:
        report["mismatch_risks"].append("chybi 'date' sloupec")
        _write(report, mrl, args.out, "FAIL")
        print("FAIL: chybi date sloupec")
        return 0
    report["schema"]["has_lookback_col"] = lbcol is not None
    report["schema"]["has_rank_col"] = rankcol is not None
    # rank_20d siroky format?
    wide_rank20 = colmap.get("rank_20d")
    report["schema"]["has_rank_20d_wide"] = wide_rank20 is not None

    idf[dcol] = idf[dcol].astype(str).str[:10]

    # ── 2. date range ──
    report["date"]["min"] = str(idf[dcol].min())
    report["date"]["max"] = str(idf[dcol].max())
    all_dates = sorted(idf[dcol].unique())
    report["date"]["unique_dates"] = len(all_dates)
    # overlap subset
    ov = idf[(idf[dcol] >= args.overlap_from) & (idf[dcol] <= args.overlap_to)]
    report["date"]["overlap_rows"] = len(ov)
    ov_dates = sorted(ov[dcol].unique())
    report["date"]["overlap_unique_dates"] = len(ov_dates)

    # ── 3. rows per date ──
    rpd = idf.groupby(dcol).size()
    report["rows_per_date"] = {
        "min": int(rpd.min()), "median": int(rpd.median()),
        "max": int(rpd.max())}

    # ── 4. taxonomy coverage ──
    if icol:
        report["taxonomy"]["unique_industry"] = int(idf[icol].nunique())
        report["taxonomy"]["industry_sample"] = sorted(
            idf[icol].dropna().unique())[:30]
    if scol:
        report["taxonomy"]["unique_sector"] = int(idf[scol].nunique())
        report["taxonomy"]["sector_sample"] = sorted(
            idf[scol].dropna().unique())[:20]
    report["taxonomy"]["has_subcategory"] = subcol is not None
    if subcol:
        report["taxonomy"]["unique_subcategory"] = int(idf[subcol].nunique())

    # ── 5. duplicates (industry/date, per lookback pokud existuje) ──
    if icol:
        if lbcol:
            dup = idf.duplicated(subset=[dcol, icol, lbcol]).sum()
            report["duplicates"]["by_date_industry_lookback"] = int(dup)
        else:
            dup = idf.duplicated(subset=[dcol, icol]).sum()
            report["duplicates"]["by_date_industry"] = int(dup)

    # ── 6. missing dates vs MLE ──
    mle_path = Path(args.mle_archive)
    if mle_path.exists():
        mdf = pd.read_csv(mle_path, dtype={"date": str}, low_memory=False,
                          usecols=lambda c: c.lower() in
                          ("date", "ticker", "sector", "industry", "subcategory"))
        mdf_dcol = next((c for c in mdf.columns if c.lower() == "date"), None)
        mle_dates = set(d[:10] for d in mdf[mdf_dcol].astype(str))
        mle_ov = sorted(d for d in mle_dates
                        if args.overlap_from <= d <= args.overlap_to)
        irc_ov_set = set(ov_dates)
        missing_in_irc = sorted(set(mle_ov) - irc_ov_set)
        missing_in_mle = sorted(irc_ov_set - set(mle_ov))
        report["missing_dates"]["mle_overlap_dates"] = len(mle_ov)
        report["missing_dates"]["irc_overlap_dates"] = len(irc_ov_set)
        report["missing_dates"]["in_mle_not_irc"] = missing_in_irc[:30]
        report["missing_dates"]["n_in_mle_not_irc"] = len(missing_in_irc)
        report["missing_dates"]["in_irc_not_mle"] = missing_in_mle[:30]
        report["missing_dates"]["n_in_irc_not_mle"] = len(missing_in_mle)
    else:
        report["warnings"].append("MLE archive neexistuje -> missing/join preskoceno")

    # ── 7. rank_20d availability ──
    # long format: filtr lookback==20; wide: rank_20d sloupec
    irc_20 = None
    if lbcol and rankcol:
        idf[lbcol] = idf[lbcol].astype(str).str.replace("d", "", regex=False)
        irc_20 = idf[idf[lbcol].isin(["20", "20.0"])].copy()
        report["rank20d"]["format"] = "long (lookback col)"
        report["rank20d"]["rank20_rows"] = len(irc_20)
        report["rank20d"]["rank20_dates"] = int(irc_20[dcol].nunique()) if len(irc_20) else 0
        rank_series = pd.to_numeric(irc_20[rankcol], errors="coerce")
    elif wide_rank20:
        irc_20 = idf.copy()
        report["rank20d"]["format"] = "wide (rank_20d col)"
        rank_series = pd.to_numeric(idf[wide_rank20], errors="coerce")
        report["rank20d"]["rank20_non_null"] = int(rank_series.notna().sum())
    else:
        report["rank20d"]["format"] = "UNKNOWN"
        report["mismatch_risks"].append(
            "nelze urcit rank_20d (chybi lookback+rank i rank_20d)")
        rank_series = None

    # ── 8. TOP10 industry count per date (rank_20d <= 10) ──
    if irc_20 is not None and rank_series is not None:
        irc_20 = irc_20.assign(_rank=rank_series.values)
        irc_20_ov = irc_20[(irc_20[dcol] >= args.overlap_from)
                           & (irc_20[dcol] <= args.overlap_to)]
        top10 = irc_20_ov[irc_20_ov["_rank"] <= TOP_N]
        t10_per_date = top10.groupby(dcol).size()
        if len(t10_per_date):
            report["top10"]["per_date_min"] = int(t10_per_date.min())
            report["top10"]["per_date_median"] = int(t10_per_date.median())
            report["top10"]["per_date_max"] = int(t10_per_date.max())
            report["top10"]["dates_with_top10"] = int(len(t10_per_date))
            # kolik unique industries se objevi v TOP10
            if icol:
                report["top10"]["unique_industries_in_top10"] = \
                    int(top10[icol].nunique())

    # ── 9. IRC <-> MLE join (industry/subcategory) ──
    if mle_path.exists() and icol:
        mle_industries = set(mdf["industry"].dropna().astype(str).unique()) \
            if "industry" in mdf.columns else set()
        irc_industries = set(idf[icol].dropna().astype(str).unique())
        common = mle_industries & irc_industries
        report["mle_join"]["mle_unique_industries"] = len(mle_industries)
        report["mle_join"]["irc_unique_industries"] = len(irc_industries)
        report["mle_join"]["common_industries"] = len(common)
        report["mle_join"]["irc_only_industries"] = sorted(
            irc_industries - mle_industries)[:30]
        report["mle_join"]["mle_only_industries"] = sorted(
            mle_industries - irc_industries)[:30]
        join_rate = len(common) / len(irc_industries) if irc_industries else 0
        report["mle_join"]["industry_join_rate"] = round(join_rate, 4)
        if join_rate < 0.9:
            report["mismatch_risks"].append(
                f"industry join rate {round(join_rate,3)} < 0.9 -> "
                f"taxonomy mismatch mezi IRC a MLE")

    # ── 10. mismatch risks (souhrn) ──
    if report["date"]["overlap_unique_dates"] == 0:
        report["mismatch_risks"].append("zadny overlap s IRC v obdobi")

    # verdikt
    if any("FAIL" in r or "chybi" in r or "nelze urcit" in r
           for r in report["mismatch_risks"]):
        verdict = "FAIL"
    elif report["mismatch_risks"] or report["warnings"]:
        verdict = "WARN"
    else:
        verdict = "PASS"

    _write(report, mrl, args.out, verdict)

    print(f"==== IRC-RECON-01: {verdict} ====")
    print(f"schema columns: {cols}")
    print(f"date range: {report['date']['min']}..{report['date']['max']} "
          f"({report['date']['unique_dates']} dni)")
    print(f"overlap: {report['date']['overlap_unique_dates']} dni")
    print(f"rows_per_date: {report['rows_per_date']}")
    print(f"taxonomy: {report['taxonomy'].get('unique_industry')} industries, "
          f"{report['taxonomy'].get('unique_sector')} sectors, "
          f"subcategory={report['taxonomy'].get('has_subcategory')}")
    print(f"rank20d: {report['rank20d']}")
    print(f"top10: {report.get('top10')}")
    print(f"mle_join: industry_join_rate="
          f"{report['mle_join'].get('industry_join_rate')}")
    print(f"mismatch_risks: {report['mismatch_risks']}")
    return 0


def _write(report, mrl, out, verdict):
    report["verdict"] = verdict
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "IRC-RECON-01_archive_inventory.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    s = report["schema"]; d = report["date"]; t = report["taxonomy"]
    L = ["# IRC-RECON-01 — Archive Inventory", "",
         f"## Verdikt: {verdict}", "",
         "## 1. Schema", "",
         f"- columns: {s.get('columns')}",
         f"- row_count: {s.get('row_count')}",
         f"- has_lookback_col: {s.get('has_lookback_col')}",
         f"- has_rank_col: {s.get('has_rank_col')}",
         f"- has_rank_20d_wide: {s.get('has_rank_20d_wide')}", "",
         "## 2. Date", "",
         f"- range: {d.get('min')} .. {d.get('max')}",
         f"- unique_dates: {d.get('unique_dates')}",
         f"- overlap ({report.get('overlap_from', OVERLAP_FROM)}.."
         f"{OVERLAP_TO}): {d.get('overlap_unique_dates')} dni, "
         f"{d.get('overlap_rows')} radku", "",
         "## 3. Rows per date", "",
         f"- {report['rows_per_date']}", "",
         "## 4. Taxonomy", "",
         f"- unique_industry: {t.get('unique_industry')}",
         f"- unique_sector: {t.get('unique_sector')}",
         f"- has_subcategory: {t.get('has_subcategory')}",
         f"- unique_subcategory: {t.get('unique_subcategory')}",
         f"- industry_sample: {t.get('industry_sample')}",
         f"- sector_sample: {t.get('sector_sample')}", "",
         "## 5. Duplicates", "",
         f"- {report['duplicates']}", "",
         "## 6. Missing dates (vs MLE overlap)", ""]
    md = report["missing_dates"]
    if md:
        L += [f"- mle_overlap_dates: {md.get('mle_overlap_dates')}",
              f"- irc_overlap_dates: {md.get('irc_overlap_dates')}",
              f"- in_mle_not_irc ({md.get('n_in_mle_not_irc')}): "
              f"{md.get('in_mle_not_irc')}",
              f"- in_irc_not_mle ({md.get('n_in_irc_not_mle')}): "
              f"{md.get('in_irc_not_mle')}"]
    L += ["", "## 7. rank_20d availability", "",
          f"- {report['rank20d']}", "",
          "## 8. TOP10 industry per date (rank_20d <= 10)", "",
          f"- {report.get('top10')}", "",
          "## 9. IRC <-> MLE join (industry)", ""]
    mj = report["mle_join"]
    if mj:
        L += [f"- mle_unique_industries: {mj.get('mle_unique_industries')}",
              f"- irc_unique_industries: {mj.get('irc_unique_industries')}",
              f"- common_industries: {mj.get('common_industries')}",
              f"- industry_join_rate: {mj.get('industry_join_rate')}",
              f"- irc_only_industries: {mj.get('irc_only_industries')}",
              f"- mle_only_industries: {mj.get('mle_only_industries')}"]
    L += ["", "## 10. Mismatch risks", ""]
    for r in report["mismatch_risks"]:
        L.append(f"- {r}")
    if not report["mismatch_risks"]:
        L.append("- zadne")
    if report["warnings"]:
        L += ["", "## Warnings", ""] + [f"- {w}" for w in report["warnings"]]
    L += ["", "## Vyhrady", "",
          "- IRC schema detekovan z hlavicky; lookback long vs rank_20d wide.",
          "- industry join = textova shoda IRC industry vs MLE industry.",
          "- NEPOUZITA Sharadar TICKERS industry (dle zadani).",
          "- industry_rank_calendar projekt necten (jen archive CSV).", ""]
    (out_dir / "IRC-RECON-01_archive_inventory.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
