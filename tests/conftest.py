"""MRL pytest conftest — sys.path pro MRL root (importy `from src....`).

Adapter (sharadar_mdsm_adapter) je optional dependency — testy, které ho
vyžadují, se SKIPnou, pokud není importovatelný (viz _requires_adapter).
V produkčním env: pip install -e (FUND-01 open issue: adapter packaging).
"""

import sys
from pathlib import Path

import pytest

_MRL_ROOT = Path(__file__).resolve().parent.parent
if str(_MRL_ROOT) not in sys.path:
    sys.path.insert(0, str(_MRL_ROOT))


def adapter_available() -> bool:
    try:
        import sharadar_mdsm_adapter  # noqa: F401
        return True
    except ImportError:
        return False


requires_adapter = pytest.mark.skipif(
    not adapter_available(),
    reason="sharadar_mdsm_adapter není nainstalován (pip install -e)",
)
