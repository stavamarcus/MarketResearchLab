"""
run_entry_timing_next_open_v1.py — RP-0009-ENTRY-TIMING

Čistý timing test close(D) vs open(D+1) nad MLE×IRC kandidáty.
Wiring 1:1 podle run_mle_irc_robustness_grid.py (MLE + IRC providery, SPY injection).

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_entry_timing_next_open_v1.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

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
from src.context.context_builder import ContextBuilder
from src.reports.report_builder import ReportBuilder
from experiments.entry_validation.entry_timing_next_open_v1 import EntryTimingNextOpen_v1

configure_logging()
logger = get_logger("mrl.run")

MDSM_PRICES   = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\prices")
MDSM_UNIVERSE = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\universe")
MDSM_METADATA = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\metadata")
MLE_ARCHIVE   = Path(r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive")
IRC_ARCHIVE   = Path(r"C:\Users\stava\Projects\industry_rank_calendar\output\archive")

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
    signal   = MDSMSignalProvider(module_paths={"MLE": MLE_ARCHIVE, "IRC": IRC_ARCHIVE}),
    metadata = MDSMMetadataProvider(metadata_dir=MDSM_METADATA, prices_dir=MDSM_PRICES),
    source_name="mdsm",
)

runner = ExperimentRunner(
    provider_bundle = bundle,
    archive_manager = ArchiveManager(results_root=Path("results")),
    registry_path   = Path("registry/experiment_runs.jsonl"),
    report_builder  = ReportBuilder(),
)

config = ExperimentConfig(
    date_from  = DATE_FROM,
    date_to    = DATE_TO,
    universe   = "sp500_rank_calendar",
    parameters = {},
    notes      = "RP-0009: Entry Timing Next-Open (close D vs open D+1)",
)

_original_build = ContextBuilder.build

def _build_with_spy(self, run_id, definition, config):
    context = _original_build(self, run_id, definition, config)
    if SPY_CONID not in context.prices:
        context.prices[SPY_CONID] = spy_df
        logger.info(f"SPY (conid={SPY_CONID}) pridan do context.prices")
    return context

ContextBuilder.build = _build_with_spy

logger.info("=== Entry Timing Next-Open (RP-0009) ===")
result = runner.run(experiment=EntryTimingNextOpen_v1(), config=config)
ContextBuilder.build = _original_build

print("\n" + "=" * 60)
print(result.summary)
print("=" * 60)
print(f"\nRun ID:      {result.run_id}")
print(f"Result hash: {result.result_hash[:20]}...")

m = result.metrics
print("\n--- HLAVNÍ METRIKY ---")
print(f"N / unique tickers   : {m.get('N_candidate_days')} / {m.get('unique_tickers')}")
print(f"ENTRY_001 close(D)   : mean {m.get('entry_001_mean_ret_pct')}%  win {m.get('entry_001_win_pct')}%")
print(f"ENTRY_004 open(D+1)  : mean {m.get('entry_004_mean_ret_pct')}%  win {m.get('entry_004_win_pct')}%")
print(f"matched alpha (004-001): {m.get('matched_alpha_004_minus_001_pp')}pp "
      f"CI[{m.get('matched_alpha_ci_lo')},{m.get('matched_alpha_ci_hi')}] "
      f"sig={m.get('matched_alpha_significant')}")

registry = ExperimentRegistry(Path("registry/experiment_runs.jsonl"))
s = registry.summary()
print(f"\nRegistry: {s['total_runs']} běh(ů) | experimenty: {s['experiments']}")
print("\n=== DONE ===")
