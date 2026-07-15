"""MRL-CAP-01 testy — market cap audit. Syntetická data."""

import json
import math
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import run_cap01_market_cap_audit as cap
from conftest import requires_adapter

MRL_ROOT = Path(__file__).resolve().parent.parent
CAND = date(2026, 6, 1)


class FakeSnap(SimpleNamespace):
    pass


class FakeProvider:
    """shares/anchor per conid; simuluje adapter fail-fast."""

    def __init__(self, shares=None, anchors=None, fail=()):
        self.shares = shares or {}
        self.anchors = anchors or {}
        self.fail = set(fail)

    def get_snapshot(self, conid, cand, fields=None):
        from sharadar_mdsm_adapter.exceptions import SharadarProviderError
        if conid in self.fail:
            raise SharadarProviderError("NO_SF1_ASOF_DATE", "synth")
        if "marketcap" in (fields or []):
            if conid not in self.anchors:
                raise SharadarProviderError(
                    "ALIAS_PRICE_FIELD_FORBIDDEN", "synth alias")
            return FakeSnap(price_derived={"marketcap": self.anchors[conid]},
                            fundamentals={})
        return FakeSnap(
            fundamentals={"sharesbas": self.shares.get(conid),
                          "sharefactor": 1.0},
            datekey=pd.Timestamp("2026-05-01"), staleness_days=31,
            price_derived={})


def prices_for(conids, close=100.0, close_datekey=None):
    """Ceny k datekey (2026-05-01) i candidate (CAND). Bez close_datekey
    je datekey cena = close (žádný cenový pohyb → date-konzistentní anchor
    se rovná candidate anchor)."""
    dk_close = close if close_datekey is None else close_datekey
    idx = pd.DatetimeIndex([pd.Timestamp("2026-05-01"), pd.Timestamp(CAND)])
    return {c: pd.DataFrame({"close": [dk_close, close]}, index=idx)
            for c in conids}


def inp_for(conids):
    return pd.DataFrame({"conid": conids,
                         "candidate_date": [CAND] * len(conids),
                         "ticker": [f"T{c}" for c in conids]})


# ---------------------------------------------------------- 1. 1:1 rows

@requires_adapter
def test_output_preserves_row_count_one_to_one():
    inp = inp_for([1, 2, 3])
    prov = FakeProvider(shares={1: 1e9, 2: 1e9}, fail=(3,))
    out = cap.compute_rows(inp, prices_for([1, 2]), prov, True, False)
    assert len(out) == 3
    assert list(out["conid"]) == [1, 2, 3]


# --------------------------------------------------- 2. missing price

@requires_adapter
def test_missing_price_reason_code():
    inp = inp_for([1])
    prov = FakeProvider(shares={1: 1e9})
    out = cap.compute_rows(inp, {}, prov, True, False)
    assert out["market_cap_reason_code"].iloc[0] == "MARKET_CAP_PRICE_MISSING"
    assert out["market_cap_bucket"].iloc[0] == cap.UNBUCKETED


# --------------------------------------------------- 3. missing shares

@requires_adapter
def test_missing_shares_reason_code():
    inp = inp_for([1, 2])
    prov = FakeProvider(shares={1: np.nan}, fail=(2,))
    out = cap.compute_rows(inp, prices_for([1, 2]), prov, True, False)
    assert (out["market_cap_reason_code"]
            == "MARKET_CAP_SHARES_MISSING").all()


# ------------------------------------------------------- 4. suspect

@requires_adapter
def test_suspect_diff_marks_unbucketed():
    inp = inp_for([1])
    # bez cenového pohybu: close(datekey)=close(cand)=100
    # datekey_computed = 100*1e9 = 1e11; anchor 5e10 -> diff 100 % > 25 %
    prov = FakeProvider(shares={1: 1e9}, anchors={1: 5e10})
    out = cap.compute_rows(inp, prices_for([1]), prov, True, True)
    assert out["market_cap_reason_code"].iloc[0] == "MARKET_CAP_SUSPECT"
    assert out["market_cap_bucket"].iloc[0] == cap.UNBUCKETED
    assert out["relative_diff_pct"].iloc[0] == 100.0


