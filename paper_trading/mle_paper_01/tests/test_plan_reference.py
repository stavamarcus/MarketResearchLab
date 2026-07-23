"""Plan reference contract tests (architekt 2026-07-23).

To, co system spocita jako plan, musi existovat i jako strojovy kontrakt,
ne pouze jako tabulka pro cloveka.
"""
import csv
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from mle_paper_01 import capital_feasibility as cf
from mle_paper_01 import manual_report as mr
from mle_paper_01.fills import matcher
from mle_paper_01.fills.states import ImportError_
from mle_paper_01.models import (Action, Decision, PriceSource, RegimeState,
                                 SignalCandidate)
from mle_paper_01.order_planner import (CSV_COLUMNS, PLAN_REFERENCE_COLUMNS,
                                        plan_rows, write_orders_plan)
from mle_paper_01.portfolio_state import PortfolioState

D = "2026-07-21"
D1 = "2026-07-22"
EXIT_DATE = "2026-08-05"


def buy(ticker, conid, target_value=3000.0):
    return Decision(action=Action.BUY, target_date=D1, reason="rank_1",
                    ticker=ticker, conid=conid, target_value=target_value,
                    price_source=PriceSource.NEXT_OPEN)


def exit_dec(ticker, conid, qty):
    return Decision(action=Action.EXIT, target_date=D1,
                    reason="planned_exit_hold10", ticker=ticker, conid=conid,
                    quantity=qty, price_source=PriceSource.CLOSE)


def feas(buys, refs, equity=30000.0, cash=30000.0):
    return cf.evaluate_plan(equity=equity, available_cash_for_buys=cash,
                            buys=buys, ref_prices=refs)


def rows_for(buys, refs, **kw):
    return plan_rows(buys, feasibility=feas(buys, refs), ref_price_date=D,
                     planned_exit_if_filled=EXIT_DATE, **kw)


# ------------------------------------------------------------------ schema
def test_new_columns_present():
    r = rows_for([buy("AAA", 1)], {"AAA": 200.0})[0]
    assert list(r.keys()) == CSV_COLUMNS
    for c in PLAN_REFERENCE_COLUMNS:
        assert c in r


def test_quantity_no_longer_empty_for_executable_buy():
    r = rows_for([buy("AAA", 1)], {"AAA": 200.0})[0]
    assert r["quantity"] not in ("", "0"), "planovane mnozstvi musi byt v planu"
    # sizing pocita s nakladovym polstarem (COST_HALF), takze 14, ne 3000/200
    expected = feas([buy("AAA", 1)], {"AAA": 200.0}).per_buy[0].indicative_qty
    assert Decimal(r["quantity"]) == Decimal(expected)


def test_ref_price_date_is_source_session():
    r = rows_for([buy("AAA", 1)], {"AAA": 200.0})[0]
    assert r["ref_price_date"] == D
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["ref_price_date"])


def test_buy_has_planned_exit():
    r = rows_for([buy("AAA", 1)], {"AAA": 200.0})[0]
    assert r["planned_exit_if_filled"] == EXIT_DATE


def test_irrelevant_fields_are_empty_not_zero():
    """Nula je hodnota, prazdno je 'neplati'. Splynuti by vypadalo jako strop 0."""
    rows = plan_rows([exit_dec("XXX", 9, Decimal("12.5"))],
                     ref_price_date=D, planned_exit_if_filled=EXIT_DATE)
    r = rows[0]
    for c in ("ref_price", "ref_price_date", "max_price_for_qty",
              "planned_exit_if_filled"):
        assert r[c] == "", f"{c} ma byt prazdne, ne {r[c]!r}"
    assert r["quantity"] == "12.5"          # EXIT qty je z resolveru


def test_non_executable_buy_has_no_price_cap():
    rows = rows_for([buy("AAA", 1, 3000.0)], {})       # bez ref ceny
    assert rows[0]["max_price_for_qty"] == ""
    assert rows[0]["quantity"] == ""


def test_decimal_not_prematurely_rounded():
    price = Decimal("199.85014277")
    rows = plan_rows([buy("AAA", 1)],
                     feasibility=feas([buy("AAA", 1)], {"AAA": float(price)}),
                     ref_price_date=D, planned_exit_if_filled=EXIT_DATE)
    cap = rows[0]["max_price_for_qty"]
    assert len(cap.split(".")[1]) > 2, f"strop zaokrouhlen: {cap}"


