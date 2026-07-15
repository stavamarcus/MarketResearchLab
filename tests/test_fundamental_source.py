"""MRL-FUND-01 wrapper testy — syntetická data / monkeypatch, žádná reálná
Sharadar data, žádné API. Smoke scénáře 1–7 zadání FUND-01."""

import json
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from conftest import requires_adapter

pytestmark = requires_adapter

SID = "sf1art_synthetic_000000"
CAND = date(2026, 6, 1)

AAPL, GOOG, GOOGL, LYB = 265598, 208813720, 208813719, 74866700
INVALID = 999999999
PERMA = {AAPL: 111, GOOG: 995, GOOGL: 995, LYB: 555}


# ------------------------------------------------------- syntetické prostředí

def _sf1_row(permaticker, ticker, datekey="2026-05-01", **kw):
    base = dict(permaticker=permaticker, dimension="ART",
                datekey=pd.Timestamp(datekey),
                calendardate=pd.Timestamp("2026-03-31"),
                lastupdated=pd.Timestamp(datekey), ticker=ticker,
                revenue=10.0, netinc=1.0, eps=0.5, fcf=2.0, roe=0.15,
                grossmargin=0.4, netmargin=0.1, debt=5.0, de=0.5,
                assets=20.0, equity=10.0,
                sharesbas=1_000_000_000.0, sharefactor=1.0,
                marketcap=100.0, pe=15.0, ps=3.0, pb=2.0)
    base.update(kw)
    return base


def _identity_csv(tmp_path):
    import csv
    cols = ("conid", "permaticker", "ticker", "sharadar_ticker",
            "identity_tier", "alias_flag", "source", "evidence",
            "identity_contract_version", "identity_artifact_version")
    rows = [
        dict(conid=AAPL, permaticker=PERMA[AAPL], ticker="AAPL",
             sharadar_ticker="AAPL", identity_tier="MATCHED_STRONG",
             alias_flag="", source="MAPPING", evidence="cusip",
             identity_contract_version="identity_v1.0",
             identity_artifact_version="v2"),
        dict(conid=GOOGL, permaticker=PERMA[GOOGL], ticker="GOOGL",
             sharadar_ticker="GOOGL", identity_tier="MATCHED_STRONG",
             alias_flag="", source="MAPPING", evidence="cusip",
             identity_contract_version="identity_v1.0",
             identity_artifact_version="v2"),
        dict(conid=GOOG, permaticker=PERMA[GOOG], ticker="GOOG",
             sharadar_ticker="GOOGL",
             identity_tier="WHITELIST_COMPANY_LEVEL",
             alias_flag="COMPANY_LEVEL_ALIAS", source="WHITELIST",
             evidence="alias", identity_contract_version="identity_v1.0",
             identity_artifact_version="v2"),
        dict(conid=LYB, permaticker=PERMA[LYB], ticker="LYB",
             sharadar_ticker="LYB",
             identity_tier="WHITELIST_NAME_VERIFIED", alias_flag="",
             source="WHITELIST", evidence="name",
             identity_contract_version="identity_v1.0",
             identity_artifact_version="v2"),
    ]
    p = tmp_path / "id.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return p


def make_source(tmp_path, extra_rows=None):
    from sharadar_mdsm_adapter.identity_map import IdentityMap
    from sharadar_mdsm_adapter.sf1_provider import SF1Provider
    from sharadar_mdsm_adapter.sf1_store import SF1Store
    from sharadar_mdsm_adapter.snapshot_hash import data_hash, schema_hash
    from src.providers.sharadar_fundamental_source import (
        MRLSharadarFundamentalSource,
    )

    rows = [
        _sf1_row(PERMA[AAPL], "AAPL"),
        _sf1_row(PERMA[GOOG], "GOOGL"),
        _sf1_row(PERMA[LYB], "LYB"),
    ] + (extra_rows or [])
    df = pd.DataFrame(rows)
    proc = tmp_path / "processed" / SID / "sf1_art_pit.parquet"
    man = tmp_path / "snapshots" / f"{SID}.json"
    proc.parent.mkdir(parents=True, exist_ok=True)
    man.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(proc, index=False)
    stored = pd.read_parquet(proc)
    man.write_text(json.dumps({
        "snapshot_id": SID, "created_at": "2026-07-04T00:00:00+00:00",
        "dimension": "ART",
        "row_counts": {"raw": len(df), "processed": len(df)},
        "schema_hash": schema_hash(stored), "data_hash": data_hash(stored),
        "contract_versions": {"identity_contract_version": "v1.0",
                              "provider_contract_version": "v1.0"},
    }), encoding="utf-8")
    handle = SF1Store(SimpleNamespace(data_root=str(tmp_path))).load(SID)
    provider = SF1Provider(handle, IdentityMap.load(_identity_csv(tmp_path)))
    return MRLSharadarFundamentalSource(provider, handle)


def cd_frame(rows):
    return pd.DataFrame(rows, columns=["conid", "candidate_date"])


# ------------------------------------------------------------------ scénáře

def test_valid_conid_returns_included_row(tmp_path):
    src = make_source(tmp_path)
    out, cov = src.get_fundamentals(cd_frame([(AAPL, CAND)]))
    r = out.iloc[0]
    assert r["coverage_status"] == "OK"
    assert r["reason_code"] is None
    assert r["sf1_datekey"] == date(2026, 5, 1)
    assert r["sf1_datekey"] <= r["candidate_date"]
    assert r["identity_tier"] == "MATCHED_STRONG"
    assert bool(r["is_alias"]) is False
    assert r["revenue"] == 10.0
    assert cov.returned_snapshots == 1


