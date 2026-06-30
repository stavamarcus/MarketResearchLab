"""
run_mle_rank_cumulative.py — MLE Rank Cumulative Thresholds

Spusteni:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_mle_rank_cumulative.py
"""

from __future__ import annotations
import sys, json
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from src.infrastructure.archive_manager import ArchiveManager
from src.infrastructure.logging_manager import configure_logging, get_logger
from src.providers.mdsm_providers import (
    MDSMMetadataProvider, MDSMPriceProvider,
    MDSMSignalProvider, MDSMUniverseProvider,
)
from src.providers.provider_factory import ProviderBundle
from src.context.context_builder import ContextBuilder
from src.core.experiment_runner import ExperimentRunner
from src.core.experiment_config import ExperimentConfig
from src.core.experiment_registry import ExperimentRegistry
from src.reports.report_builder import ReportBuilder
from experiments.edge_validation.mle_rank_cumulative_v1 import MLERankCumulative_v1

configure_logging()
logger = get_logger("mrl.run")

MDSM_PRICES   = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\prices")
MDSM_UNIVERSE = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\universe")
MDSM_METADATA = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\metadata")
MLE_ARCHIVE   = Path(r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive")

SPY_CONID = 756733
DATE_FROM = date(2025, 7, 9)
DATE_TO   = date(2026, 6, 29)

spy_path = MDSM_PRICES / f"{SPY_CONID}_D1.parquet"
spy_df   = pd.read_parquet(spy_path)
spy_df.index = pd.to_datetime(spy_df.index)
if spy_df.index.tz is not None:
    spy_df.index = spy_df.index.tz_localize(None)
spy_df = spy_df[(spy_df.index >= pd.Timestamp(DATE_FROM)) & (spy_df.index <= pd.Timestamp(DATE_TO))]
logger.info(f"SPY nacteno: {len(spy_df)} radku")

bundle = ProviderBundle(
    price    = MDSMPriceProvider(prices_dir=MDSM_PRICES),
    universe = MDSMUniverseProvider(universe_dir=MDSM_UNIVERSE),
    signal   = MDSMSignalProvider(module_paths={
        "MLE": MLE_ARCHIVE,
    }),
    metadata = MDSMMetadataProvider(
        metadata_dir=MDSM_METADATA,
        prices_dir=MDSM_PRICES,
    ),
    source_name="mdsm",
)

archive_mgr    = ArchiveManager(results_root=Path("results"))
registry_path  = Path("registry/experiment_runs.jsonl")
report_builder = ReportBuilder()

runner = ExperimentRunner(
    provider_bundle = bundle,
    archive_manager = archive_mgr,
    registry_path   = registry_path,
    report_builder  = report_builder,
)

config = ExperimentConfig(
    date_from  = DATE_FROM,
    date_to    = DATE_TO,
    universe   = "sp500_rank_calendar",
    parameters = {},
    notes      = "RP-0007 doplnek: MLE Rank Cumulative Thresholds",
)

_original_build = ContextBuilder.build

def _build_with_spy(self, run_id, definition, config):
    context = _original_build(self, run_id, definition, config)
    if SPY_CONID not in context.prices:
        context.prices[SPY_CONID] = spy_df
        logger.info(f"SPY (conid={SPY_CONID}) pridan do context.prices")
    return context

ContextBuilder.build = _build_with_spy

logger.info("=== MLE Rank Cumulative (RP-0007 doplnek) ===")
result = runner.run(experiment=MLERankCumulative_v1(), config=config)

ContextBuilder.build = _original_build

print("\n" + "="*65)
print(result.summary)
print("="*65)
print(f"\nRun ID:      {result.run_id}")
print(f"Result hash: {result.result_hash[:20]}...")

registry = ExperimentRegistry(registry_path)
s = registry.summary()
print(f"\nRegistry: {s['total_runs']} behu | {s['experiments']}")

run_path = None
for line in registry_path.read_text().splitlines():
    r = json.loads(line)
    if r["run_id"] == result.run_id:
        run_path = Path(r["run_path"])
        break

if run_path and run_path.exists():
    print(f"\nArchivace ({run_path}):")
    for f in sorted(run_path.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(run_path)}  ({f.stat().st_size:,} B)")
