"""manual_report.py — Daily Trade Plan (render-only manual workflow).

Renders the SAME order_plan / DecisionResolver output + Capital Feasibility Gate
+ local PortfolioState into a human-readable **Daily Trade Plan** so the strategy
is tradable by hand. Adds NO strategy logic and performs NO discretionary ticker
selection — every line derives deterministically from the decisions, the
marked-to-market state, the regime, the signal candidates and the feasibility
report the runner already produced.

Render-only: no broker, no order submission, no state mutation. Calendar-derived
values (estimated exit-if-filled, hold days-remaining) are computed by the runner
and passed in; this module does no calendar logic itself.

Timing (frozen strategy): BUY = target_date OPEN; EXIT = planned_exit_date CLOSE.
Concrete order_type is TBD until the execution spec — no MOO/MOC pre-locked here.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .models import Action, Decision, PortfolioState, RegimeState, SignalCandidate

# BUY entered at target_date (D+1) open; EXIT sold at planned_exit_date close.
_BUY_TIMING = "target_date open"
_EXIT_TIMING = "planned_exit_date close"
_ORDER_TYPE_TBD = "TBD (per execution spec)"

# Ticket CSV: planning context + BLANK actual-fill columns for manual entry.
TICKET_COLUMNS = [
    # planning context (from the plan) --------------------------------
    "target_date", "ticker", "conid", "side", "planned_quantity",
    "order_timing", "order_type",
    # BLANK — fill in AFTER manual execution (reconciled later) --------
    "actual_fill_price", "actual_quantity", "timestamp",
    "commission_fees", "order_id", "status",
]


def _align_md_tables(lines):
    """Pad markdown table cells so columns line up when the report is read as
    raw text (e.g. in an editor). PURELY COSMETIC: cell values, column counts
    and markdown validity are unchanged; numeric columns are right-aligned so
    prices and quantities line up."""
    def is_row(ln):
        t = ln.strip()
        return len(t) > 1 and t.startswith("|") and t.endswith("|")

    def cells(ln):
        return [c.strip() for c in ln.strip()[1:-1].split("|")]

    def is_sep(ln):
        cs = cells(ln)
        return bool(cs) and all(c and set(c) <= set("-:") for c in cs)

    def is_num(v):
        try:
            float(v)
            return True
        except ValueError:
            return False

    out, i, n = [], 0, len(lines)
    while i < n:
        if not is_row(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        block = []
        while i < n and is_row(lines[i]):
            block.append(lines[i])
            i += 1
        grid = [(cells(ln), is_sep(ln)) for ln in block]
        width = max(len(c) for c, _ in grid)
        grid = [(c + [""] * (width - len(c)), sep) for c, sep in grid]
        data = [c for c, sep in grid if not sep]
        colw = [max([len(r[j]) for r in data] or [0]) for j in range(width)]
        colw = [max(w, 3) for w in colw]
        # right-align a column when every non-empty body cell is numeric
        right = []
        for j in range(width):
            vals = [r[j] for r in data[1:] if r[j] != ""]
            right.append(bool(vals) and all(is_num(v) for v in vals))
        for c, sep in grid:
            if sep:
                out.append("|" + "|".join("-" * (colw[j] + 2)
                                          for j in range(width)) + "|")
            else:
                out.append("| " + " | ".join(
                    (c[j].rjust(colw[j]) if right[j] else c[j].ljust(colw[j]))
                    for j in range(width)) + " |")
    return out


def render_report(*, business_date: str, target_date: str,
                  regime: RegimeState, state: PortfolioState,
                  candidates: Sequence[SignalCandidate],
                  decisions: Sequence[Decision],
                  warnings: Sequence[str], errors: Sequence[str],
                  account_label: str, mode: str,
                  data_source_meta: dict,
                  orders_plan_path: str | None,
                  feasibility=None,
                  run_id: str | None = None,
                  strategy_id: str = "MLE-REGIME200-HOLD10-01",
                  portfolio_state_source: str | None = None,
                  estimated_exit_if_filled: str | None = None,
                  holds_days_remaining: Optional[Dict[str, int]] = None,
                  max_positions: int = 10,
                  plan_rows: Optional[Sequence[dict]] = None) -> str:
    """Render the Daily Trade Plan as Markdown (deterministic, render-only)."""
    buys = [d for d in decisions if d.action == Action.BUY]
    exits = [d for d in decisions if d.action == Action.EXIT]
    do_nothing = [d for d in decisions if d.action == Action.DO_NOTHING]
    exit_tickers = {d.ticker for d in exits}

    open_pos = list(state.open_positions())
    holds = [p for p in open_pos if p.ticker not in exit_tickers]
    rank_of = {c.ticker: c.rank_10d for c in candidates}
    fb = {b.ticker: b for b in feasibility.per_buy} if feasibility else {}
    # Sekce 4 se renderuje z TYCHZ plan-row objektu, ze kterych vznika CSV.
    # Kdyz je volajici neposle (starsi volani), pouzije se feasibility jako
    # fallback - nikdy ne druha vlastni vypocetni cesta.
    pr = {r["ticker"]: r for r in (plan_rows or []) if r.get("ticker")}
    days_rem = holds_days_remaining or {}

    bought = {d.ticker for d in buys}
    held = {p.ticker for p in open_pos}
    not_entered = []
    for c in sorted(candidates, key=lambda x: x.rank_10d):
        if c.ticker in bought:
            continue
        if not regime.regime_on:
            reason = "regime_off"
        elif c.ticker in held:
            reason = "already_held"
        else:
            reason = "not_selected (slots/cash cascade)"
        not_entered.append((c, reason))

    L: List[str] = []
    L.append(f"# Daily Trade Plan — {account_label}")
    L.append("")
    if mode == "dry_run":
        L.append("> **DRY_RUN ONLY - DO NOT PLACE REAL ORDERS.** This plan is "
                 "a rendering for review; do not execute unless the run mode is "
                 "explicitly `paper_manual` / `live_manual`.")
        L.append("")
    elif mode == "paper_manual":
        L.append("> **PAPER_MANUAL - PAPER ORDERS ONLY. NO LIVE ORDERS. YOU "
                 "PLACE ORDERS MANUALLY IN TWS PAPER.** Execute only what this "
                 "plan lists, by hand, in the paper account.")
        L.append("")

    # ---- 1. Header ----------------------------------------------------
    L.append("## 1. Header")
    L.append("")
    L.append(f"- strategy: **{strategy_id}**  |  run_id: `{run_id or '?'}`  |  "
             f"mode: **{mode}**")
    L.append(f"- business_date (D): **{business_date}**  |  "
             f"target_date (D+1): **{target_date}**")
    L.append(f"- data_source: **{data_source_meta.get('data_source', '?')}**  |  "
             f"portfolio_state source: **{portfolio_state_source or 'runtime_state (local PortfolioState)'}**")
    if orders_plan_path:
        L.append(f"- order_plan: `{orders_plan_path}`")
    L.append("- **TIMING: BUY = target_date OPEN;  EXIT = planned_exit_date "
             "CLOSE.** Do not execute BUYs on close or EXITs on open.")
    L.append("")

    # ---- 2. Account / portfolio state --------------------------------
    L.append("## 2. Account / portfolio state (marked to close D)")
    L.append("")
    L.append(f"- equity: {state.equity:.2f}")
    L.append(f"- cash (available for BUYs): {state.cash:.2f}")
    L.append(f"- open positions: {len(open_pos)} / {max_positions}")
    if abs(state.equity - state.cash) > 1e-6:
        L.append(f"- note: cash != equity (difference {state.equity - state.cash:.2f} "
                 f"is market value of open positions) — this is a normal, "
                 f"supported state; BUYs are sized against **cash**.")
    else:
        L.append("- note: cash == equity (no open positions) — equity = cash + "
                 "marked position value, so with 0 positions equity equals cash "
                 "by construction. A broker net-liquidation may differ by small "
                 "non-deployable residuals (e.g. accrued interest); BUYs are "
                 "sized against **cash**.")
    L.append("")

    # ---- 3. Regime ----------------------------------------------------
    L.append("## 3. Regime")
    L.append("")
    L.append(f"- regime200: **{'ON' if regime.regime_on else 'OFF'}** "
             f"(index {regime.index_level}, MA200 {regime.ma200})")
    if not regime.regime_on:
        L.append("- regime OFF → **no new BUYs today**; EXITs and HOLDs still "
                 "apply as listed below.")
    L.append("")

    # ---- 4. BUY orders ------------------------------------------------
    L.append("## 4. BUY orders — enter at **target_date OPEN**")
    L.append("")
    if buys and feasibility:
        L.append("| rank | ticker | conid | target_value | ref_price (D close) | "
                 "indicative_qty | est_debit | max_price_for_qty | "
                 "planned_exit_if_filled | note |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for d in sorted(buys, key=lambda x: rank_of.get(x.ticker, 999)):
            b = fb.get(d.ticker)
            rk = rank_of.get(d.ticker, "?")
            row = pr.get(d.ticker, {})
            v_ref = row.get("ref_price") or (b.ref_price if b else "?")
            v_cap = row.get("max_price_for_qty") or (
                b.max_price_for_estimated_qty if b and b.executable else None)
            v_exit = row.get("planned_exit_if_filled") or (
                estimated_exit_if_filled or "?")
            v_qty = row.get("quantity") or (
                b.indicative_qty if b and b.executable else 0)
            if b and b.executable:
                L.append(f"| {rk} | {d.ticker} | {d.conid} | "
                         f"{d.target_value:.2f} | {v_ref} | "
                         f"{v_qty} | {b.estimated_debit:.2f} | "
                         f"{v_cap} | {v_exit} |  |")
            else:
                reason = b.non_executable_reason if b else "?"
                L.append(f"| {rk} | {d.ticker} | {d.conid} | "
                         f"{d.target_value:.2f} | {v_ref} | "
                         f"0 | 0.00 | — | {v_exit} | "
                         f"**DO NOT BUY — {reason}** |")
        L.append("")
        L.append("_indicative_qty & planned_exit_if_filled are ESTIMATES from D "
                 "close; actual D+1 open fill qty and the real planned_exit_date "
                 "(set at fill) may differ. Enter only rows without DO NOT BUY._")
    elif buys:
        L.append("| rank | ticker | conid | target_value | timing |")
        L.append("|---|---|---|---|---|")
        for d in sorted(buys, key=lambda x: rank_of.get(x.ticker, 999)):
            L.append(f"| {rank_of.get(d.ticker, '?')} | {d.ticker} | {d.conid} | "
                     f"{d.target_value:.2f} | {_BUY_TIMING} |")
    else:
        L.append("_none_")
    L.append("")

    # ---- 5. EXIT orders ----------------------------------------------
    L.append("## 5. EXIT orders — sell at **planned_exit_date CLOSE**")
    L.append("")
    if exits:
        L.append("| ticker | conid | current_qty | exit_date (close) | timing |")
        L.append("|---|---|---|---|---|")
        for d in exits:
            exit_date = d.target_date
            timing = ("**EXIT today / target_date at CLOSE**"
                      if exit_date == target_date else _EXIT_TIMING)
            L.append(f"| {d.ticker} | {d.conid} | {d.quantity:.6f} | "
                     f"{exit_date} | {timing} |")
        L.append("")
        L.append("_Instruction: sell the **full** held position at the planned "
                 "exit close. No discretionary changes to size or timing._")
    else:
        L.append("_none_")
    L.append("")

    # ---- 6. HOLD positions -------------------------------------------
    L.append("## 6. HOLD positions — no action")
    L.append("")
    if holds:
        L.append("| ticker | conid | shares | entry_date | planned_exit_date | "
                 "days_remaining |")
        L.append("|---|---|---|---|---|---|")
        for p in holds:
            L.append(f"| {p.ticker} | {p.conid} | {p.shares:.6f} | "
                     f"{p.entry_date} | {p.planned_exit_date} | "
                     f"{days_rem.get(p.ticker, '?')} |")
        L.append("")
        L.append("_Instruction: **hold / no action.** days_remaining = XNYS "
                 "trading sessions until the planned exit close._")
    else:
        L.append("_none_")
    L.append("")

    # ---- 7. Capital Feasibility --------------------------------------
    L.append("## 7. Capital Feasibility (estimated from D close)")
    L.append("")
    if feasibility:
        f = feasibility
        L.append(f"- **status: {f.status}** "
                 f"({f.n_executable}/{f.n_buys} BUYs executable in whole shares)")
        L.append(f"- available cash for BUYs: {f.available_cash_for_buys:.2f} "
                 f"| equity: {f.equity:.2f}")
        L.append(f"- min operational capital estimate (today): "
                 f"{f.min_operational_capital_estimate}")
        L.append(f"- estimated rounding drag on today's BUYs: "
                 f"{f.estimated_rounding_drag} "
                 f"(unused buy budget {f.estimated_unused_buy_budget:.2f})")
        L.append(f"- estimated remaining cash after BUYs: "
                 f"{f.estimated_remaining_cash_after_buys:.2f}"
                 + (f" | estimated cash shortfall: {f.estimated_cash_shortfall:.2f}"
                    if f.estimated_cash_shortfall > 0 else ""))
        if f.too_expensive:
            L.append(f"- TOO_EXPENSIVE (capital-size, DO NOT BUY): "
                     f"{', '.join(f.too_expensive)}")
        if f.insufficient_cash:
            L.append(f"- INSUFFICIENT_CASH (DO NOT BUY): "
                     f"{', '.join(f.insufficient_cash)}")
        if f.no_ref_price:
            L.append(f"- NO_REF_PRICE (no D close, DO NOT BUY): "
                     f"{', '.join(f.no_ref_price)}")
    else:
        L.append("_feasibility report not provided_")
    L.append("")
    L.append(f"- warnings: {len(warnings)}")
    for w in list(warnings)[:20]:
        L.append(f"  - {w}")
    if errors:
        L.append(f"- errors: {len(errors)}")
        for e in list(errors)[:20]:
            L.append(f"  - {e}")
    L.append("")

    # ---- 8. Manual execution checklist -------------------------------
    L.append("## 8. Manual execution checklist (tick before entering orders)")
    L.append("")
    L.append(f"- [ ] verify TWS account matches the intended account "
             f"(this run: **{account_label}**; paper `DU…` vs live `U…`)")
    if mode == "paper_manual":
        L.append("- [ ] this is `paper_manual`; **place PAPER orders manually "
                 "per this plan - NO LIVE orders**")
    else:
        L.append("- [ ] this is `dry_run`; **do not execute unless mode is "
                 "explicitly `paper_manual` / `live_manual`**")
    L.append("- [ ] enter only **executable** BUYs (rows without DO NOT BUY)")
    L.append("- [ ] do **not** buy qty=0 / DO NOT BUY names")
    L.append("- [ ] no rank-11 substitutions (do not add names below the plan)")
    L.append("- [ ] no manual ticker picking — trade only what this plan lists")
    L.append("- [ ] BUY at target_date OPEN; EXIT at planned_exit_date CLOSE")
    L.append("- [ ] after execution, import the fills with launcher option 3 "
             "(do not hand-write them)")
    L.append("")

    # ---- 9. Processing the actual executions --------------------------
    # Drive tu byla "Fill recording template" s vyzvou vyplnit ticket rucne.
    # Od P2 ticket plni importer a rucni editace je zakazana - pokyn tedy
    # neodpovidal skutecnosti a operator by delal praci, kterou dela systém.
    L.append("## 9. Processing the actual executions")
    L.append("")
    L.append("After placing the orders in TWS:")
    L.append("")
    L.append("1. Launcher **3. Import broker fills** - reads the read-only "
             "execution dump and fills the ticket.")
    L.append("2. Check the import summary (matched / missing / diagnostics).")
    L.append("3. Launcher **4. Reconcile - VALIDATE**.")
    L.append("4. After PASS, launcher **5. Reconcile - APPLY**.")
    L.append("")
    L.append("**The ticket CSV is an internal system artifact. Do not edit it "
             "by hand.**")
    L.append("")
    L.append("_Planned quantities for this session are in section 4 and in "
             "`orders_plan_<target_date>.csv`; the reconciliation step ingests "
             "the ticket into the journal (execution_mode = MANUAL)._")
    L.append("")

    # ---- Appendix -----------------------------------------------------
    if not_entered or do_nothing:
        L.append("## Appendix — candidates not entered / do_nothing")
        L.append("")
        if not_entered:
            L.append("| ticker | rank_10d | reason |")
            L.append("|---|---|---|")
            for c, reason in not_entered:
                L.append(f"| {c.ticker} | {c.rank_10d} | {reason} |")
            L.append("")
        for d in do_nothing:
            L.append(f"- DO_NOTHING: `{d.reason}`")
        L.append("")

    return "\n".join(_align_md_tables(L))


def build_ticket_rows(target_date: str, decisions: Sequence[Decision],
                      feasibility=None) -> List[dict]:
    """Ticket rows: planning context + BLANK actual-fill columns."""
    fb = {b.ticker: b for b in feasibility.per_buy} if feasibility else {}
    rows: List[dict] = []
    for d in decisions:
        if d.action == Action.BUY:
            b = fb.get(d.ticker)
            planned_qty = (b.indicative_qty if b and b.executable else "")
            rows.append({
                "target_date": target_date, "ticker": d.ticker,
                "conid": d.conid, "side": "BUY",
                "planned_quantity": planned_qty, "order_timing": _BUY_TIMING,
                "order_type": _ORDER_TYPE_TBD,
                # blank actual-fill fields:
                "actual_fill_price": "", "actual_quantity": "", "timestamp": "",
                "commission_fees": "", "order_id": "", "status": "",
            })
        elif d.action == Action.EXIT:
            rows.append({
                "target_date": d.target_date, "ticker": d.ticker,
                "conid": d.conid, "side": "EXIT",
                "planned_quantity": d.quantity, "order_timing": _EXIT_TIMING,
                "order_type": _ORDER_TYPE_TBD,
                "actual_fill_price": "", "actual_quantity": "", "timestamp": "",
                "commission_fees": "", "order_id": "", "status": "",
            })
    return rows


def write_ticket(target_date: str, decisions: Sequence[Decision],
                 out_dir: str | Path, feasibility=None) -> Path:
    rows = build_ticket_rows(target_date, decisions, feasibility)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"manual_order_ticket_{target_date}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TICKET_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


def write_report(*, out_dir: str | Path, target_date: str, **kwargs) -> Path:
    text = render_report(target_date=target_date, **kwargs)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"manual_report_{target_date}.md"
    path.write_text(text, encoding="utf-8")
    return path
