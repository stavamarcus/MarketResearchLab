import journal
from journal import JournalWriter, paths
import _fixtures as fx

D = "2026-07-15"


def test_paper_write_never_touches_live_or_replay(tmp_path):
    w = JournalWriter(mode="paper", strategy_id="MLE-PAPER-01", base_dir=tmp_path,
                      source_system="IBKR_PAPER")
    w.write_daily_state(D, fx.sample_daily_state(D))
    w.write_event("INFO", "runner", "RUN_COMPLETE", business_date=D)
    w.close()

    assert (tmp_path / "paper").exists()
    assert not (tmp_path / "live").exists()
    assert not (tmp_path / "replay").exists()

    # every produced file lives under paper/
    produced = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert produced
    for p in produced:
        assert "paper" in p.relative_to(tmp_path).parts[0]


def test_unknown_mode_rejected():
    raised = False
    try:
        JournalWriter(mode="prod", strategy_id="X", base_dir="/tmp/x")
    except ValueError:
        raised = True
    assert raised
