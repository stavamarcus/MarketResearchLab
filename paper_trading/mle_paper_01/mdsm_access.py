"""mdsm_access.py — bridge to the MDSM-Lite V1 AccessLayer.

Builds close/open price matrices by calling AccessLayer.get_historical(...,
timeframe="D1", cache_only=True) per conid — NEVER by reading parquet directly.
Per-conid coverage is taken from the MDSM-Lite MetadataManager so the request is
always within cached range (avoids partial-miss errors) and yields the per-conid
last cached session (end_date) used by the freshness gate.

The MDSM-Lite import is isolated here (lazy), so the runtime never imports ibapi
or touches cache paths / parquet layout.
"""
from __future__ import annotations

import contextlib
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


@contextlib.contextmanager
def _isolated_src(project_path: str):
    """Import a project whose top package is ``src`` without colliding with
    another already-loaded ``src`` (MarketLeadershipEngine and MDSM-Lite both use
    ``src`` as their root). Saves/removes any existing ``src`` / ``src.*`` from
    sys.modules, puts project_path first on sys.path, and restores everything on
    exit — so each project's ``src`` is only ever live during its own import."""
    p = str(project_path)
    saved = {k: sys.modules[k] for k in list(sys.modules)
             if k == "src" or k.startswith("src.")}
    for k in saved:
        del sys.modules[k]
    had_path = p in sys.path
    if had_path:
        sys.path.remove(p)
    sys.path.insert(0, p)
    try:
        yield
    finally:
        for k in [k for k in list(sys.modules)
                  if k == "src" or k.startswith("src.")]:
            del sys.modules[k]
        sys.modules.update(saved)
        try:
            sys.path.remove(p)
        except ValueError:
            pass
        if had_path:
            sys.path.append(p)


def build_mdsm_access(mdsm_project_path: str):
    """Import MDSM-Lite and return (AccessLayer, MetadataManager) for CACHE_ONLY
    reads. Never connects to IBKR. Call inside _isolated_src (see
    build_matrices_isolated) so MDSM-Lite's ``src`` does not collide with the MLE
    engine's ``src``."""
    p = str(mdsm_project_path)
    if p not in sys.path:
        sys.path.insert(0, p)
    try:
        from src.utils.config_loader import load_config
        from src.access.access_layer import AccessLayer
        from src.cache.metadata_manager import MetadataManager
    except ImportError as e:
        raise RuntimeError(
            f"MDSM: cannot import MDSM-Lite access layer from {p} "
            f"(src.access.access_layer / src.cache.metadata_manager): {e}") from e
    cfg = load_config(Path(p) / "config" / "config.yaml")
    return AccessLayer(cfg), MetadataManager(cfg)


def build_matrices_isolated(mdsm_project_path: str, instruments):
    """Build (close_m, open_m, coverage) from the MDSM-Lite cache with the
    MDSM ``src`` isolated. All access-layer reads happen inside the isolation, so
    the AccessLayer object is not used again afterwards."""
    with _isolated_src(mdsm_project_path):
        layer, meta = build_mdsm_access(mdsm_project_path)
        return load_price_matrices_via_access(layer, meta, instruments)


def _to_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    try:
        return datetime.fromisoformat(str(v)[:10]).date()
    except ValueError:
        return None


def _read_meta(meta, conid: int) -> Optional[dict]:
    try:
        return meta.read(conid, "D1")
    except Exception:
        return None


def load_price_matrices_via_access(layer, meta, instruments):
    """Return (close_m, open_m, coverage, status). close_m/open_m are date x
    ticker DataFrames built through the access layer; coverage maps ticker ->
    last cached session (date) for readable conids; status maps EVERY universe
    ticker -> {conid, end_date, is_valid, has_data} so the freshness gate can
    classify fresh / stale / missing / invalid with full detail."""
    import pandas as pd

    cs: Dict[str, "pd.Series"] = {}
    os_: Dict[str, "pd.Series"] = {}
    coverage: Dict[str, date] = {}
    status: Dict[str, dict] = {}

    for inst in instruments:
        conid = int(inst["conid"])
        tk = inst["ticker"]
        m = _read_meta(meta, conid)
        end = _to_date(m.get("end_date")) if m else None
        start = _to_date(m.get("start_date")) if m else None
        is_valid = bool(m.get("is_valid", True)) if m else False
        had_data = False

        if m and is_valid and start is not None and end is not None:
            try:
                df = layer.get_historical(conid, start, end, timeframe="D1",
                                          cache_only=True)
            except Exception:
                df = None
            if df is not None and len(df) and "close" in df.columns:
                df = df.copy()
                df.index = pd.to_datetime(df.index).normalize()
                df = df.sort_index()
                cs[tk] = df["close"]
                if "open" in df.columns:
                    os_[tk] = df["open"]
                coverage[tk] = end
                had_data = True

        status[tk] = {"conid": conid,
                      "end_date": end.isoformat() if end else None,
                      "is_valid": is_valid, "has_data": had_data}

    close_m = pd.DataFrame(cs).sort_index()
    open_m = pd.DataFrame(os_).sort_index()
    if close_m.empty:
        raise ValueError(
            "MDSM: empty close matrix via access layer — no readable conids")
    return close_m, open_m, coverage, status
