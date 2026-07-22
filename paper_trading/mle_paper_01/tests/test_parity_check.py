"""DATA06 vs MDSM parity check tests (fake sources)."""
from mle_paper_01 import parity_check as pc
from mle_paper_01.models import RegimeState, SignalCandidate

D = "2026-07-02"


class FakeSrc:
    def __init__(self, top, regime_on, closes):
        self._top = top
        self._regime = regime_on
        self._closes = closes

    def signal_candidates(self, d):
        return [SignalCandidate(ticker=t, conid=i + 1, rank_10d=i + 1)
                for i, t in enumerate(self._top)]

    def regime_state(self, d):
        return RegimeState(date=d, regime_on=self._regime, index_level=1.0,
                           ma200=0.9)

    def closes_at(self, d, tickers):
        return {t: self._closes.get(t) for t in tickers}


TOP = ["A", "B", "C"]
PRICES = {"A": 100.0, "B": 50.0, "C": 70.0}


def test_parity_pass():
    a = FakeSrc(TOP, True, PRICES)
    b = FakeSrc(TOP, True, dict(PRICES))
    r = pc.run_parity(a, b, D, top_n=3)
    assert r.verdict == "PASS"


def test_parity_warn_price_diff():
    a = FakeSrc(TOP, True, PRICES)
    b = FakeSrc(TOP, True, {"A": 100.0, "B": 50.0, "C": 71.0})  # +1.4% on C
    r = pc.run_parity(a, b, D, top_n=3)
    assert r.verdict == "WARN" and r.price_diffs


def test_parity_warn_rank_order():
    a = FakeSrc(["A", "B", "C"], True, PRICES)
    b = FakeSrc(["B", "A", "C"], True, PRICES)   # same set, diff order
    r = pc.run_parity(a, b, D, top_n=3)
    assert r.verdict == "WARN"


def test_parity_fail_top_set():
    a = FakeSrc(["A", "B", "C"], True, PRICES)
    b = FakeSrc(["A", "B", "X"], True, {**PRICES, "X": 20.0})
    r = pc.run_parity(a, b, D, top_n=3)
    assert r.verdict == "FAIL"


def test_parity_fail_regime():
    a = FakeSrc(TOP, True, PRICES)
    b = FakeSrc(TOP, False, PRICES)
    r = pc.run_parity(a, b, D, top_n=3)
    assert r.verdict == "FAIL"
