"""
run_fund03_extract_candidate_days.py — deterministic extrakce reálných
MLE × IRC candidate-days pro FUND-03 coverage audit.

Zdroj (FUND-03 source review, varianta B):
    MLE  rank_matrix_archive.csv          (date, ticker, rank_10d, ...)
    IRC  industry_rank_calendar_archive.csv (date, lookback, rank, industry)
    join: MDSM sp500 universe CSV          (ticker -> conid, industry)

Definice candidate-day (konzervativní baseline):
    MLE rank_10d <= --mle-top (default 10)
    AND IRC rank(industry, lookback=--irc-lookback) <= --irc-top (default 10)
    na TÝŽ den; pouze dny přítomné v obou archivech.

ŽÁDNÉ forward returns, ŽÁDNÉ edge metriky. Trailing ret_* sloupce
MLE archivu (vstupy rankingu) se NEPŘENÁŠEJÍ. Zakázané sloupce
(future/forward/return_*d/hit/pnl) ve výstupu nevznikají by construction.

Determinismus: sort (candidate_date, conid), exact-duplicate dedup,
SHA-256 hashe zdrojů v manifestu.

Výstup: <out-dir>/candidate_days.csv + extraction_manifest.json
Exit: 0 OK, 2 setup/data fail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

MRL_ROOT = Path(__file__).resolve().parent

OUTPUT_COLUMNS = ("conid", "candidate_date", "ticker", "mle_rank",
                  "irc_rank", "source_signal_label")


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(mle_path, irc_path, universe_path, mle_top: int,
            irc_top: int, irc_lookback: int):
    """Vrací (candidate_days_df, stats_dict). Deterministické."""
    mle = pd.read_csv(mle_path, low_memory=False)
    irc = pd.read_csv(irc_path)
    uni = pd.read_csv(universe_path)

    for col, src in ((("date", "ticker", "rank_10d"), "MLE"),
                     (("date", "lookback", "rank", "industry"), "IRC"),
                     (("conid", "ticker", "industry"), "universe")):
        df = {"MLE": mle, "IRC": irc, "universe": uni}[src]
        missing = [c for c in col if c not in df.columns]
        if missing:
            raise ValueError(f"{src} archiv: chybí sloupce {missing}")

    irc20 = irc[irc["lookback"] == irc_lookback]
    common_dates = sorted(set(mle["date"]) & set(irc20["date"]))

    top = mle.loc[mle["rank_10d"] <= mle_top,
                  ["date", "ticker", "rank_10d"]]
    top = top[top["date"].isin(common_dates)]

    m = top.merge(uni[["ticker", "conid", "industry"]],
                  on="ticker", how="left")
    unmapped = m[m["conid"].isna()]
    m = m.dropna(subset=["conid"])

    irc_idx = irc20.set_index(["date", "industry"])["rank"]
    m = m.assign(irc_rank=[irc_idx.get((d, i)) for d, i
                           in zip(m["date"], m["industry"])])
    no_irc = int(m["irc_rank"].isna().sum())
    cand = m[m["irc_rank"].notna() & (m["irc_rank"] <= irc_top)]

    label = f"MLE_TOP{mle_top}xIRC_TOP{irc_top}_{irc_lookback}d"
    out = pd.DataFrame({
        "conid": cand["conid"].astype(int),
        "candidate_date": cand["date"],
        "ticker": cand["ticker"],
        "mle_rank": cand["rank_10d"].astype(int),
        "irc_rank": cand["irc_rank"].astype(int),
        "source_signal_label": label,
    })
    out = (out.drop_duplicates()
              .sort_values(["candidate_date", "conid"])
              .reset_index(drop=True))
    assert list(out.columns) == list(OUTPUT_COLUMNS)

    stats = {
        "definition": label,
        "mle_rows_total": int(len(mle)),
        "mle_top_rows": int(len(top)),
        "common_dates": len(common_dates),
        "date_range": ([common_dates[0], common_dates[-1]]
                       if common_dates else None),
        "unmapped_tickers": sorted(unmapped["ticker"].unique().tolist()),
        "unmapped_rows": int(len(unmapped)),
        "rows_without_irc_rank": no_irc,
        "candidate_days": int(len(out)),
        "unique_conids": int(out["conid"].nunique()),
        "candidate_date_range": ([out["candidate_date"].min(),
                                  out["candidate_date"].max()]
                                 if len(out) else None),
    }
    return out, stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="FUND-03 deterministic MLE×IRC candidate-day extraction")
    ap.add_argument("--mle-archive", required=True)
    ap.add_argument("--irc-archive", required=True)
    ap.add_argument("--universe", required=True,
                    help="MDSM universe CSV (conid, ticker, industry)")
    ap.add_argument("--mle-top", type=int, default=10)
    ap.add_argument("--irc-top", type=int, default=10)
    ap.add_argument("--irc-lookback", type=int, default=20)
    ap.add_argument("--out-dir", default=None,
                    help="default: results/diagnostics/fund03_candidate_days_<ts>")
    args = ap.parse_args(argv)

    try:
        out, stats = extract(args.mle_archive, args.irc_archive,
                             args.universe, args.mle_top, args.irc_top,
                             args.irc_lookback)
    except (ValueError, FileNotFoundError) as e:
        print(f"SETUP FAIL: {e}")
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else (
        MRL_ROOT / "results" / "diagnostics"
        / f"fund03_candidate_days_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "candidate_days.csv"
    out.to_csv(csv_path, index=False)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "params": {"mle_top": args.mle_top, "irc_top": args.irc_top,
                   "irc_lookback": args.irc_lookback},
        "sources": {
            "mle_archive": {"path": str(args.mle_archive),
                            "sha256": sha256(args.mle_archive)},
            "irc_archive": {"path": str(args.irc_archive),
                            "sha256": sha256(args.irc_archive)},
            "universe": {"path": str(args.universe),
                         "sha256": sha256(args.universe)},
        },
        "stats": stats,
        "output_sha256": sha256(csv_path),
        "forward_returns_used": False,
    }
    (out_dir / "extraction_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print(f"candidate-days:   {stats['candidate_days']}")
    print(f"unique conids:    {stats['unique_conids']}")
    print(f"date range:       {stats['candidate_date_range']}")
    print(f"unmapped tickers: {stats['unmapped_rows']}")
    print(f"output:           {csv_path}")
    print(f"manifest:         {out_dir / 'extraction_manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
