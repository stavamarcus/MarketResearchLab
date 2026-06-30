"""
run_mle_irc_audit.py — MLE × IRC Dependency Audit

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_mle_irc_audit.py
"""

from __future__ import annotations
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.infrastructure.archive_manager import ArchiveManager
from src.infrastructure.logging_manager import configure_logging, get_logger
from src.providers.mdsm_providers import (
    MDSMMetadataProvider, MDSMPriceProvider,
    MDSMSignalProvider, MDSMUniverseProvider,
)
from src.providers.provider_factory import ProviderBundle
from src.core.experiment_runner import ExperimentRunner
from src.core.experiment_config import ExperimentConfig
from src.core.experiment_registry import ExperimentRegistry
from src.reports.report_builder import ReportBuilder
from experiments.edge_validation.mle_irc_dependency_audit_v1 import MLEIRCDependencyAudit_v1

configure_logging()
logger = get_logger("mrl.run")

MDSM_PRICES   = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\prices")
MDSM_UNIVERSE = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\universe")
MDSM_METADATA = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\metadata")
MLE_ARCHIVE   = Path(r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive")
IRC_ARCHIVE   = Path(r"C:\Users\stava\Projects\industry_rank_calendar\output\archive")

bundle = ProviderBundle(
    price    = MDSMPriceProvider(prices_dir=MDSM_PRICES),
    universe = MDSMUniverseProvider(universe_dir=MDSM_UNIVERSE),
    signal   = MDSMSignalProvider(module_paths={
        "MLE": MLE_ARCHIVE,
        "IRC": IRC_ARCHIVE,
    }),
    metadata = MDSMMetadataProvider(
        metadata_dir=MDSM_METADATA,
        prices_dir=MDSM_PRICES,
    ),
    source_name="mdsm",
)

runner = ExperimentRunner(
    provider_bundle = bundle,
    archive_manager = ArchiveManager(results_root=Path("results")),
    registry_path   = Path("registry/experiment_runs.jsonl"),
    report_builder  = ReportBuilder(),
)

config = ExperimentConfig(
    date_from  = date(2025, 7, 9),
    date_to    = date(2026, 6, 29),
    universe   = "sp500_rank_calendar",
    parameters = {},
    notes      = "MLE x IRC Dependency Audit — first run",
)

logger.info("=== MLE x IRC Dependency Audit ===")
result = runner.run(experiment=MLEIRCDependencyAudit_v1(), config=config)

print("\n" + "="*65)
print(result.summary)
print("="*65)
print(f"\nRun ID:      {result.run_id}")
print(f"Result hash: {result.result_hash[:20]}...")

registry = ExperimentRegistry(Path("registry/experiment_runs.jsonl"))
s = registry.summary()
print(f"\nRegistry: {s['total_runs']} běh(ů) | {s['experiments']}")

run_path = Path("results") / "MLEIRCDependencyAudit" / "1.0.0" / result.run_id
print(f"\nArchivace:")
for f in sorted(run_path.rglob("*")):
    if f.is_file():
        print(f"  {f.relative_to(run_path)}  ({f.stat().st_size:,} B)")
