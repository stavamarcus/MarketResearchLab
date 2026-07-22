"""MdsmPriceSource + freshness gate tests (fake access layer, no live IBKR)."""
import ast
import csv
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from mle_paper_01 import mdsm_access
from mle_paper_01.data_source import MdsmPriceSource, DataSourceProfile
from mle_paper_01.signal_source import load_universe

DATES = pd.bdate_range("2026-05-01", "2026-07-16")


def _frame(base):
    return pd.DataFrame({"open": [base] * len(DATES),
                         "close": [base + 1] * len(DATES)}, index=DATES)


class FakeLayer:
    def __init__(self, frames):
        self.frames = frames

    def get_historical(self, conid, start, end, timeframe="D1",
                       cache_only=True):
        if conid not in self.frames:
            raise RuntimeError("cache miss")
        df = self.frames[conid]
        return df.loc[str(start):str(end)]


class FakeMeta:
    def __init__(self, cov):
        self.cov = cov     # {conid: (start, end, is_valid)}

    def read(self, conid, timeframe="D1"):
        if conid not in self.cov:
            return None
        s, e, v = self.cov[conid]
        return {"conid": conid, "timeframe": "D1", "start_date": s,
                "end_date": e, "is_valid": v}


def _universe(tmp, rows):
    p = tmp / "universe.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["conid", "ticker", "active_flag", "industry", "sector"])
        for cid, tk in rows:
            w.writerow([cid, tk, "1", "Ind", "Sec"])
    return p


def test_bridge_builds_matrix_shape():
    instruments = [{"conid": 1, "ticker": "AAA"},
                   {"conid": 2, "ticker": "BBB"}]
    layer = FakeLayer({1: _frame(100), 2: _frame(50)})
    meta = FakeMeta({1: ("2026-05-01", "2026-07-16", True),
                     2: ("2026-05-01", "2026-07-16", True)})
    close_m, open_m, cov, status = mdsm_access.load_price_matrices_via_access(
        layer, meta, instruments)
    assert list(close_m.columns) == ["AAA", "BBB"]
    assert close_m.shape[0] == len(DATES)
    assert cov["AAA"] == date(2026, 7, 16)
    assert close_m["AAA"].iloc[0] == 101   # close = base+1


def test_bridge_excludes_missing_or_invalid():
    instruments = [{"conid": 1, "ticker": "AAA"},
                   {"conid": 2, "ticker": "BBB"},   # no frame -> cache miss
                   {"conid": 3, "ticker": "CCC"}]   # invalid metadata
    layer = FakeLayer({1: _frame(100), 3: _frame(70)})
    meta = FakeMeta({1: ("2026-05-01", "2026-07-16", True),
                     3: ("2026-05-01", "2026-07-16", False)})
    close_m, open_m, cov, status = mdsm_access.load_price_matrices_via_access(
        layer, meta, instruments)
    assert list(close_m.columns) == ["AAA"]
    assert status["BBB"]["has_data"] is False and status["CCC"]["is_valid"] is False
    assert "BBB" not in cov and "CCC" not in cov


def _mdsm(tmp, universe_rows, frames, cov):
    up = _universe(tmp, universe_rows)
    layer = FakeLayer(frames)
    meta = FakeMeta(cov)
    return MdsmPriceSource(universe_path=str(up), mdsm_project_path="X",
                           mle_project_path="Y", access=(layer, meta),
                           ranker=lambda *a, **k: None)


def test_freshness_pass(tmp_path):
    src = _mdsm(tmp_path, [(1, "AAA"), (2, "BBB")],
               {1: _frame(100), 2: _frame(50)},
               {1: ("2026-05-01", "2026-07-16", True),
                2: ("2026-05-01", "2026-07-16", True)})
    fr = src.freshness_report("2026-07-16")
    assert fr.verdict == "PASS" and fr.passed and fr.fresh_count == 2


def test_freshness_pass_with_warnings_outside_plan(tmp_path):
    # BBB stale, CCC invalid, but neither is in the plan -> PASS_WITH_WARNINGS
    src = _mdsm(tmp_path, [(1, "AAA"), (2, "BBB"), (3, "CCC")],
               {1: _frame(100), 2: _frame(50)},
               {1: ("2026-05-01", "2026-07-16", True),
                2: ("2026-05-01", "2026-07-10", True),
                3: ("2026-05-01", "2026-07-16", False)})
    fr = src.freshness_report("2026-07-16", buy_tickers=["AAA"], exit_tickers=[])
    assert fr.verdict == "PASS_WITH_WARNINGS" and fr.passed
    assert len(fr.stale) == 1 and len(fr.invalid) == 1
    assert fr.stale[0]["ticker"] == "BBB" and fr.stale[0]["reason"] == "stale"


