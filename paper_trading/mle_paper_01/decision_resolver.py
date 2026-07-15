"""
decision_resolver.py — MLE-PAPER-01 Decision Resolver (Faze 1).

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md (APPROVED/FROZEN), §5.

Cista deterministicka funkce:
  resolve(mle_top10, regime, portfolio, target_date) -> list[Decision]

Kontrakt:
  - ZADNE I/O, zadny broker, zadne API, zadne nove filtry.
  - Nemutuje vstupy (vstupni typy jsou frozen dataclasses).
  - target_date = D+1 (obchodni den, pro ktery se plan vytvari).
  - regime.date = D (signalni den); regime MUSI byt z close D - kauzalita.
  - portfolio = stav po close D (equity = cash + MTM za close D).

Zavazne poradi (spec §5):
  1. EXITY: pozice s planned_exit_date == target_date -> EXIT na CLOSE
     target_date; pozice STALE drzi slot a cash pro krok 3.
  2. REGIME GATE: regime_on == False -> zadne nove vstupy.
  3. VSTUPY: free_slots pres VSECHNY otevrene pozice (vc. pending-exit);
     kandidati dle rank_10d; vyloucit drzene tickery (vc. pending-exit);
     target_value = 10 % equity; spend = min(target, cash_available);
     kaskadova rezervace cash_available (LOKALNI promenna).
  4. Zadna akce -> [DO_NOTHING].

Edge cases (spec §7):
  - <10 kandidatu -> koupit jen dostupne.
  - vic kandidatu nez free_slots -> vzit nejlepsi rank.
  - spend <= 0 -> preskocit ticker (reason se neloguje jako Decision;
    logging resi vyssi vrstva z resolver_diagnostics, viz nize).
  - duplicitni ticker v kandidatech -> pouzije se prvni (lepsi rank).
"""
from __future__ import annotations

from typing import Iterable, List, Sequence

from .models import (Action, COST_HALF, Decision, MAX_POSITIONS,
                     PortfolioState, PriceSource, RegimeState,
                     SignalCandidate, TARGET_WEIGHT)


def resolve(mle_top10: Sequence[SignalCandidate],
            regime: RegimeState,
            portfolio: PortfolioState,
            target_date: str) -> List[Decision]:
    """Vytvori order plan pro target_date (= D+1). Viz docstring modulu."""
    _validate_inputs(regime, portfolio, target_date, mle_top10)
    decisions: List[Decision] = []

    open_pos = portfolio.open_positions()

    # ---- krok 1: EXITY (planned exits) — spec §5.1 ----
    for p in open_pos:
        if p.planned_exit_date == target_date:
            decisions.append(Decision(
                action=Action.EXIT,
                target_date=target_date,
                reason="planned_exit_hold10",
                ticker=p.ticker,
                conid=p.conid,
                quantity=p.shares,
                price_source=PriceSource.CLOSE))

    # ---- krok 2: REGIME GATE — spec §5.2 ----
    if regime.regime_on:
        # ---- krok 3: VSTUPY — spec §5.3 ----
        # pending-exit pozice STALE drzi slot, cash i ticker (spec §5.1)
        free_slots = MAX_POSITIONS - len(open_pos)
        if free_slots > 0:
            held = {p.ticker for p in open_pos}
            cash_available = portfolio.cash  # LOKALNI promenna (C-4)
            equity = portfolio.equity
            candidates = sorted(mle_top10, key=lambda c: c.rank_10d)
            taken = 0
            seen = set()
            for cand in candidates:
                if taken >= free_slots:
                    break
                if cand.ticker in held or cand.ticker in seen:
                    continue
                seen.add(cand.ticker)
                target_value = TARGET_WEIGHT * equity
                # ERRATUM spec v1.1 §5.3 (k potvrzeni architektem):
                # golden master BT-04R kapuje spend na cash/(1+ch), NE na
                # cash (zdedeno z BT-04). Pro bitovou reprodukci MUSI
                # resolver pouzit shodnou formuli. Vedlejsi efekt golden
                # masteru (reprodukovany zamerne): rezidualni cash po capu
                # kaskaduje do mikro-nakupu, dokud jsou sloty a kandidati.
                spend = min(target_value, cash_available / (1 + COST_HALF))
                if spend <= 0:
                    continue
                decisions.append(Decision(
                    action=Action.BUY,
                    target_date=target_date,
                    reason=f"mle_top10_rank_{cand.rank_10d}",
                    ticker=cand.ticker,
                    conid=cand.conid,
                    target_value=spend,
                    price_source=PriceSource.NEXT_OPEN))
                cash_available -= spend
                taken += 1

    # ---- krok 4: zadna akce -> DO_NOTHING — spec §5.4 ----
    if not decisions:
        reason = ("regime_off_no_exits" if not regime.regime_on
                  else "no_action")
        decisions.append(Decision(action=Action.DO_NOTHING,
                                  target_date=target_date,
                                  reason=reason))
    return decisions


def _validate_inputs(regime: RegimeState, portfolio: PortfolioState,
                     target_date: str,
                     mle_top10: Sequence[SignalCandidate]) -> None:
    """Kauzalni sanity kontroly. Fail-fast misto ticheho spatneho planu."""
    if regime.date >= target_date:
        raise ValueError(
            f"kauzalita: regime.date ({regime.date}) musi byt < "
            f"target_date ({target_date}) - regime musi byt z close D")
    # H1: stav musi byt mark-to-market za tyz close D jako regime.
    # Stavova vrstva MUSI pred resolve provest mark_to_market(closes, D).
    if portfolio.last_updated_date != regime.date:
        raise ValueError(
            f"konzistence: portfolio.last_updated_date "
            f"({portfolio.last_updated_date!r}) != regime.date "
            f"({regime.date!r}) - stav neni aktualni za close D")
    if portfolio.cash < 0:
        raise ValueError(f"invariant: cash < 0 ({portfolio.cash})")
    open_pos = portfolio.open_positions()
    if len(open_pos) > MAX_POSITIONS:
        raise ValueError(
            f"invariant: {len(open_pos)} otevrenych pozic > {MAX_POSITIONS}")
    tickers = [p.ticker for p in open_pos]
    if len(tickers) != len(set(tickers)):
        raise ValueError("invariant: duplicitni ticker v OPEN pozicich")
    # H2: pozice s planned_exit_date < target_date mela uz byt zavrena;
    # jeji pritomnost = zastaraly/poskozeny stav, ne validni vstup.
    for p in open_pos:
        if p.planned_exit_date < target_date:
            raise ValueError(
                f"stale pozice: {p.ticker} planned_exit_date "
                f"({p.planned_exit_date}) < target_date ({target_date})")
    # H3: signal kontrakt = rank_10d v 1..10; cokoli mimo = poskozeny
    # signal input, fail-fast.
    for c in mle_top10:
        if not 1 <= c.rank_10d <= 10:
            raise ValueError(
                f"signal: {c.ticker} rank_10d={c.rank_10d} mimo 1..10")
