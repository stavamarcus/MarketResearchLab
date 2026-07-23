"""
order_planner.py — MLE-PAPER-01 order planner (Faze 1).

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md §5.4, C-4.

Z listu Decision vyrobi denni order plan:
    orders_plan_YYYY-MM-DD.csv

Sloupce (dle architektury + C-4 uprava kontraktu 2.4):
    date,ticker,conid,action,quantity,target_value,reason,price_source
  - BUY:  target_value vyplneno, quantity prazdne (urci se az z open
          ceny D+1 pri fillu — spec §9)
  - EXIT: quantity vyplneno (drzene shares), target_value prazdne
  - DO_NOTHING: jen date,action,reason (auditni radek — den bez akce
    je taky rozhodnuti a musi byt dohledatelny)

Edge cases / predpoklady:
  - vsechny Decisions v jednom volani musi mit shodny target_date
    (jeden plan = jeden den) — fail-fast pri poruseni.
  - existujici soubor pro tyz den se prepise (re-run tehoz dne je
    idempotentni; historie behu patri do logu, ne do planu).
  - CSV bez uvozovek/carek v datech (tickery a reasons je neobsahuji);
    pouziva se csv modul, takze pripadne vyjimky se escapuji korektne.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import List, Sequence

from .models import Action, Decision

# Puvodni sloupce (kontrakt 2.4) + strojove citelna plan-reference pole.
# Pole pribyla proto, ze ref_price a max_price_for_qty driv existovaly VYHRADNE
# v markdown reportu urcenem pro cloveka. Reconcile a importer je tim padem
# nemely odkud vzit a PRICE_CAP_EXCEEDED / PLAN_PRICE_DEVIATION se nedaly
# spocitat (viz FANG 2026-07-22: strop 199.8501, fill 202.81, nikdo si toho
# nevsiml). Parsovat markdown je nepripustne - prehozeny sloupec by tise
# zmenil vysledek.
CSV_COLUMNS = ["date", "ticker", "conid", "action", "quantity",
               "target_value", "reason", "price_source",
               "ref_price", "ref_price_date", "max_price_for_qty",
               "planned_exit_if_filled"]

# Pole, jejichz pritomnost odlisuje novy plan od starsiho (legacy) formatu.
PLAN_REFERENCE_COLUMNS = ("ref_price", "ref_price_date", "max_price_for_qty",
                          "planned_exit_if_filled")


def plan_rows(decisions: Sequence[Decision], feasibility=None,
              ref_price_date: str | None = None,
              planned_exit_if_filled: str | None = None) -> List[dict]:
    """Prevede Decisions na radky planu (bez zapisu). Validuje jeden den.

    JEDINE misto, kde plan-row vznika. CSV i markdown musi cist odsud, aby
    mezi nimi nemohl vzniknout rozdil - druha vypocetni cesta je presne to,
    co by se casem tise rozesla.

    Nerelevantni pole zustavaji PRAZDNA, nikdy 0: nula je hodnota, prazdno
    je "neplati", a splynuti tech dvou by pozdeji vypadalo jako strop 0.
    """
    if not decisions:
        raise ValueError("plan_rows: prazdny seznam Decisions "
                         "(resolver vraci minimalne DO_NOTHING)")
    dates = {d.target_date for d in decisions}
    if len(dates) != 1:
        raise ValueError(f"plan_rows: vice target_date v jednom planu: "
                         f"{sorted(dates)}")
    fb = {b.ticker: b for b in feasibility.per_buy} if feasibility else {}
    rows = []
    for d in decisions:
        is_buy = d.action == Action.BUY
        b = fb.get(d.ticker) if is_buy else None
        # quantity: BUY dostava planovane cele mnozstvi z feasibility
        # (driv zustavalo prazdne a jedinym zdrojem byl ticket).
        qty = d.quantity
        if is_buy and b is not None and b.executable:
            qty = b.indicative_qty
        rows.append({
            "date": d.target_date,
            "ticker": d.ticker or "",
            "conid": d.conid if d.conid is not None else "",
            "action": d.action.value,
            "quantity": _fmt(qty),
            "target_value": _fmt(d.target_value),
            "reason": d.reason,
            "price_source": d.price_source.value if d.price_source else "",
            "ref_price": _fmt(b.ref_price) if b else "",
            "ref_price_date": (ref_price_date or "") if b else "",
            "max_price_for_qty": (_fmt(b.max_price_for_estimated_qty)
                                  if b and b.executable else ""),
            "planned_exit_if_filled": ((planned_exit_if_filled or "")
                                       if is_buy else ""),
        })
    return rows


def write_orders_plan(decisions: Sequence[Decision], out_dir: Path,
                      feasibility=None, ref_price_date: str | None = None,
                      planned_exit_if_filled: str | None = None,
                      rows: List[dict] | None = None) -> Path:
    """Zapise orders_plan_YYYY-MM-DD.csv do out_dir. Vraci cestu.

    `rows` umoznuje predat uz spocitane plan-rows, aby CSV a markdown
    vychazely doslova z tychz objektu.
    """
    if rows is None:
        rows = plan_rows(decisions, feasibility, ref_price_date,
                         planned_exit_if_filled)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"orders_plan_{rows[0]['date']}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


def _fmt(value) -> str:
    """Cislo do CSV bez predcasneho zaokrouhleni.

    Decimal se zapise presne tak, jak prisel - zaokrouhleni na 6 mist by
    u cenovych stropu zahodilo informaci, kterou pozdeji porovnava
    PRICE_CAP_EXCEEDED.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, int):
        return str(value)
    return f"{value:.6f}".rstrip("0").rstrip(".")
