"""
test_decision_resolver.py — unit testy MLE-PAPER-01 Decision Resolveru.

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md §5, §7.

Spusteni (z MarketResearchLab/paper_trading/):
    python -m unittest mle_paper_01.tests.test_decision_resolver -v

Pokryti (zadani architekta + oponentni doplnky):
  A1  regime OFF -> pouze exity, zadne BUY
  A2  portfolio plne -> zadne nove BUY
  A3  planned_exit_date == target_date -> EXIT se spravnym quantity
  A4  ticker uz drzen -> nekupovat znovu
  A5  cash mensi nez target_value -> spend = cash
  A6  free_slots omezuje pocet BUY
  A7  mene nez 10 kandidatu -> koupit jen dostupne
  B1  determinismus: identicky vstup -> identicky vystup, vstup nezmutovan
  B2  kandidati zpracovani dle rank_10d
  B3  kaskadova rezervace cash pres vice BUY
  B4  pending-exit pozice drzi slot (plne portfolio s dnesnim exitem)
  B5  pending-exit ticker neni tyz den koupitelny
  B6  zadna akce -> DO_NOTHING
  B7  kauzalni validace: regime.date >= target_date -> ValueError
"""
from __future__ import annotations

import copy
import unittest

from mle_paper_01.models import (Action, PortfolioState, Position,
                                 PriceSource, RegimeState, SignalCandidate)
from mle_paper_01.decision_resolver import resolve

D = "2026-07-10"        # signalni den (close D)
D1 = "2026-07-13"       # target_date = D+1 (obchodni den)


def cand(ticker, rank, conid=None):
    return SignalCandidate(ticker=ticker, conid=conid or hash(ticker) % 10**6,
                           rank_10d=rank)


def pos(ticker, exit_date, shares=10.0, rank=1):
    return Position(ticker=ticker, conid=hash(ticker) % 10**6, shares=shares,
                    entry_date="2026-06-26", entry_price=100.0,
                    planned_exit_date=exit_date, signal_rank=rank)


def pf(cash, equity=None, positions=()):
    return PortfolioState(cash=cash,
                          equity=equity if equity is not None else cash,
                          positions=tuple(positions),
                          last_updated_date=D)


def regime(on=True):
    return RegimeState(date=D, regime_on=on)


def buys(decisions):
    return [d for d in decisions if d.action == Action.BUY]


def exits(decisions):
    return [d for d in decisions if d.action == Action.EXIT]


