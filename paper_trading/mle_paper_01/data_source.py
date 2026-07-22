"""data_source.py — configurable price data source for the Daily Offline Runner.

`DataSourceProfile` decouples the runner from *where* prices live:
  - DATA06 : development / replay-compatible dry-run (thin adapter over the
             frozen signal_source loaders + the MarketLeadershipEngine ranker)
  - MDSM   : operational daily runner after GDU (interface defined; concrete
             read lands with the GDU cache)

The adapter reuses the frozen modules and adds NO strategy logic:
  - MLE TOP10 via signal_source.SignalSource (which calls the existing
    MarketLeadershipEngine `compute_rank_matrix` — never a local reimpl)
  - regime200 via regime_source.RegimeSource
  - close prices for mark-to-market straight from the DATA-06 close matrix

The heavy build (reading parquet, importing the MLE engine) is lazy, so the
object can be imported and constructed with just paths and no data present.
"""
from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, runtime_checkable

from .models import RegimeState, SignalCandidate


class DataSourceProfile(str, Enum):
    DATA06 = "DATA06"
    MDSM = "MDSM"


@runtime_checkable
class PriceDataSource(Protocol):
    """Everything the runner needs from a price source — nothing strategy."""
    profile: DataSourceProfile

    def last_completed_session(self) -> str: ...
    def signal_candidates(self, business_date: str) -> List[SignalCandidate]: ...
    def regime_state(self, business_date: str) -> RegimeState: ...
    def closes_at(self, business_date: str,
                  tickers: Iterable[str]) -> Dict[str, Optional[float]]: ...
    def metadata(self) -> Dict[str, str]: ...


class Data06PriceSource:
    """Thin adapter over the frozen DATA-06 loaders + MLE ranker."""

    profile = DataSourceProfile.DATA06

    def __init__(self, universe_path: str, view_dir: str,
                 mle_project_path: str, signal_cache_path: str | None = None,
                 recompute_signals: bool = False):
        self.universe_path = str(universe_path)
        self.view_dir = str(view_dir)
        self.mle_project_path = str(mle_project_path)
        self.signal_cache_path = signal_cache_path
        self.recompute_signals = recompute_signals
        self._built = False
        self._close_m = None
        self._open_m = None
        self._signal_source = None
        self._regime_source = None

    # -- lazy heavy build (reads data + imports MLE engine) ---------------
    def _ensure_built(self) -> None:
        if self._built:
            return
        import pandas as pd  # noqa: F401 (used indirectly via frozen modules)
        from .signal_source import (SignalSource, load_price_matrices,
                                    load_universe)
        from .regime_source import RegimeSource

        # inject the existing MLE ranker — never reimplement rank_10d
        if self.mle_project_path not in sys.path:
            sys.path.insert(0, self.mle_project_path)
        try:
            from src.engines.rank_matrix_engine import compute_rank_matrix
        except ImportError as e:
            raise RuntimeError(
                f"DATA06: cannot import MarketLeadershipEngine ranker from "
                f"{self.mle_project_path} (src.engines.rank_matrix_engine): {e}"
            ) from e

        instruments, t2c, t2i, t2s = load_universe(Path(self.universe_path))
        self._close_m, self._open_m = load_price_matrices(
            Path(self.view_dir), instruments, t2c)
        self._regime_source = RegimeSource(self._close_m)
        cache = Path(self.signal_cache_path) if self.signal_cache_path else None
        self._signal_source = SignalSource(
            self._close_m, instruments, t2c, compute_rank_matrix,
            cache_path=cache, recompute=self.recompute_signals)
        self._built = True

    def last_completed_session(self) -> str:
        self._ensure_built()
        return str(self._close_m.index.max().date())

    def signal_candidates(self, business_date: str) -> List[SignalCandidate]:
        self._ensure_built()
        self._signal_source.compute([business_date])
        return self._signal_source.candidates(business_date)

    def regime_state(self, business_date: str) -> RegimeState:
        self._ensure_built()
        return self._regime_source.state(business_date)

    def closes_at(self, business_date: str,
                  tickers: Iterable[str]) -> Dict[str, Optional[float]]:
        self._ensure_built()
        import pandas as pd
        out: Dict[str, Optional[float]] = {}
        ts = pd.Timestamp(business_date)
        for tk in tickers:
            if tk not in self._close_m.columns:
                out[tk] = None
                continue
            try:
                v = self._close_m.at[ts, tk]
            except KeyError:
                out[tk] = None
                continue
            out[tk] = None if pd.isna(v) else float(v)
        return out

    def metadata(self) -> Dict[str, str]:
        return {
            "data_source": self.profile.value,
            "universe_path": self.universe_path,
            "price_view_dir": self.view_dir,
            "mle_project_path": self.mle_project_path,
        }


