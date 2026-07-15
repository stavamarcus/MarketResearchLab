"""
run_fundamental_edge_protocol.py — tenký launcher FUND-05 edge runu.

NEOBCHÁZÍ governance: spouští Fund05MleIrcFundamentalEdge přes
ExperimentRunner (ContextBuilder → validate → run → ArchiveManager →
registry JSONL → ReportBuilder). Launcher pouze: načte candidate-days
(forbidden-column guard), spočítá hashe, sestaví config a vytiskne souhrn.

Spuštění (Windows):
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    conda activate market_research_lab
    python run_fundamental_edge_protocol.py --candidate-days results\\diagnostics\\fund03_candidate_days_<ts>\\candidate_days.csv

Vyžaduje sharadar_fundamentals v data_paths.yaml (enabled: true nebo
--ignore-enabled) a pinned snapshot. Exit: 0 COMPLETED, 1 STOP, 2 setup.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import timedelta
from pathlib import Path

MRL_ROOT = Path(__file__).resolve().parent
if str(MRL_ROOT) not in sys.path:
    sys.path.insert(0, str(MRL_ROOT))

from src.core.experiment_config import ExperimentConfig                      # noqa: E402
from src.core.experiment_runner import ExperimentRunner                      # noqa: E402
from src.infrastructure.archive_manager import ArchiveManager                # noqa: E402
from src.infrastructure.logging_manager import configure_logging, get_logger  # noqa: E402
from src.providers.provider_factory import ProviderFactory                   # noqa: E402
from src.reports.report_builder import ReportBuilder                         # noqa: E402
from experiments.fundamental_validation.fund05_mle_irc_fundamental_edge_v1 import (  # noqa: E402
    Fund05MleIrcFundamentalEdge_v1, VARIANTS,
)
from run_fundamental_coverage_audit import load_candidate_days               # noqa: E402

configure_logging()
logger = get_logger("mrl.fund05.launcher")

DATE_BUFFER_DAYS = 35  # 20D okno + nearest +5 + rezerva


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="FUND-05 edge protocol run")
    ap.add_argument("--candidate-days", required=True)
    ap.add_argument("--config-dir", default=str(MRL_ROOT / "config"))
    ap.add_argument("--ignore-enabled", action="store_true",
                    help="explicitní aktivace fundamentals i při "
                         "enabled: false (diagnostický opt-in)")
    ap.add_argument("--universe", default="sp500_rank_calendar",
                    help="universe name; default resolvuje na "
                         "sp500_rank_calendar_universe.csv (503 instrumentů)."
                         " Pozn.: 'sp500' padá na 6řádkový universe.csv "
                         "fallback — nepoužívat.")
    args = ap.parse_args(argv)

    try:
        inp = load_candidate_days(args.candidate_days)
    except (ValueError, FileNotFoundError) as e:
        print(f"SETUP FAIL: {e}")
        return 2

    factory = ProviderFactory(Path(args.config_dir))
    try:
        bundle = factory.build()
        if bundle.fundamental is None and args.ignore_enabled:
            # explicitní CLI opt-in — čte tutéž sekci, ignoruje enabled
            import yaml
            cfg = (yaml.safe_load((Path(args.config_dir)
                                   / "data_paths.yaml").read_text(
                encoding="utf-8")) or {}).get("sharadar_fundamentals") or {}
            if cfg:
                from src.providers.sharadar_fundamental_source import (
                    build_fundamental_source,
                )
                bundle.fundamental = build_fundamental_source(
                    cfg["adapter_config"], str(cfg["snapshot_id"]))
    except Exception as e:  # noqa: BLE001 — setup-level
        print(f"SETUP FAIL: {e}")
        return 2
    if bundle.fundamental is None:
        print("SETUP FAIL: fundamental_source není k dispozici "
              "(enabled: false a chybí --ignore-enabled, nebo sekce chybí)")
        return 2

    config = ExperimentConfig(
        date_from=inp["candidate_date"].min(),
        date_to=inp["candidate_date"].max() + timedelta(days=DATE_BUFFER_DAYS),
        universe=args.universe,
        parameters={
            "candidate_days_csv": str(Path(args.candidate_days).resolve()),
            "candidate_days_sha256": sha256(args.candidate_days),
        },
        notes="MRL-FUND-05 first signal-level MLE x IRC x fundamentals run",
    )

    runner = ExperimentRunner(
        provider_bundle=bundle,
        archive_manager=ArchiveManager(MRL_ROOT / "results"),
        registry_path=MRL_ROOT / "registry" / "experiment_runs.jsonl",
        report_builder=ReportBuilder(),
    )
    result = runner.run(experiment=Fund05MleIrcFundamentalEdge_v1(),
                        config=config)

    print(f"\ncandidate-days: {result.metrics.get('candidate_days')}")
    print(f"coverage base:  {result.metrics.get('coverage_pct_base')}")
    for v in VARIANTS:
        print(f"  {v}: {result.metrics.get(f'status_{v}'):12s} "
              f"med20={result.metrics.get(f'median_20d_{v}')} "
              f"spyrel20={result.metrics.get(f'spyrel_median_20d_{v}')}")
    overall = result.metrics.get("overall_result")
    print(f"RESULT: {overall}")
    return 0 if overall == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
