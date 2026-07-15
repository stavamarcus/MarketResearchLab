"""MRL-CAP-01A testy — read-only diagnostika. Syntetická data."""

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import run_cap01a_market_cap_diagnosis as diag
from conftest import requires_adapter

MRL_ROOT = Path(__file__).resolve().parent.parent
CAND = date(2026, 6, 1)


def test_nearest_preceding_close():
    idx = pd.to_datetime(["2026-05-28", "2026-05-29", "2026-06-01"])
    pdf = pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=idx)
    # datekey 2026-05-30 (víkend) -> nejbližší <= je 05-29
    assert diag.nearest_preceding_close(pdf, date(2026, 5, 30)) == 11.0
    assert diag.nearest_preceding_close(pdf, CAND) == 12.0
    # před rozsahem -> None
    assert diag.nearest_preceding_close(pdf, date(2026, 1, 1)) is None
    assert diag.nearest_preceding_close(pd.DataFrame(), CAND) is None


def test_summarize_and_pct_in():
    s = pd.Series([0.9, 1.0, 1.1, 2.0, np.nan])
    sm = diag.summarize(s)
    assert sm["n"] == 4 and sm["median"] == 1.05
    # ≈1 pásmo (0.9-1.1): 3 ze 4 = 75 %
    assert diag.pct_in(s, 0.9, 1.1) == 75.0
    assert diag.summarize(pd.Series([], dtype=float)) == {"n": 0}


class FakeProvider:
    def __init__(self, shares, sharefactor, anchor):
        self.shares = shares
        self.sf = sharefactor
        self.anchor = anchor

    def get_snapshot(self, conid, cand, fields=None):
        if "marketcap" in (fields or []):
            return SimpleNamespace(price_derived={"marketcap": self.anchor},
                                   fundamentals={})
        return SimpleNamespace(
            fundamentals={"sharesbas": self.shares, "sharefactor": self.sf},
            datekey=date(2026, 3, 1), staleness_days=92, price_derived={})


def _prices(close_cand, close_datekey):
    idx = pd.to_datetime(["2026-03-01", "2026-06-01"])
    return {1: pd.DataFrame({"close": [close_datekey, close_cand]},
                            index=idx)}


def _inp():
    return pd.DataFrame({"conid": [1], "candidate_date": [CAND],
                         "ticker": ["AAA"]})


@requires_adapter
def test_anchor_date_mismatch_detected():
    # vendor mc vztažen k datekey: vendor = close_datekey × shares
    # computed = close_cand × shares; price vzrostla 100->130
    # ratio_candidate = 1.3; price_ratio = 1.3; anchor_adjusted ≈ 1
    shares = 1e9
    prov = FakeProvider(shares=shares, sharefactor=1.0,
                        anchor=100.0 * shares)     # vendor k datekey
    out = diag.build_diagnostics(_inp(), _prices(130.0, 100.0),
                                 prov, has_anchor=True)
    r = out.iloc[0]
    assert r["cap01_reason"] == "SUSPECT"          # diff 30 % > 25
    assert abs(r["ratio_candidate"] - 1.3) < 1e-6
    assert abs(r["price_ratio"] - 1.3) < 1e-6
    assert abs(r["anchor_adjusted_ratio"] - 1.0) < 1e-6
    result, _ = diag.classify(out)
    assert result == "ANCHOR_DATE_MISMATCH"


@requires_adapter
def test_sharefactor_mismatch_detected():
    # vendor konzistentní s candidate, ale sharesbas potřebuje ×2 (sf=2)
    shares = 5e8
    prov = FakeProvider(shares=shares, sharefactor=2.0,
                        anchor=100.0 * shares * 2)   # vendor = 2× computed
    # price beze změny -> anchor_adjusted = ratio_candidate = 0.5
    out = diag.build_diagnostics(_inp(), _prices(100.0, 100.0),
                                 prov, has_anchor=True)
    r = out.iloc[0]
    assert r["cap01_reason"] == "SUSPECT"
    assert abs(r["ratio_sharefactor_mult"] - 1.0) < 1e-6
    result, _ = diag.classify(out)
    assert result == "FIXABLE_BY_SHAREFACTOR"


@requires_adapter
def test_one_to_one_preserved():
    inp = pd.DataFrame({"conid": [1, 2], "candidate_date": [CAND, CAND],
                        "ticker": ["A", "B"]})
    prov = FakeProvider(shares=1e9, sharefactor=1.0, anchor=1e11)
    out = diag.build_diagnostics(inp, _prices(100.0, 100.0), prov, True)
    assert len(out) == 2


def test_no_forward_returns_or_cap02():
    import io
    import tokenize
    src = (MRL_ROOT / "run_cap01a_market_cap_diagnosis.py")
    toks = tokenize.generate_tokens(
        io.StringIO(src.read_text(encoding="utf-8")).readline)
    code = " ".join(t.string for t in toks
                    if t.type not in (tokenize.COMMENT, tokenize.STRING))
    for m in ("forward_return", "future_return", "ret_fwd", "hit_rate",
              "sharpe", "cagr", "pharma"):
        assert m not in code.lower()


def test_no_api_imports():
    t = (MRL_ROOT / "run_cap01a_market_cap_diagnosis.py").read_text(
        encoding="utf-8")
    for m in ("import requests", "import urllib", "import nasdaqdatalink"):
        assert m not in t


def test_does_not_modify_cap01_production():
    """CAP-01A importuje z CAP-01, ale nepředefinovává jeho konstanty."""
    import run_cap01_market_cap_audit as cap
    assert cap.TOLERANCE_PCT == 25.0
    assert cap.THRESHOLDS == (2e9, 10e9, 50e9, 200e9)