MAX_STALE_ALLOWED = 25   # revised OQ-2: tolerate known dead/invalid names


class MdsmFreshnessReport:
    """Result of the MDSM freshness gate (revised OQ-2).

    verdict: PASS / PASS_WITH_WARNINGS / FAIL. `passed` is True for PASS and
    PASS_WITH_WARNINGS. stale/missing/invalid are lists of
    {ticker, conid, end_date, reason}; traded_violations lists any BUY/EXIT
    ticker that is not fresh (a HARD FAIL)."""

    def __init__(self, verdict, expected_session, universe_size, fresh_count,
                 stale, missing, invalid, traded_violations,
                 effective_last_session, reason=""):
        self.verdict = verdict
        self.passed = verdict in ("PASS", "PASS_WITH_WARNINGS")
        self.expected_session = expected_session
        self.universe_size = universe_size
        self.fresh_count = fresh_count
        self.stale = stale
        self.missing = missing
        self.invalid = invalid
        self.traded_violations = traded_violations
        self.effective_last_session = effective_last_session
        self.reason = reason

    def bad_count(self):
        return len(self.stale) + len(self.missing) + len(self.invalid)

    def as_dict(self):
        return {"result": self.verdict, "passed": self.passed,
                "expected_session": self.expected_session,
                "effective_last_session": self.effective_last_session,
                "universe_size": self.universe_size,
                "fresh_count": self.fresh_count,
                "bad_count": self.bad_count(),
                "stale": self.stale, "missing": self.missing,
                "invalid": self.invalid,
                "traded_violations": self.traded_violations,
                "reason": self.reason}


