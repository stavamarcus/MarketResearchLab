"""MRL-FUND-05 testy — variant logika, PIT, dependence, STOP pravidla.

Syntetická data; adapter-dependent testy SKIP bez adapteru.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import experiments.fundamental_validation.fund05_mle_irc_fundamental_edge_v1 as f5
import run_fundamental_coverage_audit as audit_mod
from conftest import requires_adapter

MRL_ROOT = Path(__file__).resolve().parent.parent
CAND = date(2026, 6, 1)


def rows_df(**overrides):
    base = dict(
        conid=[1, 2, 3, 4],
        candidate_date=[CAND] * 4,
        coverage_status=["OK"] * 4,
        netinc=[1.0, -1.0, 1.0, np.nan],
        fcf=[1.0, 1.0, 1.0, 1.0],
        roe=[0.20, 0.10, 0.20, 0.20],
        de=[0.5, 3.0, 0.5, 0.5],
        equity=[10.0, 10.0, -5.0, 10.0],
        revenue=[100.0] * 4,
        revenue_yoy=[0.10, 0.10, np.nan, 0.10],
        ticker=["AA", "BB", "CC", "DD"],
    )
    base.update(overrides)
    return pd.DataFrame(base)


# ------------------------------------------------- 1. price-derived reject

@requires_adapter
def test_forbidden_price_derived_fields_rejected():
    from src.providers.sharadar_fundamental_source import (
        FundamentalSourceError, MRLSharadarFundamentalSource,
    )
    for bad in ("marketcap", "pe", "ps", "pb"):
        with pytest.raises(FundamentalSourceError):
            MRLSharadarFundamentalSource(SimpleNamespace(),
                                         SimpleNamespace(),
                                         fields=("revenue", bad))


# --------------------------------------------- 2. revenue_yoy PIT-safe

def test_revenue_yoy_uses_pit_safe_prior_lookup():
    base = pd.DataFrame({"revenue": [110.0, 110.0, 110.0, np.nan],
                         "coverage_status": ["OK"] * 4})
    prior = pd.DataFrame({
        "revenue": [100.0, np.nan, 100.0, 100.0],
        "coverage_status": ["OK", "OK", "EXCLUDED", "OK"],
    })
    yoy = f5.compute_revenue_yoy(base, prior)
    assert round(float(yoy.iloc[0]), 4) == 0.10   # OK/OK
    assert np.isnan(yoy.iloc[1])                  # prior NaN
    assert np.isnan(yoy.iloc[2])                  # prior EXCLUDED (NO_SF1_ASOF)
    assert np.isnan(yoy.iloc[3])                  # base NaN


def test_prior_lookup_dates_are_earlier():
    """Prior request = candidate_date - 365 (přísnější PIT)."""
    d = CAND - timedelta(days=f5.PRIOR_YEAR_DAYS)
    assert d < CAND
    src = (MRL_ROOT / "experiments" / "fundamental_validation"
           / "fund05_mle_irc_fundamental_edge_v1.py").read_text(
        encoding="utf-8")
    assert "PRIOR_YEAR_DAYS" in src and "- timedelta(days=PRIOR_YEAR_DAYS" in src


# ----------------------------- 3. forward returns nejsou ve features

def test_forward_return_columns_not_in_feature_construction():
    """Membership funkce nesmí přijímat/číst return sloupce."""
    rows = rows_df()
    m, _ = f5.variant_membership(rows)
    assert set(m.columns) == set(f5.VARIANTS)
    # statická kontrola: variant_membership nečte ret_/spyrel_/forward
    import inspect
    code = inspect.getsource(f5.variant_membership)
    for marker in ("ret_fwd", "spyrel", "forward_return", "future_return"):
        assert marker not in code


# ------------------------------------------- 4. membership drží identitu

def test_variant_membership_preserves_candidate_day_ids():
    rows = rows_df()
    m, _ = f5.variant_membership(rows)
    assert list(m.index) == list(rows.index)
    assert len(m) == len(rows)
    assert m["A"].all()


# --------------------------------------------- 5. field_null_excluded

def test_missing_fields_counted_as_field_null_excluded():
    rows = rows_df()
    m, nulls = f5.variant_membership(rows)
    assert nulls["B"] == 1        # řádek 4: netinc NaN
    assert nulls["C"] == 1        # řádek 3: revenue_yoy NaN
    assert nulls["D"] == 0        # equity<=0 je evaluovatelné
    assert bool(m.loc[2, "D"]) is False   # equity -5 -> ne member, ne null
    assert bool(m.loc[2, "E"]) is False   # equity<=0 -> exclude


# ------------------------------------------------ 6. composite policy

def test_composite_requires_all_five_components_evaluable():
    rows = rows_df()
    m, nulls = f5.variant_membership(rows)
    # řádek 3 (yoy NaN) a řádek 4 (netinc NaN) -> F null-excluded, ne false
    assert nulls["F"] == 2
    assert bool(m.loc[2, "F"]) is False and bool(m.loc[3, "F"]) is False
    # řádek 1: 5/5 splněno -> member
    assert bool(m.loc[0, "F"]) is True
    # řádek 2: netinc<0, de>2 -> 3/5 -> ne member (evaluovatelný)
    assert bool(m.loc[1, "F"]) is False


def test_composite_four_of_five_passes():
    rows = rows_df(netinc=[-1.0], fcf=[1.0], roe=[0.2], de=[0.5],
                   equity=[10.0], revenue_yoy=[0.1], conid=[1],
                   candidate_date=[CAND], coverage_status=["OK"],
                   revenue=[100.0], ticker=["AA"])
    m, nulls = f5.variant_membership(rows)
    assert bool(m.loc[0, "F"]) is True    # 4/5 (netinc fail)
    assert nulls["F"] == 0


# ---------------------------------------------- 7. non-overlap výběr

def test_nonoverlap_selection_deterministic_not_return_based():
    dates = [CAND + timedelta(days=i) for i in range(0, 60, 2)]  # 30 dní
    rows = pd.DataFrame({
        "conid": [1] * 30,
        "candidate_date": dates,
    })
    idx1 = f5.nonoverlap_selection(rows, gap=20)
    idx2 = f5.nonoverlap_selection(rows, gap=20)
    assert list(idx1) == list(idx2)                    # deterministické
    assert list(idx1) == [0, 20]                       # první výskyt + gap
    import inspect
    code = inspect.getsource(f5.nonoverlap_selection)
    # žádná return-based selekce (Python keyword `return` je legitimní)
    for marker in ("ret_fwd", "spyrel", "close", "price", "forward"):
        assert marker not in code


def test_nonoverlap_multiple_conids_independent():
    rows = pd.DataFrame({
        "conid": [1, 2, 1, 2],
        "candidate_date": [CAND, CAND, CAND + timedelta(days=1),
                           CAND + timedelta(days=1)],
    })
    idx = f5.nonoverlap_selection(rows, gap=20)
    assert len(idx) == 2                               # 1× per conid


# ------------------------------------------------------ 8-10. STOP pravidla

def _fake_source(cov_dict_base, cov_dict_prior, out_df):
    class FakeCov:
        def __init__(self, d):
            self._d = d
        def to_dict(self):
            return self._d
    calls = {"i": 0}
    covs = [FakeCov(cov_dict_base), FakeCov(cov_dict_prior)]

    class FakeSrc:
        snapshot_id = f5.EXPECTED_SNAPSHOT_ID
        snapshot_data_hash = "h"
        contract_versions = {}
        def get_fundamentals(self, df, experiment_id=None):
            c = covs[calls["i"]]; calls["i"] += 1
            return out_df.copy(), c
    return FakeSrc()


def _cov_dict(pct, unknown=0, cache=0, schema=0):
    rc = {c: 0 for c in ("IDENTITY_MISSING", "IDENTITY_AMBIGUOUS",
                         "IDENTITY_TIER_NOT_ALLOWED", "NO_SF1_ROWS",
                         "NO_SF1_ASOF_DATE", "ALIAS_PRICE_FIELD_FORBIDDEN",
                         "CACHE_MISSING", "SCHEMA_MISMATCH",
                         "UNKNOWN_ERROR")}
    rc.update({"UNKNOWN_ERROR": unknown, "CACHE_MISSING": cache,
               "SCHEMA_MISMATCH": schema})
    return {"coverage_pct": pct, "excluded_candidate_days": 0,
            "returned_snapshots": 0, "reason_code_counts": rc}


def _run_with_covs(tmp_path, base_cov, prior_cov):
    inp_path = tmp_path / "cd.csv"
    pd.DataFrame({"conid": [1], "candidate_date": ["2026-06-01"],
                  "ticker": ["AA"]}).to_csv(inp_path, index=False)
    out_df = pd.DataFrame({
        "conid": [1], "candidate_date": [CAND],
        "coverage_status": ["OK"], "reason_code": [None],
        "is_alias": [False], "staleness_days": [10],
        "netinc": [1.0], "fcf": [1.0], "roe": [0.2], "de": [0.5],
        "equity": [10.0], "revenue": [100.0], "eps": [1.0],
        "grossmargin": [0.4], "netmargin": [0.1], "debt": [1.0],
        "assets": [1.0], "sf1_datekey": [CAND], "staleness_flag": [None],
        "identity_tier": ["MATCHED_STRONG"],
    })
    exp = f5.Fund05MleIrcFundamentalEdge_v1()
    ctx = SimpleNamespace(
        config=SimpleNamespace(parameters={
            "candidate_days_csv": str(inp_path)}),
        fundamental_source=_fake_source(base_cov, prior_cov, out_df),
        # SPY přítomné (validate() ho garantuje), ale bez candidate date
        # -> entry_price_missing cesta, žádný KeyError
        prices={f5.SPY_CONID: pd.DataFrame(
            {"close": [100.0]},
            index=pd.DatetimeIndex([pd.Timestamp("2020-01-02")]))},
        universe=pd.DataFrame(),
        has_fundamental_source=lambda: True,
    )
    return exp.run(ctx)


def test_stop_if_coverage_below_95(tmp_path):
    r = _run_with_covs(tmp_path, _cov_dict(94.9), _cov_dict(100.0))
    assert r.metrics["overall_result"] == "STOP"
    assert "coverage" in r.metrics["stop_reasons"]


def test_stop_if_unknown_error(tmp_path):
    r = _run_with_covs(tmp_path, _cov_dict(100.0, unknown=1),
                       _cov_dict(100.0))
    assert r.metrics["overall_result"] == "STOP"


def test_stop_if_cache_or_schema(tmp_path):
    r = _run_with_covs(tmp_path, _cov_dict(100.0, cache=1),
                       _cov_dict(100.0))
    assert r.metrics["overall_result"] == "STOP"


def test_prior_no_asof_is_not_stop(tmp_path):
    prior = _cov_dict(60.0)
    prior["reason_code_counts"]["NO_SF1_ASOF_DATE"] = 4
    r = _run_with_covs(tmp_path, _cov_dict(100.0), prior)
    # bez cen -> entry_price_missing, ale ne STOP
    assert r.metrics["overall_result"] == "COMPLETED"


# ------------------------------------------------ 10b. latest snapshot

def test_stop_if_snapshot_latest_or_unpinned():
    exp = f5.Fund05MleIrcFundamentalEdge_v1()
    ctx = SimpleNamespace(
        config=SimpleNamespace(parameters={"candidate_days_csv": "x.csv"}),
        fundamental_source=SimpleNamespace(snapshot_id="latest"),
        prices={f5.SPY_CONID: pd.DataFrame({"close": [1.0]})},
        has_fundamental_source=lambda: True,
    )
    v = exp.validate(ctx)
    assert not v.is_valid()
    ctx.fundamental_source = SimpleNamespace(snapshot_id="sf1art_other")
    assert not exp.validate(ctx).is_valid()


# --------------------------------------- 11. SPY-relative jen sekundární

def test_spy_relative_secondary_only():
    """Acceptance logika (variant_status) používá raw median/hit, ne spyrel."""
    import inspect
    code = inspect.getsource(f5.variant_status)
    assert "spyrel" not in code
    # spyrel se ale počítá (sekundární diagnostika)
    rows = pd.DataFrame({"conid": [1], "candidate_date": [CAND]})
    idx = pd.date_range("2026-05-25", periods=40, freq="D")
    pdf = pd.DataFrame({"close": np.linspace(100, 110, 40)}, index=idx)
    spy = pd.DataFrame({"close": np.linspace(100, 105, 40)}, index=idx)
    rets, _ = f5.compute_forward_returns(rows, {1: pdf}, spy)
    assert "spyrel_fwd_20d" in rets.columns
    assert rets["spyrel_fwd_20d"].iloc[0] == pytest.approx(
        rets["ret_fwd_20d"].iloc[0]
        - ((float(spy.loc[f5.nearest_forward_ts(spy, CAND + timedelta(days=20)), 'close'])
            / float(spy.loc[pd.Timestamp(CAND), 'close']) - 1) * 100), abs=1e-3)


# ------------------------------------------------- 12-14. izolace importů

FUND05_FILES = (
    MRL_ROOT / "experiments" / "fundamental_validation"
    / "fund05_mle_irc_fundamental_edge_v1.py",
    MRL_ROOT / "run_fundamental_edge_protocol.py",
)


def test_no_api_http_imports():
    for p in FUND05_FILES:
        text = p.read_text(encoding="utf-8")
        for m in ("import requests", "import urllib", "import httpx",
                  "import aiohttp", "import http.client",
                  "import nasdaqdatalink"):
            assert m not in text, f"{p.name}: {m}"


def test_no_mdsm_lite_or_resolver_imports():
    for p in FUND05_FILES:
        for i, line in enumerate(
                p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            for m in ("import mdsm", "from mdsm", "import access_layer",
                      "from access_layer", "import decision_resolver",
                      "from decision_resolver"):
                assert m not in code, f"{p.name}:{i}: {m}"


# --------------------------------------------- 15. adapter unchanged proxy

@requires_adapter
def test_adapter_runtime_unchanged_proxy():
    import sharadar_mdsm_adapter
    from sharadar_mdsm_adapter.exceptions import REASON_CODES
    assert sharadar_mdsm_adapter.__version__ == "1.0.0"
    assert len(REASON_CODES) == 9 and "UNKNOWN_ERROR" not in REASON_CODES


# ------------------------------------------------- statusy (protokol §5)

def test_variant_status_rules():
    base = {"n_ret_20d": 100, "median_20d": 1.0, "hit_20d": 0.55,
            "median_5d": 0.2, "median_10d": 0.5}
    good = {"n_ret_20d": 50, "median_20d": 1.5, "hit_20d": 0.56,
            "median_5d": 0.3, "median_10d": 0.4}
    nn_a = {"median_20d": 1.0, "hit_20d": 0.55, "n": 40}
    nn_v = {"median_20d": 1.4, "hit_20d": 0.56, "n": 20}
    st, _ = f5.variant_status("B", good, base, nn_v, nn_a)
    assert st == "PASS"
    small = dict(good, n_ret_20d=10)
    st, _ = f5.variant_status("B", small, base, nn_v, nn_a)
    assert st == "INCONCLUSIVE"
    worse = dict(good, median_20d=0.5)
    st, _ = f5.variant_status("B", worse, base, nn_v, nn_a)
    assert st == "FAIL"
    contradicted = dict(good)
    nn_bad = {"median_20d": 0.2, "hit_20d": 0.4, "n": 20}
    st, _ = f5.variant_status("B", contradicted, base, nn_bad, nn_a)
    assert st == "FAIL"                        # non-overlap v rozporu
