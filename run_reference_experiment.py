"""
run_reference_experiment.py

První reálný experiment na lokálních datech.

Cíl:
    Ověřit MRL infrastrukturu end-to-end:
    1. Načtení dat z MDSM-Lite
    2. Sestavení ExperimentContext
    3. ResearchQuery API
    4. Výpočet metrik
    5. Archivace do results/
    6. Zápis do registry/experiment_runs.jsonl
    7. Generování report.md

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_reference_experiment.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Přidej projekt do path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.infrastructure.archive_manager import ArchiveManager
from src.infrastructure.logging_manager import configure_logging, get_logger
from src.providers.mdsm_providers import (
    MDSMMetadataProvider,
    MDSMPriceProvider,
    MDSMSignalProvider,
    MDSMUniverseProvider,
)
from src.providers.provider_factory import ProviderBundle
from src.core.experiment_runner import ExperimentRunner
from src.core.experiment_config import ExperimentConfig
from src.core.experiment_registry import ExperimentRegistry
from src.reports.report_builder import ReportBuilder
from experiments.edge_validation.ims_score_bucket_edge_v1 import IMSScoreBucketEdge_v1

configure_logging()
logger = get_logger("mrl.run")

# ------------------------------------------------------------------
# Cesty k datům — upravit pokud se liší
# ------------------------------------------------------------------
MDSM_PRICES   = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\prices")
MDSM_UNIVERSE = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\universe")
MDSM_METADATA = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\metadata")

IMS_ARCHIVE   = Path(r"C:\Users\stava\Projects\InstitutionalMomentumScanner\output\archive")

# ------------------------------------------------------------------
# Sestavení ProviderBundle
# ------------------------------------------------------------------
bundle = ProviderBundle(
    price    = MDSMPriceProvider(prices_dir=MDSM_PRICES),
    universe = MDSMUniverseProvider(universe_dir=MDSM_UNIVERSE),
    signal   = MDSMSignalProvider(module_paths={
        "IMS": IMS_ARCHIVE,
    }),
    metadata = MDSMMetadataProvider(
        metadata_dir=MDSM_METADATA,
        prices_dir=MDSM_PRICES,
    ),
    source_name="mdsm",
)

# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------
runner = ExperimentRunner(
    provider_bundle = bundle,
    archive_manager = ArchiveManager(results_root=Path("results")),
    registry_path   = Path("registry/experiment_runs.jsonl"),
    report_builder  = ReportBuilder(),
)

# ------------------------------------------------------------------
# Konfigurace experimentu
# ------------------------------------------------------------------
config = ExperimentConfig(
    date_from  = date(2025, 7, 9),
    date_to    = date(2026, 6, 29),
    universe   = "sp500_rank_calendar",
    parameters = {},
    notes      = "First real run on local data after GDU",
)

# ------------------------------------------------------------------
# Spuštění
# ------------------------------------------------------------------
logger.info("=== MRL — First Real Experiment Run ===")

result = runner.run(
    experiment = IMSScoreBucketEdge_v1(),
    config     = config,
)

# ------------------------------------------------------------------
# Výsledky
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print(result.summary)
print("=" * 60)

print(f"\nRun ID:      {result.run_id}")
print(f"Result hash: {result.result_hash[:20]}...")

# Ověření registry
registry = ExperimentRegistry(Path("registry/experiment_runs.jsonl"))
s = registry.summary()
print(f"\nRegistry: {s['total_runs']} běh(ů) | experimenty: {s['experiments']}")

# Ověření archivace
run_path = Path("results") / "IMSScoreBucketEdge" / "1.0.0" / result.run_id
print(f"\nArchivace ({run_path}):")
for f in sorted(run_path.rglob("*")):
    if f.is_file():
        print(f"  {f.relative_to(run_path)}  ({f.stat().st_size:,} B)")

print("\n=== DONE ===")
print("\nDalší krok:")
print("  python main.py list")
