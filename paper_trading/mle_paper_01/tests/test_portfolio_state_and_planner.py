"""
test_portfolio_state_and_planner.py — unit testy stavove vrstvy a planneru.

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md §8, §9, §5.4.

Spusteni (z MarketResearchLab/paper_trading/):
    python -m unittest mle_paper_01.tests.test_portfolio_state_and_planner -v

Pokryti:
  S1  BUY fill: quantity = spend/(open*(1+7.5bps)), cash presne o spend
  S2  EXIT fill: proceeds, pnl vc. vstupnich nakladu, pozice -> closed_trades
  S3  round-trip pnl na nulovem pohybu ceny = presne -15 bps
  S4  vstupni stav nezmutovan (funkcionalni operace)
  S5  mark_to_market: equity = cash + sum(shares*close); fallback entry cena
  S6  invarianty: 11. pozice / duplicitni ticker / zaporny cash -> ValueError
  S7  BUY prekracujici cash -> ValueError (resolver mel omezit)
  S8  EXIT s nesouhlasnym quantity -> ValueError
  S9  save/load JSON roundtrip (identicky stav)
  P1  planner: sloupce, BUY radek s target_value, EXIT s quantity
  P2  planner: DO_NOTHING auditni radek
  P3  planner: vice target_date v planu -> ValueError
  P4  planner: nazev souboru orders_plan_YYYY-MM-DD.csv, prepis idempotentni
"""
from __future__ import annotations

import copy
import csv
import tempfile
import unittest
from pathlib import Path

from mle_paper_01.models import (Action, Decision, PortfolioState, Position,
                                 PriceSource)
from mle_paper_01.portfolio_state import (COST_HALF, apply_buy_fill,
                                          apply_exit_fill, load_state,
                                          mark_to_market, save_state,
                                          validate_state)
from mle_paper_01.order_planner import plan_rows, write_orders_plan

D1 = "2026-07-13"
DX = "2026-07-27"


def buy_dec(ticker="AAA", value=10_000.0, rank=1):
    return Decision(action=Action.BUY, target_date=D1,
                    reason=f"mle_top10_rank_{rank}", ticker=ticker,
                    conid=111, target_value=value,
                    price_source=PriceSource.NEXT_OPEN)


def exit_dec(ticker="AAA", qty=None):
    return Decision(action=Action.EXIT, target_date=DX,
                    reason="planned_exit_hold10", ticker=ticker, conid=111,
                    quantity=qty, price_source=PriceSource.CLOSE)


def pos(ticker="AAA", shares=50.0, entry=100.0):
    return Position(ticker=ticker, conid=111, shares=shares,
                    entry_date=D1, entry_price=entry,
                    planned_exit_date=DX, signal_rank=1)


class TestFills(unittest.TestCase):
    def test_S1_buy_fill_quantity_and_cash(self):
        st = PortfolioState(cash=100_000, equity=100_000)
        new = apply_buy_fill(st, buy_dec(value=10_000), fill_price=200.0,
                             fill_date=D1, planned_exit_date=DX)
        expected_qty = 10_000 / (200.0 * (1 + COST_HALF))
        self.assertEqual(len(new.open_positions()), 1)
        self.assertAlmostEqual(new.open_positions()[0].shares, expected_qty)
        self.assertAlmostEqual(new.cash, 90_000)  # cash presne o spend
        self.assertEqual(new.open_positions()[0].planned_exit_date, DX)
        self.assertEqual(new.open_positions()[0].signal_rank, 1)

    def test_S2_exit_fill_proceeds_pnl_closed(self):
        st = PortfolioState(cash=0, equity=5_500,
                            positions=(pos(shares=50, entry=100.0),))
        new = apply_exit_fill(st, exit_dec(qty=50.0), fill_price=110.0,
                              fill_date=DX)
        proceeds = 50 * 110.0 * (1 - COST_HALF)
        cost_in = 50 * 100.0 * (1 + COST_HALF)
        self.assertAlmostEqual(new.cash, proceeds)
        self.assertEqual(len(new.open_positions()), 0)
        self.assertEqual(len(new.closed_trades), 1)
        self.assertAlmostEqual(new.closed_trades[0].pnl,
                               proceeds - cost_in, places=4)

    def test_S3_round_trip_cost_exact_15bps(self):
        st = PortfolioState(cash=10_000, equity=10_000)
        st = apply_buy_fill(st, buy_dec(value=10_000), fill_price=100.0,
                            fill_date=D1, planned_exit_date=DX)
        qty = st.open_positions()[0].shares
        st = apply_exit_fill(st, exit_dec(qty=qty), fill_price=100.0,
                             fill_date=DX)
        # cena beze zmeny -> ztrata = presny round-trip naklad KONVENCE
        # backtestu: buy*(1+ch), sell*(1-ch) -> 1-(1-ch)/(1+ch) ~ 14.9888 bps
        loss_bps = (10_000 - st.cash) / 10_000 * 10_000
        expected_bps = (1 - (1 - COST_HALF) / (1 + COST_HALF)) * 10_000
        self.assertAlmostEqual(loss_bps, expected_bps, places=6)
        self.assertAlmostEqual(loss_bps, 15.0, places=1)  # ~15 bps

    def test_S4_input_state_not_mutated(self):
        st = PortfolioState(cash=100_000, equity=100_000)
        snap = copy.deepcopy(st)
        apply_buy_fill(st, buy_dec(), fill_price=200.0, fill_date=D1,
                       planned_exit_date=DX)
        self.assertEqual(st, snap)

    def test_S7_buy_exceeding_cash_raises(self):
        st = PortfolioState(cash=5_000, equity=100_000)
        with self.assertRaises(ValueError):
            apply_buy_fill(st, buy_dec(value=10_000), fill_price=200.0,
                           fill_date=D1, planned_exit_date=DX)

    def test_S8_exit_quantity_mismatch_raises(self):
        st = PortfolioState(cash=0, equity=5_000,
                            positions=(pos(shares=50.0),))
        with self.assertRaises(ValueError):
            apply_exit_fill(st, exit_dec(qty=49.0), fill_price=100.0,
                            fill_date=DX)


