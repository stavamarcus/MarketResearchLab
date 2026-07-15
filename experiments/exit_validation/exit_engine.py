"""
exit_engine.py — RP-0011-EXIT-TIMING

Simulace jednoho trade nad ticker-lokální sérií barů. VEŠKERÁ fill
logika žije zde — pravidla pouze signalizují (viz exit_rules.py).

Protokol simulace (pre-registrováno, zamčeno 2026-07-02):
    - Entry: close(entry_pos). Cena z lokální série.
    - Bar iterace: pos = entry_pos+1 .. window_end_pos (včetně).
    - FillPolicy.CLOSE:     exit close(pos) baru signálu.
    - FillPolicy.NEXT_OPEN: signál close(pos) → fill první VALIDNÍ open
      v pos+1 .. window_end_pos. Chybějící open (NaN/halt) → posun na
      další dostupný open, flag `fill_gap` (zámek: „fill první dostupný
      open, flag do metadat"). Signál na close(window_end_pos) nelze
      naplnit uvnitř okna → ignorován (drženo do konce okna).
    - Bez exitu do window_end_pos → exit close(window_end_pos)
      (u primární větve = baseline ekvivalent; u H1b = time-stop).
    - Return v okně: exit_price/entry_price - 1; po exitu cash 0 %.

Edge cases:
    - entry close <= 0 → trade nevalidní (volající vyřadí kandidáta).
    - open(pos) NaN pro všechny zbývající bary → exit close(window_end),
      flag `fill_gap_unresolved`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from experiments.exit_validation.exit_rules import ExitRule, FillPolicy


@dataclass(frozen=True)
class TradeOutcome:
    ret: float                 # exit/entry - 1 (zbytek okna cash 0 %)
    exit_pos: int              # lokální index exit baru
    hold_days: int             # exit_pos - entry_pos (v barech)
    exited_early: bool         # exit před window_end_pos
    signal_pos: int | None     # bar signálu (None = bez signálu)
    fill_gap: bool             # fill posunut kvůli chybějícímu open
    fill_gap_unresolved: bool  # signál bez realizovatelného open v okně


def simulate_trade(
    rule: ExitRule,
    entry_pos: int,
    window_end_pos: int,
    opens: np.ndarray,
    closes: np.ndarray,
) -> TradeOutcome | None:
    """Simuluj trade od close(entry_pos) do window_end_pos podle pravidla.

    Vrací None, pokud entry cena není validní. Předpokládá, že
    rule.prepare(closes) už proběhlo a closes[entry_pos..window_end_pos]
    jsou validní (zajišťuje volající — common completable subset).
    """
    entry_price = closes[entry_pos]
    if not np.isfinite(entry_price) or entry_price <= 0:
        return None

    for pos in range(entry_pos + 1, window_end_pos + 1):
        if not rule.check(pos, entry_pos):
            continue

        if rule.fill is FillPolicy.CLOSE:
            price = closes[pos]
            return TradeOutcome(
                ret=float(price / entry_price - 1.0),
                exit_pos=pos,
                hold_days=pos - entry_pos,
                exited_early=(pos < window_end_pos),
                signal_pos=pos,
                fill_gap=False,
                fill_gap_unresolved=False,
            )

        # NEXT_OPEN
        if pos >= window_end_pos:
            break  # signál na posledním baru okna — nelze naplnit uvnitř okna

        fill_pos, gap = _first_valid_open(opens, pos + 1, window_end_pos)
        if fill_pos is None:
            # nerealizovatelný fill → drženo do konce okna
            return TradeOutcome(
                ret=float(closes[window_end_pos] / entry_price - 1.0),
                exit_pos=window_end_pos,
                hold_days=window_end_pos - entry_pos,
                exited_early=False,
                signal_pos=pos,
                fill_gap=False,
                fill_gap_unresolved=True,
            )
        return TradeOutcome(
            ret=float(opens[fill_pos] / entry_price - 1.0),
            exit_pos=fill_pos,
            hold_days=fill_pos - entry_pos,
            # realizovaný signálový exit = early exit i při fill_pos ==
            # window_end_pos (exit na OPEN posledního baru != baseline close)
            exited_early=True,
            signal_pos=pos,
            fill_gap=gap,
            fill_gap_unresolved=False,
        )

    # žádný signál → drženo do konce okna
    return TradeOutcome(
        ret=float(closes[window_end_pos] / entry_price - 1.0),
        exit_pos=window_end_pos,
        hold_days=window_end_pos - entry_pos,
        exited_early=False,
        signal_pos=None,
        fill_gap=False,
        fill_gap_unresolved=False,
    )


def _first_valid_open(
    opens: np.ndarray, start: int, end_incl: int
) -> tuple[int | None, bool]:
    """První pos v [start, end_incl] s validním open. (pos, posunuto?)"""
    for p in range(start, end_incl + 1):
        v = opens[p]
        if np.isfinite(v) and v > 0:
            return p, (p != start)
    return None, False
