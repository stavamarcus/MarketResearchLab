"""
full_price_reconciliation.py — PRICE-RECON-01 full price reconciliation.

Porovna vsech 503 mdsm_price_view souboru (DATA-06, Sharadar-derived)
proti puvodni MDSM cache na overlapu 2025-07-09 -> 2026-06-27.

READ-ONLY. NEDELA: backtest, MLE/IRC regeneraci, API/TWS, mazani dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\full_price_reconciliation.py

Argumenty:
    --view-dir      DATA-06 mdsm_price_view (default ze store)
    --mdsm-prices   puvodni MDSM cache (default z data_paths.yaml)
    --sharadar-store store (pro ACTIONS)
    --snapshot-id
    --identity-map
    --overlap-from/-to  default 2025-07-09 / 2026-06-27
    --ca-window     trading dni kolem corporate action (default 5)

Klasifikace (primarni gate = close):
    PASS:            mean_abs_diff < 0.01 AND max_abs_diff < 0.05
    WARN:            mean<0.01 ale max>=0.05, NEBO 0.01<=mean<1.0
    FAIL_CANDIDATE:  mean>=1.0 NEBO max>=5.0
    FAIL_CANDIDATE se dale deli:
      corporate_action_cache_artifact: large diff + CA poblizu event date
      true_reconciliation_fail:        large diff bez CA vysvetleni

Volume: reportovan zvlast (pct diff), NENI tvrdy FAIL gate.

Edge cases / predpoklady:
    - view i MDSM soubory: {conid}_D1.parquet, DatetimeIndex.
    - CA "poblizu": +-ca_window KALENDARNICH dni kolem diff data (ne trading).
    - ACTIONS labely pro CA: split, adrratiosplit, spinoff, spinoffdividend,
      tickerchangeto/from, merger*, acquisition* (substring match).
    - nearest CA: join conid -> sharadar_ticker -> ACTIONS.ticker.
    - vyzaduje pandas + pyarrow (+ pyyaml pro config).
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

PRICE_FIELDS = ["close", "open", "high", "low"]
CA_LABELS = ["split", "adrratiosplit", "spinoff", "spinoffdividend",
             "tickerchangeto", "tickerchangefrom", "merger", "acquisition"]


def classify_close(mean_ad, max_ad):
    if mean_ad < 0.01 and max_ad < 0.05:
        return "PASS"
    if mean_ad >= 1.0 or max_ad >= 5.0:
        return "FAIL_CANDIDATE"
    # WARN: mean<0.01 ale max>=0.05, nebo 0.01<=mean<1.0
    return "WARN"


def load_actions(store, snapshot_id):
    adir = Path(store) / "snapshots" / snapshot_id / "parquet" / "ACTIONS"
    if not adir.exists():
        return None
    df = pd.read_parquet(adir)
    # normalizuj
    for c in df.columns:
        if c.lower() == "date":
            df = df.rename(columns={c: "date"})
        if c.lower() == "action":
            df = df.rename(columns={c: "action"})
        if c.lower() == "ticker":
            df = df.rename(columns={c: "ticker"})
    df["date"] = df["date"].astype(str).str[:10]
    df["action_l"] = df["action"].astype(str).str.lower()
    return df


def nearest_ca(actions, shar_ticker, diff_dates, window):
    """Najdi CA event poblizu diff dat (+-window kalendarnich dni)."""
    if actions is None or not diff_dates:
        return None
    sub = actions[(actions["ticker"] == shar_ticker)
                  & actions["action_l"].apply(
                      lambda a: any(lbl in a for lbl in CA_LABELS))]
    if sub.empty:
        return None
    diff_ts = [pd.Timestamp(d) for d in diff_dates]
    for _, r in sub.iterrows():
        ca_date = pd.Timestamp(r["date"])
        for dt in diff_ts:
            if abs((dt - ca_date).days) <= window:
                return {"action": r["action"], "date": r["date"],
                        "near_diff_date": str(dt.date())}
    return None


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
    ap.add_argument("--overlap-from", default="2025-07-09")
    ap.add_argument("--overlap-to", default="2026-06-27")
    ap.add_argument("--ca-window", type=int, default=5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent

    # view dir
    view_dir = (Path(args.view_dir) if args.view_dir
                else Path(args.sharadar_store) / "snapshots"
                / args.snapshot_id / "derived" / "mdsm_price_view")
    if not view_dir.exists():
        print(f"FAIL: view_dir neexistuje: {view_dir}")
        return 2

    # mdsm prices
    mdsm_prices = args.mdsm_prices
    if not mdsm_prices and yaml is not None:
        cfg = mrl / "config" / "data_paths.yaml"
        if cfg.exists():
            c = yaml.safe_load(cfg.read_text(encoding="utf-8"))
            mdsm_prices = c.get("mdsm", {}).get("prices_dir")
    if not mdsm_prices:
        print("FAIL: MDSM prices dir neznamy (--mdsm-prices)")
        return 2
    mdsm_prices = Path(mdsm_prices)

    # identity + ACTIONS
    idmap = pd.read_csv(args.identity_map, dtype=str)
    conid2shar = dict(zip(idmap["conid"].astype(str),
                          idmap["sharadar_ticker"]))
    actions = load_actions(args.sharadar_store, args.snapshot_id)
    if actions is None:
        print("WARN: ACTIONS nenalezen -> artifact detekce vypnuta")

    dfrom, dto = args.overlap_from, args.overlap_to
    view_files = sorted(view_dir.glob("*_D1.parquet"))
    print(f"Porovnavam {len(view_files)} souboru na overlapu {dfrom}..{dto}")

    stats = {
        "tested_files": 0, "matched_files": 0,
        "missing_old_mdsm": [], "missing_new_view": [],
        "total_overlap_rows": 0,
        "exact_match_files": 0, "pass_micro_files": 0, "warn_files": 0,
        "fail_candidate_files": 0,
        "corporate_action_cache_artifact_files": [],
        "true_reconciliation_fail_files": [],
        "per_file": [], "volume": [],
    }

    for vf in view_files:
        conid = vf.stem.rsplit("_", 1)[0]
        mf = mdsm_prices / vf.name
        if not mf.exists():
            stats["missing_old_mdsm"].append(vf.name)
            continue
        try:
            v = pd.read_parquet(vf)
            m = pd.read_parquet(mf)
            v.index = pd.to_datetime(v.index).normalize()
            m.index = pd.to_datetime(m.index).normalize()
            # overlap
            vw = v[(v.index >= dfrom) & (v.index <= dto)]
            mw = m[(m.index >= dfrom) & (m.index <= dto)]
            j = vw.join(mw, lsuffix="_view", rsuffix="_mdsm", how="inner")
            if j.empty:
                stats["missing_new_view"].append(vf.name)
                continue
            stats["tested_files"] += 1
            stats["matched_files"] += 1
            stats["total_overlap_rows"] += len(j)

            # close primarni
            cdiff = (j["close_view"] - j["close_mdsm"]).abs()
            cmean = float(cdiff.mean())
            cmax = float(cdiff.max())
            crel = cdiff / j["close_mdsm"].abs().replace(0, float("nan"))
            cmatch = float((crel < 0.001).mean())
            cls = classify_close(cmean, cmax)

            fileinfo = {"file": vf.name, "conid": conid,
                        "n_overlap": len(j),
                        "close_mean_abs_diff": round(cmean, 6),
                        "close_max_abs_diff": round(cmax, 6),
                        "close_match_rate": round(cmatch, 4),
                        "classification": cls}

            if cmean == 0.0 and cmax == 0.0:
                stats["exact_match_files"] += 1
            elif cls == "PASS":
                stats["pass_micro_files"] += 1
            elif cls == "WARN":
                stats["warn_files"] += 1
            elif cls == "FAIL_CANDIDATE":
                stats["fail_candidate_files"] += 1
                # cross-check ACTIONS
                shar = conid2shar.get(conid)
                diff_days = [str(d.date()) for d in
                             j.index[cdiff >= 0.05]][:30]
                ca = nearest_ca(actions, shar, diff_days, args.ca_window)
                if ca:
                    fileinfo["classification"] = "corporate_action_cache_artifact"
                    fileinfo["nearest_corporate_action"] = ca
                    stats["corporate_action_cache_artifact_files"].append(
                        vf.name)
                else:
                    fileinfo["classification"] = "true_reconciliation_fail"
                    stats["true_reconciliation_fail_files"].append(vf.name)

            # volume zvlast (pct)
            if "volume_view" in j.columns and "volume_mdsm" in j.columns:
                vd = (j["volume_view"] - j["volume_mdsm"]).abs()
                vpct = vd / j["volume_mdsm"].abs().replace(0, float("nan"))
                stats["volume"].append({
                    "file": vf.name,
                    "volume_mean_abs_pct_diff": round(float(vpct.mean()), 6),
                    "volume_max_abs_pct_diff": round(float(vpct.max()), 6)})

            stats["per_file"].append(fileinfo)
        except Exception as e:  # noqa: BLE001
            stats["per_file"].append({"file": vf.name, "error": str(e)})

    # overall
    n_fail = len(stats["true_reconciliation_fail_files"])
    n_warn = stats["warn_files"]
    if n_fail > 0:
        overall = "FAIL"
    elif n_warn > 0 or stats["corporate_action_cache_artifact_files"]:
        overall = "WARN"
    else:
        overall = "PASS"
    stats["overall"] = overall

    # top 20 largest diffs
    valid = [f for f in stats["per_file"] if "close_max_abs_diff" in f]
    top20 = sorted(valid, key=lambda x: x["close_max_abs_diff"],
                   reverse=True)[:20]
    stats["top_20_largest_diffs"] = top20

    _write(stats, mrl, args.out, dfrom, dto)

    print(f"\n==== PRICE-RECON-01: {overall} ====")
    print(f"tested: {stats['tested_files']} | exact: {stats['exact_match_files']}"
          f" | pass_micro: {stats['pass_micro_files']} | warn: {n_warn}")
    print(f"fail_candidate: {stats['fail_candidate_files']} "
          f"(artifact: {len(stats['corporate_action_cache_artifact_files'])}, "
          f"true_fail: {n_fail})")
    print(f"missing_old_mdsm: {len(stats['missing_old_mdsm'])} | "
          f"missing_new_view: {len(stats['missing_new_view'])}")
    return 0


def _write(stats, mrl, out, dfrom, dto):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "PRICE-RECON-01_full_price_reconciliation.json").write_text(
        json.dumps(stats, indent=2, default=str), encoding="utf-8")

    L = ["# PRICE-RECON-01 — Full Price Reconciliation", "",
         f"## Overall: {stats['overall']}", "",
         f"Overlap: {dfrom} -> {dto}", "",
         "## Souhrn", "",
         f"- tested_files: {stats['tested_files']}",
         f"- matched_files: {stats['matched_files']}",
         f"- missing_old_mdsm: {len(stats['missing_old_mdsm'])}",
         f"- missing_new_view: {len(stats['missing_new_view'])}",
         f"- total_overlap_rows: {stats['total_overlap_rows']}",
         f"- exact_match_files: {stats['exact_match_files']}",
         f"- pass_micro_files: {stats['pass_micro_files']}",
         f"- warn_files: {stats['warn_files']}",
         f"- fail_candidate_files: {stats['fail_candidate_files']}",
         f"- corporate_action_cache_artifact_files: "
         f"{len(stats['corporate_action_cache_artifact_files'])}",
         f"- true_reconciliation_fail_files: "
         f"{len(stats['true_reconciliation_fail_files'])}", ""]

    if stats["true_reconciliation_fail_files"]:
        L += ["## TRUE RECONCILIATION FAILS", ""]
        for f in stats["true_reconciliation_fail_files"]:
            L.append(f"- {f}")
        L.append("")

    if stats["corporate_action_cache_artifact_files"]:
        L += ["## Corporate action cache artifacts", ""]
        for f in stats["corporate_action_cache_artifact_files"]:
            L.append(f"- {f}")
        L.append("")

    L += ["## Top 20 largest close diffs", ""]
    for f in stats.get("top_20_largest_diffs", []):
        ca = f.get("nearest_corporate_action", "")
        L.append(f"- {f['file']}: mean={f['close_mean_abs_diff']} "
                 f"max={f['close_max_abs_diff']} "
                 f"match={f['close_match_rate']} [{f['classification']}]"
                 + (f" CA={ca}" if ca else ""))
    L.append("")

    # volume souhrn
    if stats["volume"]:
        vmax = max(stats["volume"],
                   key=lambda x: x["volume_max_abs_pct_diff"])
        vmean = sum(v["volume_mean_abs_pct_diff"]
                    for v in stats["volume"]) / len(stats["volume"])
        L += ["## Volume (zvlast, ne FAIL gate)", "",
              f"- prumer volume_mean_abs_pct_diff: {round(vmean, 6)}",
              f"- nejvyssi volume_max_abs_pct_diff: "
              f"{vmax['volume_max_abs_pct_diff']} ({vmax['file']})", ""]

    L += ["## Prahy", "",
          "- PASS: close mean<0.01 AND max<0.05",
          "- WARN: mean<0.01 ale max>=0.05, nebo 0.01<=mean<1.0",
          "- FAIL_CANDIDATE: mean>=1.0 nebo max>=5.0",
          "  -> artifact (CA poblizu) nebo true_reconciliation_fail", "",
          "## Vyhrady", "",
          "- CA okno: +-ca_window kalendarnich dni (ne trading).",
          "- artifact detekce zavisi na ACTIONS labelech + identity most.",
          "- volume rozdily = vendor rozdil, ne cenovy nesoulad.", ""]
    (out_dir / "PRICE-RECON-01_full_price_reconciliation.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