class TestMarkAndInvariants(unittest.TestCase):
    def test_S5_mark_to_market_and_fallback(self):
        st = PortfolioState(cash=1_000, equity=0,
                            positions=(pos("AAA", shares=10, entry=100.0),
                                       pos("BBB", shares=5, entry=40.0)))
        new = mark_to_market(st, {"AAA": 120.0}, date=DX)  # BBB chybi
        self.assertAlmostEqual(new.equity, 1_000 + 10 * 120.0 + 5 * 40.0)
        self.assertEqual(new.last_updated_date, DX)

    def test_S6_invariants_raise(self):
        eleven = tuple(pos(f"T{i:02d}") for i in range(11))
        with self.assertRaises(ValueError):
            validate_state(PortfolioState(cash=0, equity=0,
                                          positions=eleven))
        dup = (pos("AAA"), pos("AAA"))
        with self.assertRaises(ValueError):
            validate_state(PortfolioState(cash=0, equity=0, positions=dup))
        with self.assertRaises(ValueError):
            validate_state(PortfolioState(cash=-1.0, equity=0))


class TestPersistence(unittest.TestCase):
    def test_S9_save_load_roundtrip(self):
        st = PortfolioState(cash=12_345.67, equity=20_000,
                            positions=(pos("AAA", shares=12.5),),
                            last_updated_date=D1)
        st = apply_exit_fill(
            PortfolioState(cash=st.cash, equity=st.equity,
                           positions=st.positions,
                           last_updated_date=D1),
            exit_dec(qty=12.5), fill_price=105.0, fill_date=DX)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            save_state(st, p)
            loaded = load_state(p)
        self.assertEqual(st, loaded)


class TestOrderPlanner(unittest.TestCase):
    def test_P1_columns_and_values(self):
        decs = [buy_dec("AAA", 10_000, rank=1),
                Decision(action=Action.EXIT, target_date=D1,
                         reason="planned_exit_hold10", ticker="XXX",
                         conid=999, quantity=12.5,
                         price_source=PriceSource.CLOSE)]
        rows = plan_rows(decs)
        # ZMENENO: schema rozsireno o strojove citelna plan-reference pole.
        # Driv zily ref_price a max_price_for_qty jen v markdown reportu,
        # takze je reconcile ani importer nemely odkud vzit.
        self.assertEqual(list(rows[0].keys()),
                         ["date", "ticker", "conid", "action", "quantity",
                          "target_value", "reason", "price_source",
                          "ref_price", "ref_price_date", "max_price_for_qty",
                          "planned_exit_if_filled"])
        b, e = rows[0], rows[1]
        self.assertEqual((b["action"], b["target_value"], b["quantity"]),
                         ("BUY", "10000", ""))
        self.assertEqual(b["price_source"], "next_open")
        self.assertEqual((e["action"], e["quantity"], e["target_value"]),
                         ("EXIT", "12.5", ""))
        self.assertEqual(e["price_source"], "close")

    def test_P2_do_nothing_audit_row(self):
        rows = plan_rows([Decision(action=Action.DO_NOTHING,
                                   target_date=D1, reason="no_action")])
        self.assertEqual(rows[0]["action"], "DO_NOTHING")
        self.assertEqual(rows[0]["ticker"], "")

    def test_P3_mixed_dates_raise(self):
        with self.assertRaises(ValueError):
            plan_rows([buy_dec(), Decision(action=Action.DO_NOTHING,
                                           target_date=DX, reason="x")])

    def test_P4_filename_and_idempotent_rewrite(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = write_orders_plan([buy_dec()], Path(td))
            self.assertEqual(p1.name, f"orders_plan_{D1}.csv")
            p2 = write_orders_plan([buy_dec()], Path(td))  # prepis
            self.assertEqual(p1, p2)
            with p1.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["ticker"], "AAA")


if __name__ == "__main__":
    unittest.main()
