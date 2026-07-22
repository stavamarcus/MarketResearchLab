import pyarrow.parquet as pq
import journal
from journal import JournalWriter, schemas, paths
import _fixtures as fx

MANDATORY = set(schemas.MANDATORY_COLUMNS)


def _run(tmp):
    w = JournalWriter(mode="replay", strategy_id="MLE-PAPER-01", base_dir=tmp,
                      source_system="REPLAY")
    d = "2026-07-15"
    w.write_daily_state(d, fx.sample_daily_state(d))
    w.write_signals(d, fx.sample_signals(d))
    w.write_trade_closed(d, fx.sample_trade(d))
    w.write_event("INFO", "runner", "RUN_COMPLETE", business_date=d)
    w.close()
    return w, d


def test_all_tables_carry_mandatory_identifiers(tmp_path):
    w, d = _run(tmp_path)
    for table in ("daily_state", "signals", "trades"):
        p = paths.partition_file(tmp_path, "replay", table, d, w.run_id)
        t = pq.ParquetFile(str(p)).read()  # single file; avoids hive partition inference
        cols = set(t.column_names)
        assert MANDATORY <= cols
        col = t.to_pylist()
        for row in col:
            for k in MANDATORY:
                assert row[k], f"{table}.{k} must be non-empty"
            assert row["run_id"] == w.run_id
            assert row["strategy_id"] == "MLE-PAPER-01"
            assert row["schema_version"] == "1.1.0"
            assert row["mode"] == "replay"


def test_events_carry_mandatory_identifiers(tmp_path):
    import json
    w, d = _run(tmp_path)
    ym = "2026-07"
    ev_path = paths.events_file(tmp_path, "replay", ym)
    lines = ev_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    for line in lines:
        row = json.loads(line)
        for k in schemas.EVENT_MANDATORY_KEYS:
            assert k in row and row[k] != "", f"event missing {k}"
        assert row["run_id"] == w.run_id
