import json
import journal
from journal import JournalWriter, paths

D = "2026-07-15"


def test_events_are_append_only_valid_jsonl(tmp_path):
    w = JournalWriter(mode="replay", strategy_id="MLE-PAPER-01", base_dir=tmp_path)
    w.write_event("WARNING", "signal_source", "MISSING_PRICE",
                  business_date=D, ticker="XYZ",
                  message="Missing open price, BUY skipped")
    w.write_event("INFO", "runner", "RUN_COMPLETE", business_date=D)
    w.close()

    path = paths.events_file(tmp_path, "replay", "2026-07")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        row = json.loads(line)  # each line must be valid JSON
        assert row["severity"] in ("WARNING", "INFO")
        assert row["component"]
        assert row["event_type"]


def test_events_append_across_writers_same_month(tmp_path):
    for _ in range(2):
        w = JournalWriter(mode="replay", strategy_id="MLE-PAPER-01",
                          base_dir=tmp_path)
        w.write_event("INFO", "runner", "PING", business_date=D)
        w.close()
    path = paths.events_file(tmp_path, "replay", "2026-07")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # appended, not overwritten
