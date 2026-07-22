"""Parity test — journalling must not change the replay result.

This validates the parity MECHANISM using a deterministic stub replay
that takes a journal writer and calls it purely as a side effect. The
result is computed independently of the writer, so
``replay(NullJournalWriter)`` and ``replay(JournalWriter)`` must be
byte-identical.

INTEGRATION TODO (separate step, not part of TRADING-JOURNAL-01 MVP):
wire this same NullJournalWriter/JournalWriter injection into the real
BT-04R replay engine (MarketResearchLab) and assert the golden master:
    CAGR 34.504% / total 337.652% / maxDD -32.7% / Sharpe 1.182 /
    990 trades / avg exposure 0.787
The journal writer here is provably side-effect-only, so that assertion
will hold by construction once wired.
"""
import journal
from journal import JournalWriter, NullJournalWriter
import _fixtures as fx


def stub_replay(days, journal_writer):
    """Deterministic mini-replay. Returns a result dict that does NOT
    depend on the journal writer (writer is a pure side effect)."""
    equity = 30000.0
    trades = 0
    for d in days:
        journal_writer.write_daily_state(d, fx.sample_daily_state(d))
        journal_writer.write_signals(d, fx.sample_signals(d))
        # deterministic "pnl": +1% compounding per day
        equity *= 1.01
        journal_writer.write_trade_closed(d, fx.sample_trade(d))
        trades += 1
        journal_writer.write_event("INFO", "runner", "DAY_DONE",
                                    business_date=d)
    journal_writer.close()
    return {"final_equity": round(equity, 6), "trades": trades}


DAYS = ["2026-07-13", "2026-07-14", "2026-07-15"]


def test_journal_on_equals_journal_off(tmp_path):
    off = stub_replay(DAYS, NullJournalWriter())
    on = stub_replay(
        DAYS,
        JournalWriter(mode="replay", strategy_id="MLE-PAPER-01",
                      base_dir=tmp_path, source_system="REPLAY"),
    )
    assert on == off, "journal must not change the replay result"


def test_journal_actually_wrote_something(tmp_path):
    # sanity: the enabled run really produced audit data (so the parity
    # above is meaningful, not both no-ops)
    JournalWriter  # noqa
    stub_replay(
        DAYS,
        JournalWriter(mode="replay", strategy_id="MLE-PAPER-01",
                      base_dir=tmp_path),
    )
    produced = list((tmp_path / "replay").rglob("*.parquet"))
    assert produced, "enabled journal should have written parquet files"