@requires_adapter
def test_within_tolerance_not_suspect():
    # datekey_computed = 100*1e9 = 1e11; anchor 0.9e11 -> diff 11.1 %
    prov = FakeProvider(shares={1: 1e9}, anchors={1: 0.9e11})
    out = cap.compute_rows(inp_for([1]), prices_for([1]), prov, True, True)
    assert out["market_cap_reason_code"].iloc[0] == "MARKET_CAP_OK"


@requires_adapter
def test_price_move_between_datekey_and_candidate_not_suspect():
    """CAP-01B regrese: cenový pohyb mezi datekey a candidate NESMÍ
    způsobit suspect (to byl root cause CAP-01A ANCHOR_DATE_MISMATCH).

    vendor je k datekey. close(datekey)=100, close(cand)=130 (+30 %).
    candidate computed = 130*1e9 = 1.3e11; kdyby se srovnávalo candidate
    vs vendor(1e11), diff = 30 % > 25 % → falešný suspect.
    date-konzistentní: datekey_computed = 100*1e9 = 1e11 == vendor → OK.
    bucket ale z candidate mc (1.3e11 → Mega)."""
    prov = FakeProvider(shares={1: 1e9}, anchors={1: 1e11})
    out = cap.compute_rows(
        inp_for([1]),
        prices_for([1], close=130.0, close_datekey=100.0),
        prov, True, True)
    r = out.iloc[0]
    assert r["market_cap_reason_code"] == "MARKET_CAP_OK"     # ne suspect
    assert r["relative_diff_pct"] == 0.0                      # date-konzist.
    assert r["computed_market_cap"] == 130.0 * 1e9            # candidate
    assert r["datekey_computed_market_cap"] == 100.0 * 1e9    # datekey
    assert r["market_cap_bucket"] == "Large-high"    # 130B z candidate mc


# ------------------------------------------------- 5. bucket boundaries

@pytest.mark.parametrize("mc,expected", [
    (1.999e9, "Small"), (2e9, "Mid"), (9.999e9, "Mid"),
    (10e9, "Large-low"), (49.99e9, "Large-low"), (50e9, "Large-high"),
    (199.9e9, "Large-high"), (200e9, "Mega"), (5e12, "Mega"),
])
def test_bucket_boundaries(mc, expected):
    assert cap.assign_bucket(mc) == expected


def test_boundary_distance_pct():
    assert cap.boundary_distance_pct(2.1e9) == 5.0     # 5 % nad 2B
    assert cap.boundary_distance_pct(220e9) == 10.0    # 10 % nad 200B


# --------------------------------------------- 6. UNBUCKETED not dropped

@requires_adapter
def test_unbucketed_rows_not_dropped():
    inp = inp_for([1, 2, 3])
    prov = FakeProvider(shares={1: 1e9, 3: 1e9}, anchors={3: 1e9})
    out = cap.compute_rows(inp, prices_for([1, 3]), prov, True, True)
    assert len(out) == 3
    unb = out[out["market_cap_bucket"] == cap.UNBUCKETED]
    assert len(unb) == 2                     # price missing + suspect
    assert set(unb["market_cap_reason_code"]) == {
        "MARKET_CAP_PRICE_MISSING", "MARKET_CAP_SUSPECT"}


# ------------------------------------------------- 7. coverage výpočet

@requires_adapter
def test_coverage_pct_computation():
    inp = inp_for([1, 2, 3, 4])
    prov = FakeProvider(shares={1: 1e9, 2: 1e9, 3: 1e9})
    out = cap.compute_rows(inp, prices_for([1, 2, 3]), prov, True, False)
    result, coverage, _ = cap.audit_result(out, anchor_available=False)
    assert coverage == 75.0
    assert result == "STOP"                  # <90


# -------------------------------------------------- audit result pravidla

