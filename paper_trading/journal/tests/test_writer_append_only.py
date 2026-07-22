import time
import pyarrow.parquet as pq
import journal
from journal import JournalWriter, paths
import _fixtures as fx

D = "2026-07-15"


def _write_run(tmp, run_id=None):
    w = JournalWriter(mode="replay", strategy_id="MLE-PAPER-01", base_dir=tmp,
                      run_id=run_id, source_system="REPLAY")
    w.write_daily_state(D, fx.sample_daily_state(D))
    w.close()
    return w


def test_rerun_creates_new_partition_and_leaves_old_untouched(tmp_path):
    w1 = _write_run(tmp_path)
    p1 = paths.partition_file(tmp_path, "replay", "daily_state", D, w1.run_id)
    assert p1.exists()
    original_bytes = p1.read_bytes()

    time.sleep(0.01)
    w2 = _write_run(tmp_path)  # new auto run_id
    p2 = paths.partition_file(tmp_path, "replay", "daily_state", D, w2.run_id)

    assert w1.run_id != w2.run_id
    assert p1.exists() and p2.exists()
    assert p1 != p2
    # old partition byte-for-byte unchanged
    assert p1.read_bytes() == original_bytes


def test_flush_refuses_to_overwrite_existing_partition(tmp_path):
    # force a run_id collision to prove the defensive backstop fires
    w1 = _write_run(tmp_path, run_id="FIXED")
    w2 = JournalWriter(mode="replay", strategy_id="MLE-PAPER-01",
                       base_dir=tmp_path, run_id="FIXED")
    w2.write_daily_state(D, fx.sample_daily_state(D))
    raised = False
    try:
        w2.close()
    except journal.JournalWriteError:
        raised = True
    assert raised, "collision on an existing partition must raise"