def test_legacy_plan_without_new_columns_still_readable(tmp_path):
    p = tmp_path / "orders_plan_old.csv"
    p.write_text("date,ticker,conid,action,quantity,target_value,reason,"
                 "price_source\n2026-07-22,AAA,1,BUY,,3000,rank_1,close\n",
                 encoding="utf-8")
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert rows[0]["quantity"] == ""
    assert "ref_price" not in rows[0]


# ------------------------------------------------------- parita CSV/markdown
def _render(buys, refs, rows):
    st = PortfolioState(cash=30000.0, equity=30000.0, last_updated_date=D,
                        positions=(), closed_trades=())
    cands = [SignalCandidate(ticker=b.ticker, conid=b.conid, rank_10d=i + 1)
             for i, b in enumerate(buys)]
    return mr.render_report(
        business_date=D, target_date=D1,
        regime=RegimeState(date=D, regime_on=True, index_level=100.0,
                           ma200=90.0),
        state=st, candidates=cands, decisions=buys, warnings=[], errors=[],
        account_label="DU-PAPER", mode="paper_manual",
        data_source_meta={"data_source": "MDSM"}, orders_plan_path=None,
        feasibility=feas(buys, refs), estimated_exit_if_filled=EXIT_DATE,
        plan_rows=rows)


def test_csv_and_markdown_agree_per_ticker():
    """Oba vystupy musi vychazet z tychz plan-row objektu."""
    buys = [buy("AAA", 1), buy("BBB", 2)]
    refs = {"AAA": 200.0, "BBB": 61.19}
    rows = rows_for(buys, refs)
    txt = _render(buys, refs, rows)

    # tabulka je zarovnana mezerami, proto se porovnavaji orizle bunky
    table = [[c.strip() for c in l.split("|")] for l in txt.splitlines()
             if l.startswith("|") and "DO NOT BUY" not in l]
    for r in rows:
        cells = next(c for c in table if r["ticker"] in c)
        assert r["ref_price"] in cells, f"{r['ticker']} ref_price"
        assert r["quantity"] in cells, f"{r['ticker']} quantity"
        assert r["max_price_for_qty"] in cells, f"{r['ticker']} cap"
        assert r["planned_exit_if_filled"] in cells, f"{r['ticker']} exit"


def test_markdown_has_no_second_computation_path():
    """Kdyz plan-rows rekne jine cislo, markdown ho musi prevzit."""
    buys = [buy("AAA", 1)]
    refs = {"AAA": 200.0}
    rows = rows_for(buys, refs)
    rows[0]["max_price_for_qty"] = "111.111111"
    txt = _render(buys, refs, rows)
    assert "111.111111" in txt


# --------------------------------------------------------------- section 9
def test_report_has_no_manual_ticket_instruction():
    buys = [buy("AAA", 1)]
    txt = _render(buys, {"AAA": 200.0}, rows_for(buys, {"AAA": 200.0}))
    for gone in ("Fill recording template", "fill in AFTER execution",
                 "record actual fills on the ticket",
                 "Record each actual fill"):
        assert gone not in txt, gone
    assert "Import broker fills" in txt
    assert "Do not edit it by hand" in txt


# ------------------------------------------------- plan vs ticket quantity
def _plan_row(ticker, conid, qty=""):
    return {"date": D1, "ticker": ticker, "conid": str(conid), "action": "BUY",
            "quantity": qty, "target_value": "3000", "reason": "rank_1",
            "price_source": "close", "ref_price": "200",
            "ref_price_date": D, "max_price_for_qty": "205",
            "planned_exit_if_filled": EXIT_DATE}


def _ticket_row(ticker, conid, qty):
    return {"target_date": D1, "ticker": ticker, "conid": str(conid),
            "side": "BUY", "planned_quantity": str(qty)}


def _group(ticker, conid, qty, perm="P1"):
    return {"perm_id": perm, "order_id": "0", "account": "DUQ1", "ticker": ticker,
            "conid": conid, "sec_type": "STK", "currency": "USD", "side": "BUY",
            "broker_side": "BOT", "session": D1,
            "total_quantity": Decimal(qty), "gross_notional": Decimal(qty) * 200,
            "commission_total": Decimal("1"), "commission_currency": "USD",
            "avg_fill_price": Decimal("200"),
            "first_fill_timestamp": f"{D1}T11:00:00-04:00",
            "last_fill_timestamp": f"{D1}T11:00:00-04:00",
            "execution_ids": ["E1"], "executions": []}