TOP10 = [cand(t, i + 1) for i, t in enumerate(
    ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ"])]


class TestRegimeGate(unittest.TestCase):
    def test_A1_regime_off_only_exits_no_buys(self):
        p = pf(cash=50_000, equity=100_000,
               positions=[pos("XXX", exit_date=D1, shares=7.0)])
        dec = resolve(TOP10, regime(on=False), p, D1)
        self.assertEqual(len(buys(dec)), 0)
        ex = exits(dec)
        self.assertEqual(len(ex), 1)
        self.assertEqual(ex[0].ticker, "XXX")

    def test_A1b_regime_off_no_positions_do_nothing(self):
        dec = resolve(TOP10, regime(on=False), pf(cash=100_000), D1)
        self.assertEqual(len(dec), 1)
        self.assertEqual(dec[0].action, Action.DO_NOTHING)


class TestSlots(unittest.TestCase):
    def test_A2_portfolio_full_no_buys(self):
        positions = [pos(f"P{i:02d}", exit_date="2026-07-20")
                     for i in range(10)]
        p = pf(cash=10_000, equity=110_000, positions=positions)
        dec = resolve(TOP10, regime(), p, D1)
        self.assertEqual(len(buys(dec)), 0)
        self.assertEqual(dec[0].action, Action.DO_NOTHING)

    def test_A6_free_slots_limits_buys(self):
        positions = [pos(f"P{i:02d}", exit_date="2026-07-20")
                     for i in range(7)]
        p = pf(cash=30_000, equity=100_000, positions=positions)
        dec = resolve(TOP10, regime(), p, D1)
        self.assertEqual(len(buys(dec)), 3)  # 10 - 7

    def test_B4_pending_exit_holds_slot(self):
        # 10 pozic, jedna exituje na close target_date -> slot se uvolni
        # az pro D+2 -> DNES zadne BUY (spec §5.1, §5.3)
        positions = [pos(f"P{i:02d}", exit_date="2026-07-20")
                     for i in range(9)]
        positions.append(pos("EXITING", exit_date=D1))
        p = pf(cash=10_000, equity=110_000, positions=positions)
        dec = resolve(TOP10, regime(), p, D1)
        self.assertEqual(len(buys(dec)), 0)
        self.assertEqual(len(exits(dec)), 1)


class TestExits(unittest.TestCase):
    def test_A3_planned_exit_produces_exit_with_quantity(self):
        p = pf(cash=0, equity=100_000,
               positions=[pos("XXX", exit_date=D1, shares=12.5),
                          pos("YYY", exit_date="2026-07-20", shares=3.0)])
        dec = resolve([], regime(), p, D1)
        ex = exits(dec)
        self.assertEqual(len(ex), 1)
        self.assertEqual(ex[0].ticker, "XXX")
        self.assertEqual(ex[0].quantity, 12.5)
        self.assertEqual(ex[0].price_source, PriceSource.CLOSE)
        self.assertEqual(ex[0].target_date, D1)
        self.assertIsNone(ex[0].target_value)


class TestEntries(unittest.TestCase):
    def test_A4_held_ticker_not_rebought(self):
        p = pf(cash=100_000, equity=110_000,
               positions=[pos("AAA", exit_date="2026-07-20")])
        dec = resolve(TOP10, regime(), p, D1)
        self.assertNotIn("AAA", [d.ticker for d in buys(dec)])

    def test_B5_pending_exit_ticker_not_buyable_same_day(self):
        p = pf(cash=100_000, equity=110_000,
               positions=[pos("AAA", exit_date=D1)])
        dec = resolve(TOP10, regime(), p, D1)
        self.assertNotIn("AAA", [d.ticker for d in buys(dec)])
        self.assertEqual(len(exits(dec)), 1)

    def test_A5_cash_below_target_spend_capped(self):
        # ERRATUM §5.3: cap = cash/(1+ch), shodne s BT-04R golden masterem
        from mle_paper_01.models import COST_HALF
        p = pf(cash=4_000, equity=100_000)  # target = 10_000 > cash
        dec = resolve(TOP10[:1], regime(), p, D1)
        b = buys(dec)
        self.assertEqual(len(b), 1)
        self.assertAlmostEqual(b[0].target_value, 4_000 / (1 + COST_HALF))

    def test_A7_fewer_candidates_than_slots(self):
        p = pf(cash=100_000, equity=100_000)
        dec = resolve(TOP10[:3], regime(), p, D1)
        self.assertEqual(len(buys(dec)), 3)

    def test_B2_candidates_processed_by_rank(self):
        shuffled = [cand("CCC", 3), cand("AAA", 1), cand("BBB", 2)]
        p = pf(cash=100_000, equity=100_000)
        dec = resolve(shuffled, regime(), p, D1)
        b = buys(dec)
        self.assertEqual([d.ticker for d in b], ["AAA", "BBB", "CCC"])
        self.assertEqual(b[0].price_source, PriceSource.NEXT_OPEN)

    def test_B3_cascading_cash_reservation(self):
        # ERRATUM §5.3 / golden master: cash 25k -> 10k, 10k, ~5k/(1+ch),
        # pote rezidualni cash kaskaduje do mikro-nakupu (BT-04R semantika)
        from mle_paper_01.models import COST_HALF
        p = pf(cash=25_000, equity=100_000)
        dec = resolve(TOP10, regime(), p, D1)
        b = buys(dec)
        self.assertAlmostEqual(b[0].target_value, 10_000)
        self.assertAlmostEqual(b[1].target_value, 10_000)
        self.assertAlmostEqual(b[2].target_value, 5_000 / (1 + COST_HALF))
        for later in b[3:]:                      # mikro-kaskada
            self.assertLess(later.target_value, 5.0)
            self.assertGreater(later.target_value, 0.0)
        total = sum(d.target_value for d in b)
        self.assertLessEqual(total, 25_000 + 1e-6)  # nikdy nepretratit cash

    def test_B3b_micro_cascade_matches_golden_master(self):
        # cash < 1 target: prvni BUY ~cash/(1+ch), pak geometricka
        # mikro-kaskada (BT-04R quirk, reprodukovan zamerne)
        from mle_paper_01.models import COST_HALF
        p = pf(cash=10_000, equity=100_000)
        dec = resolve(TOP10, regime(), p, D1)
        b = buys(dec)
        self.assertAlmostEqual(b[0].target_value, 10_000 / (1 + COST_HALF))
        self.assertEqual(len(b), 10)  # kaskada bezi pres vsechny sloty
        total = sum(d.target_value for d in b)
        self.assertLessEqual(total, 10_000 + 1e-6)


class TestPurity(unittest.TestCase):
    def test_B1_determinism_and_no_mutation(self):
        p = pf(cash=25_000, equity=100_000,
               positions=[pos("XXX", exit_date=D1, shares=5.0)])
        r = regime()
        snap = copy.deepcopy(p)
        dec1 = resolve(TOP10, r, p, D1)
        dec2 = resolve(TOP10, r, p, D1)
        self.assertEqual(dec1, dec2)          # determinismus
        self.assertEqual(p, snap)             # vstup nezmutovan
        self.assertEqual(p.cash, 25_000)      # cash_available byla lokalni

    def test_B6_no_action_do_nothing(self):
        dec = resolve([], regime(), pf(cash=100_000), D1)
        self.assertEqual(len(dec), 1)
        self.assertEqual(dec[0].action, Action.DO_NOTHING)

    def test_B7_causality_validation(self):
        bad = RegimeState(date=D1, regime_on=True)  # regime z D+1 = lookahead
        with self.assertRaises(ValueError):
            resolve(TOP10, bad, pf(cash=100_000), D1)


class TestHardening(unittest.TestCase):
    """Hardening z code review architekta (2026-07-14)."""

    def test_H1_state_regime_date_mismatch_raises(self):
        stale_pf = PortfolioState(cash=100_000, equity=100_000,
                                  last_updated_date="2026-07-09")  # != D
        with self.assertRaises(ValueError):
            resolve(TOP10, regime(), stale_pf, D1)

    def test_H2_stale_open_position_raises(self):
        p = pf(cash=0, equity=5_000,
               positions=[pos("OLD", exit_date="2026-07-01")])  # < D1
        with self.assertRaises(ValueError):
            resolve([], regime(), p, D1)

    def test_H3_candidate_rank_out_of_range_raises(self):
        for bad_rank in (0, 11, -3):
            with self.assertRaises(ValueError):
                resolve([cand("BAD", bad_rank)], regime(),
                        pf(cash=100_000), D1)

    def test_H4_decision_contract_invariants(self):
        from mle_paper_01.models import Decision, Action, PriceSource
        with self.assertRaises(ValueError):   # BUY s quantity
            Decision(action=Action.BUY, target_date=D1, reason="r",
                     ticker="A", conid=1, target_value=100.0, quantity=1.0,
                     price_source=PriceSource.NEXT_OPEN)
        with self.assertRaises(ValueError):   # BUY se spatnym price_source
            Decision(action=Action.BUY, target_date=D1, reason="r",
                     ticker="A", conid=1, target_value=100.0,
                     price_source=PriceSource.CLOSE)
        with self.assertRaises(ValueError):   # EXIT bez quantity
            Decision(action=Action.EXIT, target_date=D1, reason="r",
                     ticker="A", conid=1, price_source=PriceSource.CLOSE)
        with self.assertRaises(ValueError):   # EXIT s target_value
            Decision(action=Action.EXIT, target_date=D1, reason="r",
                     ticker="A", conid=1, quantity=1.0, target_value=5.0,
                     price_source=PriceSource.CLOSE)
        with self.assertRaises(ValueError):   # DO_NOTHING s tickerem
            Decision(action=Action.DO_NOTHING, target_date=D1, reason="r",
                     ticker="A")


if __name__ == "__main__":
    unittest.main()
