"""Make the ``journal`` package importable when running the test suite
directly (pytest picks up this conftest and prepends the package's parent
directory to sys.path). In the wider project the package is normally
imported as ``paper_trading.journal``; these tests use the bare
``journal`` name for self-contained execution.
"""

import sys
from pathlib import Path

# tests/ -> journal/ -> paper_trading/  (parent of the journal package)
PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))
