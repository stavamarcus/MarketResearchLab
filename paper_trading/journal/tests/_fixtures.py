"""Shared sample records for the test suite (kept out of conftest so it
is importable as a plain module)."""


def sample_daily_state(date="2026-07-15"):
    return {
        "date": date, "account_id": "DU-PAPER", "cash": 10000.0,
        "equity": 30000.0, "net_liquidation": 30000.0, "gross_exposure": 20000.0,
        "net_exposure": 20000.0, "open_positions_count": 3, "regime_on": True,
        "regime_index_level": 5200.0, "regime_ma200": 5000.0,
        "valid_constituents_count": 500, "kill_switch_active": False,
        "override_active": False, "orders_planned_count": 2,
        "orders_filled_count": 0, "warnings_count": 0, "errors_count": 0,
    }


def sample_signals(date="2026-07-15"):
    return [
        {"signal_date": date, "ticker": "AAPL", "conid": "265598",
         "rank_1d": 1.0, "rank_3d": 2.0, "rank_5d": 1.0, "rank_10d": 1.0,
         "rank_20d": 3.0, "is_top10": True, "is_top50": True,
         "sector": "Tech", "industry": "Hardware", "price_close": 210.0,
         "source": "DATA-06"},
        {"signal_date": date, "ticker": "MSFT", "conid": "272093",
         "rank_1d": 2.0, "rank_3d": 1.0, "rank_5d": 2.0, "rank_10d": 2.0,
         "rank_20d": 1.0, "is_top10": True, "is_top50": True,
         "sector": "Tech", "industry": "Software", "price_close": 430.0,
         "source": "DATA-06"},
    ]


def sample_trade(date="2026-07-15"):
    return {
        "trade_id": "T-1", "ticker": "AAPL", "conid": "265598",
        "entry_date": "2026-07-01", "exit_date": date, "entry_price": 200.0,
        "exit_price": 210.0, "shares": 10.0, "entry_value": 2000.0,
        "exit_value": 2100.0, "pnl": 100.0, "pnl_pct": 5.0, "holding_days": 10,
        "rank_10d_at_entry": 1.0, "regime_at_entry": True,
        "exit_reason": "HOLD_EXPIRED", "cost_bps": 2.0, "slippage_bps": 1.0,
        # mfe_pct / mae_pct intentionally omitted -> NULL in MVP
    }