class MdsmPriceSource:
    """Current MDSM-Lite source: builds price matrices through the MDSM-Lite V1
    AccessLayer (cache_only) — never direct parquet — then reuses the same
    SignalSource / RegimeSource / injected MLE ranker as DATA06. Pure data
    bridge: implements only the PriceDataSource contract; nothing downstream
    (candidate selection, ranking, order-plan generation) is touched here."""

    profile = DataSourceProfile.MDSM

    def __init__(self, universe_path: str, mdsm_project_path: str,
                 mle_project_path: str, signal_cache_path: str | None = None,
                 recompute_signals: bool = False, access=None, ranker=None):
        self.universe_path = str(universe_path)
        self.mdsm_project_path = str(mdsm_project_path)
        self.mle_project_path = str(mle_project_path)
        self.signal_cache_path = signal_cache_path
        self.recompute_signals = recompute_signals
        self._access = access          # optional injected (layer, meta) for tests
        self._ranker = ranker          # optional injected MLE ranker for tests
        self._built = False
        self._close_m = None
        self._open_m = None
        self._coverage = {}
        self._status = {}
        self._instruments = None
        self._signal_source = None
        self._regime_source = None

    def _ensure_built(self) -> None:
        if self._built:
            return
        from .signal_source import SignalSource, load_universe
        from .regime_source import RegimeSource

        instruments, t2c, t2i, t2s = load_universe(Path(self.universe_path))
        self._instruments = instruments

        # 1) build price matrices from the MDSM-Lite cache FIRST, with the MDSM
        #    ``src`` isolated (MLE engine also uses ``src``). All access-layer
        #    reads happen here; afterwards the MDSM src is unloaded.
        if self._access is not None:
            from .mdsm_access import load_price_matrices_via_access
            layer, meta = self._access
            self._close_m, self._open_m, self._coverage, self._status = \
                load_price_matrices_via_access(layer, meta, instruments)
        else:
            from .mdsm_access import build_matrices_isolated
            self._close_m, self._open_m, self._coverage, self._status = \
                build_matrices_isolated(self.mdsm_project_path, instruments)

        # 2) now import the MLE ranker (its own ``src``), unless injected
        if self._ranker is not None:
            compute_rank_matrix = self._ranker
        else:
            if self.mle_project_path not in sys.path:
                sys.path.insert(0, self.mle_project_path)
            try:
                from src.engines.rank_matrix_engine import compute_rank_matrix
            except ImportError as e:
                raise RuntimeError(
                    f"MDSM: cannot import MarketLeadershipEngine ranker from "
                    f"{self.mle_project_path}: {e}") from e

        self._regime_source = RegimeSource(self._close_m)
        cache = Path(self.signal_cache_path) if self.signal_cache_path else None
        self._signal_source = SignalSource(
            self._close_m, instruments, t2c, compute_rank_matrix,
            cache_path=cache, recompute=self.recompute_signals)
        self._built = True

    def last_completed_session(self) -> str:
        self._ensure_built()
        return str(self._close_m.index.max().date())

    def signal_candidates(self, business_date: str) -> List[SignalCandidate]:
        self._ensure_built()
        self._signal_source.compute([business_date])
        return self._signal_source.candidates(business_date)

    def regime_state(self, business_date: str) -> RegimeState:
        self._ensure_built()
        return self._regime_source.state(business_date)

    def closes_at(self, business_date: str,
                  tickers: Iterable[str]) -> Dict[str, Optional[float]]:
        self._ensure_built()
        import pandas as pd
        out: Dict[str, Optional[float]] = {}
        ts = pd.Timestamp(business_date)
        for tk in tickers:
            if tk not in self._close_m.columns:
                out[tk] = None
                continue
            try:
                v = self._close_m.at[ts, tk]
            except KeyError:
                out[tk] = None
                continue
            out[tk] = None if pd.isna(v) else float(v)
        return out

    def freshness_report(self, expected_session: str, buy_tickers=None,
                         exit_tickers=None) -> MdsmFreshnessReport:
        """Revised OQ-2 gate. Classifies every universe ticker vs the last
        completed session, then:
          - HARD FAIL if any BUY/EXIT ticker is not fresh, or if the total
            stale+missing+invalid exceeds MAX_STALE_ALLOWED (GDU clearly did
            not run), else
          - PASS_WITH_WARNINGS if some tolerated dead/invalid names exist, else
          - PASS.
        stale/missing/invalid are listed with ticker, conid, end_date, reason."""
        self._ensure_built()
        from datetime import date as _date
        exp = _date.fromisoformat(str(expected_session)[:10])

        stale, missing, invalid, fresh = [], [], [], set()
        last_dates = []
        for tk, st in self._status.items():
            conid = st.get("conid")
            ed = st.get("end_date")
            entry = {"ticker": tk, "conid": conid, "end_date": ed}
            if not st.get("is_valid", True):
                invalid.append({**entry, "reason": "invalid"})
                continue
            if not st.get("has_data") or ed is None:
                missing.append({**entry, "reason": "missing"})
                continue
            last_dates.append(_date.fromisoformat(ed))
            if _date.fromisoformat(ed) < exp:
                stale.append({**entry, "reason": "stale"})
            else:
                fresh.add(tk)
        effective = min(last_dates).isoformat() if last_dates else None
        bad = len(stale) + len(missing) + len(invalid)

        # traded-name protection: any BUY/EXIT ticker must be fresh
        traded = list(buy_tickers or []) + list(exit_tickers or [])
        traded_violations = [t for t in traded if t not in fresh]

        if bad > MAX_STALE_ALLOWED:
            verdict = "FAIL"
            reason = (f"{bad} stale/missing/invalid > {MAX_STALE_ALLOWED} — "
                      f"GDU likely did not run")
        elif traded_violations:
            verdict = "FAIL"
            reason = (f"traded tickers not fresh: {traded_violations}")
        elif bad > 0:
            verdict = "PASS_WITH_WARNINGS"
            reason = f"{bad} tolerated stale/missing/invalid name(s)"
        else:
            verdict = "PASS"
            reason = "all universe tickers fresh"

        return MdsmFreshnessReport(
            verdict, exp.isoformat(), len(self._status), len(fresh),
            stale, missing, invalid, traded_violations, effective, reason)

    def metadata(self) -> Dict[str, str]:
        return {
            "data_source": self.profile.value,
            "universe_path": self.universe_path,
            "mdsm_project_path": self.mdsm_project_path,
            "mle_project_path": self.mle_project_path,
        }


def build_data_source(config) -> PriceDataSource:
    """Factory: build the configured price source from RunnerConfig."""
    if config.data_source == DataSourceProfile.DATA06:
        return Data06PriceSource(
            universe_path=config.universe_path,
            view_dir=config.data06_view_dir,
            mle_project_path=config.mle_project_path,
            signal_cache_path=config.signal_cache_path,
            recompute_signals=config.recompute_signals)
    if config.data_source == DataSourceProfile.MDSM:
        return MdsmPriceSource(
            universe_path=config.universe_path,
            mdsm_project_path=config.mdsm_project_path,
            mle_project_path=config.mle_project_path,
            signal_cache_path=config.signal_cache_path,
            recompute_signals=config.recompute_signals)
    raise ValueError(f"unknown data_source: {config.data_source!r}")