def test_invalid_conid_excluded_identity_missing(tmp_path):
    src = make_source(tmp_path)
    out, cov = src.get_fundamentals(cd_frame([(INVALID, CAND)]))
    r = out.iloc[0]
    assert r["coverage_status"] == "EXCLUDED"
    assert r["reason_code"] == "IDENTITY_MISSING"
    assert pd.isna(r["revenue"])
    assert cov.reason_code_counts["IDENTITY_MISSING"] == 1


def test_date_before_first_row_no_asof(tmp_path):
    src = make_source(tmp_path)
    out, _ = src.get_fundamentals(cd_frame([(AAPL, date(1990, 1, 1))]))
    assert out.iloc[0]["reason_code"] == "NO_SF1_ASOF_DATE"
    assert out.iloc[0]["coverage_status"] == "EXCLUDED"


def test_alias_handling_preserved(tmp_path):
    src = make_source(tmp_path)
    out, cov = src.get_fundamentals(cd_frame([(GOOG, CAND)]))
    r = out.iloc[0]
    assert r["coverage_status"] == "OK"
    assert bool(r["is_alias"]) is True
    assert r["revenue"] == 10.0            # fundamentals u aliasu OK
    # price-derived pole ve schema vůbec neexistují
    for col in ("marketcap", "pe", "ps", "pb"):
        assert col not in out.columns
    assert cov.alias_count == 1


def test_coverage_counts_match_provider_requests(tmp_path):
    src = make_source(tmp_path)
    calls = {"n": 0}
    orig = src._provider.get_snapshot

    def counting(conid, cand, fields=None):
        calls["n"] += 1
        return orig(conid, cand, fields=fields)

    src._provider = SimpleNamespace(get_snapshot=counting)
    inp = cd_frame([(AAPL, CAND), (GOOG, CAND), (INVALID, CAND),
                    (AAPL, date(1990, 1, 1))])
    out, cov = src.get_fundamentals(inp)
    assert calls["n"] == 4                              # žádná memoizace
    assert cov.requested_candidate_days == 4
    assert cov.returned_snapshots == 2
    assert cov.excluded_candidate_days == 2
    assert cov.coverage_pct == 50.0


def test_output_preserves_one_to_one_including_duplicates(tmp_path):
    src = make_source(tmp_path)
    inp = cd_frame([(AAPL, CAND), (AAPL, CAND), (INVALID, CAND)])
    out, cov = src.get_fundamentals(inp)
    assert len(out) == 3                                # 1:1 včetně duplicit
    assert cov.requested_candidate_days == 3
    assert list(out["conid"]) == [AAPL, AAPL, INVALID]  # pořadí zachováno


def test_missing_fundamentals_not_dropped(tmp_path):
    src = make_source(tmp_path)
    inp = cd_frame([(AAPL, CAND), (INVALID, CAND), (LYB, CAND)])
    out, _ = src.get_fundamentals(inp)
    assert len(out) == len(inp)
    excluded = out[out["coverage_status"] == "EXCLUDED"]
    assert len(excluded) == 1
    assert excluded.iloc[0]["reason_code"] == "IDENTITY_MISSING"
    assert excluded[list(src.fields)].isna().all().all()


def test_unknown_error_mapping(tmp_path):
    src = make_source(tmp_path)

    def boom(conid, cand, fields=None):
        raise RuntimeError("neočekávaná chyba")

    src._provider = SimpleNamespace(get_snapshot=boom)
    out, cov = src.get_fundamentals(cd_frame([(AAPL, CAND)]))
    assert out.iloc[0]["reason_code"] == "UNKNOWN_ERROR"
    assert cov.reason_code_counts["UNKNOWN_ERROR"] == 1


def test_price_derived_fields_forbidden_at_wrapper():
    from src.providers.sharadar_fundamental_source import (
        FundamentalSourceError, MRLSharadarFundamentalSource,
    )
    with pytest.raises(FundamentalSourceError):
        MRLSharadarFundamentalSource(
            provider=SimpleNamespace(), handle=SimpleNamespace(),
            fields=("revenue", "marketcap"))


def test_missing_input_columns_raise(tmp_path):
    from src.providers.sharadar_fundamental_source import (
        FundamentalSourceError,
    )
    src = make_source(tmp_path)
    with pytest.raises(FundamentalSourceError):
        src.get_fundamentals(pd.DataFrame({"conid": [AAPL]}))


def test_coverage_report_written(tmp_path):
    src = make_source(tmp_path)
    _, cov = src.get_fundamentals(cd_frame([(AAPL, CAND), (INVALID, CAND)]))
    p = src.write_coverage_report(cov, tmp_path / "artifacts", "run_x")
    text = p.read_text(encoding="utf-8")
    assert SID in text
    assert "IDENTITY_MISSING | 1" in text


def test_build_source_rejects_unpinned_latest():
    from src.providers.sharadar_fundamental_source import (
        FundamentalSourceError, build_fundamental_source,
    )
    with pytest.raises(FundamentalSourceError):
        build_fundamental_source("whatever.yaml", "latest")
