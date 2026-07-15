"""
run_cap01_market_cap_audit.py — MRL-CAP-01 market-cap coverage audit.

TOTO NENÍ performance test — žádné forward returns, žádná profitabilita.

Tok: candidate-days CSV → MDSM close (canonical price) × sharesbas (PIT
přes adapter SF1Provider) → computed_market_cap → fixed bucket →
sanity anchor (Sharadar marketcap, validation-only) → audit summary.

Reason codes (CAP vrstva):
    MARKET_CAP_OK | MARKET_CAP_PRICE_MISSING | MARKET_CAP_SHARES_MISSING
    MARKET_CAP_SUSPECT | MARKET_CAP_INVALID | UNKNOWN_ERROR

Pre-registrovaná tolerance (docs/MRL_CAP01_COVERAGE_AUDIT_REPORT.md):
    relative_diff_pct > 25 % → MARKET_CAP_SUSPECT → UNBUCKETED
    boundary sensitivity: ±10 % od bucket hranic
    systematický anchor problém (median ratio mimo [0.5, 2.0])
    → minimálně CONDITIONAL; CAP-02 blokován

Spuštění (Windows):
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    conda activate market_research_lab
    python run_cap01_market_cap_audit.py --input results\\diagnostics\\fund03_candidate_days_<ts>\\candidate_days.csv --ignore-enabled

Exit: 0 PASS, 1 CONDITIONAL/STOP, 2 setup fail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
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

configure_logging()
logger = get_logger("mrl.cap01.audit")

# fixed buckets — MRL_CAP00_BUCKET_POLICY.md (LOCKED, po výsledku neměnit)
BUCKETS = (
    ("Mega", 200e9, math.inf),
    ("Large-high", 50e9, 200e9),
    ("Large-low", 10e9, 50e9),
    ("Mid", 2e9, 10e9),
    ("Small", 0.0, 2e9),
)
THRESHOLDS = (2e9, 10e9, 50e9, 200e9)
UNBUCKETED = "UNBUCKETED"

CAP_REASON_CODES = ("MARKET_CAP_OK", "MARKET_CAP_PRICE_MISSING",
                    "MARKET_CAP_SHARES_MISSING", "MARKET_CAP_SUSPECT",
                    "MARKET_CAP_INVALID", "UNKNOWN_ERROR")

TOLERANCE_PCT = 25.0            # pre-registrováno, neměnit po výsledku
BOUNDARY_BAND_PCT = 10.0
ANCHOR_SYSTEMATIC_BAND = (0.5, 2.0)   # median(datekey_computed/vendor)


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def df_to_markdown(df: pd.DataFrame) -> str:
    """Markdown tabulka bez závislosti na `tabulate`.

    Konzistentní se zbytkem MRL reportů (FUND-03/05 generují md ručně).
    Prázdný DataFrame → '—'. Hodnoty přes str(); NaN jako prázdná buňka.
    """
    if df.empty:
        return "—"
    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    rows = []
    for row in df.itertuples(index=False):
        cells = ["" if pd.isna(v) else str(v) for v in row]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, sep, *rows])


def assign_bucket(mc: float) -> str:
    """Dolní mez inclusive, horní exclusive."""
    for name, lo, hi in BUCKETS:
        if lo <= mc < hi:
            return name
    return UNBUCKETED


def nearest_preceding_close(pdf, target) -> float | None:
    """Close k nejbližšímu obchodnímu dni <= target (datekey nemusí být
    obchodní den). None pokud pdf prázdné nebo žádný den <= target.

    Pozn.: candidate_date close vyžaduje PŘESNÝ den (existující chování,
    MARKET_CAP_PRICE_MISSING); tento helper je JEN pro datekey anchor,
    kde je nearest-preceding korektní (datekey = filing date)."""
    if pdf is None or pdf.empty:
        return None
    ts = pd.Timestamp(target)
    sub = pdf.index[pdf.index <= ts]
    if len(sub) == 0:
        return None
    return float(pdf.loc[sub.max(), "close"])


def boundary_distance_pct(mc: float) -> float:
    """Min relativní vzdálenost k nejbližší bucket hranici (v %)."""
    return round(min(abs(mc - t) / t for t in THRESHOLDS) * 100, 2)


def compute_rows(inp: pd.DataFrame, prices: dict, provider,
                 has_sharefactor: bool, has_anchor: bool,
                 tolerance_pct: float = TOLERANCE_PCT) -> pd.DataFrame:
    """Per-row market cap + bucket + reason_code. 1:1 s inputem,
    žádný silent drop."""
    from sharadar_mdsm_adapter.exceptions import SharadarProviderError

    shares_fields = ["sharesbas"] + (["sharefactor"] if has_sharefactor
                                     else [])
    records = []
    for row in inp.itertuples(index=False):
        conid, cand = int(row.conid), row.candidate_date
        rec = {
            "conid": conid,
            "ticker": getattr(row, "ticker", None),
            "candidate_date": cand,
            "close_asof": np.nan, "sharesbas": np.nan,
            "sharefactor": np.nan, "sf1_datekey": pd.NaT,
            "staleness_days": np.nan,
            "computed_market_cap": np.nan,
            "close_datekey": np.nan,
            "datekey_computed_market_cap": np.nan,
            "vendor_marketcap_anchor": np.nan,
            "relative_diff_pct": np.nan,
            "boundary_distance_pct": np.nan,
            "market_cap_bucket": UNBUCKETED,
            "market_cap_reason_code": None,
        }
        try:
            # 1. price — canonical MDSM close asof candidate_date
            pdf = prices.get(conid)
            ts = pd.Timestamp(cand)
            if pdf is None or pdf.empty or ts not in pdf.index:
                rec["market_cap_reason_code"] = "MARKET_CAP_PRICE_MISSING"
                records.append(rec)
                continue
            close = float(pdf.loc[ts, "close"])
            rec["close_asof"] = close

            # 2. shares — PIT přes adapter (zamčená PIT logika)
            try:
                snap = provider.get_snapshot(conid, cand,
                                             fields=shares_fields)
            except SharadarProviderError:
                rec["market_cap_reason_code"] = "MARKET_CAP_SHARES_MISSING"
                records.append(rec)
                continue
            shares = snap.fundamentals.get("sharesbas")
            rec["sharesbas"] = shares
            rec["sharefactor"] = snap.fundamentals.get("sharefactor",
                                                       np.nan)
            rec["sf1_datekey"] = snap.datekey
            rec["staleness_days"] = snap.staleness_days
            if shares is None or not np.isfinite(shares) or shares <= 0:
                rec["market_cap_reason_code"] = "MARKET_CAP_SHARES_MISSING"
                records.append(rec)
                continue

            # 3. computed market cap
            mc = close * shares
            rec["computed_market_cap"] = mc
            if not np.isfinite(mc) or mc <= 0 or close <= 0:
                rec["market_cap_reason_code"] = "MARKET_CAP_INVALID"
                records.append(rec)
                continue
            rec["boundary_distance_pct"] = boundary_distance_pct(mc)

            # 4. sanity anchor (validation-only; alias → nedostupný)
            # CAP-01B: date-konzistentní srovnání. Vendor marketcap je
            # vztažen k sf1_datekey, ne candidate_date. Porovnává se proto
            # datekey_computed = close(datekey) × sharesbas vs vendor(datekey),
            # ne candidate-date computed. Tím se eliminuje falešný SUSPECT
            # způsobený cenovým pohybem mezi datekey a candidate_date
            # (CAP-01A diagnóza: ANCHOR_DATE_MISMATCH, 96.3 %).
            # relative_diff_pct = odchylka date-konzistentní; bucket dál
            # z candidate-date mc (beze změny).
            if has_anchor:
                try:
                    a = provider.get_snapshot(conid, cand,
                                              fields=["marketcap"])
                    anchor = a.price_derived.get("marketcap")
                except SharadarProviderError:
                    anchor = None    # alias / jiný fail-fast — bez anchoru
                if anchor is not None and np.isfinite(anchor) and anchor > 0:
                    rec["vendor_marketcap_anchor"] = anchor
                    close_dk = nearest_preceding_close(pdf, snap.datekey)
                    if (close_dk is not None and np.isfinite(close_dk)
                            and close_dk > 0):
                        rec["close_datekey"] = close_dk
                        dk_mc = close_dk * shares
                        rec["datekey_computed_market_cap"] = dk_mc
                        diff = abs(dk_mc - anchor) / anchor * 100
                        rec["relative_diff_pct"] = round(diff, 2)
                        if diff > tolerance_pct:
                            rec["market_cap_reason_code"] = \
                                "MARKET_CAP_SUSPECT"
                            records.append(rec)
                            continue
                    # close(datekey) nedostupný → nelze date-konzistentně
                    # validovat; není to suspect (anchor jen nedostupný),
                    # ale zaznamenat pro report
                    else:
                        rec["relative_diff_pct"] = np.nan

            rec["market_cap_bucket"] = assign_bucket(mc)
            rec["market_cap_reason_code"] = "MARKET_CAP_OK"
        except Exception as e:  # noqa: BLE001 — CAP-interní kategorie
            logger.warning(f"CAP01 UNKNOWN_ERROR conid={conid} "
                           f"date={cand}: {e!r}")
            rec["market_cap_reason_code"] = "UNKNOWN_ERROR"
        records.append(rec)

    out = pd.DataFrame.from_records(records)
    if len(out) != len(inp):
        raise RuntimeError(f"1:1 invarianta porušena: {len(inp)} vs "
                           f"{len(out)}")
    return out


def audit_result(out: pd.DataFrame, anchor_available: bool) -> tuple:
    """PASS / CONDITIONAL / STOP dle zadání CAP-01 Úkol 4."""
    n = len(out)
    rc = out["market_cap_reason_code"].value_counts().to_dict()
    ok = rc.get("MARKET_CAP_OK", 0)
    coverage = round(ok / n * 100, 2) if n else 0.0
    unknown = rc.get("UNKNOWN_ERROR", 0)
    suspect = rc.get("MARKET_CAP_SUSPECT", 0)
    reasons = []

    if unknown > 0:
        return "STOP", coverage, [f"UNKNOWN_ERROR={unknown}"]
    if coverage < 90.0:
        return "STOP", coverage, [f"coverage {coverage} < 90"]

    # systematický anchor problém
    # date-konzistentní ratio (CAP-01B): datekey_computed vs vendor
    ratios = (out["datekey_computed_market_cap"]
              / out["vendor_marketcap_anchor"]).dropna()
    if anchor_available and len(ratios):
        med = float(ratios.median())
        if not (ANCHOR_SYSTEMATIC_BAND[0] <= med
                <= ANCHOR_SYSTEMATIC_BAND[1]):
            reasons.append(f"systematický anchor problém: median ratio "
                           f"{med:.4g} mimo {ANCHOR_SYSTEMATIC_BAND} "
                           "— CAP-02 blokován do vyřešení")
    if not anchor_available:
        reasons.append("sanity anchor nedostupný (marketcap chybí) — "
                       "primary source bez validace")
    if suspect > 0 and suspect / n > 0.02:
        reasons.append(f"MARKET_CAP_SUSPECT koncentrace {suspect}/{n}")

    if coverage < 95.0:
        reasons.insert(0, f"coverage {coverage} v pásmu 90–95")
        return "CONDITIONAL", coverage, reasons
    if reasons:
        return "CONDITIONAL", coverage, reasons
    return "PASS", coverage, []


def bucket_tables(out: pd.DataFrame):
    dist = (out.groupby("market_cap_bucket")
            .agg(candidate_days=("conid", "size"),
                 unique_conids=("conid", "nunique"),
                 unique_dates=("candidate_date", "nunique"))
            .reset_index())
    tops = []
    for b, g in out.groupby("market_cap_bucket"):
        top = g.groupby(["conid"]).size().sort_values(ascending=False)
        for conid, cnt in top.head(5).items():
            tick = g.loc[g["conid"] == conid, "ticker"].iloc[0]
            tops.append({"bucket": b, "conid": conid, "ticker": tick,
                         "count": int(cnt)})
    return dist, pd.DataFrame(tops)


def write_summary(path, *, run_id, snapshot_id, data_hash, input_path,
                  inp, out, dist, tops, result, coverage, reasons,
                  anchor_available, has_sharefactor) -> Path:
    rc = out["market_cap_reason_code"].value_counts().to_dict()
    per_date = out.groupby("candidate_date").size()
    boundary_close = out.loc[
        out["market_cap_reason_code"] == "MARKET_CAP_OK",
        "boundary_distance_pct"]
    diffs = out["relative_diff_pct"].dropna()
    # date-konzistentní ratio (CAP-01B): datekey_computed vs vendor
    ratios = (out["datekey_computed_market_cap"]
              / out["vendor_marketcap_anchor"]).dropna()
    lines = [
        "# CAP-01 Market Cap Coverage Audit Summary",
        "",
        "CAP-01 není performance test — žádné forward returns, žádná "
        "profitabilita.",
        "",
        f"- generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"- run_id: `{run_id}`",
        f"- input: `{input_path}`",
        f"- snapshot_id: `{snapshot_id}` (data_hash `{data_hash}`)",
        f"- sharefactor available: {has_sharefactor}",
        f"- sanity anchor available: {anchor_available}",
        f"- tolerance (pre-registrováno): {TOLERANCE_PCT} % | boundary "
        f"band ±{BOUNDARY_BAND_PCT} %",
        "",
        "## Coverage",
        "",
        f"- candidate-days: {len(inp)} | unique conids: "
        f"{inp['conid'].nunique()}",
        f"- date range: {inp['candidate_date'].min()} → "
        f"{inp['candidate_date'].max()}",
        f"- market_cap_available (OK): {rc.get('MARKET_CAP_OK', 0)}",
        f"- missing (price/shares): "
        f"{rc.get('MARKET_CAP_PRICE_MISSING', 0)} / "
        f"{rc.get('MARKET_CAP_SHARES_MISSING', 0)}",
        f"- suspect: {rc.get('MARKET_CAP_SUSPECT', 0)} | invalid: "
        f"{rc.get('MARKET_CAP_INVALID', 0)} | unknown: "
        f"{rc.get('UNKNOWN_ERROR', 0)}",
        f"- coverage_pct: {coverage}",
        f"- candidate-days per date: min={int(per_date.min())} "
        f"median={float(per_date.median())} max={int(per_date.max())}",
        f"- boundary sensitivity (±{BOUNDARY_BAND_PCT} % od hranice): "
        f"{int((boundary_close <= BOUNDARY_BAND_PCT).sum())} OK řádků",
        "",
        "## Reason code distribution", "",
        "| reason_code | count |", "|---|---|",
    ]
    lines += [f"| {c} | {rc.get(c, 0)} |" for c in CAP_REASON_CODES]
    lines += ["", "## Bucket distribution", "",
              df_to_markdown(dist), "",
              "## Top repeated conids per bucket", "",
              df_to_markdown(tops),
              ""]
    if len(diffs):
        lines += ["## Sanity anchor",
                  "",
                  f"- relative_diff_pct: median={diffs.median():.2f} "
                  f"p95={diffs.quantile(0.95):.2f} max={diffs.max():.2f}",
                  f"- median(computed/vendor) ratio: "
                  f"{float(ratios.median()):.4g}", ""]
    lines += [f"## RESULT: {result}", ""]
    if reasons:
        lines += ["Důvody:", ""] + [f"- {r}" for r in reasons] + [""]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="CAP-01 market cap coverage audit (bez výnosů)")
    ap.add_argument("--input", required=True)
    ap.add_argument("--config", default=str(MRL_ROOT / "config"
                                            / "data_paths.yaml"))
    ap.add_argument("--ignore-enabled", action="store_true")
    args = ap.parse_args(argv)

    dp = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    cfg = dp.get("sharadar_fundamentals") or {}
    if not cfg:
        print("SETUP FAIL: sekce sharadar_fundamentals chybí")
        return 2
    if not cfg.get("enabled", False) and not args.ignore_enabled:
        print("SETUP FAIL: enabled=false (použij --ignore-enabled)")
        return 2

    try:
        inp = load_candidate_days(args.input)
    except (ValueError, FileNotFoundError) as e:
        print(f"SETUP FAIL: {e}")
        return 2

    # adapter stack — výhradně veřejné API, pinned snapshot
    try:
        from sharadar_mdsm_adapter.config import load_config
        from sharadar_mdsm_adapter.identity_map import IdentityMap
        from sharadar_mdsm_adapter.sf1_provider import SF1Provider
        from sharadar_mdsm_adapter.sf1_store import SF1Store
        sid = str(cfg["snapshot_id"])
        if sid == "latest":
            print("SETUP FAIL: snapshot_id musí být pinovaný, ne 'latest'")
            return 2
        acfg = load_config(cfg["adapter_config"])
        handle = SF1Store(acfg).load(sid)
        ident = IdentityMap.load(acfg.identity_map_path, acfg.allowed_tiers)
        provider = SF1Provider(
            handle, ident,
            staleness_warning_days=acfg.staleness_warning_days)
    except Exception as e:  # noqa: BLE001
        print(f"SETUP FAIL (adapter): {e}")
        return 2

    cols = set(handle.dataframe.columns)
    if "sharesbas" not in cols:
        print("STOP: sharesbas chybí v snapshotu (field gate)")
        return 1
    has_sharefactor = "sharefactor" in cols
    has_anchor = "marketcap" in cols

    # MDSM ceny — canonical price source
    prices_dir = Path((dp.get("mdsm") or {}).get("prices_dir", ""))
    if not str(prices_dir):
        print("SETUP FAIL: mdsm.prices_dir chybí v data_paths.yaml")
        return 2
    price_provider = MDSMPriceProvider(prices_dir=prices_dir)
    conids = sorted(inp["conid"].unique())
    prices = price_provider.load_prices(
        conids=conids,
        date_from=inp["candidate_date"].min(),
        date_to=inp["candidate_date"].max())

    out = compute_rows(inp, prices, provider, has_sharefactor, has_anchor)
    result, coverage, reasons = audit_result(out, has_anchor)
    dist, tops = bucket_tables(out)

    run_id = (f"cap01_market_cap_coverage_"
              f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{sid}")
    out_dir = MRL_ROOT / "results" / "diagnostics" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    inp.to_csv(out_dir / "candidate_days.csv", index=False)
    out.to_csv(out_dir / "market_cap_output.csv", index=False)
    dist.to_csv(out_dir / "cap_bucket_distribution.csv", index=False)
    summary_path = write_summary(
        out_dir / "cap01_audit_summary.md", run_id=run_id, snapshot_id=sid,
        data_hash=handle.manifest.get("data_hash"), input_path=args.input,
        inp=inp, out=out, dist=dist, tops=tops, result=result,
        coverage=coverage, reasons=reasons, anchor_available=has_anchor,
        has_sharefactor=has_sharefactor)
    manifest = {
        "run_id": run_id,
        "input": {"path": str(args.input), "sha256": sha256(args.input),
                  "rows": int(len(inp))},
        "snapshot": {"snapshot_id": sid,
                     "data_hash": handle.manifest.get("data_hash")},
        "fields": {"sharesbas": True, "sharefactor": has_sharefactor,
                   "marketcap_anchor": has_anchor},
        "tolerance_pct": TOLERANCE_PCT,
        "boundary_band_pct": BOUNDARY_BAND_PCT,
        "buckets": [(n, lo, ("inf" if hi == math.inf else hi))
                    for n, lo, hi in BUCKETS],
        "coverage_pct": coverage,
        "result": result,
        "forward_returns_used": False,
        "current_market_cap_used": False,
    }
    (out_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    rc = out["market_cap_reason_code"].value_counts().to_dict()
    print(f"candidate-days: {len(inp)} | coverage_pct: {coverage}")
    print(f"reason codes: {rc}")
    print(dist.to_string(index=False))
    print(f"audit summary: {summary_path}")
    print(f"manifest:      {out_dir / 'source_manifest.json'}")
    print(f"RESULT: {result}"
          + (f"  [{'; '.join(reasons)}]" if reasons else ""))
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
