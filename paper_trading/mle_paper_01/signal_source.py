"""
signal_source.py — MLE-PAPER-01 zdroj dat a MLE signalu (Faze 1).

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md §1 (DATA-06, universe),
§3 (MLE TOP10) a §12 RB-1 (Faze 1 = DATA-06 povinne).

Odpovednost:
  - nacteni universe CSV (503 active) a OHLCV parquetu z DATA-06 view
  - vypocet MLE TOP10 per signalni den (okno D-45..D, rank_10d <= 10)
    pres compute_rank_matrix z MLE enginu (injektovan pres mle_root)
  - cache signalu: STEJNY format i cesta jako MLE-BT-05
    (reports/backtests/mle_signals_cache_<from>_<to>.json) — replay tak
    znovupouzije cache z BT-05 behu a signaly se nepocitaji znovu

Edge cases / predpoklady:
  - vypocet je bitove shodny se signalovou smyckou BT-04/04R/05 (stejne
    okno, stejny engine, stejne NaN handling) — nutne pro reprodukci.
  - cache je vazana na okno from..to a data ve view; pri zmene dat je
    nutny prepocet (recompute=True).
  - conid se doplnuje z universe mapy (cache nese jen ticker+rank).
"""
from __future__ import annotations

import json
from datetime import date as _date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from .models import SignalCandidate

LOOKBACKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
MLE_GATE_LB = 10


def is_active(v) -> bool:
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_universe(ucsv: Path):
    """Shodne s BT-04 load_universe (bitova kompatibilita nacitani)."""
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    icol = cols.get("industry"); scol = cols.get("sector")
    instruments, t2c, t2i, t2s = [], {}, {}, {}
    for _, r in df.iterrows():
        if not is_active(r[acol]):
            continue
        tk = str(r[tcol]).strip().upper()
        instruments.append({"conid": int(float(r[ccol])), "ticker": tk,
                            "sector": str(r[scol]).strip() if scol else "",
                            "industry": str(r[icol]).strip() if icol else "",
                            "subcategory": ""})
        t2c[tk] = str(r[ccol]); t2i[tk] = str(r[icol]).strip() if icol else ""
        t2s[tk] = str(r[scol]).strip() if scol else ""
    return instruments, t2c, t2i, t2s


def load_price_matrices(view_dir: Path, instruments, t2c
                        ) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Close/open matice z DATA-06 view ({conid}_D1.parquet)."""
    cs, os_ = {}, {}
    for inst in instruments:
        f = Path(view_dir) / f"{t2c[inst['ticker']]}_D1.parquet"
        if not f.exists():
            continue
        df = pd.read_parquet(f)
        df.index = pd.to_datetime(df.index).normalize()
        df = df.sort_index()
        if "close" in df.columns:
            cs[inst["ticker"]] = df["close"]
            if "open" in df.columns:
                os_[inst["ticker"]] = df["open"]
    close_m = pd.DataFrame(cs).sort_index()
    open_m = pd.DataFrame(os_).sort_index()
    if close_m.empty:
        raise ValueError("load_price_matrices: prazdna close matice - "
                         "zkontroluj view_dir a universe CSV")
    return close_m, open_m


class SignalSource:
    """MLE TOP10 per signalni den, s JSON cache kompatibilni s BT-05."""

    def __init__(self, close_m: pd.DataFrame, instruments, t2c: Dict[str, str],
                 compute_rank_matrix, cache_path: Path | None = None,
                 recompute: bool = False):
        self._t2conid = {tk: int(float(c)) for tk, c in t2c.items()}
        self._close_m = close_m
        self._instruments = instruments
        self._compute = compute_rank_matrix
        self._cache_path = Path(cache_path) if cache_path else None
        self._by_date: Dict[str, List[Tuple[str, int]]] = {}
        if (self._cache_path and self._cache_path.exists()
                and not recompute):
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            self._by_date = {d: [(tk, int(rk)) for tk, rk in lst]
                             for d, lst in raw.items()}
            print(f"signaly: nacitam cache {self._cache_path.name} "
                  f"({len(self._by_date)} dni)")

    def compute(self, signal_dates: List[str]) -> None:
        """Dopocita chybejici dny (bitove shodne s BT-04/04R/05 smyckou)."""
        missing = [d for d in signal_dates if d not in self._by_date]
        if not missing:
            return
        print(f"signaly: pocitam {len(missing)} dni (pomala cast)...")
        for i, td in enumerate(missing):
            rd = _date.fromisoformat(td)
            ws = pd.Timestamp(rd - timedelta(days=45))
            we = pd.Timestamp(rd)
            cp = {}
            for tk in self._close_m.columns:
                s = self._close_m[tk]
                sub = s[(s.index >= ws) & (s.index <= we)]
                if not sub.empty:
                    cp[tk] = sub
            inst = [x for x in self._instruments if x["ticker"] in cp]
            try:
                rm = self._compute(cp, inst, rd,
                                   LOOKBACKS).set_index("ticker")
            except Exception:
                continue
            col = f"rank_{MLE_GATE_LB}d"
            lst = [(tk, int(rm.loc[tk, col])) for tk in rm.index
                   if not pd.isna(rm.loc[tk, col])
                   and int(rm.loc[tk, col]) <= 10]
            lst.sort(key=lambda x: x[1])
            self._by_date[td] = lst
            if (i + 1) % 250 == 0:
                print(f"  ... signaly {i + 1}/{len(missing)}")
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            ser = {d: [[tk, rk] for tk, rk in lst]
                   for d, lst in self._by_date.items()}
            self._cache_path.write_text(json.dumps(ser), encoding="utf-8")
            print(f"signaly: ulozeny do cache {self._cache_path.name}")

    def candidates(self, date: str) -> List[SignalCandidate]:
        """MLE_TOP10 pro signalni den (prazdny list = zadny signal)."""
        return [SignalCandidate(ticker=tk,
                                conid=self._t2conid.get(tk, -1),
                                rank_10d=rk)
                for tk, rk in self._by_date.get(date, [])]

    def raw_dict(self) -> Dict[str, List[Tuple[str, int]]]:
        """{date: [(ticker, rank)]} — kompatibilni s BT-04R run_causal
        (pouziva replay engine pro in-process golden reference)."""
        return self._by_date
