"""
regime_source.py — MLE-PAPER-01 regime200 zdroj (Faze 1).

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md §4 (explicitne
zafixovany vypocet, C-8) a §12 RB-3 (frozen 503 universe).

Vypocet (bitove shodny s MLE-BT-04R build_regime_causal):
  rets       = close.pct_change(fill_method=None)   # ZADNY implicitni ffill
  daily_ret  = rets.mean(axis=1, skipna=True)        # NaN se preskakuji
  index      = cumprod(1 + daily_ret.fillna(0))      # den bez dat -> 0
  MA200      = rolling(200, min_periods=200).mean()
  regime_ON[D] = index[D] > MA200[D]; NaN MA -> True (neblokovat)

Kauzalita: stav pro den D pouziva jen data do close D. Resolver pro
vstupy na open D+1 cte state(D) — nikdy state(D+1).

Edge cases / predpoklady:
  - close matice = frozen 503 universe (RB-3); delisting -> NaN -> skip.
  - valid_constituents se loguje per den (spec §10); referencni rozsah
    z BT-04R: 492-503, median 498.
  - date mimo index -> KeyError (fail-fast; kalendar dodava DATA-06).
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from .models import RegimeState

REGIME_MA = 200


class RegimeSource:
    """Predpocita regime serie z close matice; vraci RegimeState per den."""

    def __init__(self, close_m: pd.DataFrame):
        if close_m.empty:
            raise ValueError("RegimeSource: prazdna close matice")
        rets = close_m.pct_change(fill_method=None)
        self._valid = rets.notna().sum(axis=1)
        daily_ret = rets.mean(axis=1, skipna=True)
        self._index = (1 + daily_ret.fillna(0)).cumprod()
        self._ma = self._index.rolling(REGIME_MA,
                                       min_periods=REGIME_MA).mean()
        self._by_date: Dict[str, RegimeState] = {}
        for ts in self._index.index:
            d = str(ts.date())
            m = self._ma.loc[ts]
            on = True if pd.isna(m) else bool(self._index.loc[ts] > m)
            self._by_date[d] = RegimeState(
                date=d, regime_on=on,
                index_level=float(self._index.loc[ts]),
                ma200=None if pd.isna(m) else float(m),
                valid_constituents=int(self._valid.loc[ts]))

    def state(self, date: str) -> RegimeState:
        """RegimeState po close dne `date`. Fail-fast pro neznamy den."""
        if date not in self._by_date:
            raise KeyError(f"RegimeSource: den {date} neni v datech")
        return self._by_date[date]

    def ok_dict(self) -> Dict[str, bool]:
        """{date: regime_on} — kompatibilni s BT-04R run_causal
        (pouziva replay engine pro in-process golden reference)."""
        return {d: s.regime_on for d, s in self._by_date.items()}
