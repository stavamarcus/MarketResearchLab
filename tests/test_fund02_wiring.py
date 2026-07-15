"""MRL-FUND-02 wiring testy — bundle.fundamental → context.fundamental_source.

Syntetická data; adapter-dependent testy se SKIPnou bez adapteru.
"""

import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from conftest import requires_adapter

MRL_ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------ env buildery

def write_data_paths(tmp_path, sharadar_section=None) -> Path:
    cfg = {
        "active_provider": "mdsm",
        "mdsm": {
            "prices_dir": str(tmp_path / "prices"),
            "universe_dir": str(tmp_path / "universe"),
            "signals": {},
        },
    }
    if sharadar_section is not None:
        cfg["sharadar_fundamentals"] = sharadar_section
    d = tmp_path / "config"
    d.mkdir(exist_ok=True)
    p = d / "data_paths.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return d


def make_adapter_env(tmp_path):
    """Syntetický adapter projekt: config + identity + whitelist + snapshot."""
    from sharadar_mdsm_adapter.snapshot_hash import data_hash, schema_hash

    sid = "sf1art_wiring_000000"
    data_root = tmp_path / "adapter_data"
    row = dict(permaticker=111, dimension="ART",
               datekey=pd.Timestamp("2026-05-01"),
               calendardate=pd.Timestamp("2026-03-31"),
               lastupdated=pd.Timestamp("2026-05-01"), ticker="AAPL",
               revenue=10.0, netinc=1.0, eps=0.5, fcf=2.0, roe=0.15,
               grossmargin=0.4, netmargin=0.1, debt=5.0, de=0.5,
               assets=20.0, equity=10.0,
               sharesbas=1_000_000_000.0, sharefactor=1.0,
                marketcap=100.0, pe=15.0, ps=3.0, pb=2.0)
    df = pd.DataFrame([row])
    proc = data_root / "processed" / sid / "sf1_art_pit.parquet"
    man = data_root / "snapshots" / f"{sid}.json"
    proc.parent.mkdir(parents=True, exist_ok=True)
    man.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(proc, index=False)
    stored = pd.read_parquet(proc)
    man.write_text(json.dumps({
        "snapshot_id": sid, "created_at": "2026-07-04T00:00:00+00:00",
        "dimension": "ART",
        "row_counts": {"raw": 1, "processed": 1},
        "schema_hash": schema_hash(stored), "data_hash": data_hash(stored),
        "contract_versions": {"identity_contract_version": "v1.0",
                              "provider_contract_version": "v1.0"},
    }), encoding="utf-8")

    proj = tmp_path / "adapter_proj"
    (proj / "config").mkdir(parents=True, exist_ok=True)
    (proj / "identity").mkdir(exist_ok=True)
    (proj / "whitelist").mkdir(exist_ok=True)
    (proj / "identity" / "identity_map_resolved_v2.csv").write_text(
        "conid,permaticker,ticker,sharadar_ticker,identity_tier,alias_flag,"
        "source,evidence,identity_contract_version,identity_artifact_version\n"
        "265598,111,AAPL,AAPL,MATCHED_STRONG,,MAPPING,cusip,"
        "identity_v1.0,v2\n", encoding="utf-8")
    (proj / "whitelist" / "whitelist.csv").write_text("x", encoding="utf-8")
    (proj / "config" / "adapter_config.yaml").write_text(yaml.safe_dump({
        "data_root": data_root.as_posix(), "snapshot_id": sid,
        "identity_map_path": "identity/identity_map_resolved_v2.csv",
        "whitelist_path": "whitelist/whitelist.csv",
        "sf1_snapshot_path":
            "{data_root}/processed/{snapshot_id}/sf1_art_pit.parquet",
        "manifest_path": "{data_root}/snapshots/{snapshot_id}.json",
        "allowed_tiers": ["MATCHED_STRONG"],
        "staleness_warning_days": 180, "retention_snapshots": 3,
        "sf1_dimension": "ART"}), encoding="utf-8")
    return (proj / "config" / "adapter_config.yaml").as_posix(), sid


# ---------------------------------------------------- enabled=false / absent

def test_factory_without_section_bundle_fundamental_none(tmp_path):
    from src.providers.provider_factory import ProviderFactory
    bundle = ProviderFactory(write_data_paths(tmp_path)).build()
    assert bundle.fundamental is None


def test_factory_enabled_false_bundle_fundamental_none(tmp_path):
    from src.providers.provider_factory import ProviderFactory
    cfg_dir = write_data_paths(tmp_path, {
        "enabled": False, "adapter_config": "x", "snapshot_id": "y"})
    assert ProviderFactory(cfg_dir).build().fundamental is None
    assert ProviderFactory(cfg_dir).build_fundamental_source() is None


