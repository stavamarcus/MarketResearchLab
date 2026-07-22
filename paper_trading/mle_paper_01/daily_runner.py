"""daily_runner.py — MLE-PAPER-01 Daily Offline Runner (dry_run, no broker).

One production-shaped day:
    business_date D  ->  target_date D+1
    load state -> mark_to_market at close D -> verify last_updated==regime.date==D
    -> resolve() -> orders_plan_<D+1>.csv -> manual report -> journal(dry_run)

Calls the REAL frozen modules (SignalSource/RegimeSource via the data source,
resolve, mark_to_market, write_orders_plan). No strategy logic here, no fills,
no broker, no order submission. Fail-closed on any data/regime/state problem.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional

from .models import Action, PortfolioState, RegimeState, MAX_POSITIONS
from .decision_resolver import resolve
from .portfolio_state import mark_to_market
from .order_planner import write_orders_plan
from . import capital_feasibility, manual_report, runtime_state
from .calendar_util import next_session_xnys, add_sessions, sessions_until
from .data_source import DataSourceProfile, PriceDataSource, build_data_source
from .runner_config import RunnerConfig, load_config

SS_RUNNER = "DAILY_RUNNER"
SS_STATE = "RUNTIME_STATE"


class RunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class RunnerStop(RuntimeError):
    """Controlled fail-closed stop (missing data, inconsistent state, ...)."""


@dataclass
class RunResult:
    status: RunStatus
    business_date: Optional[str] = None
    target_date: Optional[str] = None
    run_id: Optional[str] = None
    data_source: Optional[str] = None
    n_buy: int = 0
    n_exit: int = 0
    n_do_nothing: int = 0
    regime_on: Optional[bool] = None
    cash: Optional[float] = None
    equity: Optional[float] = None
    open_positions: Optional[int] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    orders_plan_path: Optional[str] = None
    manual_report_path: Optional[str] = None
    feasibility_status: Optional[str] = None
    min_operational_capital_estimate: Optional[float] = None
    reason: Optional[str] = None


def _default_journal_factory(config: RunnerConfig):
    """Real JournalWriter in dry_run mode (source_system default DAILY_RUNNER)."""
    from journal import JournalWriter
    return JournalWriter(mode=config.mode, strategy_id=config.strategy_id,
                         base_dir=config.journal_base_dir,
                         source_system=SS_RUNNER)


class DailyOfflineRunner:
    def __init__(self, config: RunnerConfig,
                 data_source: PriceDataSource,
                 next_session_fn: Callable[[str], str] = next_session_xnys,
                 journal_factory: Optional[Callable[[RunnerConfig], object]] = None,
                 write_manual_report: bool = True,
                 write_manual_ticket: bool = False):
        self.cfg = config
        self.ds = data_source
        self.next_session_fn = next_session_fn
        self.journal_factory = journal_factory or _default_journal_factory
        self.write_manual_report = write_manual_report
        self.write_manual_ticket = write_manual_ticket

    def _write_freshness_report(self, fr, business_date: str) -> None:
        """Write mdsm_freshness_<D>.md/.json listing every stale/missing/invalid
        name (ticker, conid, end_date, reason) plus any traded violations."""
        import json as _json
        from pathlib import Path as _Path
        from .manual_report import _align_md_tables
        out = _Path(self.cfg.reports_dir)
        out.mkdir(parents=True, exist_ok=True)
        L = [f"# MDSM Freshness - {business_date}", "",
             f"- verdict: **{fr.verdict}**",
             f"- expected session: {fr.expected_session}  |  effective_last: "
             f"{fr.effective_last_session}",
             f"- fresh: {fr.fresh_count}/{fr.universe_size}  |  "
             f"stale+missing+invalid: {fr.bad_count()}  |  reason: {fr.reason}",
             ""]
        if fr.traded_violations:
            L.append(f"## TRADED VIOLATIONS ({len(fr.traded_violations)}) - HARD "
                     f"FAIL\n- {fr.traded_violations}\n")
        for name, rows in (("Stale", fr.stale), ("Missing", fr.missing),
                           ("Invalid", fr.invalid)):
            L.append(f"## {name} ({len(rows)})")
            if rows:
                L.append("| ticker | conid | end_date | reason |")
                L.append("|---|---|---|---|")
                for r in rows:
                    L.append(f"| {r['ticker']} | {r['conid']} | "
                             f"{r['end_date']} | {r['reason']} |")
            else:
                L.append("_none_")
            L.append("")
        (out / f"mdsm_freshness_{business_date}.md").write_text(
            "\n".join(_align_md_tables(L)), encoding="utf-8")
        (out / f"mdsm_freshness_{business_date}.json").write_text(
            _json.dumps(fr.as_dict(), indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ run
    def run(self, business_date: Optional[str] = None) -> RunResult:
        warnings: List[str] = []
        journal = self.journal_factory(self.cfg)
        run_id = getattr(journal, "run_id", None)
        meta = self.ds.metadata()
        try:
            journal.write_event("INFO", "daily_runner", "RUN_START",
                                source_system=SS_RUNNER)
            journal.write_event("INFO", "daily_runner", "DATA_SOURCE",
                                source_system=SS_RUNNER, **meta)

            # 1) business_date D + target_date D+1
            # MDSM freshness gate (data_source=MDSM only). Early pass: systemic
            # staleness (GDU clearly did not run) -> STOP before building a plan.
            # The traded-name check runs after resolve (see below), since the
            # verdict depends on which tickers the plan actually trades.
            if self.ds.profile == DataSourceProfile.MDSM:
                from .calendar_util import last_completed_session_xnys
                expected = business_date or last_completed_session_xnys()
                fr0 = self.ds.freshness_report(expected)
                if not fr0.passed:      # systemic (bad > MAX_STALE_ALLOWED)
                    journal.write_event(
                        "INFO", "daily_runner", "MDSM_FRESHNESS",
                        source_system=SS_RUNNER, business_date=expected,
                        result=fr0.verdict, fresh=fr0.fresh_count,
                        universe=fr0.universe_size, bad=fr0.bad_count())
                    raise RunnerStop(
                        f"MDSM freshness FAIL for {expected}: {fr0.reason} "
                        f"(fresh {fr0.fresh_count}/{fr0.universe_size}, "
                        f"effective_last={fr0.effective_last_session}). "
                        f"No paper_manual plan.")
                business_date = expected

            D = business_date or self.ds.last_completed_session()
            target_date = self.next_session_fn(D)
            if not (D < target_date):
                raise RunnerStop(
                    f"target_date {target_date} not after business_date {D}")

            # 2) load or bootstrap state
            state, bootstrapped = runtime_state.load_or_bootstrap(
                self.cfg.state_path, self.cfg.starting_equity)
            if bootstrapped:
                journal.write_event("INFO", "runtime_state",
                                    "STATE_BOOTSTRAPPED", business_date=D,
                                    source_system=SS_STATE,
                                    starting_equity=self.cfg.starting_equity)

            # 3) mark-to-market at close D (fail-closed if a position lacks a
            #    valid close). Resolver requires last_updated_date == D.
            open_tickers = [p.ticker for p in state.open_positions()]
            closes = self.ds.closes_at(D, open_tickers)
            missing = [t for t in open_tickers
                       if closes.get(t) is None or closes.get(t) <= 0]
            if missing:
                raise RunnerStop(
                    f"cannot mark open positions to close {D}: {missing}")
            state = mark_to_market(state, {t: closes[t] for t in open_tickers}, D)

            # 4) regime + consistency (regime.date must equal D)
            regime = self.ds.regime_state(D)
            if regime.date != D:
                raise RunnerStop(
                    f"regime.date {regime.date} != business_date {D}")
            if state.last_updated_date != D:
                raise RunnerStop(
                    f"state.last_updated_date {state.last_updated_date} != {D}")

            # 5) signal candidates + resolve (frozen strategy, unchanged)
            candidates = self.ds.signal_candidates(D)
            decisions = resolve(candidates, regime, state, target_date)

            buys = [d for d in decisions if d.action == Action.BUY]
            exits = [d for d in decisions if d.action == Action.EXIT]
            do_nothing = [d for d in decisions
                          if d.action == Action.DO_NOTHING]

            # 5a) MDSM freshness — traded-name protection (revised OQ-2).
            # Any BUY/EXIT ticker must be fresh; tolerated dead/invalid names
            # outside the plan -> PASS_WITH_WARNINGS. Writes an explicit report.
            if self.ds.profile == DataSourceProfile.MDSM:
                fr = self.ds.freshness_report(
                    D, [b.ticker for b in buys], [e.ticker for e in exits])
                self._write_freshness_report(fr, D)
                journal.write_event(
                    "INFO", "daily_runner", "MDSM_FRESHNESS",
                    source_system=SS_RUNNER, business_date=D,
                    result=fr.verdict, fresh=fr.fresh_count,
                    universe=fr.universe_size, bad=fr.bad_count(),
                    traded_violations=len(fr.traded_violations))
                if not fr.passed:
                    raise RunnerStop(
                        f"MDSM freshness FAIL for {D}: {fr.reason}. "
                        f"No paper_manual plan (a traded ticker is not fresh).")
                if fr.verdict == "PASS_WITH_WARNINGS":
                    warnings.append(
                        f"MDSM freshness PASS_WITH_WARNINGS: {fr.bad_count()} "
                        f"stale/missing/invalid name(s) outside the plan "
                        f"(see mdsm_freshness_{D}.md)")

            # 5b) capital feasibility (render/analysis-only; advisory).
            # ref price = D close as proxy for the D+1 open (estimate);
            # available_cash_for_buys = current cash (equity may sit in positions).
            buy_ref_prices = self.ds.closes_at(D, [b.ticker for b in buys])
            feasibility = capital_feasibility.evaluate_plan(
                equity=state.equity, available_cash_for_buys=state.cash,
                buys=buys, ref_prices=buy_ref_prices)
            warnings.extend(feasibility.warnings)

            # 6) orders_plan_<D+1>.csv (frozen order_planner convention)
            plan_path = write_orders_plan(decisions, self.cfg.order_plans_dir)

            # 7) manual report + optional fillable ticket (render-only)
            # 7) Daily Trade Plan + optional fillable ticket (render-only).
            # Calendar-derived values computed here (manual_report stays
            # calendar-free): estimated exit-if-filled = D+1 entry + 10 XNYS
            # sessions (frozen hold10); per-hold days_remaining in sessions.
            HOLD_PERIOD = 10
            try:
                estimated_exit_if_filled = add_sessions(
                    self.next_session_fn, target_date, HOLD_PERIOD)
            except Exception:
                estimated_exit_if_filled = None  # advisory estimate only
            holds_days_remaining = {}
            for p in state.open_positions():
                try:
                    holds_days_remaining[p.ticker] = sessions_until(
                        self.next_session_fn, D, p.planned_exit_date)
                except Exception:
                    pass  # leave out -> rendered as '?'
            portfolio_state_source = (
                f"runtime_state (local PortfolioState, {self.cfg.mode})")
            report_path = None
            if self.write_manual_report:
                report_path = manual_report.write_report(
                    out_dir=self.cfg.reports_dir, business_date=D,
                    target_date=target_date, regime=regime, state=state,
                    candidates=candidates, decisions=decisions,
                    warnings=warnings, errors=[],
                    account_label=self.cfg.account_label, mode=self.cfg.mode,
                    data_source_meta=meta, orders_plan_path=str(plan_path),
                    feasibility=feasibility, run_id=run_id,
                    strategy_id=self.cfg.strategy_id,
                    portfolio_state_source=portfolio_state_source,
                    estimated_exit_if_filled=estimated_exit_if_filled,
                    holds_days_remaining=holds_days_remaining,
                    max_positions=MAX_POSITIONS)
            if self.write_manual_ticket:
                manual_report.write_ticket(target_date, decisions,
                                           self.cfg.order_plans_dir,
                                           feasibility=feasibility)

            # 8) journal (dry_run) — per-table source_system
            self._journal_outputs(journal, D, target_date, state, regime,
                                   candidates, decisions, warnings)
            journal.write_event("INFO", "capital_feasibility",
                                "CAPITAL_FEASIBILITY", business_date=D,
                                source_system=SS_RUNNER,
                                **feasibility.summary())
            journal.write_event("INFO", "manual_report",
                                "MANUAL_REPORT_GENERATED", business_date=D,
                                source_system=SS_RUNNER,
                                report=str(report_path) if report_path else "")
            journal.write_event("INFO", "daily_runner", "RUN_COMPLETE",
                                business_date=D, source_system=SS_RUNNER,
                                n_buy=len(buys), n_exit=len(exits))
            journal.close()

            # 9) persist state (mark-to-market valuation only; no fills)
            runtime_state.persist(state, self.cfg.state_path)

            return RunResult(
                status=RunStatus.SUCCESS, business_date=D,
                target_date=target_date, run_id=run_id,
                data_source=meta.get("data_source"),
                n_buy=len(buys), n_exit=len(exits), n_do_nothing=len(do_nothing),
                regime_on=regime.regime_on, cash=state.cash, equity=state.equity,
                open_positions=len(state.open_positions()), warnings=warnings,
                orders_plan_path=str(plan_path),
                manual_report_path=str(report_path) if report_path else None,
                feasibility_status=feasibility.status,
                min_operational_capital_estimate=
                feasibility.min_operational_capital_estimate)

        except RunnerStop as stop:
            self._fail(journal, "STOP", str(stop))
            return RunResult(status=RunStatus.STOPPED, run_id=run_id,
                             business_date=business_date, reason=str(stop),
                             errors=[str(stop)], warnings=warnings)
        except Exception as exc:  # unexpected — still fail-closed
            self._fail(journal, "ERROR", f"{type(exc).__name__}: {exc}")
            return RunResult(status=RunStatus.FAILED, run_id=run_id,
                             business_date=business_date,
                             reason=f"{type(exc).__name__}: {exc}",
                             errors=[str(exc)], warnings=warnings)

    # ------------------------------------------------------------- helpers
    def _fail(self, journal, severity: str, reason: str) -> None:
        """Record the failed run; no orders_plan / manual report were written
        (both happen only after resolve succeeds)."""
        try:
            journal.write_event(severity, "daily_runner", "RUN_FAILED",
                                source_system=SS_RUNNER, reason=reason)
            journal.close()
        except Exception:
            pass

    def _journal_outputs(self, journal, D, target_date, state, regime,
                         candidates, decisions, warnings) -> None:
        buys = [d for d in decisions if d.action == Action.BUY]
        exits = [d for d in decisions if d.action == Action.EXIT]
        held = {p.ticker for p in state.open_positions()}
        exit_tickers = {d.ticker for d in exits}

        journal.write_daily_state(D, {
            "date": D, "account_id": self.cfg.account_label,
            "cash": state.cash, "equity": state.equity,
            "net_liquidation": state.equity,
            "gross_exposure": state.equity - state.cash,
            "net_exposure": state.equity - state.cash,
            "open_positions_count": len(state.open_positions()),
            "regime_on": regime.regime_on,
            "regime_index_level": regime.index_level,
            "regime_ma200": regime.ma200,
            "valid_constituents_count": regime.valid_constituents,
            "kill_switch_active": False, "override_active": False,
            "orders_planned_count": len(buys) + len(exits),
            "orders_filled_count": 0,
            "warnings_count": len(warnings), "errors_count": 0,
        }, source_system=SS_RUNNER)

        journal.write_signals(D, [{
            "signal_date": D, "ticker": c.ticker, "conid": str(c.conid),
            "rank_10d": float(c.rank_10d), "is_top10": True,
            "source": self.ds.metadata().get("data_source"),
        } for c in candidates], source_system=self.ds.profile.value)

        journal.write_decisions(D, [{
            "decision_id": f"{D}-{i}", "signal_date": D,
            "target_date": target_date, "ticker": d.ticker,
            "conid": None if d.conid is None else str(d.conid),
            "action": d.action.value, "reason": d.reason,
            "regime_on": regime.regime_on, "cash_before": state.cash,
            "equity_before": state.equity, "target_value": d.target_value,
            "quantity": d.quantity,
            "price_source": d.price_source.value if d.price_source else None,
            "free_slots_before": 10 - len(state.open_positions()),
            "already_held": bool(d.ticker and d.ticker in held),
            "pending_exit": bool(d.ticker and d.ticker in exit_tickers),
        } for i, d in enumerate(decisions)], source_system=SS_RUNNER)

        journal.write_order_plan(D, [{
            "plan_id": f"{target_date}-{i}", "signal_date": D,
            "target_date": target_date, "ticker": d.ticker,
            "conid": None if d.conid is None else str(d.conid),
            "action": d.action.value, "target_value": d.target_value,
            "quantity": d.quantity,
            "price_source": d.price_source.value if d.price_source else None,
            "order_type": "TBD", "status": "PLANNED", "reason": d.reason,
        } for i, d in enumerate(d for d in decisions
                                if d.action != Action.DO_NOTHING)],
            source_system=SS_RUNNER)

        journal.write_positions_snapshot(D, [{
            "date": D, "ticker": p.ticker, "conid": str(p.conid),
            "shares": p.shares, "entry_date": p.entry_date,
            "entry_price": p.entry_price, "planned_exit_date": p.planned_exit_date,
            "rank_at_entry": float(p.signal_rank),
            "regime_at_entry": p.regime_at_entry, "status": p.status.value,
        } for p in state.open_positions()], source_system=SS_STATE)

        journal.ensure_empty_tables(D, ["fills"])


# --------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="MLE-PAPER-01 Daily Offline Runner")
    ap.add_argument("--business-date", default=None,
                    help="ISO date D; default = last completed session")
    ap.add_argument("--data-source", default=None,
                    choices=[p.value for p in DataSourceProfile])
    ap.add_argument("--config", default=None, help="runner_config JSON")
    ap.add_argument("--base", default=None,
                    help="paper_trading base dir (default: package parent)")
    ap.add_argument("--no-manual-report", action="store_true")
    ap.add_argument("--manual-ticket", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.data_source:
        from dataclasses import replace
        cfg = replace(cfg, data_source=DataSourceProfile(args.data_source))
    base = Path(args.base) if args.base else Path(__file__).resolve().parent.parent
    cfg = cfg.with_base(base)

    ds = build_data_source(cfg)
    runner = DailyOfflineRunner(
        cfg, ds,
        write_manual_report=not args.no_manual_report,
        write_manual_ticket=args.manual_ticket)
    result = runner.run(args.business_date)

    print(f"\nVERDICT: {result.status.value}")
    if result.status == RunStatus.SUCCESS:
        print(f"  D={result.business_date} -> D+1={result.target_date} "
              f"| data_source={result.data_source}")
        print(f"  regime={'ON' if result.regime_on else 'OFF'} "
              f"| BUY={result.n_buy} EXIT={result.n_exit} "
              f"DO_NOTHING={result.n_do_nothing}")
        print(f"  cash={result.cash:.2f} equity={result.equity:.2f} "
              f"open={result.open_positions}")
        print(f"  feasibility: {result.feasibility_status} "
              f"(min operational capital est. "
              f"{result.min_operational_capital_estimate})")
        print(f"  order_plan: {result.orders_plan_path}")
        if result.manual_report_path:
            print(f"  manual_report: {result.manual_report_path}")
        return 0
    print(f"  reason: {result.reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
