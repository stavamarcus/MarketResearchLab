"""Test doubles for the Daily Offline Runner. Fakes are allowed ONLY in tests
(architect). They stand in for the DATA boundary; the runner still calls the
REAL frozen strategy modules (resolve, mark_to_market, write_orders_plan)."""
from mle_paper_01.data_source import DataSourceProfile
from mle_paper_01.models import RegimeState, SignalCandidate


class FakePriceDataSource:
    profile = DataSourceProfile.DATA06

    def __init__(self, last_session, candidates, regime, closes):
        self._last = last_session
        self._candidates = list(candidates)
        self._regime = regime
        self._closes = dict(closes)

    def last_completed_session(self):
        return self._last

    def signal_candidates(self, business_date):
        return list(self._candidates)

    def regime_state(self, business_date):
        return self._regime

    def closes_at(self, business_date, tickers):
        return {t: self._closes.get(t) for t in tickers}

    def metadata(self):
        return {"data_source": self.profile.value,
                "universe_path": "FAKE_UNIVERSE",
                "price_view_dir": "FAKE_VIEW",
                "mle_project_path": "FAKE_MLE"}


def cand(ticker, conid, rank):
    return SignalCandidate(ticker=ticker, conid=conid, rank_10d=rank)


def regime_on(date):
    return RegimeState(date=date, regime_on=True, index_level=5200.0,
                       ma200=5000.0, valid_constituents=500)


def regime_off(date):
    return RegimeState(date=date, regime_on=False, index_level=4800.0,
                       ma200=5000.0, valid_constituents=500)


def make_next_session(mapping):
    def _next(d):
        return mapping[d]
    return _next
