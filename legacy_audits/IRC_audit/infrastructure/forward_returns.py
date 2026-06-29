"""
Industry Rank Calendar Audit — Forward Returns
audit/forward_returns.py

Zodpovědnost:
    Pro každý signal (date × ticker) vypočítat forward returns,
    SPY returns a alpha.

Výstup:
    pd.DataFrame — jeden řádek per signal
    Sloupce:
        date, ticker, industry, industry_rank, industry_persist, industry_members
        entry_price
        fwd_5d, fwd_10d, fwd_20d, fwd_30d
        spy_5d, spy_10d, spy_20d, spy_30d
        alpha_5d, alpha_10d, alpha_20d, alpha_30d
        dd_5d, dd_10d, dd_20d, dd_30d
        usable_5d, usable_10d, usable_20d, usable_30d
"""

from __future__ import annotations

import pandas as pd

from audit.data_loader import (
    AuditData,
    FORWARD_WINDOWS,
    get_entry_price,
    get_forward_price,
    get_window_low,
)

SPY_TICKER = "SPY"


def compute_forward_returns(data: AuditData, verbose: bool = True) -> pd.DataFrame:
    """
    Vypočítá forward returns pro každý signál (date × ticker).

    Poznámka: signálů může být řádově 100k+ (269 dní × ~490 tickerů).
    Optimalizujeme vektorizací na úrovni tickerů.
    """
    if verbose:
        print("=" * 60)
        print("INDUSTRY RANK CALENDAR AUDIT — FORWARD RETURNS")
        print("=" * 60)
        print(f"Zpracovávám {len(data.signals)} signálů...")

    spy_map = {SPY_TICKER: data.spy_close}
    rows    = []

    no_entry = 0
    no_spy   = 0

    for idx, signal in data.signals.iterrows():
        ticker      = signal["ticker"]
        signal_date = signal["date"]

        entry_price = get_entry_price(data.close_map, ticker, signal_date)
        if entry_price is None or entry_price <= 0:
            no_entry += 1
            continue

        spy_entry = get_entry_price(spy_map, SPY_TICKER, signal_date)
        if spy_entry is None or spy_entry <= 0:
            no_spy += 1
            continue

        row = {
            "date":              signal_date,
            "ticker":            ticker,
            "industry":          signal["industry"],
            "industry_rank":     signal["industry_rank"],
            "industry_persist":  signal["industry_persist"],
            "industry_members":  signal.get("industry_members"),
            "advance_ratio":     signal.get("advance_ratio"),
            "is_new_entrant":    signal.get("is_new_entrant", False),
            "entry_price":       round(entry_price, 4),
        }

        for window in FORWARD_WINDOWS:
            fwd_price = get_forward_price(data.close_map, ticker, signal_date, window)
            spy_price = get_forward_price(spy_map, SPY_TICKER, signal_date, window)
            low_price = get_window_low(data.close_map, ticker, signal_date, window)

            if fwd_price and spy_price and low_price:
                fwd_ret  = (fwd_price / entry_price - 1) * 100
                spy_ret  = (spy_price / spy_entry - 1) * 100
                alpha    = fwd_ret - spy_ret
                drawdown = (low_price / entry_price - 1) * 100

                row[f"fwd_{window}d"]   = round(fwd_ret, 4)
                row[f"spy_{window}d"]   = round(spy_ret, 4)
                row[f"alpha_{window}d"] = round(alpha, 4)
                row[f"dd_{window}d"]    = round(drawdown, 4)
                row[f"usable_{window}d"] = True
            else:
                row[f"fwd_{window}d"]   = None
                row[f"spy_{window}d"]   = None
                row[f"alpha_{window}d"] = None
                row[f"dd_{window}d"]    = None
                row[f"usable_{window}d"] = False

        rows.append(row)

        if verbose and (idx + 1) % 10000 == 0:
            print(f"  Zpracováno {idx + 1} / {len(data.signals)}...")

    df = pd.DataFrame(rows)

    if verbose:
        print(f"Signálů celkem  : {len(data.signals)}")
        print(f"Bez entry price : {no_entry}")
        print(f"Bez SPY entry   : {no_spy}")
        print(f"Zpracováno      : {len(df)}")
        print()
        for window in FORWARD_WINDOWS:
            col = f"usable_{window}d"
            if col in df.columns:
                n = df[col].sum()
                print(f"  {window:>3}D usable: {int(n):>6} řádků")
        print()
        print("Forward Returns dokončeny.")
        print("=" * 60)

    return df