def test_freshness_fail_when_traded_ticker_stale(tmp_path):
    # BBB is stale AND in the BUY plan -> HARD FAIL
    src = _mdsm(tmp_path, [(1, "AAA"), (2, "BBB")],
               {1: _frame(100), 2: _frame(50)},
               {1: ("2026-05-01", "2026-07-16", True),
                2: ("2026-05-01", "2026-07-10", True)})
    fr = src.freshness_report("2026-07-16", buy_tickers=["BBB"])
    assert fr.verdict == "FAIL" and not fr.passed
    assert "BBB" in fr.traded_violations


def test_freshness_fail_systemic_over_threshold(tmp_path):
    # >25 stale names -> systemic FAIL (GDU likely did not run)
    rows = [(i, f"T{i}") for i in range(1, 31)]        # 30 tickers
    frames = {i: _frame(100 + i) for i, _ in rows}
    cov = {i: ("2026-05-01", "2026-06-01", True) for i, _ in rows}  # all stale
    src = _mdsm(tmp_path, rows, frames, cov)
    fr = src.freshness_report("2026-07-16")
    assert fr.verdict == "FAIL" and not fr.passed
    assert fr.bad_count() > 25


def test_runner_refuses_paper_manual_when_stale(tmp_path):
    """daily_runner STOPs (no plan) when MDSM freshness FAILs."""
    from mle_paper_01.daily_runner import DailyOfflineRunner, RunStatus
    from mle_paper_01.runner_config import RunnerConfig
    from mle_paper_01.data_source import DataSourceProfile as DP
    from journal import NullJournalWriter

    class StaleMdsm:
        profile = DP.MDSM

        def metadata(self):
            return {"data_source": "MDSM"}

        def freshness_report(self, expected, buy_tickers=None,
                             exit_tickers=None):
            class R:
                verdict = "FAIL"
                passed = False
                fresh_count = 0
                universe_size = 30
                effective_last_session = "2026-06-01"
                reason = "30 stale > 25 - GDU likely did not run"
                def bad_count(self):
                    return 30
            return R()

    cfg = RunnerConfig(state_path=str(tmp_path / "s.json"),
                       order_plans_dir=str(tmp_path / "p"),
                       reports_dir=str(tmp_path / "r"),
                       journal_base_dir=str(tmp_path / "j"))
    runner = DailyOfflineRunner(
        cfg, StaleMdsm(), next_session_fn=lambda d: "2026-07-17",
        journal_factory=lambda c: NullJournalWriter())
    res = runner.run("2026-07-16")     # explicit D -> no calendar dependency
    assert res.status == RunStatus.STOPPED
    assert not (tmp_path / "s.json").exists()   # no state / plan written


def test_no_direct_parquet_in_bridge_and_runner():
    """mdsm_access + daily_runner must not read parquet directly."""
    import mle_paper_01.mdsm_access as m
    import mle_paper_01.daily_runner as dr
    forbidden_calls = {"read_parquet", "ParquetFile"}
    for mod in (m, dr):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "_D1.parquet" not in src, f"{mod.__file__} references parquet path"
        assert "cache/prices" not in src and "cache\\prices" not in src
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func,
                                                         ast.Attribute):
                assert node.func.attr not in forbidden_calls, \
                    f"{mod.__file__} calls {node.func.attr}"


def test_isolated_src_avoids_collision(tmp_path):
    """Both MLE and MDSM-Lite use top package 'src'; isolation must let each
    import its own without clobbering the other."""
    import sys
    import importlib
    from mle_paper_01.mdsm_access import _isolated_src

    # start from a clean slate: a real 'src' (e.g. the MLE engine) may already
    # be cached from an earlier test; save and remove it, restore at the end.
    preexisting = {k: sys.modules[k] for k in list(sys.modules)
                   if k == "src" or k.startswith("src.")}
    for k in preexisting:
        del sys.modules[k]

    mle = tmp_path / "mle"; (mle / "src").mkdir(parents=True)
    (mle / "src" / "__init__.py").write_text("")
    (mle / "src" / "engines.py").write_text("MARKER = 'MLE'\n")
    mdsm = tmp_path / "mdsm"; (mdsm / "src").mkdir(parents=True)
    (mdsm / "src" / "__init__.py").write_text("")
    (mdsm / "src" / "access.py").write_text("MARKER = 'MDSM'\n")

    sys.path.insert(0, str(mle))
    try:
        eng = importlib.import_module("src.engines")
        assert eng.MARKER == "MLE"

        with _isolated_src(str(mdsm)):
            acc = importlib.import_module("src.access")
            assert acc.MARKER == "MDSM"   # MDSM src resolved despite MLE loaded

        # after isolation, MLE src is restored and usable
        eng2 = importlib.import_module("src.engines")
        assert eng2.MARKER == "MLE"
    finally:
        sys.path.remove(str(mle))
        for k in [k for k in list(sys.modules)
                  if k == "src" or k.startswith("src.")]:
            del sys.modules[k]
        sys.modules.update(preexisting)
