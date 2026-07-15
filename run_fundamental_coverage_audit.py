"""
run_fundamental_coverage_audit.py — FUND-03 coverage audit runner.

Účel: změřit fundamental coverage nad reálnými MLE × IRC candidate-days.
TOTO NENÍ EDGE TEST — neříká nic o profitabilitě fundamentals.

Tok: candidate-days CSV → MRLSharadarFundamentalSource (pinovaný snapshot)
     → output DataFrame 1:1 → coverage report → audit summary + manifest.

Zakázané vstupní sloupce (fail-fast při načtení):
    future_return, forward_return, return_5d, return_10d, return_20d,
    hit, pnl, alpha, sharpe, score_improvement
Zakázané metriky: forward returns, hit rate, Sharpe, CAGR, drawdown,
    ranking improvement, portfolio výsledky.

RESULT pravidla (pouze datová kvalita, žádné edge metriky):
    PASS:        coverage_pct >= 95 a UNKNOWN_ERROR == 0
                 (>180d staleness pouze reportováno)
    CONDITIONAL: coverage_pct 90–95
    STOP:        coverage_pct < 90 nebo UNKNOWN_ERROR > 0
                 nebo CACHE_MISSING/SCHEMA_MISMATCH > 0
                 (setup-level cache/schema fail shodí běh ještě dřív)

Výstup: results/diagnostics/fund03_coverage_<run_id>/
    candidate_days.csv, fundamentals_output.csv, coverage_<run_id>.md,
    audit_summary.md, source_manifest.json

Spuštění (Windows):
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    conda activate market_research_lab
    python run_fundamental_coverage_audit.py --input <candidate_days.csv>

Vyžaduje sharadar_fundamentals v config/data_paths.yaml s PINOVANÝM
snapshot_id (latest je odmítnut). Exit: 0 PASS, 1 CONDITIONAL/STOP, 2 setup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

MRL_ROOT = Path(__file__).resolve().parent
if str(MRL_ROOT) not in sys.path:
    sys.path.insert(0, str(MRL_ROOT))

from src.infrastructure.logging_manager import configure_logging, get_logger  # noqa: E402
from src.providers.sharadar_fundamental_source import (                        # noqa: E402
    FundamentalSourceError, build_fundamental_source,
)

configure_logging()
logger = get_logger("mrl.fund03.coverage_audit")

FORBIDDEN_INPUT_COLUMNS = (
    "future_return", "forward_return", "return_5d", "return_10d",
    "return_20d", "hit", "pnl", "alpha", "sharpe", "score_improvement",
)
OPTIONAL_ECHO_COLUMNS = ("ticker", "mle_rank", "irc_rank",
                         "source_signal_label")
STALENESS_BUCKETS = ((0, 90), (91, 180), (181, None))


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_candidate_days(path) -> pd.DataFrame:
    """Načte a zvaliduje candidate-days. Fail-fast na zakázané sloupce."""
    inp = pd.read_csv(path)
    forbidden = [c for c in inp.columns
                 if c.lower() in FORBIDDEN_INPUT_COLUMNS]
    if forbidden:
        raise ValueError(
            f"Input obsahuje zakázané forward-return/edge sloupce: "
            f"{forbidden} — FUND-03 je nesmí přenášet ani načítat.")
    if not {"conid", "candidate_date"}.issubset(inp.columns):
        raise ValueError("Input musí mít sloupce conid, candidate_date")
    inp = inp.copy()
    inp["conid"] = inp["conid"].astype(int)
    inp["candidate_date"] = pd.to_datetime(inp["candidate_date"]).dt.date
    return inp


def staleness_bucket_counts(out: pd.DataFrame) -> dict:
    ok = out[out["coverage_status"] == "OK"]
    counts = {}
    for lo, hi in STALENESS_BUCKETS:
        label = f"{lo}-{hi}d" if hi is not None else f">{lo - 1}d"
        if hi is None:
            mask = ok["staleness_days"] >= lo
        else:
            mask = (ok["staleness_days"] >= lo) & (ok["staleness_days"] <= hi)
        counts[label] = int(mask.sum())
    counts["missing/excluded"] = int(
        (out["coverage_status"] == "EXCLUDED").sum())
    return counts


def audit_result(cov) -> tuple[str, list[str]]:
    """PASS | CONDITIONAL | STOP — pouze datová kvalita."""
    d = cov.to_dict()
    reasons = []
    rc = d["reason_code_counts"]
    if rc["UNKNOWN_ERROR"] > 0:
        reasons.append(f"UNKNOWN_ERROR={rc['UNKNOWN_ERROR']}")
    if rc["CACHE_MISSING"] > 0 or rc["SCHEMA_MISMATCH"] > 0:
        reasons.append(
            f"CACHE_MISSING={rc['CACHE_MISSING']} "
            f"SCHEMA_MISMATCH={rc['SCHEMA_MISMATCH']}")
    if reasons:
        return "STOP", reasons
    pct = d["coverage_pct"]
    if pct >= 95.0:
        return "PASS", []
    if pct >= 90.0:
        return "CONDITIONAL", [f"coverage_pct={pct} v pásmu 90–95"]
    return "STOP", [f"coverage_pct={pct} < 90"]


def write_audit_summary(path, *, run_id, source, input_path, inp, out,
                        cov, stale_buckets, result, result_reasons) -> Path:
    d = cov.to_dict()
    date_min, date_max = (str(inp["candidate_date"].min()),
                          str(inp["candidate_date"].max()))
    lines = [
        "# FUND-03 Coverage Audit Summary",
        "",
        "FUND-03 není edge test a neříká nic o profitabilitě fundamentals.",
        "Měří pouze datové pokrytí PIT SF1 ART snapshotu nad candidate-days.",
        "",
        f"- generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"- run_id: `{run_id}`",
        f"- input: `{input_path}`",
        f"- snapshot_id: `{source.snapshot_id}`",
        f"- snapshot_data_hash: `{source.snapshot_data_hash}`",
        f"- contract_versions: `{source.contract_versions}`",
        "",
        "## Coverage",
        "",
        f"- candidate-days count: {len(inp)}",
        f"- unique conids: {inp['conid'].nunique()}",
        f"- date range: {date_min} → {date_max}",
        f"- included: {d['returned_snapshots']}",
        f"- excluded: {d['excluded_candidate_days']}",
        f"- coverage_pct: {d['coverage_pct']}",
        f"- alias_count: {d['alias_count']}",
        f"- alias_pct: "
        f"{round(100 * d['alias_count'] / max(d['returned_snapshots'], 1), 2)}",
        f"- stale_warnings (>180d): {d['stale_warnings']}",
        f"- identity_excluded: {d['identity_excluded']}",
        f"- missing_sf1: {d['missing_sf1']}",
        f"- no_asof_date: {d['no_asof_date']}",
        f"- UNKNOWN_ERROR: {d['reason_code_counts']['UNKNOWN_ERROR']}",
        "",
        "## Reason code distribution",
        "",
        "| reason_code | count |", "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in d["reason_code_counts"].items()]
    lines += ["", "## Staleness buckets", "",
              "| bucket | count |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in stale_buckets.items()]
    lines += ["", f"## RESULT: {result}", ""]
    if result_reasons:
        lines += ["Důvody:", ""] + [f"- {r}" for r in result_reasons] + [""]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="FUND-03 fundamental coverage audit (bez edge logiky)")
    ap.add_argument("--input", required=True,
                    help="candidate_days.csv (conid, candidate_date, ...)")
    ap.add_argument("--config", default=str(MRL_ROOT / "config"
                                            / "data_paths.yaml"))
    ap.add_argument("--ignore-enabled", action="store_true")
    args = ap.parse_args(argv)

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = (yaml.safe_load(f) or {}).get("sharadar_fundamentals") or {}
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

    try:
        source = build_fundamental_source(
            adapter_config_path=cfg["adapter_config"],
            snapshot_id=str(cfg["snapshot_id"]),
        )
    except FundamentalSourceError as e:
        print(f"SETUP FAIL: {e}")
        return 2
    except Exception as e:  # SharadarProviderError setup-level
        print(f"SETUP FAIL (adapter): {e}")
        return 2

    run_id = (f"fund03_coverage_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}"
              f"_{source.snapshot_id}")
    out_dir = MRL_ROOT / "results" / "diagnostics" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    out, cov = source.get_fundamentals(
        inp[["conid", "candidate_date"]], experiment_id=run_id)

    # echo volitelných sloupců (audit trail, 1:1 pořadí zachováno)
    echo = {c: inp[c].values for c in OPTIONAL_ECHO_COLUMNS
            if c in inp.columns}
    out_full = out.assign(**echo)

    stale_buckets = staleness_bucket_counts(out)
    result, result_reasons = audit_result(cov)

    inp.to_csv(out_dir / "candidate_days.csv", index=False)
    out_full.to_csv(out_dir / "fundamentals_output.csv", index=False)
    coverage_path = source.write_coverage_report(cov, out_dir, run_id)
    summary_path = write_audit_summary(
        out_dir / "audit_summary.md", run_id=run_id, source=source,
        input_path=args.input, inp=inp, out=out, cov=cov,
        stale_buckets=stale_buckets, result=result,
        result_reasons=result_reasons)
    manifest = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": {"path": str(args.input), "sha256": sha256(args.input),
                  "rows": int(len(inp))},
        "snapshot": {"snapshot_id": source.snapshot_id,
                     "data_hash": source.snapshot_data_hash,
                     "contract_versions": source.contract_versions},
        "source_hashes": {"sf1_snapshot_id": source.snapshot_id,
                          "sf1_data_hash": source.snapshot_data_hash},
        "coverage": cov.to_dict(),
        "staleness_buckets": stale_buckets,
        "result": result,
        "forward_returns_used": False,
    }
    (out_dir / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    d = cov.to_dict()
    print(f"candidate-days: {len(inp)} | unique conids: "
          f"{inp['conid'].nunique()}")
    print(f"included={d['returned_snapshots']} "
          f"excluded={d['excluded_candidate_days']} "
          f"coverage_pct={d['coverage_pct']}")
    print(f"staleness: {stale_buckets}")
    print(f"audit summary:   {summary_path}")
    print(f"coverage report: {coverage_path}")
    print(f"manifest:        {out_dir / 'source_manifest.json'}")
    print(f"RESULT: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
