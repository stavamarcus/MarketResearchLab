"""
IMS Audit — Forward Returns
audit/forward_returns.py

Zodpovědnost:
    Pro každý signál v archivu vypočítat:
        - forward return 5D / 10D / 20D / 30D
        - SPY forward return pro stejná okna
        - alpha vs SPY (excess return)
        - entry-to-low drawdown pro každé okno

    Výstup je jeden řádek per signál (date + ticker) se všemi metrikami.
    Řádky kde forward data nejsou dostupná mají NaN — nejsou vyhazovány,
    ale jsou označeny. Každý test si sám filtruje podle dostupnosti.

Výstup:
    pd.DataFrame — jeden řádek per signál
    Sloupce:
        date, ticker, score, priority_group, sector, industry
        entry_price
        fwd_5d, fwd_10d, fwd_20d, fwd_30d         (% return od entry)
        spy_5d, spy_10d, spy_20d, spy_30d          (% SPY return)
        alpha_5d, alpha_10d, alpha_20d, alpha_30d  (excess vs SPY)
        dd_5d, dd_10d, dd_20d, dd_30d              (entry-to-low drawdown %)
        usable_5d, usable_10d, usable_20d, usable_30d  (bool — data dostupná)

Použití:
    from audit.data_loader import load_audit_data
    from audit.forward_returns import compute_forward_returns

    data    = load_audit_data()
    results = compute_forward_returns(data)
"""

from __future__ import annotations

from datetime import date

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
    Vypočítá forward returns, alpha a drawdown pro každý signál.

    Args:
        data:    AuditData z load_audit_data()
        verbose: logovat průběh

    Returns:
        pd.DataFrame — jeden řádek per signál
    """
    if verbose:
        print("=" * 60)
        print("IMS AUDIT — FORWARD RETURNS")
        print("=" * 60)

    rows = []
    signals   = data.signals
    close_map = data.close_map
    spy_close = {SPY_TICKER: data.spy_close}

    total     = len(signals)
    no_entry  = 0
    no_spy    = 0

    for idx, signal in signals.iterrows():
        ticker      = signal["ticker"]
        signal_date = signal["date"]
        score       = signal["score"]
        group       = signal["priority_group"]
        sector      = signal.get("sector", "")
        industry    = signal.get("industry", "")

        # Entry price
        entry_price = get_entry_price(close_map, ticker, signal_date)
        if entry_price is None or entry_price <= 0:
            no_entry += 1
            continue

        spy_entry = get_entry_price(spy_close, SPY_TICKER, signal_date)
        if spy_entry is None or spy_entry <= 0:
            no_spy += 1
            continue

        row = {
            "date":           signal_date,
            "ticker":         ticker,
            "score":          score,
            "priority_group": group,
            "sector":         sector,
            "industry":       industry,
            "entry_price":    round(entry_price, 4),
        }

        # Forward returns per window
        for window in FORWARD_WINDOWS:
            col_fwd   = f"fwd_{window}d"
            col_spy   = f"spy_{window}d"
            col_alpha = f"alpha_{window}d"
            col_dd    = f"dd_{window}d"
            col_use   = f"usable_{window}d"

            fwd_price = get_forward_price(close_map, ticker, signal_date, window)
            spy_price = get_forward_price(spy_close, SPY_TICKER, signal_date, window)
            low_price = get_window_low(close_map, ticker, signal_date, window)

            if fwd_price is not None and spy_price is not None and low_price is not None:
                fwd_ret   = (fwd_price / entry_price - 1) * 100
                spy_ret   = (spy_price / spy_entry - 1) * 100
                alpha     = fwd_ret - spy_ret
                drawdown  = (low_price / entry_price - 1) * 100

                row[col_fwd]   = round(fwd_ret, 4)
                row[col_spy]   = round(spy_ret, 4)
                row[col_alpha] = round(alpha, 4)
                row[col_dd]    = round(drawdown, 4)
                row[col_use]   = True
            else:
                row[col_fwd]   = None
                row[col_spy]   = None
                row[col_alpha] = None
                row[col_dd]    = None
                row[col_use]   = False

        rows.append(row)

    df = pd.DataFrame(rows)

    if verbose:
        print(f"Signálů celkem    : {total}")
        print(f"Bez entry price   : {no_entry}")
        print(f"Bez SPY entry     : {no_spy}")
        print(f"Zpracováno        : {len(df)}")
        print()
        print("USABLE SAMPLE PER WINDOW")
        print("-" * 40)
        for window in FORWARD_WINDOWS:
            col = f"usable_{window}d"
            if col in df.columns:
                n     = df[col].sum()
                dates = df[df[col] == True]["date"]
                d_min = dates.min() if not dates.empty else "N/A"
                d_max = dates.max() if not dates.empty else "N/A"
                print(f"  {window:>3}D : {int(n):>5} řádků  |  {d_min} → {d_max}")
        print()
        print("Forward Returns dokončeny.")
        print("=" * 60)

    return df
