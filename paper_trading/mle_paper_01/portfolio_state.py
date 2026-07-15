"""
portfolio_state.py — MLE-PAPER-01 stavova vrstva (Faze 1).

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md §8 (stavovy model),
§9 (fill logika Faze 1), C-4 (resolver stav pouze cte).

Odpovednost:
  - aplikace fillu na PortfolioState (BUY na open, EXIT na close)
  - mark-to-market za close dne (equity pro resolver)
  - invarianty (spec §8) — fail-fast pri poruseni
  - persistence JSON (Faze 1: JSON, ne databaze — rozhodnuti architekta)

Vsechny operace jsou funkcionalni: vraci NOVY PortfolioState, vstup
nemutuji (kontrakty jsou frozen dataclasses). Stav meni VYHRADNE tato
vrstva podle skutecnych fillu; Decision Resolver stav pouze cte.

Fill matematika (spec §9, Faze 1 simulovany fill, 15 bps round-trip):
  BUY:  quantity = spend / (open_price * (1 + 7.5 bps))
        cash -= quantity * open_price * (1 + 7.5 bps)  (= spend)
  EXIT: proceeds = shares * close_price * (1 - 7.5 bps)
        cash += proceeds
        pnl = proceeds - shares * entry_price * (1 + 7.5 bps)

Edge cases / predpoklady:
  - planned_exit_date dodava volajici (replay/signal vrstva) — stavova
    vrstva je kalendar-agnosticka.
  - apply_exit_fill s fallback cenou (chybejici close) je odpovednost
    volajiciho dle §7: POUZE BT-04R-compatible reproduction mechanism,
    kazdy pripad zalogovat jako data warning.
  - float shares (frakcni) — shodne s backtestem; celociselne
    zaokrouhleni resi az Faze 2 (IBKR).
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Dict, Mapping

from .models import (COST_BPS_ROUND_TRIP, COST_HALF, ClosedTrade,
                     Decision, Action, MAX_POSITIONS, PortfolioState,
                     Position, PositionStatus)


# ---------------------------------------------------------------- invarianty
def validate_state(state: PortfolioState) -> None:
    """Invarianty spec §8. Fail-fast misto ticheho spatneho stavu."""
    open_pos = state.open_positions()
    if len(open_pos) > MAX_POSITIONS:
        raise ValueError(
            f"invariant: {len(open_pos)} OPEN pozic > {MAX_POSITIONS}")
    if state.cash < -1e-6:
        raise ValueError(f"invariant: cash < 0 ({state.cash})")
    tickers = [p.ticker for p in open_pos]
    if len(tickers) != len(set(tickers)):
        raise ValueError("invariant: duplicitni ticker v OPEN pozicich")


# ---------------------------------------------------------------- fills
def apply_buy_fill(state: PortfolioState, decision: Decision,
                   fill_price: float, fill_date: str,
                   planned_exit_date: str) -> PortfolioState:
    """Aplikuje BUY fill na open (spec §9 Faze 1).

    quantity se urcuje az ZDE ze skutecne fill ceny (C-4: Decision nese
    target_value). planned_exit_date dodava volajici (kalendar §6).
    """
    if decision.action != Action.BUY:
        raise ValueError(f"apply_buy_fill: ocekavan BUY, je {decision.action}")
    if fill_price is None or fill_price <= 0:
        raise ValueError(f"apply_buy_fill: neplatna fill cena {fill_price}")
    if decision.target_value is None or decision.target_value <= 0:
        raise ValueError(
            f"apply_buy_fill: neplatny target_value {decision.target_value}")

    spend = decision.target_value
    quantity = spend / (fill_price * (1 + COST_HALF))
    cost_total = quantity * fill_price * (1 + COST_HALF)  # == spend
    if cost_total > state.cash + 1e-6:
        raise ValueError(
            f"apply_buy_fill: cost {cost_total:.2f} > cash {state.cash:.2f} "
            f"(resolver mel spend omezit cash_available)")

    signal_rank = _rank_from_reason(decision.reason)
    pos = Position(ticker=decision.ticker, conid=decision.conid,
                   shares=quantity, entry_date=fill_date,
                   entry_price=fill_price,
                   planned_exit_date=planned_exit_date,
                   signal_rank=signal_rank)
    new_state = replace(state,
                        cash=state.cash - cost_total,
                        positions=state.positions + (pos,),
                        last_updated_date=fill_date)
    validate_state(new_state)
    return new_state


def apply_exit_fill(state: PortfolioState, decision: Decision,
                    fill_price: float, fill_date: str,
                    reason: str = "planned_exit_hold10") -> PortfolioState:
    """Aplikuje EXIT fill na close (spec §9 Faze 1).

    Proceeds jsou v cash od tohoto okamziku — tedy dostupne pro vstupy
    az na open NASLEDUJICIHO dne (resolver pro tyz den uz bezel, spec §2).
    """
    if decision.action != Action.EXIT:
        raise ValueError(f"apply_exit_fill: ocekavan EXIT, je {decision.action}")
    if fill_price is None or fill_price <= 0:
        raise ValueError(f"apply_exit_fill: neplatna fill cena {fill_price}")

    target = None
    for p in state.open_positions():
        if p.ticker == decision.ticker:
            target = p
            break
    if target is None:
        raise ValueError(
            f"apply_exit_fill: OPEN pozice {decision.ticker} neexistuje")
    if decision.quantity is not None and \
            abs(decision.quantity - target.shares) > 1e-9:
        raise ValueError(
            f"apply_exit_fill: quantity v Decision ({decision.quantity}) "
            f"!= drzene shares ({target.shares})")

    proceeds = target.shares * fill_price * (1 - COST_HALF)
    cost_in = target.shares * target.entry_price * (1 + COST_HALF)
    trade = ClosedTrade(ticker=target.ticker, conid=target.conid,
                        shares=target.shares, entry_date=target.entry_date,
                        entry_price=target.entry_price, exit_date=fill_date,
                        exit_price=fill_price,
                        pnl=round(proceeds - cost_in, 6), reason=reason)
    remaining = tuple(p for p in state.positions if p is not target)
    new_state = replace(state,
                        cash=state.cash + proceeds,
                        positions=remaining,
                        closed_trades=state.closed_trades + (trade,),
                        last_updated_date=fill_date)
    validate_state(new_state)
    return new_state


def mark_to_market(state: PortfolioState, closes: Mapping[str, float],
                   date: str) -> PortfolioState:
    """Prepocita equity za close dne (spec §8 invariant).

    closes = {ticker: close cena za `date`}. Chybejici cena -> fallback
    entry cena pozice (§7 reproduction mechanism) — volajici MUSI
    zalogovat data warning.
    """
    mv = 0.0
    for p in state.open_positions():
        px = closes.get(p.ticker)
        mv += p.shares * (px if px is not None and px > 0 else p.entry_price)
    new_state = replace(state, equity=state.cash + mv,
                        last_updated_date=date)
    validate_state(new_state)
    return new_state


def _rank_from_reason(reason: str) -> int:
    """Extrahuje rank z resolver reason 'mle_top10_rank_N' (best effort)."""
    try:
        return int(reason.rsplit("_", 1)[-1])
    except (ValueError, AttributeError):
        return -1


# ---------------------------------------------------------------- persistence
def state_to_dict(state: PortfolioState) -> Dict:
    return {
        "cash": state.cash,
        "equity": state.equity,
        "last_updated_date": state.last_updated_date,
        "positions": [vars(p) | {"status": p.status.value}
                      for p in state.positions],
        "closed_trades": [vars(t) for t in state.closed_trades],
    }


def state_from_dict(d: Dict) -> PortfolioState:
    positions = tuple(
        Position(**{**p, "status": PositionStatus(p["status"])})
        for p in d.get("positions", []))
    closed = tuple(ClosedTrade(**t) for t in d.get("closed_trades", []))
    state = PortfolioState(cash=d["cash"], equity=d["equity"],
                           positions=positions, closed_trades=closed,
                           last_updated_date=d.get("last_updated_date", ""))
    validate_state(state)
    return state


def save_state(state: PortfolioState, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state_to_dict(state), indent=2),
                    encoding="utf-8")


def load_state(path: Path) -> PortfolioState:
    return state_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
