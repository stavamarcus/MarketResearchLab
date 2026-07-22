"""Put paper_trading on sys.path so `mle_paper_01.*` and `journal` import as
top-level packages (project convention: cwd = paper_trading). Also add the
tests dir so sibling helpers like `_runner_fakes` import cleanly."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER_TRADING = HERE.parents[1]  # tests -> mle_paper_01 -> paper_trading
for p in (str(PAPER_TRADING), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)
