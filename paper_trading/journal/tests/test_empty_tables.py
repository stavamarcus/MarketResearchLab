import pyarrow.parquet as pq
import journal
from journal import JournalWriter, paths, schemas

D = "2026-07-15"


def test_empty_list_writes_schema_correct_empty_file(tmp_path):
    w = JournalWriter(mode="replay", strategy_id="MLE-PAPER-01", base_dir=tmp_path)
    w.write_signals(D, [])            # nothing happened today
    w.ensure_empty_tables(D, ["fills", "trades"])
    w.close()

    for table in ("signals", "fills", "trades"):
        p = paths.partition_file(tmp_path, "replay", table, D, w.run_id)
        assert p.exists(), f"{table} empty partition should still be written"
        t = pq.ParquetFile(str(p)).read()  # single file; avoids hive partition inference
        assert t.num_rows == 0
        assert t.schema == schemas.get_schema(table)
