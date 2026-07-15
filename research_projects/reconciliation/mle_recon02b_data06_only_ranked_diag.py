"""
mle_recon02b_data06_only_ranked_diag.py — MLE-RECON-02B.

READ-ONLY. Vysvetli data06_only_ranked_total=514 z MLE-RECON-02.
Pro kazdy pripad (DATA-06 ma rank, MDSM cache ne) klasifikuje pricinu.

NEDELA: MLE-RECON-02 opravu, IRC, backtest, MLE archive overwrite,
API/TWS, zmenu dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\mle_recon02b_data06_only_ranked_diag.py

Reason klasifikace:
    MDSM_file_missing         : {conid}_D1.parquet neexistuje v cache
    MDSM_missing_close_now     : cache nema close pro target_date
    MDSM_missing_close_past    : cache nema close pro past_date
    MDSM_insufficient_45d_window: cache ma < lookback+1 dni v okne
    MDSM_cache_gap             : cache ma data pred i po, ale gap v okne
    ticker_mapping_issue       : conid nesedi
    unknown                    : jine

Edge cases / predpoklady:
    - MDSM/DATA-06 price_matrix = compute_rank_matrix per 45d slice.
    - data06_only = ticker s ne-NaN rank v DATA-06 compute, ale ne v MDSM.
    - past_idx = target_idx - lookback (pozicni, MLE engine).
    - reason se urcuje z MDSM cache serie daneho tickeru v 45d okne.
    - engine z MLE.
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
START_BUFFER = 45
INSUFFICIENT = {"EXE", "PSKY", "Q", "SNDK"}


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_universe(ucsv):
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    instruments = []
    tick2conid = {}
    order = {}
    idx = 0
    for _, r in df.iterrows():
        if not is_active(r[acol]):
            continue
        tk = str(r[tcol]).strip().upper()
        instruments.append({"conid": int(float(r[ccol])), "ticker": tk,
                            "sector": "", "industry": "", "subcategory": ""})
        tick2conid[tk] = str(r[ccol])
        order[tk] = idx
        idx += 1
    return instruments, tick2conid, order


def load_series(dir_path, conid):
    f = dir_path / f"{conid}_D1.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    if "close" not in df.columns:
        return None
    df.index = pd.to_datetime(df.index).normalize()
    return df["close"].sort_index()


def build_cp(dir_path, instruments, tick2conid):
    cp = {}
    meta = {}
    for inst in instruments:
        tk = inst["ticker"]
        s = load_series(dir_path, tick2conid[tk])
        if s is not None and not s.empty:
            cp[tk] = s
            meta[tk] = (str(s.index.min().date()), str(s.index.max().date()),
                        len(s))
    return cp, meta


def slice_window(cp, run_date):
    ws = pd.Timestamp(run_date - timedelta(days=START_BUFFER))
    we = pd.Timestamp(run_date)
    out = {}
    for tk, s in cp.items():
        sub = s[(s.index >= ws) & (s.index <= we)]
        if not sub.empty:
            out[tk] = sub
    return out


def classify_reason(tk, conid, lb, run_date, mdsm_cp, mdsm_meta,
                    mdsm_dir, d_slice):
    """Proc MDSM nema rank pro tento ticker/lookback/den."""
    mf = mdsm_dir / f"{conid}_D1.parquet"
    if not mf.exists():
        return "MDSM_file_missing", {}
    if tk not in mdsm_cp:
        return "MDSM_file_missing", {}  # nacetl se prazdny
    # MDSM 45d slice
    ws = pd.Timestamp(run_date - timedelta(days=START_BUFFER))
    we = pd.Timestamp(run_date)
    s = mdsm_cp[tk]
    m_sub = s[(s.index >= ws) & (s.index <= we)]
    detail = {"mdsm_first": mdsm_meta.get(tk, (None,))[0],
              "mdsm_last": mdsm_meta.get(tk, (None, None))[1],
              "mdsm_window_rows": len(m_sub)}
    if m_sub.empty:
        return "MDSM_insufficient_45d_window", detail
    # target/past v MDSM okne
    idx = m_sub.index
    avail = idx[idx <= we]
    if len(avail) == 0:
        return "MDSM_missing_close_now", detail
    m_target = avail[-1]
    tpos = len(avail) - 1
    ppos = tpos - lb
    detail["mdsm_target_date"] = str(m_target.date())
    detail["mdsm_window_trading_days"] = len(avail)
    if ppos < 0:
        return "MDSM_insufficient_45d_window", detail
    m_past = avail[ppos]
    detail["mdsm_past_date"] = str(m_past.date())
    # close hodnoty
    cn = m_sub.get(m_target)
    cp_ = m_sub.get(m_past)
    if pd.isna(cn):
        return "MDSM_missing_close_now", detail
    if pd.isna(cp_):
        return "MDSM_missing_close_past", detail
    # DATA-06 past date pro srovnani
    d_target_past = None
    if tk in d_slice:
        didx = d_slice[tk].index
        davail = didx[didx <= we]
        if len(davail) > lb:
            d_target_past = str(davail[len(davail) - 1 - lb].date())
    detail["data06_past_date"] = d_target_past
    # gap: MDSM ma data pred i po okne, ale mene trading dni nez DATA-06
    if tk in d_slice:
        d_window = len(d_slice[tk].index[d_slice[tk].index <= we])
        if len(avail) < d_window:
            detail["data06_window_trading_days"] = d_window
            return "MDSM_cache_gap", detail
    return "unknown", detail


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
    instruments, tick2conid, order = load_universe(Path(args.universe_csv))
    mdsm_dir = Path(args.mdsm_prices)
    view_dir = Path(args.view_dir)

    cp_mdsm, meta_mdsm = build_cp(mdsm_dir, instruments, tick2conid)
    cp_data06, meta_data06 = build_cp(view_dir, instruments, tick2conid)
    print(f"MDSM {len(cp_mdsm)}, DATA-06 {len(cp_data06)}")

    adf = pd.read_csv(args.mle_archive, dtype={"date": str}, low_memory=False)
    arch_dates = sorted(d for d in adf["date"].unique()
                        if args.range_from <= d <= args.range_to)
    print(f"dni: {len(arch_dates)}")

    cases = []
    for tdate in arch_dates:
        run_date = date.fromisoformat(tdate)
        m_slice = slice_window(cp_mdsm, run_date)
        d_slice = slice_window(cp_data06, run_date)
        m_inst = [i for i in instruments if i["ticker"] in m_slice]
        d_inst = [i for i in instruments if i["ticker"] in d_slice]
        if not m_slice or not d_slice:
            continue
        try:
            rm_m = compute_rank_matrix(m_slice, m_inst, run_date, LOOKBACKS).set_index("ticker")
            rm_d = compute_rank_matrix(d_slice, d_inst, run_date, LOOKBACKS).set_index("ticker")
        except Exception:  # noqa: BLE001
            continue
        for lb in LOOKBACKS:
            rcol = f"rank_{lb}d"
            m_ranked = {t for t in rm_m.index if not pd.isna(rm_m.loc[t, rcol])}
            d_ranked = {t for t in rm_d.index if not pd.isna(rm_d.loc[t, rcol])}
            only = d_ranked - m_ranked
            for tk in only:
                conid = tick2conid.get(tk)
                reason, detail = classify_reason(
                    tk, conid, lb, run_date, cp_mdsm, meta_mdsm, mdsm_dir, d_slice)
                cases.append({"date": tdate, "lookback": lb, "ticker": tk,
                              "conid": conid,
                              "universe_order": order.get(tk),
                              "reason": reason,
                              "mdsm_first": detail.get("mdsm_first"),
                              "mdsm_last": detail.get("mdsm_last"),
                              "mdsm_window_rows": detail.get("mdsm_window_rows"),
                              "data06_first": meta_data06.get(tk, (None,))[0],
                              "data06_last": meta_data06.get(tk, (None, None))[1]})

    # souhrn
    total = len(cases)
    uniq_tk = sorted({c["ticker"] for c in cases})
    by_reason = {}
    by_lb = {}
    by_date = {}
    by_ticker = {}
    for c in cases:
        by_reason[c["reason"]] = by_reason.get(c["reason"], 0) + 1
        by_lb[c["lookback"]] = by_lb.get(c["lookback"], 0) + 1
        by_date[c["date"]] = by_date.get(c["date"], 0) + 1
        by_ticker[c["ticker"]] = by_ticker.get(c["ticker"], 0) + 1
    top_tickers = sorted(by_ticker.items(), key=lambda x: -x[1])[:20]
    # zhorseni s lookbackem
    lb_trend = [(lb, by_lb.get(lb, 0)) for lb in LOOKBACKS]
    worsens = (by_lb.get(20, 0) > by_lb.get(1, 0))
    # koncentrace na EXE/PSKY/Q/SNDK
    insuf_cases = sum(by_ticker.get(t, 0) for t in INSUFFICIENT)
    insuf_share = round(insuf_cases / total, 4) if total else 0

    summary = {
        "total_data06_only_observations": total,
        "unique_tickers": len(uniq_tk),
        "unique_ticker_list": uniq_tk[:50],
        "count_by_reason": by_reason,
        "count_by_lookback": by_lb,
        "top_affected_tickers": top_tickers,
        "worsens_with_lookback": worsens,
        "lookback_trend": lb_trend,
        "insufficient_history_cases": insuf_cases,
        "insufficient_history_share": insuf_share,
        "count_by_date_sample": dict(sorted(by_date.items())[:10]),
        "n_dates_affected": len(by_date),
        "cases_sample": cases[:50],
    }

    _write(summary, mrl, args.out)
    print(f"\n==== MLE-RECON-02B ====")
    print(f"total data06_only: {total}, unique tickers: {len(uniq_tk)}")
    print(f"count_by_reason: {by_reason}")
    print(f"worsens_with_lookback: {worsens} (L1={by_lb.get(1)}, L20={by_lb.get(20)})")
    print(f"insufficient_history (EXE/PSKY/Q/SNDK) share: {insuf_share} "
          f"({insuf_cases}/{total})")
    print(f"top affected: {top_tickers[:8]}")
    return 0


def _write(summary, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-RECON-02B_data06_only_ranked_diagnostics.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    L = ["# MLE-RECON-02B — data06_only_ranked Diagnostics", "",
         "## Souhrn", "",
         f"- total_data06_only_observations: {summary['total_data06_only_observations']}",
         f"- unique_tickers: {summary['unique_tickers']}",
         f"- count_by_reason: {summary['count_by_reason']}",
         f"- worsens_with_lookback: {summary['worsens_with_lookback']}",
         f"- insufficient_history_share (EXE/PSKY/Q/SNDK): "
         f"{summary['insufficient_history_share']} "
         f"({summary['insufficient_history_cases']}/"
         f"{summary['total_data06_only_observations']})",
         f"- n_dates_affected: {summary['n_dates_affected']}", "",
         "## Count by lookback", ""]
    for lb, n in summary["lookback_trend"]:
        L.append(f"- L{lb}: {n}")
    L += ["", "## Top affected tickers", ""]
    for tk, n in summary["top_affected_tickers"]:
        L.append(f"- {tk}: {n}")
    L += ["", "## Unique ticker list (sample)", "",
          f"{summary['unique_ticker_list']}", "",
          "## Cases sample (prvnich 50)", "",
          "| date | lb | ticker | conid | reason | mdsm_range | data06_range |",
          "|---|---|---|---|---|---|---|"]
    for c in summary["cases_sample"]:
        L.append(f"| {c['date']} | {c['lookback']} | {c['ticker']} | "
                 f"{c['conid']} | {c['reason']} | "
                 f"{c['mdsm_first']}..{c['mdsm_last']} | "
                 f"{c['data06_first']}..{c['data06_last']} |")
    L += ["", "## Zaver (interpretace)", "",
          "- pokud vetsina reason = MDSM_insufficient_45d_window / "
          "MDSM_missing_close_past / MDSM_cache_gap / MDSM_file_missing:",
          "  MDSM cache NENI kompletni rank oracle -> rank recon proti MDSM",
          "  cache je metodicky omezena.",
          "- pokud reason = ticker_mapping_issue: bug v mapovani -> opravit.",
          "- pokud koncentrace na EXE/PSKY/Q/SNDK: znama insufficient history.",
          "- pokud sirsi mnozina: MDSM cache coverage limit obecne.", "",
          "## Vyhrady", "",
          "- reason klasifikace z MDSM cache serie v 45d okne.",
          "- data06_only = rank v DATA-06 compute, ne v MDSM compute.",
          "- 45d okno, engine z MLE.", ""]
    (out_dir / "MLE-RECON-02B_data06_only_ranked_diagnostics.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