@requires_adapter
def test_audit_result_rules():
    def mk(ok, extra_code=None, n_extra=0):
        codes = ["MARKET_CAP_OK"] * ok + [extra_code] * n_extra
        return pd.DataFrame({
            "market_cap_reason_code": codes,
            "computed_market_cap": [1e11] * len(codes),
            "datekey_computed_market_cap": [1e11] * len(codes),
            "vendor_marketcap_anchor": [1e11] * len(codes),
        })
    r, c, _ = cap.audit_result(mk(100), anchor_available=True)
    assert (r, c) == ("PASS", 100.0)
    r, c, _ = cap.audit_result(mk(92, "MARKET_CAP_PRICE_MISSING", 8), True)
    assert (r, c) == ("CONDITIONAL", 92.0)
    r, *_ = cap.audit_result(mk(100, "UNKNOWN_ERROR", 1), True)
    assert r == "STOP"
    r, _, reasons = cap.audit_result(mk(100), anchor_available=False)
    assert r == "CONDITIONAL" and any("anchor" in x for x in reasons)


@requires_adapter
def test_systematic_anchor_problem_blocks():
    out = pd.DataFrame({
        "market_cap_reason_code": ["MARKET_CAP_OK"] * 100,
        "computed_market_cap": [1e11] * 100,
        "datekey_computed_market_cap": [1e11] * 100,
        "vendor_marketcap_anchor": [1e5] * 100,   # ratio 1e6 — jiné units
    })
    r, _, reasons = cap.audit_result(out, anchor_available=True)
    assert r == "CONDITIONAL"
    assert any("systematický" in x for x in reasons)


# ---------------------------------------------------- 8. source manifest

@requires_adapter
def test_source_manifest_created(tmp_path, monkeypatch):
    from test_fund02_wiring import make_adapter_env, write_data_paths
    adapter_cfg, sid = make_adapter_env(tmp_path)
    cfg_dir = write_data_paths(tmp_path, {
        "enabled": True, "adapter_config": adapter_cfg,
        "snapshot_id": sid})
    # doplnit mdsm.prices_dir do configu
    import yaml
    cfgf = cfg_dir / "data_paths.yaml"
    d = yaml.safe_load(cfgf.read_text(encoding="utf-8"))
    pdir = tmp_path / "prices"; pdir.mkdir()
    idx = pd.DatetimeIndex([pd.Timestamp(CAND)])
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0,
                       "close": [100.0], "volume": 1}, index=idx)
    df.index.name = "date"
    from src.providers.mdsm_providers import TIMEFRAME
    df.to_parquet(pdir / f"265598_{TIMEFRAME}.parquet")
    d["mdsm"] = {"prices_dir": str(pdir), "universe_dir": str(pdir),
                 "signals": {}}
    cfgf.write_text(yaml.safe_dump(d), encoding="utf-8")

    inp = tmp_path / "cd.csv"
    pd.DataFrame({"conid": [265598], "candidate_date": ["2026-06-01"],
                  "ticker": ["AAPL"]}).to_csv(inp, index=False)
    monkeypatch.setattr(cap, "MRL_ROOT", tmp_path)
    rc = cap.main(["--input", str(inp), "--config", str(cfgf)])
    runs = list((tmp_path / "results" / "diagnostics").glob(
        "cap01_market_cap_coverage_*"))
    assert len(runs) == 1
    man = json.loads((runs[0] / "source_manifest.json").read_text())
    assert man["input"]["sha256"]
    assert man["forward_returns_used"] is False
    assert man["current_market_cap_used"] is False
    for f in ("candidate_days.csv", "market_cap_output.csv",
              "cap_bucket_distribution.csv", "cap01_audit_summary.md"):
        assert (runs[0] / f).exists()
    assert rc in (0, 1)


# ------------------------------------------- 9. forward returns nepoužity

def test_no_forward_return_columns_used():
    import io
    import tokenize
    src_path = MRL_ROOT / "run_cap01_market_cap_audit.py"
    toks = tokenize.generate_tokens(
        io.StringIO(src_path.read_text(encoding="utf-8")).readline)
    code = " ".join(t.string for t in toks
                    if t.type not in (tokenize.COMMENT, tokenize.STRING))
    for marker in ("forward_return", "future_return", "ret_fwd", "hit_rate",
                   "sharpe", "cagr", "drawdown"):
        assert marker not in code.lower()


def test_loader_rejects_forbidden_columns(tmp_path):
    import run_fundamental_coverage_audit as audit_mod
    p = tmp_path / "bad.csv"
    pd.DataFrame({"conid": [1], "candidate_date": ["2026-06-01"],
                  "forward_return": [1.0]}).to_csv(p, index=False)
    with pytest.raises(ValueError):
        audit_mod.load_candidate_days(p)


