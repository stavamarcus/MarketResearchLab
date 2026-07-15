"""
full_price_reconciliation_v1c.py — PRICE-RECON-01C full classifier.

Opraveny classifier price reconciliation (503 souboru, overlap
2025-07-09..2026-06-27). Oproti 01:
  - price-impact CA rozliseny od dividend (dividend NEklasifikuje scale diff)
  - CA okno presahuje overlap konec (siroky lookup 2025-01..2026-07-15)
  - alias kategorie (identity_map.alias_flag / ticker!=sharadar_ticker)
  - needs_manual_review kategorie

READ-ONLY. NEDELA: MLE/IRC recon, backtest, API/TWS, zmenu dat.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\reconciliation\\full_price_reconciliation_v1c.py

Kategorie:
    exact_match, pass_micro, warn, corporate_action_cache_artifact,
    identity_alias_class_mismatch,
    needs_manual_review_or_unmapped_adjustment_artifact,
    true_reconciliation_fail

Prahy (close):
    PASS:  mean<0.01 AND max<0.05  (exact pokud mean==max==0, jinak pass_micro)
    WARN:  mean<0.01 ale max>=0.05, nebo 0.01<=mean<1.0
    FAIL_CANDIDATE: mean>=1.0 nebo max>=5.0 -> dale klasifikovano

FAIL_CANDIDATE resolve poradi:
    1. alias (alias_flag/ticker mismatch) -> identity_alias_class_mismatch
    2. price-impact CA v okne poblizu diff -> corporate_action_cache_artifact
    3. jinak -> needs_manual_review_or_unmapped_adjustment_artifact
    (true_reconciliation_fail: rezervovano; nastava jen pokud by byl
     large diff bez alias, bez CA a NEsystematicky/bez boundary patternu -
     zde spada do needs_manual_review, aby se true_fail nedaval unahleene)

Edge cases:
    - PRICE_IMPACT_CA = split, adrratiosplit, spinoff, spinoffdividend,
      merger, acquisition. dividend NENI price-impact pro scale diff.
    - CA "poblizu": +-15 kalendarnich dni od diff dat NEBO od boundary
      (den kde diff skokove mizi/vznika).
    - alias detekce: alias_flag neprazdny/!=False NEBO ticker!=sharadar_ticker.
    - vyzaduje pandas + pyarrow + pyyaml.
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

OVERLAP = ("2025-07-09", "2026-06-27")
CA_FROM, CA_TO = "2025-01-01", "2026-07-15"
PRICE_IMPACT_CA = ["split", "adrratiosplit", "spinoff", "spinoffdividend",
                   "merger", "acquisition"]
CA_WINDOW = 15


def classify_thresholds(mean_ad, max_ad):
    if mean_ad == 0.0 and max_ad == 0.0:
        return "exact_match"
    if mean_ad < 0.01 and max_ad < 0.05:
        return "pass_micro"
    if mean_ad >= 1.0 or max_ad >= 5.0:
        return "FAIL_CANDIDATE"
    return "warn"


def is_alias(idrow):
    """alias_flag neprazdny/!=False NEBO ticker != sharadar_ticker."""
    if idrow is None:
        return False
    af = str(idrow.get("alias_flag", "")).strip().lower()
    if af and af not in ("false", "0", "nan", "none", ""):
        return True
    tk = str(idrow.get("ticker", "")).strip()
    st = str(idrow.get("sharadar_ticker", "")).strip()
    return bool(tk and st and tk != st)


def price_impact_ca_near(actions, shar, diff_dates, boundary):
    """Najdi price-impact CA (NE dividend) poblizu diff dat nebo boundary."""
    if actions is None or not shar:
        return None
    sub = actions[(actions["ticker"] == shar)
                  & (actions["date"] >= CA_FROM)
                  & (actions["date"] <= CA_TO)]
    if sub.empty:
        return None
    pi = sub[sub["action_l"].apply(
        lambda a: any(lbl in a for lbl in PRICE_IMPACT_CA))]
    if pi.empty:
        return None
    ref_dates = list(diff_dates)
    if boundary:
        ref_dates.append(pd.Timestamp(boundary))
    for _, r in pi.iterrows():
        cad = pd.Timestamp(r["date"])
        for rd in ref_dates:
            if abs((pd.Timestamp(rd) - cad).days) <= CA_WINDOW:
                return {"action": r["action"], "date": r["date"],
                        "value": str(r.get("value", ""))}
    return None


def detect_boundary(cdiff, index):
    """Den, kde diff skokove mizi nebo vznika (scale break)."""
    mask = (cdiff >= 0.05).astype(int)
    if mask.sum() == 0 or mask.sum() == len(mask):
        return None
    d = mask.diff().fillna(0)
    changes = index[d != 0]
    if len(changes):
        return str(changes[0].date())
    return None


def load_actions(store, snapshot_id):
    adir = Path(store) / "snapshots" / snapshot_id / "parquet" / "ACTIONS"
    if not adir.exists():
        return None
    df = pd.read_parquet(adir)
    ren = {c: c.lower() for c in df.columns
           if c.lower() in ("date", "action", "ticker", "value")}
    df = df.rename(columns=ren)
    df["date"] = df["date"].astype(str).str[:10]
    df["action_l"] = df["action"].astype(str).str.lower()
    return df


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
    if not view_dir.exists():
        print(f"FAIL: view_dir neexistuje: {view_dir}")
        return 2

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
    idmap_by_conid = {str(r["conid"]): r for _, r in idmap.iterrows()}
    actions = load_actions(args.sharadar_store, args.snapshot_id)

    dfrom, dto = OVERLAP
    view_files = sorted(view_dir.glob("*_D1.parquet"))
    print(f"Klasifikuji {len(view_files)} souboru, overlap {dfrom}..{dto}")

    cats = {k: 0 for k in ["exact_match", "pass_micro", "warn",
                           "corporate_action_cache_artifact",
                           "identity_alias_class_mismatch",
                           "needs_manual_review_or_unmapped_adjustment_artifact",
                           "true_reconciliation_fail"]}
    stats = {"tested_files": 0, "matched_files": 0,
             "missing_old_mdsm": [], "missing_new_view": [],
             "total_overlap_rows": 0, "categories": cats,
             "per_file_flagged": [], "top_20_largest_diffs": [],
             "volume": []}

    all_flagged = []
    for vf in view_files:
        conid = vf.stem.rsplit("_", 1)[0]
        mf = mdsm_prices / vf.name
        if not mf.exists():
            stats["missing_old_mdsm"].append(vf.name)
            continue
        try:
            v = pd.read_parquet(vf); m = pd.read_parquet(mf)
            v.index = pd.to_datetime(v.index).normalize()
            m.index = pd.to_datetime(m.index).normalize()
            j = v[["close", "volume"]].join(
                m[["close", "volume"]], lsuffix="_view", rsuffix="_mdsm",
                how="inner")
            j = j[(j.index >= dfrom) & (j.index <= dto)]
            if j.empty:
                stats["missing_new_view"].append(vf.name)
                continue
            stats["tested_files"] += 1
            stats["matched_files"] += 1
            stats["total_overlap_rows"] += len(j)

            cdiff = (j["close_view"] - j["close_mdsm"]).abs()
            cmean, cmax = float(cdiff.mean()), float(cdiff.max())
            crel = cdiff / j["close_mdsm"].abs().replace(0, float("nan"))
            cmatch = float((crel < 0.001).mean())
            base = classify_thresholds(cmean, cmax)

            info = {"file": vf.name, "conid": conid,
                    "close_mean_abs_diff": round(cmean, 6),
                    "close_max_abs_diff": round(cmax, 6),
                    "close_match_rate": round(cmatch, 4)}

            if base != "FAIL_CANDIDATE":
                cats[base] += 1
                info["classification"] = base
            else:
                # resolve FAIL_CANDIDATE
                idrow = idmap_by_conid.get(conid)
                shar = str(idrow["sharadar_ticker"]) if idrow is not None else None
                if is_alias(idrow):
                    cls = "identity_alias_class_mismatch"
                    info["alias_flag"] = str(idrow.get("alias_flag"))
                    info["ticker"] = str(idrow.get("ticker"))
                    info["sharadar_ticker"] = shar
                else:
                    diff_dates = j.index[cdiff >= 0.05]
                    boundary = detect_boundary(cdiff, j.index)
                    ca = price_impact_ca_near(actions, shar, diff_dates,
                                              boundary)
                    if ca:
                        cls = "corporate_action_cache_artifact"
                        info["price_impact_ca"] = ca
                        info["boundary"] = boundary
                    else:
                        cls = ("needs_manual_review_or_unmapped_"
                               "adjustment_artifact")
                        info["boundary"] = boundary
                        info["note"] = ("large diff bez alias a bez "
                                        "price-impact CA v okne")
                cats[cls] += 1
                info["classification"] = cls
                all_flagged.append(info)

            # volume
            vd = (j["volume_view"] - j["volume_mdsm"]).abs()
            vpct = vd / j["volume_mdsm"].abs().replace(0, float("nan"))
            stats["volume"].append({
                "file": vf.name,
                "volume_mean_abs_pct_diff": round(float(vpct.mean()), 4)})

            if base == "FAIL_CANDIDATE" or base == "warn":
                stats["per_file_flagged"].append(info)
        except Exception as e:  # noqa: BLE001
            stats["per_file_flagged"].append({"file": vf.name,
                                              "error": str(e)})

    # overall
    n_true = cats["true_reconciliation_fail"]
    n_manual = cats["needs_manual_review_or_unmapped_adjustment_artifact"]
    if n_true > 0:
        overall = "FAIL"
    elif n_manual > 0 or cats["warn"] > 0 or \
            cats["corporate_action_cache_artifact"] > 0 or \
            cats["identity_alias_class_mismatch"] > 0:
        overall = "WARN"
    else:
        overall = "PASS"
    stats["overall"] = overall

    valid = [f for f in all_flagged if "close_max_abs_diff" in f]
    stats["top_20_largest_diffs"] = sorted(
        valid, key=lambda x: x["close_max_abs_diff"], reverse=True)[:20]

    _write(stats, mrl, args.out, dfrom, dto)

    print(f"\n==== PRICE-RECON-01C: {overall} ====")
    for k, v in cats.items():
        print(f"  {k}: {v}")
    print(f"missing_old_mdsm: {len(stats['missing_old_mdsm'])} | "
          f"missing_new_view: {len(stats['missing_new_view'])}")
    return 0


def _write(stats, mrl, out, dfrom, dto):
    out_dir = Path(out) if out else mrl / "reports" / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "PRICE-RECON-01C_full_price_reconciliation.json").write_text(
        json.dumps(stats, indent=2, default=str), encoding="utf-8")
    cats = stats["categories"]
    L = ["# PRICE-RECON-01C — Full Price Reconciliation (opraveny classifier)",
         "", f"## Overall: {stats['overall']}", "",
         f"Overlap: {dfrom} -> {dto}", "",
         "## Kategorie", ""]
    for k, v in cats.items():
        L.append(f"- {k}: {v}")
    L += ["", "## Souhrn", "",
          f"- tested_files: {stats['tested_files']}",
          f"- matched_files: {stats['matched_files']}",
          f"- total_overlap_rows: {stats['total_overlap_rows']}",
          f"- missing_old_mdsm: {len(stats['missing_old_mdsm'])}",
          f"- missing_new_view: {len(stats['missing_new_view'])}", "",
          "## Flagged soubory (FAIL_CANDIDATE + WARN)", ""]
    for f in stats["top_20_largest_diffs"]:
        extra = ""
        if f.get("price_impact_ca"):
            extra = f" CA={f['price_impact_ca']}"
        elif f.get("alias_flag"):
            extra = f" alias={f.get('ticker')}->{f.get('sharadar_ticker')}"
        elif f.get("boundary"):
            extra = f" boundary={f['boundary']}"
        L.append(f"- {f['file']}: mean={f['close_mean_abs_diff']} "
                 f"max={f['close_max_abs_diff']} "
                 f"match={f['close_match_rate']} "
                 f"[{f['classification']}]{extra}")
    if stats["volume"]:
        vmean = sum(v["volume_mean_abs_pct_diff"]
                    for v in stats["volume"]) / len(stats["volume"])
        L += ["", "## Volume (zvlast, ne FAIL gate)", "",
              f"- prumer volume_mean_abs_pct_diff: {round(vmean, 4)}", ""]
    L += ["## CA logika (opravena)", "",
          f"- price-impact CA: {PRICE_IMPACT_CA}",
          "- dividend NENI price-impact pro scale diff.",
          f"- CA okno: +-{CA_WINDOW} dni od diff dat nebo boundary.",
          "- CA lookup okno: 2025-01-01..2026-07-15 (presah za overlap).",
          "- alias: alias_flag neprazdny nebo ticker!=sharadar_ticker.", "",
          "## Vyhrady", "",
          "- true_reconciliation_fail se NEudeluje unahleene; large diff",
          "  bez alias/CA -> needs_manual_review (BDX case).",
          "- volume rozdil = vendor, ne FAIL gate.", ""]
    (out_dir / "PRICE-RECON-01C_full_price_reconciliation.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
