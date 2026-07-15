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
from pathlib import Path
from typing import List, Sequence

from .models import Action, Decision

CSV_COLUMNS = ["date", "ticker", "conid", "action", "quantity",
               "target_value", "reason", "price_source"]


def plan_rows(decisions: Sequence[Decision]) -> List[dict]:
    """Prevede Decisions na CSV radky (bez zapisu). Validuje jeden den."""
    if not decisions:
        raise ValueError("plan_rows: prazdny seznam Decisions "
                         "(resolver vraci minimalne DO_NOTHING)")
    dates = {d.target_date for d in decisions}
    if len(dates) != 1:
        raise ValueError(f"plan_rows: vice target_date v jednom planu: "
                         f"{sorted(dates)}")
    rows = []
    for d in decisions:
        rows.append({
            "date": d.target_date,
            "ticker": d.ticker or "",
            "conid": d.conid if d.conid is not None else "",
            "action": d.action.value,
            "quantity": _fmt(d.quantity),
            "target_value": _fmt(d.target_value),
            "reason": d.reason,
            "price_source": d.price_source.value if d.price_source else "",
        })
    return rows


def write_orders_plan(decisions: Sequence[Decision], out_dir: Path) -> Path:
    """Zapise orders_plan_YYYY-MM-DD.csv do out_dir. Vraci cestu."""
    rows = plan_rows(decisions)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"orders_plan_{rows[0]['date']}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


def _fmt(value) -> str:
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")
