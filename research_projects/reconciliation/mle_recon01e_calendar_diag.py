"""
mle_recon01e_calendar_diag.py — MLE-RECON-01E calendar/close_past diag.

READ-ONLY. Overi, zda zbytkove clean mismatche (klastry 2026-06-25,
2026-06-16) vznikaji rozdilem past_date mezi MDSM cache a DATA-06.

NEDELA: MLE recon oprava, IRC, backtest, API/TWS, zmenu dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\mle_recon01e_calendar_diag.py

Metoda:
    Pro kazdy diag den porovna:
    - MDSM price_matrix index (vsechny MDSM cache trading dates v okne)
    - DATA-06 price_matrix index (vsechny DATA-06 trading dates v okne)
    - target_idx, past_idx (target - 10), resolved past_date v OBOU
    - close_now, close_past, computed ret v obou

Klasifikace:
    A) calendar_mismatch_confirmed: mdsm_past_date != data06_past_date
    B) price_value_mismatch: past_date sedi, close_past se lisi
    C) archive_compute_mismatch: computed_ret_mdsm != arch_ret
    D) corporate_action_or_unknown: jen jednotlivci, ne plosny posun

Edge cases / predpoklady:
    - MDSM price_matrix index = UNION vsech MDSM cache dat (jako MLE engine
      pd.DataFrame(close_prices)). ALE MLE original mel jen ~45d okno a jen
      universe tickery s daty -> index muze byt jiny. ZDE aproximace:
      MDSM index = union MDSM cache dat vsech universe tickeru v okne.
    - DATA-06 index = union DATA-06 dat.
    - past_idx = target_idx - lookback (pozicni, jako MLE engine).
    - close_past se bere z resolved past_date daneho indexu.
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

LOOKBACK = 10
START_BUFFER = 45

CLUSTER_1 = ("2026-06-25", ["SMCI", "TECH", "MU", "TER", "GLW", "AMAT",
                            "CAT", "GNRC"])
CLUSTER_2 = ("2026-06-16", ["COHR", "LITE", "CASY", "HPE", "GLW", "MPWR"])
FTV_DAYS = ["2025-07-09", "2025-07-10", "2025-07-11", "2025-07-14"]


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_universe(ucsv):
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    tick2conid = {}
    for _, r in df.iterrows():
        if is_active(r[acol]):
            tick2conid[str(r[tcol]).strip().upper()] = str(r[ccol])
    return tick2conid


def load_series(view_dir, conid):
    f = view_dir / f"{conid}_D1.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    if "close" not in df.columns:
        return None
    df.index = pd.to_datetime(df.index).normalize()
    return df["close"].sort_index()


def build_index(dir_path, tick2conid, tickers, win_start, win_end):
    """Union trading dates vsech tickeru v okne (price_matrix index)."""
    all_dates = set()
    per_ticker = {}
    for tk in tickers:
        conid = tick2conid.get(tk)
        if not conid:
            continue
        s = load_series(dir_path, conid)
        if s is None:
            continue
        sub = s[(s.index >= win_start) & (s.index <= win_end)]
        per_ticker[tk] = sub
        all_dates |= set(sub.index)
    idx = pd.DatetimeIndex(sorted(all_dates))
    return idx, per_ticker


def resolve_past(idx, target_ts, lookback):
    avail = idx[idx <= target_ts]
    if len(avail) == 0:
        return None, None, None, None
    tpos = len(avail) - 1
    target_res = avail[-1]
    ppos = tpos - lookback
    if ppos < 0:
        return target_res, None, tpos, None
    return target_res, avail[ppos], tpos, ppos


def diag_day(tdate, tickers, tick2conid, mdsm_dir, view_dir, adf_idx):
    tdate_ts = pd.Timestamp(tdate)
    win_start = tdate_ts - timedelta(days=START_BUFFER)
    win_end = tdate_ts
    # potrebujeme VSECHNY universe tickery pro spravny price_matrix index
    all_tk = list(tick2conid.keys())
    mdsm_idx, mdsm_pt = build_index(mdsm_dir, tick2conid, all_tk,
                                    win_start, win_end)
    d06_idx, d06_pt = build_index(view_dir, tick2conid, all_tk,
                                  win_start, win_end)

    out = {"date": tdate,
           "mdsm_index_count": len(mdsm_idx),
           "data06_index_count": len(d06_idx),
           "dates_only_in_mdsm": [str(d.date()) for d in
                                  sorted(set(mdsm_idx) - set(d06_idx))][:20],
           "dates_only_in_data06": [str(d.date()) for d in
                                    sorted(set(d06_idx) - set(mdsm_idx))][:20],
           "tickers": {}}

    m_target, m_past, m_tpos, m_ppos = resolve_past(mdsm_idx, tdate_ts, LOOKBACK)
    d_target, d_past, d_tpos, d_ppos = resolve_past(d06_idx, tdate_ts, LOOKBACK)
    out["mdsm_target_date"] = str(m_target.date()) if m_target is not None else None
    out["mdsm_past_date"] = str(m_past.date()) if m_past is not None else None
    out["data06_target_date"] = str(d_target.date()) if d_target is not None else None
    out["data06_past_date"] = str(d_past.date()) if d_past is not None else None
    out["past_date_match"] = (out["mdsm_past_date"] == out["data06_past_date"])

    for tk in tickers:
        conid = tick2conid.get(tk)
        info = {"conid": conid}
        # arch ret
        try:
            arch_row = adf_idx.loc[(tdate, tk.upper())]
            info["arch_ret_10d"] = float(arch_row.get(f"ret_{LOOKBACK}d"))
        except (KeyError, TypeError):
            info["arch_ret_10d"] = None
        # MDSM close now/past
        ms = mdsm_pt.get(tk)
        if ms is not None and m_target is not None:
            info["mdsm_close_now"] = (round(float(ms.get(m_target)), 4)
                                      if m_target in ms.index else None)
            info["mdsm_close_past"] = (round(float(ms.get(m_past)), 4)
                                       if m_past is not None and m_past in ms.index else None)
            if info.get("mdsm_close_now") and info.get("mdsm_close_past"):
                info["computed_ret_from_mdsm"] = round(
                    (info["mdsm_close_now"] / info["mdsm_close_past"] - 1) * 100, 2)
        # DATA-06 close now/past
        ds = d06_pt.get(tk)
        if ds is not None and d_target is not None:
            info["data06_close_now"] = (round(float(ds.get(d_target)), 4)
                                        if d_target in ds.index else None)
            info["data06_close_past"] = (round(float(ds.get(d_past)), 4)
                                         if d_past is not None and d_past in ds.index else None)
            if info.get("data06_close_now") and info.get("data06_close_past"):
                info["computed_ret_from_data06"] = round(
                    (info["data06_close_now"] / info["data06_close_past"] - 1) * 100, 2)
        # diffs
        if info.get("mdsm_close_now") and info.get("data06_close_now"):
            info["close_now_diff"] = round(
                abs(info["mdsm_close_now"] - info["data06_close_now"]), 4)
        if info.get("mdsm_close_past") and info.get("data06_close_past"):
            info["close_past_diff"] = round(
                abs(info["mdsm_close_past"] - info["data06_close_past"]), 4)
        # ret_diff arch vs recon(data06)
        if info.get("arch_ret_10d") is not None and \
                info.get("computed_ret_from_data06") is not None:
            info["ret_diff"] = round(
                abs(info["arch_ret_10d"] - info["computed_ret_from_data06"]), 2)
        out["tickers"][tk] = info

    # klasifikace dne
    if not out["past_date_match"]:
        out["classification"] = "calendar_mismatch_confirmed"
    else:
        # past_date sedi -> zkontroluj close_past diffy
        cp_diffs = [i.get("close_past_diff") for i in out["tickers"].values()
                    if i.get("close_past_diff") is not None]
        big_cp = [d for d in cp_diffs if d > 0.05]
        # archive_compute: computed_mdsm vs arch_ret
        ac_mism = 0
        for i in out["tickers"].values():
            if i.get("computed_ret_from_mdsm") is not None and \
                    i.get("arch_ret_10d") is not None:
                if abs(i["computed_ret_from_mdsm"] - i["arch_ret_10d"]) > 0.01:
                    ac_mism += 1
        if len(big_cp) >= len(out["tickers"]) * 0.5:
            out["classification"] = "price_value_mismatch"
        elif ac_mism >= len(out["tickers"]) * 0.5:
            out["classification"] = "archive_compute_mismatch"
        else:
            out["classification"] = "corporate_action_or_unknown"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--mdsm-prices",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\cache\prices")
    ap.add_argument("--mle-archive",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive\rank_matrix_archive.csv")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    tick2conid = load_universe(Path(args.universe_csv))
    mdsm_dir = Path(args.mdsm_prices)
    view_dir = Path(args.view_dir)

    adf = pd.read_csv(args.mle_archive, dtype={"date": str}, low_memory=False)
    adf["ticker"] = adf["ticker"].astype(str).str.upper()
    adf_idx = adf.set_index(["date", "ticker"])

    results = {"clusters": {}}
    for label, (day, tickers) in [("cluster_2026-06-25", CLUSTER_1),
                                  ("cluster_2026-06-16", CLUSTER_2)]:
        print(f"diag {label} ({day}) ...")
        results["clusters"][label] = diag_day(
            day, tickers, tick2conid, mdsm_dir, view_dir, adf_idx)

    # FTV zvlast
    results["ftv"] = {}
    for day in FTV_DAYS:
        print(f"diag FTV {day} ...")
        results["ftv"][day] = diag_day(
            day, ["FTV"], tick2conid, mdsm_dir, view_dir, adf_idx)

    _write(results, mrl, args.out)

    print("\n==== MLE-RECON-01E ====")
    for label, r in results["clusters"].items():
        print(f"\n{label}: {r['classification']}")
        print(f"  mdsm_index {r['mdsm_index_count']} vs data06 {r['data06_index_count']}")
        print(f"  mdsm_past={r['mdsm_past_date']} data06_past={r['data06_past_date']} "
              f"match={r['past_date_match']}")
        print(f"  only_mdsm: {r['dates_only_in_mdsm']}")
        print(f"  only_data06: {r['dates_only_in_data06']}")
    for day, r in results["ftv"].items():
        print(f"\nFTV {day}: {r['classification']} "
              f"past_match={r['past_date_match']}")
    return 0


def _write(results, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-RECON-01E_calendar_close_past_diagnostics.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8")
    L = ["# MLE-RECON-01E — Calendar / close_past Diagnostics", ""]
    for label, r in results["clusters"].items():
        L += [f"## {label} ({r['date']})", "",
              f"- **classification: {r['classification']}**",
              f"- mdsm_index_count: {r['mdsm_index_count']}",
              f"- data06_index_count: {r['data06_index_count']}",
              f"- mdsm_target_date: {r['mdsm_target_date']}",
              f"- mdsm_past_date: {r['mdsm_past_date']}",
              f"- data06_target_date: {r['data06_target_date']}",
              f"- data06_past_date: {r['data06_past_date']}",
              f"- **past_date_match: {r['past_date_match']}**",
              f"- dates_only_in_mdsm: {r['dates_only_in_mdsm']}",
              f"- dates_only_in_data06: {r['dates_only_in_data06']}", "",
              "### Tickery", ""]
        for tk, i in r["tickers"].items():
            L.append(f"#### {tk}")
            L.append(f"- arch_ret_10d: {i.get('arch_ret_10d')}")
            L.append(f"- computed_ret_from_mdsm: {i.get('computed_ret_from_mdsm')}")
            L.append(f"- computed_ret_from_data06: {i.get('computed_ret_from_data06')}")
            L.append(f"- ret_diff (arch vs data06): {i.get('ret_diff')}")
            L.append(f"- mdsm close: now={i.get('mdsm_close_now')} "
                     f"past={i.get('mdsm_close_past')}")
            L.append(f"- data06 close: now={i.get('data06_close_now')} "
                     f"past={i.get('data06_close_past')}")
            L.append(f"- close_now_diff={i.get('close_now_diff')} "
                     f"close_past_diff={i.get('close_past_diff')}")
            L.append("")
    L += ["## FTV (2025-07-09 .. 07-14)", ""]
    for day, r in results["ftv"].items():
        i = r["tickers"].get("FTV", {})
        L.append(f"### {day} — {r['classification']} "
                 f"(past_match={r['past_date_match']})")
        L.append(f"- mdsm_past={r['mdsm_past_date']} "
                 f"data06_past={r['data06_past_date']}")
        L.append(f"- arch_ret={i.get('arch_ret_10d')} "
                 f"computed_data06={i.get('computed_ret_from_data06')} "
                 f"ret_diff={i.get('ret_diff')}")
        L.append(f"- close: mdsm now={i.get('mdsm_close_now')} "
                 f"past={i.get('mdsm_close_past')} | "
                 f"data06 now={i.get('data06_close_now')} "
                 f"past={i.get('data06_close_past')}")
        L.append("")
    L += ["## Klasifikace (vyznam)", "",
          "- calendar_mismatch_confirmed: mdsm_past_date != data06_past_date",
          "  -> recon musi pouzit stejny trading calendar jako MDSM archiv.",
          "- price_value_mismatch: past_date sedi, close_past se lisi.",
          "- archive_compute_mismatch: computed_ret_mdsm != arch_ret.",
          "- corporate_action_or_unknown: jen jednotlivci.", "",
          "## Vyhrady", "",
          "- MDSM/DATA-06 price_matrix index = union vsech universe tickeru",
          "  v 45d okne (aproximace MLE engine indexu).",
          "- MLE original mel jen universe tickery s daty v MDSM cache;",
          "  presny index nelze rekonstruovat bez puvodniho behu.", ""]
    (out_dir / "MLE-RECON-01E_calendar_close_past_diagnostics.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
