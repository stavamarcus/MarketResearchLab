"""MRL-FUND-02 kontraktní testy — izolace + neporušenost adapter runtime."""

from pathlib import Path

import pytest

from conftest import requires_adapter

MRL_ROOT = Path(__file__).resolve().parent.parent

FUND02_FILES = (
    MRL_ROOT / "src" / "context" / "context_builder.py",
    MRL_ROOT / "src" / "core" / "experiment_runner.py",
    MRL_ROOT / "run_fundamental_coverage_audit.py",
    MRL_ROOT / "run_fund03_extract_candidate_days.py",
)

HTTP_MARKERS = ("import requests", "import urllib", "import http.client",
                "import httpx", "import aiohttp", "import nasdaqdatalink")
FORBIDDEN = ("import mdsm", "from mdsm", "import access_layer",
             "from access_layer", "import decision_resolver",
             "from decision_resolver")
EDGE_MARKERS = ("forward_return", "hit_rate", "sharpe", "cagr",
                "drawdown", "alpha_")


def _lines(p):
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        yield i, line.split("#")[0]


def test_no_api_http_imports():
    for p in FUND02_FILES:
        for i, code in _lines(p):
            for m in HTTP_MARKERS:
                assert m not in code, f"{p.name}:{i}: {m!r}"


def test_no_mdsm_lite_or_resolver_imports():
    for p in FUND02_FILES:
        for i, code in _lines(p):
            for m in FORBIDDEN:
                assert m not in code, f"{p.name}:{i}: {m!r}"


def test_coverage_audit_has_no_edge_metrics():
    """Žádné edge metriky v KÓDU FUND-03 runnerů (docstringy dokumentující
    zákaz jsou legitimní — tokenize vynechává STRING/COMMENT)."""
    import io
    import tokenize
    for p in (MRL_ROOT / "run_fundamental_coverage_audit.py",
              MRL_ROOT / "run_fund03_extract_candidate_days.py"):
        _check_no_edge(p)


def _check_no_edge(p):
    import io
    import tokenize
    code_tokens = []
    with io.BytesIO(p.read_bytes()) as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type not in (tokenize.STRING, tokenize.COMMENT):
                code_tokens.append(tok.string.lower())
    code = " ".join(code_tokens)
    for m in EDGE_MARKERS:
        assert m not in code, f"coverage audit obsahuje edge marker {m!r}"


def test_no_adapter_code_copied_into_mrl():
    """Adapter je dependency — jeho moduly nesmí být zkopírované do MRL."""
    for name in ("sf1_store.py", "sf1_provider.py", "snapshot_hash.py"):
        hits = list(MRL_ROOT.rglob(name))
        assert hits == [], f"adapter soubor zkopírován do MRL: {hits}"


@requires_adapter
def test_adapter_runtime_invariants_locked():
    """Proxy kontrola neporušenosti adapteru: verze + zamčené REASON_CODES.
    Plný diff proti release ZIPu provádí PM review."""
    import sharadar_mdsm_adapter
    from sharadar_mdsm_adapter.exceptions import REASON_CODES
    assert sharadar_mdsm_adapter.__version__ == "1.0.0"
    assert REASON_CODES == (
        "IDENTITY_MISSING", "IDENTITY_AMBIGUOUS",
        "IDENTITY_TIER_NOT_ALLOWED", "NO_SF1_ROWS", "NO_SF1_ASOF_DATE",
        "STALE_SNAPSHOT", "ALIAS_PRICE_FIELD_FORBIDDEN", "CACHE_MISSING",
        "SCHEMA_MISMATCH")
