"""
run_exit_timing_edge_v1.py — RP-0011-EXIT-TIMING

Exit-edge validace (TIME_20 baseline vs EMA20 primární, EMA10/30
sensitivity, H1b exploratorní) nad MLE×IRC kandidáty.
Wiring 1:1 podle run_entry_timing_edge_v1.py.

Integrita preregistrace: před během se ověří shoda
experiments/exit_validation/config/EXIT_001.yaml s LOCKED_PARAMS
v exit_timing_edge.py. Divergence = abort.

Spuštění:
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python run_exit_timing_edge_v1.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

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
from experiments.exit_validation.exit_timing_edge import (
    ExitTimingEdge_v1, LOCKED_PARAMS,
)

configure_logging()
logger = get_logger("mrl.run")

# ---- integrita preregistrace (YAML vs LOCKED_PARAMS) ----
PREREG = Path("experiments/exit_validation/config/EXIT_001.yaml")
prereg = yaml.safe_load(PREREG.read_text(encoding="utf-8"))
if prereg["params"] != LOCKED_PARAMS:
    diff_keys = {
        k for k in set(prereg["params"]) | set(LOCKED_PARAMS)
        if prereg["params"].get(k) != LOCKED_PARAMS.get(k)
    }
    logger.error(f"PREREGISTRACE DIVERGUJE: {sorted(diff_keys)}")
    sys.exit(1)
logger.info(f"Preregistrace OK (locked {prereg['locked']})")

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
    notes      = "RP-0011: Exit Timing Edge (pre-registered, PM approved 2026-07-02)",
)

_original_build = ContextBuilder.build

def _build_with_spy(self, run_id, definition, config):
    context = _original_build(self, run_id, definition, config)
    if SPY_CONID not in context.prices:
        context.prices[SPY_CONID] = spy_df
        logger.info(f"SPY (conid={SPY_CONID}) pridan do context.prices")
    return context

ContextBuilder.build = _build_with_spy

logger.info("=== Exit Timing Edge (RP-0011) ===")
result = runner.run(experiment=ExitTimingEdge_v1(), config=config)

print("\n" + "=" * 60)
print(result.summary)
print("=" * 60)
print(f"\nRun ID:      {result.run_id}")
print(f"Result hash: {result.result_hash[:20]}...")

m = result.metrics
print("\n--- H1a (PRIMÁRNÍ, EMA_20 vs TIME_20) ---")
print(f"N candidate-days / unique tickers : {m.get('N_candidate_days')} / {m.get('unique_tickers')}")
print(f"excluded: warmup {m.get('excluded_warmup')} | price data {m.get('excluded_price_data')}")
print(f"paired diff : {m.get('H1a_paired_diff_pp')}pp "
      f"CI[{m.get('H1a_ci_lo_pp')}, {m.get('H1a_ci_hi_pp')}]  PASS={m.get('H1a_pass')}")
print(f"baseline TIME_20 mean : {m.get('baseline_mean_pct')}%")
print("\n--- SENSITIVITY (ne hypotézy) ---")
print(f"EMA_10 : {m.get('ema_10_paired_diff_pp')}pp | early {m.get('ema_10_early_exit_pct')}% | hold {m.get('ema_10_hold_mean_d')}d")
print(f"EMA_20 : {m.get('ema_20_paired_diff_pp')}pp | early {m.get('ema_20_early_exit_pct')}% | hold {m.get('ema_20_hold_mean_d')}d")
print(f"EMA_30 : {m.get('ema_30_paired_diff_pp')}pp | early {m.get('ema_30_early_exit_pct')}% | hold {m.get('ema_30_hold_mean_d')}d")
print("\n--- H1b (EXPLORATORNÍ) ---")
print(f"N={m.get('H1b_N')} (censored excl. {m.get('H1b_censored_excluded')}) | "
      f"ret/den {m.get('H1b_ret_per_day_bps')}bps | hold mean {m.get('H1b_hold_mean_d')}d | "
      f"time-stop {m.get('H1b_timestop_pct')}%")

registry = ExperimentRegistry(Path("registry/experiment_runs.jsonl"))
s = registry.summary()
print(f"\nRegistry: {s['total_runs']} běh(ů) | experimenty: {s['experiments']}")
print("\n=== DONE ===")
