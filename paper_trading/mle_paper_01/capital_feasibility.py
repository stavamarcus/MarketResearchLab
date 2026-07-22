"""capital_feasibility.py — Capital Feasibility Gate (render/analysis-only).

Spec: docs/CAPITAL-FEASIBILITY-GATE_design.md

Classifies whether today's whole-share BUY plan is executable at the account's
actual equity + available cash, in rank order (rank 1 -> rank 10), carrying a
running remaining_cash (BT-06 Model A: budget = min(target_value,
remaining_cash), floor, no recycling, no rank-11 substitution).

This gate does NOT alter resolver decisions, does NOT substitute rank 11+, does
NOT resize/recycle cash, and does NOT touch the broker. All quantities are
ESTIMATES based on D close; actual D+1 open fills reconcile from real fills.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .models import COST_HALF, TARGET_WEIGHT

# BT-06 tested minimum operational capital (advisory threshold)
MIN_OPERATIONAL_CAPITAL = 10_000.0

# non-executable reasons
TOO_EXPENSIVE = "TOO_EXPENSIVE"        # target can't buy 1 share -> capital-size
INSUFFICIENT_CASH = "INSUFFICIENT_CASH"  # target could, remaining cash can't
NO_REF_PRICE = "NO_REF_PRICE"          # missing D close


@dataclass
class BuyFeasibility:
    ticker: str
    conid: Optional[int]
    target_value: float
    ref_price: Optional[float]                 # D close proxy for D+1 open
    indicative_qty: int
    estimated_debit: float
    estimated_unused_target: float
    max_price_for_estimated_qty: Optional[float]
    min_equity_for_name: Optional[float]
    executable: bool
    non_executable_reason: Optional[str]


@dataclass
class FeasibilityReport:
    status: str                                # EXECUTABLE / PARTIAL / NOT_EXECUTABLE
    equity: float
    available_cash_for_buys: float
    n_buys: int
    n_executable: int
    too_expensive: List[str]
    insufficient_cash: List[str]
    no_ref_price: List[str]
    min_operational_capital_estimate: Optional[float]
    intended_buy_budget: float
    estimated_actual_buy_debit: float
    estimated_rounding_drag: Optional[float]
    estimated_unused_buy_budget: float
    estimated_remaining_cash_after_buys: float
    estimated_cash_shortfall: float
    per_buy: List[BuyFeasibility] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> dict:
        """Flat dict for journal event / logging (no nested objects)."""
        return {
            "status": self.status,
            "n_buys": self.n_buys, "n_executable": self.n_executable,
            "too_expensive": ",".join(self.too_expensive),
            "insufficient_cash": ",".join(self.insufficient_cash),
            "no_ref_price": ",".join(self.no_ref_price),
            "min_operational_capital_estimate": self.min_operational_capital_estimate,
            "estimated_rounding_drag": self.estimated_rounding_drag,
            "estimated_remaining_cash_after_buys": self.estimated_remaining_cash_after_buys,
            "estimated_cash_shortfall": self.estimated_cash_shortfall,
        }


def evaluate_plan(equity: float, available_cash_for_buys: float,
                  buys: Sequence, ref_prices: Dict[str, Optional[float]], *,
                  cost_half: float = COST_HALF,
                  target_weight: float = TARGET_WEIGHT,
                  min_operational_capital: float = MIN_OPERATIONAL_CAPITAL
                  ) -> FeasibilityReport:
    """Evaluate today's BUY plan. `buys` are BUY Decisions in rank order
    (the resolver already orders by rank). `ref_prices` maps ticker -> D close."""
    remaining = float(available_cash_for_buys)
    per_buy: List[BuyFeasibility] = []
    too_exp: List[str] = []
    insuf: List[str] = []
    noref: List[str] = []
    intended = 0.0
    actual = 0.0
    min_equity_vals: List[float] = []

    for d in buys:
        tv = float(d.target_value)
        intended += tv
        P = ref_prices.get(d.ticker)
        if P is None or P <= 0:
            noref.append(d.ticker)
            per_buy.append(BuyFeasibility(
                d.ticker, d.conid, tv, None, 0, 0.0, round(tv, 2),
                None, None, False, NO_REF_PRICE))
            continue
        denom = P * (1 + cost_half)
        min_eq = denom / target_weight
        min_equity_vals.append(min_eq)
        budget = min(tv, remaining)
        qty = math.floor(budget / denom)
        if qty < 1:
            if math.floor(tv / denom) < 1:
                reason = TOO_EXPENSIVE
                too_exp.append(d.ticker)
            else:
                reason = INSUFFICIENT_CASH
                insuf.append(d.ticker)
            per_buy.append(BuyFeasibility(
                d.ticker, d.conid, tv, P, 0, 0.0, round(tv, 2),
                None, round(min_eq, 2), False, reason))
            continue
        debit = qty * denom
        remaining -= debit
        actual += debit
        max_price = tv / (qty * (1 + cost_half))
        per_buy.append(BuyFeasibility(
            d.ticker, d.conid, tv, P, int(qty), round(debit, 2),
            round(tv - debit, 2), round(max_price, 4), round(min_eq, 2),
            True, None))

    n_exec = sum(1 for b in per_buy if b.executable)
    n_buys = len(list(buys)) if not isinstance(buys, list) else len(buys)
    n_buys = len(per_buy)
    if n_buys == 0 or n_exec == n_buys:
        status = "EXECUTABLE"
    elif n_exec == 0:
        status = "NOT_EXECUTABLE"
    else:
        status = "PARTIAL"

    min_op = round(max(min_equity_vals), 2) if min_equity_vals else None
    rounding_drag = round(1 - actual / intended, 4) if intended > 0 else None
    # extra cash today's plan would need to also place the cash-blocked names
    shortfall_need = sum((ref_prices[t] * (1 + cost_half))
                         for t in insuf if ref_prices.get(t))
    shortfall = round(max(0.0, shortfall_need - remaining), 2)

    warnings: List[str] = []
    if too_exp:
        warnings.append(f"TOO_EXPENSIVE (capital-size): {', '.join(too_exp)}")
    if insuf:
        warnings.append(f"INSUFFICIENT_CASH: {', '.join(insuf)}")
    if noref:
        warnings.append(f"NO_REF_PRICE: {', '.join(noref)}")
    if equity < min_operational_capital:
        warnings.append(
            f"equity {equity:.0f} below BT-06 tested minimum operational "
            f"capital ({min_operational_capital:.0f})")
    if status in ("PARTIAL", "NOT_EXECUTABLE"):
        warnings.append(
            f"plan status {status}: reduced whole-share executability "
            f"({n_exec}/{n_buys} BUYs executable)")

    return FeasibilityReport(
        status=status, equity=float(equity),
        available_cash_for_buys=float(available_cash_for_buys),
        n_buys=n_buys, n_executable=n_exec, too_expensive=too_exp,
        insufficient_cash=insuf, no_ref_price=noref,
        min_operational_capital_estimate=min_op,
        intended_buy_budget=round(intended, 2),
        estimated_actual_buy_debit=round(actual, 2),
        estimated_rounding_drag=rounding_drag,
        estimated_unused_buy_budget=round(intended - actual, 2),
        estimated_remaining_cash_after_buys=round(remaining, 2),
        estimated_cash_shortfall=shortfall,
        per_buy=per_buy, warnings=warnings)
