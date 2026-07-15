"""
mle_recon01c_universe_diag.py — MLE-RECON-01C universe/ranked diagnostics.

READ-ONLY. Zjisti, proc recon ranguje 503 tickeru vs archiv 497.
Overi: (1) input window (full vs 45d slice), (2) recon_only tickery,
(3) per-date rank ve full vs sliced rezimu.

NEDELA: MLE-RECON rerun, IRC, backtest, API/TWS, zmenu dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\mle_recon01c_universe_diag.py

Edge cases:
    - alternativni ticker formaty: BRK.B/BRK-B/BRKB, BF.B/BF-B/BFB.
    - sliced rezim: run_date - 45 kalendarnich dni (jako MLE original).
    - full rezim: cela DATA-06 serie (jako soucasny MLE-RECON-01).
    - rank ve sliced: engine dostane jen okno -> ticker bez 10d historie
      v okne nedostane rank_10d.
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

RECON_ONLY = ["BF.B", "BRK.B", "EXE", "PSKY", "Q", "SNDK"]
START_BUFFER = 45
GATE_LB = 10
CLEAN_DAY = "2026-03-20"
ALT_FORMATS = {"BRK.B": ["BRK-B", "BRKB", "BRK.B"],
               "BF.B": ["BF-B", "BFB", "BF.B"]}


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_close(view_dir, conid):
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
    ap.add_argument("--mdsm-prices",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\cache\prices")
    ap.add_argument("--mle-archive",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive\rank_matrix_archive.csv")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--clean-day", default=CLEAN_DAY)
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
    mdsm_dir = Path(args.mdsm_prices)

    # universe
    udf = pd.read_csv(args.universe_csv, dtype=str)
    cols = {c.lower(): c for c in udf.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    tick2conid = {}
    tick2order = {}
    tick2active = {}
    for i, (_, r) in enumerate(udf.iterrows()):
        tk = str(r[tcol]).strip().upper()
        tick2conid[tk] = str(r[ccol])
        tick2order[tk] = i
        tick2active[tk] = is_active(r[acol])

    # archiv
    adf = pd.read_csv(args.mle_archive, dtype={"date": str}, low_memory=False)
    adf["ticker"] = adf["ticker"].astype(str).str.upper()
    arch_tickers = set(adf["ticker"])

    report = {"input_window": {}, "recon_only_tickers": {},
              "per_date_check": {}}

    # ── 1. input window ──
    # zjisti, jak MLE-RECON-01 nacita (full vs slice) — staticky z faktu,
    # ze load_close_series cte cely parquet.
    report["input_window"] = {
        "mle_original": f"run_date - {START_BUFFER} kalendarnich dni "
                        f"(extended_start .. run_date)",
        "mle_recon01": "cela DATA-06 serie per ticker (bez oriznuti okna)",
        "difference": "recon posila FULL series, MLE original 45d slice",
        "methodological_note": ("recon full-series muze dat rank tickerum, "
                                "ktere MLE original v 45d okne vyloucil "
                                "(nedostatek historie) -> ranking universe "
                                "mismatch"),
        "classification": "METHODOLOGICAL_DIFFERENCE_RECON"}

    # ── 2. recon_only tickery ──
    for tk in RECON_ONLY:
        info = {"ticker": tk}
        conid = tick2conid.get(tk)
        info["conid"] = conid
        info["in_universe"] = tk in tick2conid
        info["active_flag"] = tick2active.get(tk)
        info["universe_order"] = tick2order.get(tk)
        # DATA-06 file
        if conid:
            vf = view_dir / f"{conid}_D1.parquet"
            info["data06_file_exists"] = vf.exists()
            if vf.exists():
                s = load_close(view_dir, conid)
                if s is not None and not s.empty:
                    info["data06_first"] = str(s.index.min().date())
                    info["data06_last"] = str(s.index.max().date())
                    info["data06_rows"] = len(s)
            # MDSM cache file
            mf = mdsm_dir / f"{conid}_D1.parquet"
            info["mdsm_file_exists"] = mf.exists()
            if mf.exists():
                try:
                    m = pd.read_parquet(mf)
                    m.index = pd.to_datetime(m.index).normalize()
                    info["mdsm_first"] = str(m.index.min().date())
                    info["mdsm_last"] = str(m.index.max().date())
                    info["mdsm_rows"] = len(m)
                except Exception as e:  # noqa: BLE001
                    info["mdsm_error"] = str(e)
        # v archivu?
        info["in_archive"] = tk in arch_tickers
        # alternativni formaty
        alts = ALT_FORMATS.get(tk, [])
        info["alt_formats_in_archive"] = {
            alt: (alt.upper() in arch_tickers) for alt in alts}
        report["recon_only_tickers"][tk] = info

    # ── 3. per-date check: full vs sliced rezim pro clean_day ──
    # nacti VSECHNY close_prices (full) v poradi universe
    active_instruments = []
    close_full = {}
    for tk, order in sorted(tick2order.items(), key=lambda x: x[1]):
        if not tick2active.get(tk):
            continue
        conid = tick2conid.get(tk)
        s = load_close(view_dir, conid) if conid else None
        if s is not None and not s.empty:
            close_full[tk] = s
            active_instruments.append(
                {"conid": int(float(conid)), "ticker": tk,
                 "sector": "", "industry": "", "subcategory": ""})

    run_date = date.fromisoformat(args.clean_day)
    # sliced: orizni kazdou serii na [run_date-45d, run_date]
    slice_start = pd.Timestamp(run_date - timedelta(days=START_BUFFER))
    slice_end = pd.Timestamp(run_date)
    close_sliced = {}
    for tk, s in close_full.items():
        sub = s[(s.index >= slice_start) & (s.index <= slice_end)]
        if not sub.empty:
            close_sliced[tk] = sub

    # compute full
    rm_full = compute_rank_matrix(close_full, active_instruments,
                                  run_date, [GATE_LB])
    rm_full_idx = rm_full.set_index("ticker")
    # compute sliced
    sliced_instruments = [i for i in active_instruments
                          if i["ticker"] in close_sliced]
    try:
        rm_sliced = compute_rank_matrix(close_sliced, sliced_instruments,
                                        run_date, [GATE_LB])
        rm_sliced_idx = rm_sliced.set_index("ticker")
    except Exception as e:  # noqa: BLE001
        rm_sliced_idx = None
        report["per_date_check"]["sliced_error"] = str(e)

    rcol = f"rank_{GATE_LB}d"
    # ranked counts
    full_ranked = {t for t in rm_full_idx.index
                   if not pd.isna(rm_full_idx.loc[t, rcol])}
    report["per_date_check"]["full_ranked_count"] = len(full_ranked)
    if rm_sliced_idx is not None:
        sliced_ranked = {t for t in rm_sliced_idx.index
                         if not pd.isna(rm_sliced_idx.loc[t, rcol])}
        report["per_date_check"]["sliced_ranked_count"] = len(sliced_ranked)
        report["per_date_check"]["full_only_ranked"] = \
            sorted(full_ranked - sliced_ranked)[:30]

    # pro 6 recon_only: rank ve full vs sliced
    detail = {}
    for tk in RECON_ONLY:
        d = {"in_full_ranked": tk in full_ranked}
        if tk in rm_full_idx.index:
            rv = rm_full_idx.loc[tk, rcol]
            d["full_rank"] = None if pd.isna(rv) else int(rv)
        if rm_sliced_idx is not None:
            d["in_sliced_ranked"] = tk in (sliced_ranked
                                           if 'sliced_ranked' in dir() else set())
            if tk in rm_sliced_idx.index:
                rv = rm_sliced_idx.loc[tk, rcol]
                d["sliced_rank"] = None if pd.isna(rv) else int(rv)
            else:
                d["sliced_rank"] = "not_in_sliced_universe"
        # close_now / close_past 10d
        s = close_full.get(tk)
        if s is not None:
            avail = s[s.index <= pd.Timestamp(run_date)]
            d["has_close_now"] = not avail.empty
            d["n_days_available_full"] = len(avail)
            ssub = close_sliced.get(tk)
            d["n_days_available_sliced"] = len(ssub) if ssub is not None else 0
        detail[tk] = d
    report["per_date_check"]["recon_only_detail"] = detail

    _write(report, mrl, args.out)

    print("==== MLE-RECON-01C universe diag ====")
    print(f"input_window: {report['input_window']['difference']}")
    print(f"\nper_date_check ({args.clean_day}):")
    print(f"  full_ranked: {report['per_date_check'].get('full_ranked_count')}")
    print(f"  sliced_ranked: {report['per_date_check'].get('sliced_ranked_count')}")
    print(f"  full_only_ranked: {report['per_date_check'].get('full_only_ranked')}")
    print("\nrecon_only tickery:")
    for tk, info in report["recon_only_tickers"].items():
        print(f"  {tk}: conid={info.get('conid')} "
              f"in_archive={info.get('in_archive')} "
              f"alt={info.get('alt_formats_in_archive')} "
              f"data06={info.get('data06_first')}..{info.get('data06_last')}")
    return 0


def _write(report, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-RECON-01C_universe_ranked_diagnostics.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    iw = report["input_window"]
    pd_ = report["per_date_check"]
    L = ["# MLE-RECON-01C — Universe / Ranked Diagnostics", "",
         "## 1. Input window", "",
         f"- MLE original: {iw['mle_original']}",
         f"- MLE-RECON-01: {iw['mle_recon01']}",
         f"- rozdil: {iw['difference']}",
         f"- **{iw['classification']}**",
         f"- poznamka: {iw['methodological_note']}", "",
         "## 2. recon_only tickery", ""]
    for tk, info in report["recon_only_tickers"].items():
        L.append(f"### {tk}")
        L.append(f"- conid: {info.get('conid')}")
        L.append(f"- in_universe: {info.get('in_universe')}, "
                 f"active: {info.get('active_flag')}, "
                 f"order: {info.get('universe_order')}")
        L.append(f"- data06: exists={info.get('data06_file_exists')} "
                 f"range={info.get('data06_first')}..{info.get('data06_last')} "
                 f"rows={info.get('data06_rows')}")
        L.append(f"- mdsm_cache: exists={info.get('mdsm_file_exists')} "
                 f"range={info.get('mdsm_first')}..{info.get('mdsm_last')} "
                 f"rows={info.get('mdsm_rows')}")
        L.append(f"- in_archive: {info.get('in_archive')}")
        L.append(f"- alt_formats_in_archive: {info.get('alt_formats_in_archive')}")
        L.append("")
    L += ["## 3. Per-date check (full vs sliced)", "",
          f"- clean_day: {pd_.get('full_ranked_count')} full ranked, "
          f"{pd_.get('sliced_ranked_count')} sliced ranked",
          f"- full_only_ranked (rank ve full, ne ve sliced): "
          f"{pd_.get('full_only_ranked')}", "",
          "### recon_only detail (full vs sliced rank)", ""]
    for tk, d in pd_.get("recon_only_detail", {}).items():
        L.append(f"- {tk}: full_rank={d.get('full_rank')} "
                 f"sliced_rank={d.get('sliced_rank')} "
                 f"days_full={d.get('n_days_available_full')} "
                 f"days_sliced={d.get('n_days_available_sliced')}")
    L += ["", "## Zaver", "",
          "- pokud full_only_ranked obsahuje recon_only tickery -> "
          "potvrzeno: full-series rezim dava rank tickerum, ktere sliced "
          "(MLE original) vyloucil.",
          "- oprava: MLE-RECON musi orezavat na 45d okno jako MLE original,",
          "  NEBO rangovat jen pres archive-ranked tickery per den.", "",
          "## Vyhrady", "",
          "- alt ticker formaty: kontrolovany BRK.B/BRK-B/BRKB, BF.B/BF-B/BFB.",
          "- sliced rezim: 45 KALENDARNICH dni (jako MLE start_buffer).", ""]
    (out_dir / "MLE-RECON-01C_universe_ranked_diagnostics.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
