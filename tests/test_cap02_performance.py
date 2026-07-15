"""MRL-CAP-02 testy — per-bucket performance. Syntetická data."""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import experiments.cap_validation.cap02_market_cap_performance_v1 as c2

MRL_ROOT = Path(__file__).resolve().parent.parent
CAND = date(2026, 6, 1)


def test_nonoverlap_deterministic():
    dates = [CAND + timedelta(days=i) for i in range(0, 60, 2)]
    rows = pd.DataFrame({"conid": [1] * 30, "candidate_date": dates})
    a = c2.nonoverlap_selection(rows, gap=20)
    b = c2.nonoverlap_selection(rows, gap=20)
    assert list(a) == list(b) == [0, 20]


def test_group_stats_basic():
    rets = pd.DataFrame({
        "ret_fwd_5d": [1.0, 2.0, 3.0], "ret_fwd_10d": [1.0, 2.0, 3.0],
        "ret_fwd_20d": [1.0, -2.0, 3.0],
        "spyrel_fwd_5d": [0.5, 0.5, 0.5], "spyrel_fwd_10d": [0.5] * 3,
        "spyrel_fwd_20d": [0.5, 0.5, 0.5]})
    mask = pd.Series([True, True, True])
    st = c2.group_stats(rets, mask)
    assert st["n_ret_20d"] == 3
    assert st["median_20d"] == 1.0
    assert st["hit_20d"] == round(2 / 3, 4)   # 2 z 3 kladné


def test_bucket_status_inconclusive_small_n():
    st = {"n_ret_20d": 18, "median_20d": 5.0, "median_5d": 1.0,
          "median_10d": 2.0}
    base = {"median_20d": 2.0, "median_5d": 0.5, "median_10d": 1.0}
    status, _ = c2.bucket_status("Mid", st, base, {}, {}, unique_conids=7)
    assert status == "INCONCLUSIVE"


def test_bucket_status_inconclusive_few_conids():
    st = {"n_ret_20d": 100, "median_20d": 5.0, "median_5d": 1.0,
          "median_10d": 2.0}
    base = {"median_20d": 2.0, "median_5d": 0.5, "median_10d": 1.0}
    status, _ = c2.bucket_status("Mega", st, base, {"median_20d": 5.0},
                                 {"median_20d": 2.0}, unique_conids=5)
    assert status == "INCONCLUSIVE"        # <10 unique conidů


def test_bucket_status_pass_consistent():
    st = {"n_ret_20d": 100, "median_20d": 5.0, "median_5d": 1.0,
          "median_10d": 2.0}
    base = {"median_20d": 2.0, "median_5d": 0.5, "median_10d": 1.0}
    nono_b = {"median_20d": 4.5}
    nono_all = {"median_20d": 2.0}
    status, _ = c2.bucket_status("Mega", st, base, nono_b, nono_all,
                                 unique_conids=25)
    assert status == "PASS"     # nad baseline, 5/10D konzist, non-overlap ok


def test_bucket_status_fail_non_overlap_contradiction():
    st = {"n_ret_20d": 100, "median_20d": 5.0, "median_5d": 1.0,
          "median_10d": 2.0}
    base = {"median_20d": 2.0, "median_5d": 0.5, "median_10d": 1.0}
    # non-overlap opačný směr → FAIL
    status, _ = c2.bucket_status("Mega", st, base, {"median_20d": 1.0},
                                 {"median_20d": 2.0}, unique_conids=25)
    assert status == "FAIL"


def test_bucket_status_fail_short_inconsistent():
    st = {"n_ret_20d": 100, "median_20d": 5.0, "median_5d": -1.0,
          "median_10d": -2.0}   # 20D nad, ale 5/10D pod baseline
    base = {"median_20d": 2.0, "median_5d": 0.5, "median_10d": 1.0}
    status, _ = c2.bucket_status("Mega", st, base, {"median_20d": 4.5},
                                 {"median_20d": 2.0}, unique_conids=25)
    assert status == "FAIL"


def test_small_and_unbucketed_not_interpreted():
    st = {"n_ret_20d": 0, "median_20d": None, "median_5d": None,
          "median_10d": None}
    for b in ("Small", "UNBUCKETED"):
        status, _ = c2.bucket_status(b, st, st, {}, {}, unique_conids=0)
        assert status == "NOT_INTERPRETED"


def test_no_forward_returns_in_input_guard(tmp_path):
    """market_cap loader odmítne forward-return sloupce."""
    exp = c2.Cap02MarketCapPerformance_v1()
    p = tmp_path / "mc.csv"
    pd.DataFrame({"conid": [1], "candidate_date": ["2026-06-01"],
                  "market_cap_bucket": ["Mega"],
                  "market_cap_reason_code": ["MARKET_CAP_OK"],
                  "forward_return": [1.0]}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="zakázané"):
        exp._load_market_cap(p)


def test_no_prohibited_conclusion_metrics():
    import io
    import tokenize
    src = (MRL_ROOT / "experiments" / "cap_validation"
           / "cap02_market_cap_performance_v1.py")
    toks = tokenize.generate_tokens(
        io.StringIO(src.read_text(encoding="utf-8")).readline)
    code = " ".join(t.string for t in toks
                    if t.type not in (tokenize.COMMENT, tokenize.STRING))
    for m in ("sharpe", "cagr", "drawdown", "kelly", "position_sizing"):
        assert m not in code.lower()


def test_no_api_or_resolver_imports():
    for fn in ("experiments/cap_validation/cap02_market_cap_performance_v1.py",
               "run_cap02_performance.py"):
        t = (MRL_ROOT / fn).read_text(encoding="utf-8")
        for m in ("import requests", "import urllib", "nasdaqdatalink",
                  "decision_resolver", "access_layer"):
            assert m not in t.lower(), f"{fn}: {m}"


def test_bucket_source_is_candidate_date_market_cap():
    """CAP-02 nesmí přepočítávat market cap — bere bucket z CAP-01B CSV."""
    src = (MRL_ROOT / "experiments" / "cap_validation"
           / "cap02_market_cap_performance_v1.py").read_text(encoding="utf-8")
    assert "market_cap_output_csv" in src
    assert "sharesbas" not in src        # nepočítá market cap znovu
    assert "assign_bucket" not in src     # nebucketuje znovu