def test_plan_quantity_is_authoritative():
    matched, _ = matcher.match([_group("AAA", 1, 15)], [_plan_row("AAA", 1, "15")],
                               [_ticket_row("AAA", 1, 15)], "DUQ1")
    assert len(matched) == 1


def test_plan_ticket_quantity_mismatch_blocks():
    with pytest.raises(ImportError_) as e:
        matcher.match([_group("AAA", 1, 15)], [_plan_row("AAA", 1, "15")],
                      [_ticket_row("AAA", 1, 14)], "DUQ1")
    assert e.value.code == "PLAN_TICKET_QUANTITY_MISMATCH"


def test_legacy_plan_falls_back_to_ticket_quantity():
    """Stary plan s prazdnou quantity musi dal fungovat pres ticket."""
    matched, _ = matcher.match([_group("AAA", 1, 15)], [_plan_row("AAA", 1, "")],
                               [_ticket_row("AAA", 1, 15)], "DUQ1")
    assert len(matched) == 1
    with pytest.raises(ImportError_) as e:
        matcher.match([_group("AAA", 1, 16)], [_plan_row("AAA", 1, "")],
                      [_ticket_row("AAA", 1, 15)], "DUQ1")
    assert e.value.code == "QUANTITY_OVER_PLAN"


# ------------------------------------------------------------- neutralita
def test_plan_reference_does_not_change_decisions():
    """Stejny vstup, stejny vyber jmen, sizing i exit."""
    buys = [buy("AAA", 1), buy("BBB", 2)]
    refs = {"AAA": 200.0, "BBB": 61.19}
    plain = plan_rows(buys)
    rich = rows_for(buys, refs)
    for a, b in zip(plain, rich):
        for f in ("date", "ticker", "conid", "action", "target_value",
                  "reason", "price_source"):
            assert a[f] == b[f], f


# =================================================== P5 doplneni (architekt)
# a) quantity u VSECH executable radku, ne jen BUY
# b) obousmerna one-to-one kontrola plan vs ticket
# c) zdroj oddeleny od uplnosti, diagnostika per radek

def test_exit_row_has_quantity():
    """Bod (a): SELL/EXIT musi mit planovane mnozstvi taky."""
    rows = plan_rows([exit_dec("PYPL", 199169591, Decimal("53"))],
                     ref_price_date=D, planned_exit_if_filled=EXIT_DATE)
    assert rows[0]["action"] == "EXIT"
    assert Decimal(rows[0]["quantity"]) == Decimal(53)


def test_buy_and_exit_both_have_quantity():
    buys = [buy("AAA", 1)]
    decs = buys + [exit_dec("BBB", 2, Decimal("7"))]
    rows = plan_rows(decs, feasibility=feas(buys, {"AAA": 200.0}),
                     ref_price_date=D, planned_exit_if_filled=EXIT_DATE)
    by = {r["ticker"]: r for r in rows}
    assert by["AAA"]["quantity"] not in ("", "0")
    assert Decimal(by["BBB"]["quantity"]) == Decimal(7)


# ------------------------------------------- b) one-to-one plan vs ticket
def _p(ticker, conid, action="BUY", qty="15", p5=True):
    r = {"date": D1, "ticker": ticker, "conid": str(conid), "action": action,
         "quantity": qty, "target_value": "3000", "reason": "rank_1",
         "price_source": "next_open"}
    if p5:
        r.update({"ref_price": "200", "ref_price_date": D,
                  "max_price_for_qty": "205",
                  "planned_exit_if_filled": EXIT_DATE})
    return r


def _t(ticker, conid, side="BUY", qty="15"):
    return {"target_date": D1, "ticker": ticker, "conid": str(conid),
            "side": side, "planned_quantity": qty}


def contract(plan, ticket):
    matcher.check_plan_ticket_contract(plan, ticket)


def test_contract_passes_when_one_to_one():
    contract([_p("AAA", 1), _p("BBB", 2, qty="7")],
             [_t("AAA", 1), _t("BBB", 2, qty="7")])


def test_plan_row_missing_in_ticket():
    with pytest.raises(ImportError_) as e:
        contract([_p("AAA", 1), _p("BBB", 2)], [_t("AAA", 1)])
    assert e.value.code == "PLAN_ROW_MISSING_IN_TICKET"


