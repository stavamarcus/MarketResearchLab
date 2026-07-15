"""
run_cap02_performance.py — tenký launcher CAP-02 přes ExperimentRunner
(registry/archiv/report governance, neobchází).

Vstup: CAP-01B market_cap_output.csv (bucket per candidate-day).
Spuštění (Windows):
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    conda activate market_research_lab
    python run_cap02_performance.py --market-cap results\\diagnostics\\cap01_market_cap_coverage_<run_id>\\market_cap_output.csv

Exit: 0 COMPLETED, 1 jiný RESULT, 2 setup.
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
from experiments.cap_validation.cap02_market_cap_performance_v1 import (      # noqa: E402
    Cap02MarketCapPerformance_v1, VALID_BUCKETS, ALL_BUCKETS,
)
import pandas as pd                                                          # noqa: E402

configure_logging()
logger = get_logger("mrl.cap02.launcher")
DATE_BUFFER_DAYS = 35


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CAP-02 performance run")
    ap.add_argument("--market-cap", required=True,
                    help="CAP-01B market_cap_output.csv")
    ap.add_argument("--config-dir", default=str(MRL_ROOT / "config"))
    ap.add_argument("--universe", default="sp500_rank_calendar")
    args = ap.parse_args(argv)

    mc_path = Path(args.market_cap)
    if not mc_path.exists():
        print(f"SETUP FAIL: {mc_path} neexistuje")
        return 2
    df = pd.read_csv(mc_path)
    dates = pd.to_datetime(df["candidate_date"])

    factory = ProviderFactory(Path(args.config_dir))
    try:
        bundle = factory.build()
    except Exception as e:  # noqa: BLE001
        print(f"SETUP FAIL: {e}")
        return 2

    config = ExperimentConfig(
        date_from=dates.min().date(),
        date_to=dates.max().date() + timedelta(days=DATE_BUFFER_DAYS),
        universe=args.universe,
        parameters={
            "market_cap_output_csv": str(mc_path.resolve()),
            "market_cap_sha256": sha256(mc_path),
        },
        notes="MRL-CAP-02 signal-level market-cap performance",
    )
    runner = ExperimentRunner(
        provider_bundle=bundle,
        archive_manager=ArchiveManager(MRL_ROOT / "results"),
        registry_path=MRL_ROOT / "registry" / "experiment_runs.jsonl",
        report_builder=ReportBuilder(),
    )
    result = runner.run(experiment=Cap02MarketCapPerformance_v1(),
                        config=config)

    print(f"\ncandidate-days: {result.metrics.get('candidate_days')}")
    print(f"baseline median20: {result.metrics.get('baseline_median_20d')} "
          f"| hit20: {result.metrics.get('baseline_hit_20d')}")
    for b in ALL_BUCKETS:
        st = result.metrics.get(f"status_{b}")
        md = result.metrics.get(f"median_20d_{b}")
        print(f"  {b:12s}: {st:15s}" + (f" median20={md}" if md is not None
                                        else ""))
    overall = result.metrics.get("overall_result")
    print(f"RESULT: {overall}")
    return 0 if overall == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
