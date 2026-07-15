"""MRL-FUND-01 kontraktní testy — scénáře 8–10 zadání (statické, bez adapteru)."""

from pathlib import Path

MRL_ROOT = Path(__file__).resolve().parent.parent

FUND01_FILES = (
    MRL_ROOT / "src" / "providers" / "sharadar_fundamental_source.py",
    MRL_ROOT / "run_fundamental_smoke_integration.py",
)

HTTP_MARKERS = ("import requests", "import urllib", "import http.client",
                "import httpx", "import aiohttp", "import nasdaqdatalink")

FORBIDDEN_MODULE_MARKERS = (
    "import mdsm", "from mdsm",            # MDSM-Lite
    "import access_layer", "from access_layer",
    "import decision_resolver", "from decision_resolver",
)


def test_no_api_http_imports():
    for p in FUND01_FILES:
        text = p.read_text(encoding="utf-8")
        for m in HTTP_MARKERS:
            assert m not in text, f"{p.name}: {m!r}"


def test_no_mdsm_lite_or_resolver_imports():
    for p in FUND01_FILES:
        for i, line in enumerate(
                p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#")[0]
            for m in FORBIDDEN_MODULE_MARKERS:
                assert m not in code, f"{p.name}:{i}: {m!r}"


def test_wrapper_uses_only_public_adapter_modules():
    """Wrapper importuje pouze veřejné adapter moduly — žádné čtení
    parquet/manifestů napřímo."""
    text = FUND01_FILES[0].read_text(encoding="utf-8")
    assert "read_parquet" not in text
    assert "from sharadar_mdsm_adapter import" in text


def test_no_pinned_snapshot_bypass():
    """Wrapper vynucuje pinning: 'latest' pouze přes allow_latest."""
    text = FUND01_FILES[0].read_text(encoding="utf-8")
    assert "allow_latest" in text
