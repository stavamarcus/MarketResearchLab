"""
fail_diagnostics.py — PRICE-RECON-01B: diagnostika 9 fail conid.

READ-ONLY. Cilena analyza 9 true_reconciliation_fail + 1 kontrolni (CVNA)
z PRICE-RECON-01. Zjisti, proc cross-check selhal a spravna klasifikace.

NEDELA: MLE/IRC recon, backtest, API/TWS, zmenu dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\fail_diagnostics.py

Klasifikace (po diagnostice):
    corporate_action_cache_artifact: diff cluster u split/spinoff/ticker CA
    systematic_vendor_or_adjustment_mismatch: soustavny diff kazdy den
    true_reconciliation_fail: bez CA vysvetleni ani systematiky
    needs_manual_review: nelze rozhodnout

Edge cases:
    - ACTIONS lookup: siroke okno 2025-01-01..2026-07-15 (ne jen overlap).
    - cluster vs systematik: podil dnu s diff>=0.05 z overlap dnu.
      vysoky podil (>0.5) -> systematik; nizky + koncentrovany -> cluster.
    - ACTIONS.ticker vs sharadar_ticker: reportovano (diagnoza join bugu).
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
try:
    import yaml
except ImportError:
    yaml = None

FAIL_CONIDS = ["129348130", "208813720", "270957", "356858007",
               "370757467", "4350", "4886", "748351585", "887235923"]
CONTROL_CONIDS = ["274144952"]  # CVNA
CA_LABELS = ["split", "adrratiosplit", "spinoff", "spinoffdividend",
             "tickerchangeto", "tickerchangefrom", "merger", "acquisition"]
CA_FROM, CA_TO = "2025-01-01", "2026-07-15"
OVERLAP = ("2025-07-09", "2026-06-27")


def load_actions(store, snapshot_id):
    adir = Path(store) / "snapshots" / snapshot_id / "parquet" / "ACTIONS"
    if not adir.exists():
        return None
    df = pd.read_parquet(adir)
    ren = {}
    for c in df.columns:
        cl = c.lower()
        if cl in ("date", "action", "ticker", "value"):
            ren[c] = cl
    df = df.rename(columns=ren)
    df["date"] = df["date"].astype(str).str[:10]
    df["action_l"] = df["action"].astype(str).str.lower()
    return df


def diagnose(conid, view_dir, mdsm_dir, actions, conid2shar,
             conid2ticker, conid2perma):
    out = {"conid": conid,
           "ticker": conid2ticker.get(conid),
           "sharadar_ticker": conid2shar.get(conid),
           "permaticker": conid2perma.get(conid)}
    vf = view_dir / f"{conid}_D1.parquet"
    mf = mdsm_dir / f"{conid}_D1.parquet"
    out["view_file_exists"] = vf.exists()
    out["mdsm_file_exists"] = mf.exists()
    if not (vf.exists() and mf.exists()):
        out["classification"] = "needs_manual_review"
        out["note"] = "chybi view nebo mdsm soubor"
        return out

    v = pd.read_parquet(vf)
    m = pd.read_parquet(mf)
    v.index = pd.to_datetime(v.index).normalize()
    m.index = pd.to_datetime(m.index).normalize()
    dfrom, dto = OVERLAP
    j = v[["close", "volume"]].join(
        m[["close", "volume"]], lsuffix="_view", rsuffix="_mdsm",
        how="inner")
    j = j[(j.index >= dfrom) & (j.index <= dto)]
    if j.empty:
        out["classification"] = "needs_manual_review"
        out["note"] = "prazdny overlap"
        return out

    cdiff = (j["close_view"] - j["close_mdsm"]).abs()
    crel = cdiff / j["close_mdsm"].abs().replace(0, float("nan"))
    n = len(j)
    n_005 = int((cdiff >= 0.05).sum())
    n_1 = int((cdiff >= 1.0).sum())
    out["diff_profile"] = {
        "overlap_rows": n,
        "mean_abs_diff": round(float(cdiff.mean()), 6),
        "max_abs_diff": round(float(cdiff.max()), 6),
        "match_rate": round(float((crel < 0.001).mean()), 4),
        "n_days_diff_ge_005": n_005,
        "n_days_diff_ge_1": n_1,
        "pct_days_diff_ge_005": round(n_005 / n, 4),
    }
    # cluster vs systematik
    max_date = cdiff.idxmax()
    out["diff_profile"]["max_diff_date"] = str(max_date.date())
    diff_dates = j.index[cdiff >= 0.05]
    if len(diff_dates):
        out["diff_profile"]["first_diff_date"] = str(diff_dates.min().date())
        out["diff_profile"]["last_diff_date"] = str(diff_dates.max().date())
    # systematik: >50% dnu se lisi
    is_systematic = (n_005 / n) > 0.5

    # sample rows kolem max_diff (+-10)
    pos = j.index.get_loc(max_date)
    lo, hi = max(0, pos - 10), min(n, pos + 11)
    sample = []
    for idx in range(lo, hi):
        d = j.index[idx]
        mc = float(j["close_mdsm"].iloc[idx])
        vc = float(j["close_view"].iloc[idx])
        ad = abs(vc - mc)
        sample.append({"date": str(d.date()),
                       "mdsm_close": round(mc, 4),
                       "sharadar_view_close": round(vc, 4),
                       "abs_diff": round(ad, 4),
                       "rel_diff": round(ad / mc, 6) if mc else None})
    out["sample_rows"] = sample

    # volume diff
    vdiff = (j["volume_view"] - j["volume_mdsm"]).abs()
    vpct = vdiff / j["volume_mdsm"].abs().replace(0, float("nan"))
    out["volume"] = {
        "volume_mean_abs_pct_diff": round(float(vpct.mean()), 4),
        "volume_max_abs_pct_diff": round(float(vpct.max()), 4)}

    # ACTIONS lookup (siroke okno)
    shar = conid2shar.get(conid)
    ca_events = []
    ticker_match = None
    if actions is not None and shar:
        sub = actions[(actions["ticker"] == shar)
                      & (actions["date"] >= CA_FROM)
                      & (actions["date"] <= CA_TO)]
        ticker_match = not sub.empty or (shar in set(actions["ticker"]))
        rel = sub[sub["action_l"].apply(
            lambda a: any(lbl in a for lbl in CA_LABELS))]
        for _, r in rel.iterrows():
            ca_events.append({
                "action_date": r["date"], "action": r["action"],
                "value": str(r.get("value", "")),
                "actions_ticker": r["ticker"],
                "matches_sharadar_ticker": r["ticker"] == shar})
    out["actions_ticker_found"] = ticker_match
    out["corporate_actions"] = ca_events

    # klasifikace
    # CA poblizu diff clusteru?
    ca_near = False
    if ca_events and len(diff_dates):
        for ca in ca_events:
            cad = pd.Timestamp(ca["action_date"])
            for dd in diff_dates:
                if abs((dd - cad).days) <= 10:
                    ca_near = True
                    ca["near_diff"] = True
                    break
    if ca_near:
        out["classification"] = "corporate_action_cache_artifact"
    elif ca_events and not is_systematic:
        # ma CA v okne, ale diff cluster ne uplne u nej -> pravdepodobne
        # split za koncem overlapu posunul celou radu
        out["classification"] = "corporate_action_cache_artifact"
        out["note"] = ("CA v okne, diff mimo +-10d cluster; "
                       "pravdepodobne split za koncem overlapu")
    elif is_systematic and not ca_events:
        out["classification"] = "systematic_vendor_or_adjustment_mismatch"
    elif not ca_events and not is_systematic:
        out["classification"] = "true_reconciliation_fail"
    else:
        out["classification"] = "needs_manual_review"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--view-dir", default=None)
    ap.add_argument("--mdsm-prices", default=None)
    ap.add_argument("--sharadar-store",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store")
    ap.add_argument("--snapshot-id",
                    default="sharadar_full_equity_v20260705_01")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--identity-map",
                    default=r"C:\Users\stava\Projects\sharadar_mdsm_adapter\identity\identity_map_resolved_v2.csv")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    view_dir = (Path(args.view_dir) if args.view_dir
                else Path(args.sharadar_store) / "snapshots"
                / args.snapshot_id / "derived" / "mdsm_price_view")
    mdsm_prices = args.mdsm_prices
    if not mdsm_prices and yaml is not None:
        cfg = mrl / "config" / "data_paths.yaml"
        if cfg.exists():
            c = yaml.safe_load(cfg.read_text(encoding="utf-8"))
            mdsm_prices = c.get("mdsm", {}).get("prices_dir")
    if not mdsm_prices:
        print("FAIL: MDSM prices dir neznamy")
        return 2
    mdsm_prices = Path(mdsm_prices)

    idmap = pd.read_csv(args.identity_map, dtype=str)
    conid2shar = dict(zip(idmap["conid"].astype(str), idmap["sharadar_ticker"]))
    conid2ticker = dict(zip(idmap["conid"].astype(str), idmap["ticker"]))
    conid2perma = dict(zip(idmap["conid"].astype(str),
                           idmap.get("permaticker", pd.Series(dtype=str))))
    actions = load_actions(args.sharadar_store, args.snapshot_id)
    if actions is None:
        print("WARN: ACTIONS nenalezen")

    all_conids = FAIL_CONIDS + CONTROL_CONIDS
    results = []
    for cid in all_conids:
        r = diagnose(cid, view_dir, mdsm_prices, actions, conid2shar,
                     conid2ticker, conid2perma)
        results.append(r)
        tk = r.get("ticker") or "?"
        cls = r.get("classification")
        nca = len(r.get("corporate_actions", []))
        print(f"  {cid} ({tk}): {cls} | CA_events={nca} | "
              f"actions_ticker_found={r.get('actions_ticker_found')}")

    # souhrn klasifikaci
    summary = {}
    for r in results:
        c = r.get("classification")
        summary[c] = summary.get(c, 0) + 1

    _write(results, summary, mrl, args.out)
    print(f"\nsouhrn: {summary}")
    return 0


def _write(results, summary, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "PRICE-RECON-01B_fail_diagnostics.json").write_text(
        json.dumps({"summary": summary, "diagnostics": results},
                   indent=2, default=str), encoding="utf-8")
    L = ["# PRICE-RECON-01B — Fail Diagnostics", "",
         f"## Souhrn klasifikaci: {summary}", ""]
    for r in results:
        L.append(f"## {r['conid']} ({r.get('ticker')})")
        L.append(f"- sharadar_ticker: {r.get('sharadar_ticker')}")
        L.append(f"- classification: **{r.get('classification')}**")
        if r.get("note"):
            L.append(f"- note: {r['note']}")
        L.append(f"- actions_ticker_found: {r.get('actions_ticker_found')}")
        dp = r.get("diff_profile", {})
        if dp:
            L.append(f"- diff: mean={dp.get('mean_abs_diff')} "
                     f"max={dp.get('max_abs_diff')} "
                     f"match_rate={dp.get('match_rate')}")
            L.append(f"- diff dates: first={dp.get('first_diff_date')} "
                     f"last={dp.get('last_diff_date')} "
                     f"max={dp.get('max_diff_date')}")
            L.append(f"- pct_days_diff>=0.05: {dp.get('pct_days_diff_ge_005')} "
                     f"(n>=0.05: {dp.get('n_days_diff_ge_005')}, "
                     f"n>=1.0: {dp.get('n_days_diff_ge_1')})")
        vol = r.get("volume", {})
        if vol:
            L.append(f"- volume: mean_pct={vol.get('volume_mean_abs_pct_diff')} "
                     f"max_pct={vol.get('volume_max_abs_pct_diff')}")
        cas = r.get("corporate_actions", [])
        if cas:
            L.append(f"- corporate actions ({len(cas)}):")
            for ca in cas:
                L.append(f"  - {ca['action_date']} {ca['action']} "
                         f"value={ca['value']} ticker={ca['actions_ticker']} "
                         f"match={ca['matches_sharadar_ticker']}"
                         + (" [NEAR DIFF]" if ca.get("near_diff") else ""))
        else:
            L.append("- corporate actions: ZADNE v okne 2025-01..2026-07")
        # sample rows kolem max diff
        sr = r.get("sample_rows", [])
        if sr:
            L.append("- sample kolem max_diff_date:")
            L.append("  | date | mdsm_close | view_close | abs_diff | rel_diff |")
            L.append("  |---|---|---|---|---|")
            for s in sr:
                L.append(f"  | {s['date']} | {s['mdsm_close']} | "
                         f"{s['sharadar_view_close']} | {s['abs_diff']} | "
                         f"{s['rel_diff']} |")
        L.append("")
    (out_dir / "PRICE-RECON-01B_fail_diagnostics.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
