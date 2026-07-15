"""
run_entry_timing_edge_v1.py — RP-0009-ENTRY-TIMING

Entry-edge validace (ENTRY_001/002/003) nad MLE×IRC kandidáty.
Wiring 1:1 podle run_mle_irc_rolling_validation.py (MLE + IRC providery,
ACF-007 SPY injection monkeypatch — ponechán pro konzistenci, i když
tento experiment SPY nevyžaduje).

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_entry_timing_edge_v1.py
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
from experiments.entry_validation.entry_timing_edge_v1 import EntryTimingEdge_v1

configure_logging()
logger = get_logger("mrl.run")

# ---- cesty ----
MDSM_PRICES   = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\prices")
MDSM_UNIVERSE = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\universe")
MDSM_METADATA = Path(r"C:\Users\stava\Projects\MDSM-Lite\data\cache\metadata")
MLE_ARCHIVE   = Path(r"C:\Users\stava\Projects\MarketLeadershipEngine\output\archive")
IRC_ARCHIVE   = Path(r"C:\Users\stava\Projects\industry_rank_calendar\output\archive")

SPY_CONID = 756733
DATE_FROM = date(2025, 7, 9)
DATE_TO   = date(2026, 6, 29)

# ACF-007: SPY injection (ponecháno pro konzistenci s MLE×IRC launchery)
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
        "IRC": IRC_ARCHIVE,
    }),
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
    notes      = "RP-0009: Entry Timing Edge (pre-registered ENTRY_001/002/003)",
)

_original_build = ContextBuilder.build

def _build_with_spy(self, run_id, definition, config):
    context = _original_build(self, run_id, definition, config)
    if SPY_CONID not in context.prices:
        context.prices[SPY_CONID] = spy_df
        logger.info(f"SPY (conid={SPY_CONID}) pridan do context.prices")
    return context

ContextBuilder.build = _build_with_spy

logger.info("=== Entry Timing Edge (RP-0009) ===")
result = runner.run(experiment=EntryTimingEdge_v1(), config=config)

print("\n" + "=" * 60)
print(result.summary)
print("=" * 60)
print(f"\nRun ID:      {result.run_id}")
print(f"Result hash: {result.result_hash[:20]}...")

m = result.metrics
print("\n--- HLAVNÍ METRIKY ---")
print(f"N candidate-days / unique tickers : {m.get('N_candidate_days')} / {m.get('unique_tickers')}")
print(f"ENTRY_002 matched alpha : {m.get('entry_alpha_002_pp')}pp "
      f"CI[{m.get('entry_alpha_002_ci_lo')},{m.get('entry_alpha_002_ci_hi')}] "
      f"sig={m.get('entry_alpha_002_significant')}  fill {m.get('fill_002_pct')}%")
print(f"ENTRY_003 matched alpha : {m.get('entry_alpha_003_pp')}pp "
      f"CI[{m.get('entry_alpha_003_ci_lo')},{m.get('entry_alpha_003_ci_hi')}] "
      f"sig={m.get('entry_alpha_003_significant')}  fill {m.get('fill_003_pct')}%")
print(f"strategy net  base {m.get('strategy_net_baseline_pct')}% | "
      f"002 {m.get('strategy_net_002_delta_pp')}pp | 003 {m.get('strategy_net_003_delta_pp')}pp")
print(f"skipped baseline ret  K3 {m.get('skipped_K3_baseline_ret_mean_pct')}% "
      f"vs entered S3 {m.get('entered_S3_baseline_ret_mean_pct')}%")

registry = ExperimentRegistry(Path("registry/experiment_runs.jsonl"))
s = registry.summary()
print(f"\nRegistry: {s['total_runs']} běh(ů) | experimenty: {s['experiments']}")
print("\n=== DONE ===")
