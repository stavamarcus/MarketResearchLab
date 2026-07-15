"""
run_cap01a_market_cap_diagnosis.py — MRL-CAP-01A read-only diagnóza
příčiny MARKET_CAP_SUSPECT z CAP-01.

NEMĚNÍ produkční CAP-01 formuli, bucket logiku ani tolerance.
Žádný CAP-02, žádné forward returns, žádná pharma, žádné API,
žádný snapshot rebuild.

Pro každý candidate-day počítá diagnostické poměry:
    ratio_candidate          = close_cand × sharesbas / vendor_mc
    ratio_sharefactor_mult   = close_cand × sharesbas × sharefactor / vendor_mc
    ratio_sharefactor_div    = close_cand × sharesbas / sharefactor / vendor_mc
    price_ratio              = close_cand / close_at_datekey
    anchor_adjusted_ratio    = ratio_candidate / price_ratio

Hypotéza (architekt): pokud anchor_adjusted_ratio ≈ 1, vendor marketcap
je vztažen k datekey, ne candidate_date → suspect je anchor-date
mismatch, ne špatný market cap.

Výsledek (jeden z):
    FIXABLE_BY_SHAREFACTOR | ANCHOR_DATE_MISMATCH | NEEDS_RAW_CLOSE
    | NEEDS_SOURCE_CHANGE | INCONCLUSIVE

Spuštění (Windows):
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    conda activate market_research_lab
    python run_cap01a_market_cap_diagnosis.py --input results\\diagnostics\\fund03_candidate_days_<ts>\\candidate_days.csv --ignore-enabled

Exit: 0 diagnóza hotová, 2 setup fail.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

MRL_ROOT = Path(__file__).resolve().parent
if str(MRL_ROOT) not in sys.path:
    sys.path.insert(0, str(MRL_ROOT))

from src.infrastructure.logging_manager import configure_logging, get_logger  # noqa: E402
from src.providers.mdsm_providers import MDSMPriceProvider                    # noqa: E402
from run_fundamental_coverage_audit import load_candidate_days                # noqa: E402
from run_cap01_market_cap_audit import (                                      # noqa: E402
    TOLERANCE_PCT, assign_bucket, df_to_markdown,
)

configure_logging()
logger = get_logger("mrl.cap01a.diagnosis")

# pásma pro klasifikaci výsledku (diagnostické, ne acceptance prahy)
NEAR_ONE = (0.90, 1.10)       # "≈ 1"
DATEKEY_LOOKBACK_DAYS = 420   # nejstarší datekey ~1Y+ před candidate


def nearest_preceding_close(pdf: pd.DataFrame, target) -> float | None:
    """Close k nejbližšímu obchodnímu dni <= target (datekey nemusí být
    obchodní den). None pokud žádný."""
    if pdf is None or pdf.empty:
        return None
    ts = pd.Timestamp(target)
    sub = pdf.index[pdf.index <= ts]
    if len(sub) == 0:
        return None
    return float(pdf.loc[sub.max(), "close"])


def build_diagnostics(inp, prices, provider, has_anchor):
    """Read-only: per-row diagnostické poměry. Nepoužívá bucket logiku
    k rozhodnutí, jen zrcadlí CAP-01 SUSPECT klasifikaci pro srovnání."""
    from sharadar_mdsm_adapter.exceptions import SharadarProviderError

    rows = []
    for r in inp.itertuples(index=False):
        conid, cand = int(r.conid), r.candidate_date
        rec = {
            "conid": conid, "ticker": getattr(r, "ticker", None),
            "candidate_date": cand,
            "close_candidate": np.nan, "close_datekey": np.nan,
            "sharesbas": np.nan, "sharefactor": np.nan,
            "sf1_datekey": pd.NaT, "staleness_days": np.nan,
            "computed_market_cap": np.nan, "vendor_marketcap": np.nan,
            "relative_diff_pct": np.nan,
            "ratio_candidate": np.nan,
            "ratio_sharefactor_mult": np.nan,
            "ratio_sharefactor_div": np.nan,
            "price_ratio": np.nan, "anchor_adjusted_ratio": np.nan,
            "cap01_reason": None,
        }
        pdf = prices.get(conid)
        close_c = nearest_preceding_close(pdf, cand) if pdf is not None else None
        if close_c is None:
            rec["cap01_reason"] = "PRICE_MISSING"
            rows.append(rec)
            continue
        rec["close_candidate"] = close_c
        try:
            snap = provider.get_snapshot(conid, cand,
                                         fields=["sharesbas", "sharefactor"])
        except SharadarProviderError:
            rec["cap01_reason"] = "SHARES_MISSING"
            rows.append(rec)
            continue
        shares = snap.fundamentals.get("sharesbas")
        sf = snap.fundamentals.get("sharefactor")
        rec["sharesbas"] = shares
        rec["sharefactor"] = sf
        rec["sf1_datekey"] = snap.datekey
        rec["staleness_days"] = snap.staleness_days
        if shares is None or not np.isfinite(shares) or shares <= 0:
            rec["cap01_reason"] = "SHARES_MISSING"
            rows.append(rec)
            continue
        mc = close_c * shares
        rec["computed_market_cap"] = mc
        rec["close_datekey"] = nearest_preceding_close(pdf, snap.datekey)

        vendor = None
        if has_anchor:
            try:
                a = provider.get_snapshot(conid, cand, fields=["marketcap"])
                vendor = a.price_derived.get("marketcap")
            except SharadarProviderError:
                vendor = None
        if vendor is not None and np.isfinite(vendor) and vendor > 0:
            rec["vendor_marketcap"] = vendor
            rec["relative_diff_pct"] = round(abs(mc - vendor) / vendor * 100, 2)
            rec["ratio_candidate"] = mc / vendor
            if sf is not None and np.isfinite(sf) and sf != 0:
                rec["ratio_sharefactor_mult"] = mc * sf / vendor
                rec["ratio_sharefactor_div"] = mc / sf / vendor
            if (rec["close_datekey"] is not None
                    and np.isfinite(rec["close_datekey"])
                    and rec["close_datekey"] > 0):
                pr = close_c / rec["close_datekey"]
                rec["price_ratio"] = pr
                rec["anchor_adjusted_ratio"] = (mc / vendor) / pr
            # zrcadlo CAP-01 klasifikace
            rec["cap01_reason"] = ("SUSPECT"
                                   if rec["relative_diff_pct"] > TOLERANCE_PCT
                                   else "OK")
        else:
            rec["cap01_reason"] = "OK_NO_ANCHOR"
        rows.append(rec)

    out = pd.DataFrame.from_records(rows)
    if len(out) != len(inp):
        raise RuntimeError(f"1:1 porušeno: {len(inp)} vs {len(out)}")
    return out


def pct_in(series, lo, hi):
    s = series.dropna()
    if not len(s):
        return None
    return round(float(((s >= lo) & (s <= hi)).mean()) * 100, 1)


def summarize(series):
    s = series.dropna()
    if not len(s):
        return {"n": 0}
    return {"n": int(len(s)), "median": round(float(s.median()), 4),
            "p05": round(float(s.quantile(0.05)), 4),
            "p95": round(float(s.quantile(0.95)), 4),
            "min": round(float(s.min()), 4), "max": round(float(s.max()), 4)}


def classify(out) -> tuple[str, list[str]]:
    """Výsledek diagnózy z distribucí. Prahy diagnostické, ne acceptance."""
    susp = out[out["cap01_reason"] == "SUSPECT"]
    n = len(susp)
    notes = []
    if n == 0:
        return "INCONCLUSIVE", ["0 suspect řádků k diagnostice"]

    # kolik suspectů by "opravil" každý přístup (ratio ≈ 1)
    fix_anchor = pct_in(susp["anchor_adjusted_ratio"], *NEAR_ONE)
    fix_mult = pct_in(susp["ratio_sharefactor_mult"], *NEAR_ONE)
    fix_div = pct_in(susp["ratio_sharefactor_div"], *NEAR_ONE)
    base_near = pct_in(susp["ratio_candidate"], *NEAR_ONE)
    notes.append(f"suspect ratio_candidate ≈1: {base_near}%")
    notes.append(f"anchor_adjusted ≈1: {fix_anchor}%")
    notes.append(f"sharefactor× ≈1: {fix_mult}% | sharefactor/ ≈1: {fix_div}%")

    cand = {
        "ANCHOR_DATE_MISMATCH": fix_anchor or 0,
        "FIXABLE_BY_SHAREFACTOR": max(fix_mult or 0, fix_div or 0),
    }
    best = max(cand, key=cand.get)
    best_pct = cand[best]
    if best_pct >= 70:
        return best, notes
    if best_pct >= 40:
        notes.append(f"nejlepší vysvětlení {best} pokrývá jen {best_pct}% "
                     "— částečné")
        return "INCONCLUSIVE", notes
    # žádné vysvětlení nefunguje → cena/shares nekompatibilní
    notes.append("žádný z testů nevysvětluje většinu suspectů")
    return "NEEDS_SOURCE_CHANGE", notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CAP-01A market cap diagnosis")
    ap.add_argument("--input", required=True)
    ap.add_argument("--config", default=str(MRL_ROOT / "config"
                                            / "data_paths.yaml"))
    ap.add_argument("--ignore-enabled", action="store_true")
    args = ap.parse_args(argv)

    dp = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    cfg = dp.get("sharadar_fundamentals") or {}
    if not cfg or (not cfg.get("enabled", False) and not args.ignore_enabled):
        print("SETUP FAIL: sharadar_fundamentals chybí/enabled=false")
        return 2
    try:
        inp = load_candidate_days(args.input)
    except (ValueError, FileNotFoundError) as e:
        print(f"SETUP FAIL: {e}")
        return 2

    try:
        from sharadar_mdsm_adapter.config import load_config
        from sharadar_mdsm_adapter.identity_map import IdentityMap
        from sharadar_mdsm_adapter.sf1_provider import SF1Provider
        from sharadar_mdsm_adapter.sf1_store import SF1Store
        sid = str(cfg["snapshot_id"])
        acfg = load_config(cfg["adapter_config"])
        handle = SF1Store(acfg).load(sid)
        ident = IdentityMap.load(acfg.identity_map_path, acfg.allowed_tiers)
        provider = SF1Provider(
            handle, ident,
            staleness_warning_days=acfg.staleness_warning_days)
    except Exception as e:  # noqa: BLE001
        print(f"SETUP FAIL (adapter): {e}")
        return 2

    has_anchor = "marketcap" in set(handle.dataframe.columns)
    if not has_anchor:
        print("SETUP FAIL: marketcap anchor není v snapshotu — "
              "anchor-date hypotézu nelze testovat")
        return 2

    prices_dir = Path((dp.get("mdsm") or {}).get("prices_dir", ""))
    price_provider = MDSMPriceProvider(prices_dir=prices_dir)
    # rozšířený rozsah: pokrýt i nejstarší datekey (~1Y před candidate)
    prices = price_provider.load_prices(
        conids=sorted(inp["conid"].unique()),
        date_from=inp["candidate_date"].min() - timedelta(
            days=DATEKEY_LOOKBACK_DAYS),
        date_to=inp["candidate_date"].max())

    out = build_diagnostics(inp, prices, provider, has_anchor)
    result, notes = classify(out)

    susp = out[out["cap01_reason"] == "SUSPECT"]
    ratio_summary = pd.DataFrame({
        "metric": ["ratio_candidate", "ratio_sharefactor_mult",
                   "ratio_sharefactor_div", "price_ratio",
                   "anchor_adjusted_ratio", "relative_diff_pct"],
        **{}}).set_index("metric")
    rs_rows = []
    for m in ["ratio_candidate", "ratio_sharefactor_mult",
              "ratio_sharefactor_div", "price_ratio",
              "anchor_adjusted_ratio", "relative_diff_pct"]:
        rs_rows.append({"metric": m, "scope": "suspect", **summarize(susp[m])})
        rs_rows.append({"metric": m, "scope": "all",
                        **summarize(out[m])})
    ratio_summary = pd.DataFrame(rs_rows)

    # suspect koncentrace podle conidu
    top_susp = (susp.groupby(["conid", "ticker"]).size()
                .sort_values(ascending=False).head(30)
                .reset_index(name="suspect_count"))
    # korelace
    def corr(a, b):
        d = out[[a, b]].dropna()
        return (round(float(d[a].corr(d[b])), 4)
                if len(d) > 2 else None)
    correlations = {
        "relative_diff_pct~staleness_days":
            corr("relative_diff_pct", "staleness_days"),
        "ratio_candidate~price_ratio":
            corr("ratio_candidate", "price_ratio"),
    }
    # staleness buckety pro suspecty
    stale_buckets = {}
    if len(susp):
        sb = pd.cut(susp["staleness_days"],
                    [0, 90, 180, 10_000],
                    labels=["0-90", "91-180", ">180"])
        stale_buckets = sb.value_counts().to_dict()

    run_id = (f"cap01a_market_cap_diagnosis_"
              f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{sid}")
    out_dir = MRL_ROOT / "results" / "diagnostics" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "suspect_diagnostics.csv", index=False)
    ratio_summary.to_csv(out_dir / "ratio_summary.csv", index=False)
    top_susp.to_csv(out_dir / "top_suspects.csv", index=False)

    lines = [
        "# CAP-01A Market Cap Diagnosis Summary",
        "",
        "Read-only diagnóza příčiny MARKET_CAP_SUSPECT. Nemění produkční "
        "CAP-01 formuli, bucket logiku ani tolerance.",
        "",
        f"- generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"- snapshot_id: `{sid}`",
        f"- candidate-days: {len(inp)} | suspect: {len(susp)}",
        f"- tolerance (CAP-01, referenční): {TOLERANCE_PCT} %",
        "",
        f"## DIAGNOSIS RESULT: {result}",
        "",
    ] + [f"- {n}" for n in notes] + [
        "",
        "## Ratio summary (suspect vs all)",
        "",
        df_to_markdown(ratio_summary),
        "",
        "## Korelace",
        "",
    ] + [f"- {k}: {v}" for k, v in correlations.items()] + [
        "",
        "## Suspect podle staleness bucketu", "",
    ] + [f"- {k}: {v}" for k, v in stale_buckets.items()] + [
        "",
        "## Top 30 suspect conidů", "",
        df_to_markdown(top_susp),
        "",
        "## Interpretace testů", "",
        "- anchor_adjusted_ratio ≈ 1 → vendor marketcap vztažen k "
        "datekey, ne candidate_date (anchor-date mismatch; market cap "
        "výpočet OK)",
        "- ratio_sharefactor_mult/div ≈ 1 → chybějící sharefactor korekce",
        "- žádný ≈ 1 → cena/shares nekompatibilní (source change)",
        "",
    ]
    summary_path = out_dir / "diagnosis_summary.md"
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    doc = MRL_ROOT / "docs" / "MRL_CAP01A_MARKET_CAP_DIAGNOSIS_REPORT.md"
    doc.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "run_id": run_id, "snapshot_id": sid,
        "input": {"path": str(args.input), "rows": int(len(inp))},
        "result": result, "notes": notes,
        "correlations": correlations,
        "forward_returns_used": False, "cap01_formula_changed": False,
    }
    (out_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    print(f"candidate-days: {len(inp)} | suspect: {len(susp)}")
    print(f"DIAGNOSIS: {result}")
    for nt in notes:
        print(f"  {nt}")
    print(f"summary: {summary_path}")
    print(f"report:  {doc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