# ------------------------------------------- 10-12. izolace importů

CAP_FILES = (MRL_ROOT / "run_cap01_market_cap_audit.py",
             MRL_ROOT / "run_cap01_field_gate.py")


def test_no_api_http_imports():
    for p in CAP_FILES:
        t = p.read_text(encoding="utf-8")
        for m in ("import requests", "import urllib", "import httpx",
                  "import aiohttp", "import nasdaqdatalink"):
            assert m not in t, f"{p.name}: {m}"


def test_no_tabulate_dependency():
    """CAP-01 runner nesmí IMPORTOVAT tabulate ani volat
    DataFrame.to_markdown() (report přes df_to_markdown). Zmínka slova
    v docstringu je legitimní — kontrolujeme import/volání, ne substring."""
    for i, line in enumerate((MRL_ROOT / "run_cap01_market_cap_audit.py")
                             .read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("#")[0]
        assert "import tabulate" not in code, f"line {i}"
        assert ".to_markdown(" not in code, f"line {i}"


def test_df_to_markdown_without_tabulate():
    """df_to_markdown funguje bez tabulate; NaN → prázdná buňka;
    prázdný df → '—'. (int sloupec se str() renderuje bez .0;
    float s NaN zůstává float → 5.0.)"""
    df = pd.DataFrame({"bucket": ["Mega", "Mid"], "n": [5, 3]})
    md = cap.df_to_markdown(df)
    assert md.startswith("| bucket | n |")
    assert "|---|---|" in md
    assert "| Mega | 5 |" in md
    nan_df = pd.DataFrame({"bucket": ["Mid"], "n": [np.nan]})
    assert "| Mid |  |" in cap.df_to_markdown(nan_df)   # NaN → prázdná
    assert cap.df_to_markdown(pd.DataFrame()) == "—"


def test_no_mdsm_lite_imports():
    """MDSM-Lite (access_layer/collector) zakázán; MRL MDSMPriceProvider
    je povolený canonical price source."""
    for p in CAP_FILES:
        for i, line in enumerate(p.read_text(encoding="utf-8")
                                 .splitlines(), 1):
            code = line.split("#")[0]
            for m in ("import access_layer", "from access_layer",
                      "import data_collector", "import intraday_collector"):
                assert m not in code, f"{p.name}:{i}"


def test_no_decision_resolver_imports():
    for p in CAP_FILES:
        t = p.read_text(encoding="utf-8")
        assert "decision_resolver" not in t.lower().replace(
            "decision resolver", "")


# ------------------------------- 13. thresholds nejsou optimalizované

def test_bucket_thresholds_match_approved_policy():
    """Prahy = schválená CAP-00 policy (LOCKED); test brání tichému
    tuningu z výsledků."""
    assert cap.THRESHOLDS == (2e9, 10e9, 50e9, 200e9)
    assert cap.TOLERANCE_PCT == 25.0
    assert cap.BOUNDARY_BAND_PCT == 10.0
    names = [b[0] for b in cap.BUCKETS]
    assert names == ["Mega", "Large-high", "Large-low", "Mid", "Small"]
    assert cap.BUCKETS[0][2] == math.inf


# ------------------------------------- 14. adapter runtime unchanged

@requires_adapter
def test_adapter_runtime_modules_unchanged():
    import sharadar_mdsm_adapter
    from sharadar_mdsm_adapter import schemas, sf1_provider, sf1_store
    import inspect
    assert sharadar_mdsm_adapter.__version__ == "1.0.0"
    # schemas: schválené append-only rozšíření
    assert schemas.FUNDAMENTAL_FIELDS[-2:] == ("sharesbas", "sharefactor")
    assert schemas.FUNDAMENTAL_FIELDS[:11] == (
        "revenue", "netinc", "eps", "fcf", "roe", "grossmargin",
        "netmargin", "debt", "de", "assets", "equity")
    # provider/store runtime beze změn — nesmí obsahovat CAP logiku
    for mod in (sf1_provider, sf1_store):
        src = inspect.getsource(mod)
        for marker in ("market_cap_bucket", "MARKET_CAP_", "bucket",
                       "TOLERANCE"):
            assert marker not in src, f"{mod.__name__}: {marker}"
