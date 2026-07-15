"""
run_fundamental_smoke_integration.py — MRL-FUND-01 smoke integration runner.

Tok: candidate-days → MRLSharadarFundamentalSource → SF1Provider
     → output DataFrame 1:1 → coverage report → smoke report.

Toto NENÍ edge test — žádné forward returns, žádný scoring, žádná selekce.

Výstup: results/diagnostics/fundamental_smoke_<ts>_<snapshot_id>/
    smoke_report.md
    coverage_<run_id>.md
    fundamentals_output.csv   (audit — pouze fundamentals + metadata)

Spuštění (Windows, lokálně — vyžaduje nainstalovaný adapter a reálný snapshot):
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    conda activate <mrl_env>
    python run_fundamental_smoke_integration.py

Vyžaduje sekci sharadar_fundamentals v config/data_paths.yaml (enabled: true,
nebo --ignore-enabled pro jednorázový diagnostický běh).
Exit: 0 = PASS, 1 = STOP, 2 = setup fail.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
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
logger = get_logger("mrl.fund01.smoke")

# Fixní smoke vzorek — reálné conidy S&P universe (viz adapter identity mapa).
AAPL, GOOG, LYB = 265598, 208813720, 74866700
INVALID_CONID = 999999999
BEFORE_FIRST = date(1990, 1, 1)


def build_candidate_days(candidate_date: date) -> pd.DataFrame:
    return pd.DataFrame([
        {"conid": AAPL, "candidate_date": candidate_date,
         "label": "AAPL strong"},
        {"conid": AAPL, "candidate_date": candidate_date,
         "label": "AAPL duplicate (1:1 check)"},
        {"conid": GOOG, "candidate_date": candidate_date,
         "label": "GOOG alias"},
        {"conid": LYB, "candidate_date": candidate_date,
         "label": "LYB whitelist"},
        {"conid": INVALID_CONID, "candidate_date": candidate_date,
         "label": "invalid conid"},
        {"conid": AAPL, "candidate_date": BEFORE_FIRST,
         "label": "before first datekey"},
    ])


def evaluate(out: pd.DataFrame, cov) -> list[tuple[str, str, str]]:
    """Vrací [(check, PASS/FAIL, detail)]. Žádné SKIPPED — scénáře nejsou
    datově podmíněné."""
    checks = []

    def add(name, ok, detail=""):
        checks.append((name, "PASS" if ok else "FAIL", detail))

    add("1:1 řádky (včetně duplicity)", len(out) == 6,
        f"output rows={len(out)}")
    ok_rows = out[out["coverage_status"] == "OK"]
    ex_rows = out[out["coverage_status"] == "EXCLUDED"]
    add("AAPL/GOOG/LYB OK (4 řádky)", len(ok_rows) == 4,
        f"OK={len(ok_rows)}")
    add("PIT: sf1_datekey <= candidate_date",
        bool((ok_rows["sf1_datekey"] <= ok_rows["candidate_date"]).all()))
    add("alias flag zachován (GOOG)",
        bool(out.loc[out["conid"] == GOOG, "is_alias"].iloc[0] is True
             or out.loc[out["conid"] == GOOG, "is_alias"].iloc[0] == True))  # noqa: E712
    reasons = set(ex_rows["reason_code"])
    add("EXCLUDED reason codes",
        reasons == {"IDENTITY_MISSING", "NO_SF1_ASOF_DATE"},
        f"reasons={sorted(reasons)}")
    add("EXCLUDED řádky nedropnuty, NaN fundamentals",
        len(ex_rows) == 2 and bool(ex_rows["revenue"].isna().all()))
    add("coverage requested = 6",
        cov.requested_candidate_days == 6,
        f"requested={cov.requested_candidate_days}")
    add("coverage returned = 4",
        cov.returned_snapshots == 4,
        f"returned={cov.returned_snapshots}")
    add("UNKNOWN_ERROR == 0",
        cov.reason_code_counts["UNKNOWN_ERROR"] == 0)
    add("price-derived pole mimo output",
        all(c not in out.columns for c in ("marketcap", "pe", "ps", "pb")))
    return checks


def write_smoke_report(path, *, run_id, source, candidate_date, out, cov,
                       checks, coverage_path, result) -> Path:
    d = cov.to_dict()
    lines = [
        "# MRL-FUND-01 Fundamental Smoke Integration Report",
        "",
        f"- generated_at_utc: {datetime.now(timezone.utc).isoformat()}",
        f"- run_id: `{run_id}`",
        f"- snapshot_id: `{source.snapshot_id}`",
        f"- snapshot_data_hash: `{source.snapshot_data_hash}`",
        f"- contract_versions: `{source.contract_versions}`",
        f"- candidate_date: {candidate_date}",
        f"- candidate-days count: {len(out)}",
        f"- included: {d['returned_snapshots']}",
        f"- excluded: {d['excluded_candidate_days']}",
        f"- coverage_pct: {d['coverage_pct']}",
        f"- alias_count: {d['alias_count']}",
        f"- staleness warnings: {d['stale_warnings']}",
        "",
        "## Reason code distribution",
        "",
        "| reason_code | count |", "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in d["reason_code_counts"].items()]
    lines += ["", "## Checks", "", "| check | status | detail |",
              "|---|---|---|"]
    lines += [f"| {n} | {s} | {det or '-'} |" for n, s, det in checks]
    lines += ["", f"- coverage report: `{coverage_path}`", "",
              f"## RESULT: {result}", ""]
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="MRL-FUND-01 fundamental smoke integration")
    ap.add_argument("--config", default=str(MRL_ROOT / "config"
                                            / "data_paths.yaml"))
    ap.add_argument("--candidate-date", default=None, help="YYYY-MM-DD")
    ap.add_argument("--ignore-enabled", action="store_true",
                    help="diagnostický běh i při enabled: false")
    args = ap.parse_args(argv)

    candidate_date = (date.fromisoformat(args.candidate_date)
                      if args.candidate_date else date.today())

    with open(args.config, "r", encoding="utf-8") as f:
        cfg = (yaml.safe_load(f) or {}).get("sharadar_fundamentals") or {}
    if not cfg:
        print("STOP: sekce sharadar_fundamentals chybí v data_paths.yaml")
        return 2
    if not cfg.get("enabled", False) and not args.ignore_enabled:
        print("STOP: sharadar_fundamentals.enabled=false "
              "(použij --ignore-enabled pro diagnostiku)")
        return 2

    try:
        source = build_fundamental_source(
            adapter_config_path=cfg["adapter_config"],
            snapshot_id=str(cfg["snapshot_id"]),
        )
    except FundamentalSourceError as e:
        print(f"SETUP FAIL: {e}")
        return 2
    except Exception as e:  # SharadarProviderError (CACHE_MISSING, ...)
        print(f"SETUP FAIL (adapter): {e}")
        return 2

    run_id = (f"fund01_smoke_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}"
              f"_{source.snapshot_id}")
    out_dir = MRL_ROOT / "results" / "diagnostics" / run_id

    candidate_days = build_candidate_days(candidate_date)
    out, cov = source.get_fundamentals(
        candidate_days[["conid", "candidate_date"]],
        experiment_id=run_id)

    checks = evaluate(out, cov)
    result = "PASS" if all(s == "PASS" for _, s, _ in checks) else "STOP"

    coverage_path = source.write_coverage_report(cov, out_dir, run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out.assign(label=candidate_days["label"].values).to_csv(
        out_dir / "fundamentals_output.csv", index=False)
    smoke_path = write_smoke_report(
        out_dir / "smoke_report.md", run_id=run_id, source=source,
        candidate_date=candidate_date, out=out, cov=cov, checks=checks,
        coverage_path=coverage_path, result=result)

    for n, s, det in checks:
        print(f"  {s:5s} {n}" + (f"  [{det}]" if det else ""))
    d = cov.to_dict()
    print(f"coverage: requested={d['requested_candidate_days']} "
          f"returned={d['returned_snapshots']} pct={d['coverage_pct']}")
    print(f"smoke report:    {smoke_path}")
    print(f"coverage report: {coverage_path}")
    print(f"RESULT: {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
