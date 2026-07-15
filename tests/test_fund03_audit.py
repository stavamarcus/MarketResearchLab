"""MRL-FUND-03 testy — extraction + coverage audit. Syntetická data."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import run_fund03_extract_candidate_days as extract_mod
import run_fundamental_coverage_audit as audit_mod
from conftest import requires_adapter

CAND = date(2026, 6, 1)


# ------------------------------------------------------- input validation

def test_loader_rejects_forward_return_columns(tmp_path):
    p = tmp_path / "bad.csv"
    pd.DataFrame({"conid": [1], "candidate_date": ["2026-06-01"],
                  "forward_return": [0.05]}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="zakázané"):
        audit_mod.load_candidate_days(p)


@pytest.mark.parametrize("col", ["return_10d", "alpha", "hit", "pnl",
                                 "sharpe", "score_improvement"])
def test_loader_rejects_each_forbidden_column(tmp_path, col):
    p = tmp_path / "bad.csv"
    pd.DataFrame({"conid": [1], "candidate_date": ["2026-06-01"],
                  col: [1.0]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        audit_mod.load_candidate_days(p)


def test_loader_accepts_valid_input(tmp_path):
    p = tmp_path / "ok.csv"
    pd.DataFrame({"conid": [1, 2], "candidate_date": ["2026-06-01"] * 2,
                  "ticker": ["A", "B"], "mle_rank": [1, 2],
                  "irc_rank": [3, 4],
                  "source_signal_label": ["x"] * 2}).to_csv(p, index=False)
    inp = audit_mod.load_candidate_days(p)
    assert len(inp) == 2
    assert inp["candidate_date"].iloc[0] == CAND


# ---------------------------------------------------------- audit rules

def _cov(pct_ok, pct_total, unknown=0, cache=0, schema=0):
    from sharadar_mdsm_adapter.coverage import CoverageAccumulator
    cov = CoverageAccumulator("sid", {})
    for _ in range(pct_ok):
        cov.record_success(1, "d", SimpleNamespace(alias_flag=None,
                                                   staleness_flag=None))
    for _ in range(pct_total - pct_ok - unknown - cache - schema):
        cov.record_failure(1, "d", "NO_SF1_ROWS")
    for _ in range(unknown):
        cov.record_failure(1, "d", "UNKNOWN_ERROR")
    for _ in range(cache):
        cov.record_failure(1, "d", "CACHE_MISSING")
    for _ in range(schema):
        cov.record_failure(1, "d", "SCHEMA_MISMATCH")
    return cov


@requires_adapter
@pytest.mark.parametrize("ok,total,kw,expected", [
    (96, 100, {}, "PASS"),
    (95, 100, {}, "PASS"),
    (92, 100, {}, "CONDITIONAL"),
    (89, 100, {}, "STOP"),
    (99, 100, {"unknown": 1}, "STOP"),
    (99, 100, {"cache": 1}, "STOP"),
    (99, 100, {"schema": 1}, "STOP"),
])
def test_audit_result_rules(ok, total, kw, expected):
    result, _ = audit_mod.audit_result(_cov(ok, total, **kw))
    assert result == expected


@requires_adapter
def test_coverage_pct_computation():
    cov = _cov(3, 4)
    assert cov.to_dict()["coverage_pct"] == 75.0


# ------------------------------------------------------ staleness buckets

def test_staleness_buckets():
    out = pd.DataFrame({
        "coverage_status": ["OK", "OK", "OK", "OK", "EXCLUDED"],
        "staleness_days": [10, 90, 91, 200, float("nan")],
    })
    b = audit_mod.staleness_bucket_counts(out)
    assert b == {"0-90d": 2, "91-180d": 1, ">180d": 1,
                 "missing/excluded": 1}


# ------------------------------------------------------------- extraction

def _synthetic_sources(tmp_path):
    mle = pd.DataFrame({
        "date": ["2026-06-01"] * 3 + ["2026-06-02"] * 2,
        "ticker": ["AAA", "BBB", "CCC", "AAA", "ZZZ"],
        "rank_10d": [1, 5, 40, 2, 3],
        "ret_10d": [9.9] * 5,  # trailing — nesmí projít do outputu
    })
    irc = pd.DataFrame({
        "date": ["2026-06-01", "2026-06-01", "2026-06-02"],
        "lookback": [20, 20, 20],
        "rank": [1, 30, 5],
        "industry": ["Semis", "Retail", "Semis"],
    })
    uni = pd.DataFrame({
        "conid": [11, 22, 33],
        "ticker": ["AAA", "BBB", "CCC"],
        "industry": ["Semis", "Retail", "Semis"],
    })
    paths = {}
    for name, df in (("mle.csv", mle), ("irc.csv", irc), ("uni.csv", uni)):
        p = tmp_path / name
        df.to_csv(p, index=False)
        paths[name] = p
    return paths


def test_extraction_join_and_filters(tmp_path):
    p = _synthetic_sources(tmp_path)
    out, stats = extract_mod.extract(p["mle.csv"], p["irc.csv"],
                                     p["uni.csv"], 10, 10, 20)
    # AAA@0601: mle1, Semis irc1 -> IN; BBB@0601: Retail irc30 -> OUT
    # CCC@0601: rank40 -> OUT; AAA@0602: Semis irc5 -> IN
    # ZZZ@0602: unmapped ticker -> OUT (počítá se)
    assert len(out) == 2
    assert list(out["conid"]) == [11, 11]
    assert list(out["candidate_date"]) == ["2026-06-01", "2026-06-02"]
    assert stats["unmapped_rows"] == 1
    assert stats["unmapped_tickers"] == ["ZZZ"]
    assert "ret_10d" not in out.columns
    for c in audit_mod.FORBIDDEN_INPUT_COLUMNS:
        assert c not in out.columns
    assert out["source_signal_label"].iloc[0] == "MLE_TOP10xIRC_TOP10_20d"


def test_extraction_deterministic(tmp_path):
    p = _synthetic_sources(tmp_path)
    a, _ = extract_mod.extract(p["mle.csv"], p["irc.csv"], p["uni.csv"],
                               10, 10, 20)
    b, _ = extract_mod.extract(p["mle.csv"], p["irc.csv"], p["uni.csv"],
                               10, 10, 20)
    pd.testing.assert_frame_equal(a, b)


# --------------------------------------------------- E2E audit (adapter)

@requires_adapter
def test_audit_e2e_manifest_and_one_to_one(tmp_path, monkeypatch):
    from test_fund02_wiring import make_adapter_env, write_data_paths
    adapter_cfg, sid = make_adapter_env(tmp_path)
    cfg_dir = write_data_paths(tmp_path, {
        "enabled": True, "adapter_config": adapter_cfg, "snapshot_id": sid})

    inp_path = tmp_path / "cand.csv"
    pd.DataFrame({
        "conid": [265598, 265598, 999999999],
        "candidate_date": ["2026-06-01", "1990-01-01", "2026-06-01"],
        "ticker": ["AAPL", "AAPL", "XXX"],
        "source_signal_label": ["MLE_TOP10xIRC_TOP10_20d"] * 3,
    }).to_csv(inp_path, index=False)

    monkeypatch.setattr(audit_mod, "MRL_ROOT", tmp_path)
    rc = audit_mod.main(["--input", str(inp_path),
                         "--config", str(cfg_dir / "data_paths.yaml")])
    runs = list((tmp_path / "results" / "diagnostics").glob(
        "fund03_coverage_*"))
    assert len(runs) == 1
    run_dir = runs[0]
    out = pd.read_csv(run_dir / "fundamentals_output.csv")
    assert len(out) == 3                              # 1:1, EXCLUDED nedropnuty
    assert (out["coverage_status"] == "EXCLUDED").sum() == 2
    assert set(out.loc[out["coverage_status"] == "EXCLUDED",
                       "reason_code"]) == {"NO_SF1_ASOF_DATE",
                                           "IDENTITY_MISSING"}
    assert "source_signal_label" in out.columns       # echo zachováno
    manifest = json.loads((run_dir / "source_manifest.json").read_text())
    assert manifest["input"]["sha256"]
    assert manifest["snapshot"]["snapshot_id"] == sid
    assert manifest["forward_returns_used"] is False
    assert manifest["coverage"]["coverage_pct"] == 33.33
    assert rc == 1                                    # 33 % -> STOP
    summary = (run_dir / "audit_summary.md").read_text(encoding="utf-8")
    assert "RESULT: STOP" in summary
    assert "není edge test" in summary


@requires_adapter
def test_audit_rejects_latest_snapshot(tmp_path, monkeypatch):
    from test_fund02_wiring import make_adapter_env, write_data_paths
    adapter_cfg, _ = make_adapter_env(tmp_path)
    cfg_dir = write_data_paths(tmp_path, {
        "enabled": True, "adapter_config": adapter_cfg,
        "snapshot_id": "latest"})
    inp_path = tmp_path / "cand.csv"
    pd.DataFrame({"conid": [1], "candidate_date": ["2026-06-01"]}
                 ).to_csv(inp_path, index=False)
    monkeypatch.setattr(audit_mod, "MRL_ROOT", tmp_path)
    rc = audit_mod.main(["--input", str(inp_path),
                         "--config", str(cfg_dir / "data_paths.yaml")])
    assert rc == 2
