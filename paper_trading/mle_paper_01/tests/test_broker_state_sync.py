"""Tests for broker state -> PortfolioState sync (fake adapter, no live TWS)."""
from pathlib import Path

from mle_paper_01 import broker_state_sync as sync
from mle_paper_01.broker.check import CheckConfig
from mle_paper_01.broker.fake import FakeBroker
from mle_paper_01.broker.interface import PositionRow
from mle_paper_01.models import PortfolioState
from mle_paper_01.portfolio_state import load_state, save_state
from mle_paper_01.runtime_state import load_or_bootstrap

ACC = "DU1234567"
TODAY = "2026-07-17"


def cfg():
    return CheckConfig(expected_account_id=ACC, paper_prefix="DU")


def broker(**kw):
    base = dict(account_id=ACC, net_liquidation=30086.08, total_cash=30000.0)
    base.update(kw)
    return FakeBroker(**base)


def test_flat_seed_validate_only_no_write(tmp_path):
    sp = tmp_path / "state.json"
    r = sync.run_sync(broker(), cfg(), sp, TODAY, apply=False)
    assert r.passed and not r.applied
    assert r.target == {"cash": 30000.0, "equity": 30086.08, "positions": 0}
    assert not sp.exists()               # validate-only writes nothing


def test_flat_seed_apply_writes_state(tmp_path):
    sp = tmp_path / "state.json"
    r = sync.run_sync(broker(), cfg(), sp, TODAY, apply=True)
    assert r.passed and r.applied and sp.exists()
    st = load_state(sp)
    assert st.cash == 30000.0 and st.equity == 30086.08
    assert len(st.open_positions()) == 0 and st.last_updated_date == TODAY


def test_apply_over_existing_creates_backup(tmp_path):
    sp = tmp_path / "state.json"
    save_state(PortfolioState(cash=1.0, equity=1.0, last_updated_date="2026-01-01"),
               sp)
    r = sync.run_sync(broker(), cfg(), sp, TODAY, apply=True, overwrite=True)
    assert r.applied and r.backup_path
    assert any(".bak" in p.name for p in tmp_path.iterdir())
    assert load_state(sp).cash == 30000.0


def test_positions_present_hard_fail(tmp_path):
    sp = tmp_path / "state.json"
    pos = [PositionRow(symbol="AXON", conid=1, quantity=5, avg_cost=597.0)]
    r = sync.run_sync(broker(positions=pos), cfg(), sp, TODAY, apply=True)
    assert not r.passed and r.hard_fail and not r.applied
    assert not sp.exists()
    assert any("does not import broker positions" in e for e in r.errors)


def test_drift_without_overwrite_no_write(tmp_path):
    sp = tmp_path / "state.json"
    save_state(PortfolioState(cash=5000.0, equity=5000.0,
                              last_updated_date="2026-01-01"), sp)
    r = sync.run_sync(broker(), cfg(), sp, TODAY, apply=True, overwrite=False)
    assert r.drift and not r.applied
    assert load_state(sp).cash == 5000.0          # unchanged
    assert any("--overwrite" in w for w in r.warnings)


def test_drift_with_overwrite_writes(tmp_path):
    sp = tmp_path / "state.json"
    save_state(PortfolioState(cash=5000.0, equity=5000.0,
                              last_updated_date="2026-01-01"), sp)
    r = sync.run_sync(broker(), cfg(), sp, TODAY, apply=True, overwrite=True)
    assert r.applied and load_state(sp).cash == 30000.0


def test_equity_cash_mismatch_warns(tmp_path):
    sp = tmp_path / "state.json"
    r = sync.run_sync(broker(net_liquidation=40000.0, total_cash=30000.0),
                      cfg(), sp, TODAY, apply=False)
    assert any("differs from cash" in w for w in r.warnings)


def test_broker_check_fail_blocks_sync(tmp_path):
    sp = tmp_path / "state.json"
    # account mismatch -> check hard fails -> no sync
    r = sync.run_sync(broker(account_id="DU9999999"), cfg(), sp, TODAY,
                      apply=True)
    assert not r.passed and not r.applied and not sp.exists()


def test_synced_state_has_priority_over_starting_equity(tmp_path):
    """OQ-5: once synced, load_or_bootstrap uses the state, not starting_equity."""
    sp = tmp_path / "state.json"
    sync.run_sync(broker(), cfg(), sp, TODAY, apply=True)
    state, bootstrapped = load_or_bootstrap(sp, starting_equity=999999.0)
    assert not bootstrapped                 # used the synced file
    assert state.cash == 30000.0            # not the 999999 fallback