def test_ticket_row_not_in_plan():
    with pytest.raises(ImportError_) as e:
        contract([_p("AAA", 1)], [_t("AAA", 1), _t("BBB", 2)])
    assert e.value.code == "TICKET_ROW_NOT_IN_PLAN"


def test_duplicate_plan_row():
    with pytest.raises(ImportError_) as e:
        contract([_p("AAA", 1), _p("AAA", 1)], [_t("AAA", 1)])
    assert e.value.code == "DUPLICATE_PLAN_ROW"


def test_duplicate_ticket_row():
    with pytest.raises(ImportError_) as e:
        contract([_p("AAA", 1)], [_t("AAA", 1), _t("AAA", 1)])
    assert e.value.code == "DUPLICATE_TICKET_ROW"


def test_contract_quantity_mismatch():
    with pytest.raises(ImportError_) as e:
        contract([_p("AAA", 1, qty="15")], [_t("AAA", 1, qty="14")])
    assert e.value.code == "PLAN_TICKET_QUANTITY_MISMATCH"


def test_contract_identity_is_conid_not_ticker():
    """Ticker je krizova kontrola, conid je identita."""
    with pytest.raises(ImportError_) as e:
        contract([_p("AAA", 1)], [_t("RENAMED", 1)])
    assert e.value.code == "TICKER_CONID_MISMATCH"


def test_contract_covers_exit_rows_too():
    contract([_p("AAA", 1, action="EXIT", qty="53")],
             [_t("AAA", 1, side="EXIT", qty="53")])
    with pytest.raises(ImportError_) as e:
        contract([_p("AAA", 1, action="EXIT", qty="53")],
                 [_t("AAA", 1, side="EXIT", qty="52")])
    assert e.value.code == "PLAN_TICKET_QUANTITY_MISMATCH"


def test_contract_ignores_non_executable_rows():
    """DO_NOTHING a nulove mnozstvi do kontraktu nepatri."""
    plan = [_p("AAA", 1),
            _p("ZZZ", 9, action="DO_NOTHING", qty=""),
            _p("QQQ", 8, qty="0")]
    contract(plan, [_t("AAA", 1)])


def test_contract_skipped_for_legacy_plan():
    """Stary plan bez plan-reference sloupcu zustava v legacy rezimu."""
    contract([_p("AAA", 1, p5=False), _p("BBB", 2, p5=False)], [_t("AAA", 1)])


# ------------------------------------------------- c) source vs completeness
def _artifact_fields(plan, matched_tickers=("AAA",)):
    """Spocita completeness stejnou logikou jako importer."""
    from mle_paper_01.fills.states import (COMPLETENESS_FULL,
                                           COMPLETENESS_NONE,
                                           COMPLETENESS_PARTIAL)
    if not matcher.is_p5_plan(plan):
        return COMPLETENESS_NONE, 0, 0
    rows = [r for r in plan if r["ticker"] in matched_tickers]
    n = len(rows)
    have_ref = sum(1 for r in rows if (r.get("ref_price") or "").strip())
    have_cap = sum(1 for r in rows if (r.get("max_price_for_qty") or "").strip())
    if n and have_ref == n and have_cap == n:
        return COMPLETENESS_FULL, 0, 0
    if have_ref or have_cap:
        return COMPLETENESS_PARTIAL, n - have_ref, n - have_cap
    return COMPLETENESS_NONE, n - have_ref, n - have_cap


def test_completeness_full():
    c, mr_, mc = _artifact_fields([_p("AAA", 1)])
    assert c == "FULL" and mr_ == 0 and mc == 0


def test_completeness_partial():
    row = _p("AAA", 1)
    row["max_price_for_qty"] = ""
    c, mr_, mc = _artifact_fields([row])
    assert c == "PARTIAL" and mc == 1 and mr_ == 0


def test_completeness_none_for_legacy_plan():
    c, _, _ = _artifact_fields([_p("AAA", 1, p5=False)])
    assert c == "NONE"


def test_partial_reference_still_computes_available_rows():
    """Chybejici hodnota u jednoho radku nesmi zablokovat ostatni."""
    full = _p("AAA", 1)
    partial = _p("BBB", 2)
    partial["max_price_for_qty"] = ""
    plan = [full, partial]
    c, _, mc = _artifact_fields(plan, matched_tickers=("AAA", "BBB"))
    assert c == "PARTIAL" and mc == 1
    # radek s hodnotou ji ma dal
    assert full["max_price_for_qty"] == "205"