def test_context_builder_default_fundamental_source_none():
    """MRL bez fundamentals se nerozbije — context má None (bez adapteru)."""
    from src.context.experiment_context import ExperimentContext
    ctx = ExperimentContext(run_id="x", config=SimpleNamespace())
    assert ctx.fundamental_source is None
    assert ctx.has_fundamental_source() is False


def test_runner_wires_none_without_fundamental(tmp_path):
    """ExperimentRunner + bundle bez fundamental → builder dostane None."""
    from src.core.experiment_runner import ExperimentRunner
    from src.providers.provider_factory import ProviderFactory
    bundle = ProviderFactory(write_data_paths(tmp_path)).build()
    runner = ExperimentRunner(
        provider_bundle=bundle,
        archive_manager=SimpleNamespace(save=lambda **kw: tmp_path),
        registry_path=tmp_path / "registry.jsonl")
    assert runner._context_builder._fundamental_source is None


# ------------------------------------------------------------- enabled=true

@requires_adapter
def test_factory_enabled_true_builds_source(tmp_path):
    from src.providers.provider_factory import ProviderFactory
    adapter_cfg, sid = make_adapter_env(tmp_path)
    cfg_dir = write_data_paths(tmp_path, {
        "enabled": True, "adapter_config": adapter_cfg, "snapshot_id": sid})
    bundle = ProviderFactory(cfg_dir).build()
    assert bundle.fundamental is not None
    assert bundle.fundamental.snapshot_id == sid


@requires_adapter
def test_context_builder_injects_source_and_hashes(tmp_path):
    from src.context.context_builder import ContextBuilder
    from src.core.experiment_config import ExperimentConfig
    from src.providers.provider_factory import ProviderFactory
    from src.providers.sharadar_fundamental_source import (
        build_fundamental_source,
    )

    adapter_cfg, sid = make_adapter_env(tmp_path)
    source = build_fundamental_source(adapter_cfg, sid)

    universe_df = pd.DataFrame(
        {"ticker": ["AAPL"], "active_flag": [True]}, index=[265598])

    class FakeUniverse:
        source_name = "fake"

        def load_universe(self, universe_name="sp500"):
            return universe_df

        def load_assets(self, universe_name="sp500"):
            class AU:
                def __len__(self):
                    return 1

                def active(self):
                    return []
            return AU()

        def get_asset(self, conid, universe_name="sp500"):
            return None

    class FakePrice:
        source_name = "fake"

        def load_prices(self, conids, date_from, date_to):
            return {}

        def get_available_price_range(self, conid):
            return None

        def available_conids(self):
            return []

        def file_hash(self, conid):
            return None

    builder = ContextBuilder(price_provider=FakePrice(),
                             universe_provider=FakeUniverse(),
                             fundamental_source=source)
    definition = SimpleNamespace(required_data=[])
    config = ExperimentConfig(
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30))
    ctx = builder.build("run_x", definition, config)
    assert ctx.fundamental_source is source
    assert ctx.has_fundamental_source() is True
    assert ctx.source_hashes["sf1_snapshot_id"] == sid
    assert "sf1_data_hash" in ctx.source_hashes
    # 1:1 accounting drží i přes wired context
    out, cov = ctx.fundamental_source.get_fundamentals(pd.DataFrame(
        {"conid": [265598, 999999999],
         "candidate_date": [date(2026, 6, 1)] * 2}))
    assert len(out) == 2
    assert cov.requested_candidate_days == 2
    assert cov.returned_snapshots == 1


@requires_adapter
def test_factory_latest_without_allow_rejected(tmp_path):
    from src.providers.provider_factory import ProviderFactory
    from src.providers.sharadar_fundamental_source import (
        FundamentalSourceError,
    )
    adapter_cfg, _ = make_adapter_env(tmp_path)
    cfg_dir = write_data_paths(tmp_path, {
        "enabled": True, "adapter_config": adapter_cfg,
        "snapshot_id": "latest"})
    with pytest.raises(FundamentalSourceError):
        ProviderFactory(cfg_dir).build_fundamental_source()


def test_missing_adapter_dependency_graceful_error(monkeypatch):
    """Chybějící adapter → srozumitelná chyba s instalační instrukcí."""
    from src.providers import sharadar_fundamental_source as sfs

    blocked = [m for m in list(sys.modules)
               if m.startswith("sharadar_mdsm_adapter")]
    for m in blocked:
        monkeypatch.delitem(sys.modules, m, raising=False)

    class Blocker:
        def find_spec(self, name, path=None, target=None):
            if name.startswith("sharadar_mdsm_adapter"):
                raise ImportError("blocked for test")
            return None

    monkeypatch.setattr(sys, "meta_path", [Blocker()] + sys.meta_path)
    with pytest.raises(sfs.FundamentalSourceError) as e:
        sfs._adapter()
    assert "pip install -e" in str(e.value)
