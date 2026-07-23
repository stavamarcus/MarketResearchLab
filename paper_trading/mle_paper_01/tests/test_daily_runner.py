import csv
from pathlib import Path

import pyarrow.parquet as pq

from mle_paper_01.runner_config import RunnerConfig
from mle_paper_01.data_source import DataSourceProfile, build_data_source
from mle_paper_01.daily_runner import DailyOfflineRunner, RunStatus
from mle_paper_01.models import (PortfolioState, Position, PriceSource,
                                 Action, RegimeState, SignalCandidate)
from mle_paper_01 import decision_resolver, portfolio_state
from mle_paper_01.order_planner import write_orders_plan
import mle_paper_01.runtime_state as rs

from journal import JournalWriter
from journal import paths as jpaths

import _runner_fakes as fk

D = "2026-07-15"
D1 = "2026-07-16"
NEXT = fk.make_next_session({D: D1})


def _cfg(tmp_path, **over):
    base = tmp_path
    cfg = RunnerConfig(
        state_path=str(base / "state.json"),
        order_plans_dir=str(base / "plans"),
        reports_dir=str(base / "reports"),
        journal_base_dir=str(base / "journal_data"),
        **over)
    return cfg


def _journal_factory(cfg):
    return JournalWriter(mode=cfg.mode, strategy_id=cfg.strategy_id,
                         base_dir=cfg.journal_base_dir,
                         source_system="DAILY_RUNNER")


def _run(tmp_path, ds, **runner_kw):
    cfg = _cfg(tmp_path)
    runner = DailyOfflineRunner(cfg, ds, next_session_fn=NEXT,
                                journal_factory=_journal_factory, **runner_kw)
    return cfg, runner.run()


# ---------------------------------------------------------------- happy path
def test_success_bootstrap_two_buys(tmp_path):
    ds = fk.FakePriceDataSource(
        D, [fk.cand("AAPL", 265598, 1), fk.cand("MSFT", 272093, 2)],
        fk.regime_on(D), {})
    cfg, res = _run(tmp_path, ds)
    assert res.status == RunStatus.SUCCESS
    assert res.business_date == D and res.target_date == D1
    assert res.n_buy == 2 and res.n_exit == 0
    assert Path(res.orders_plan_path).exists()
    assert Path(res.manual_report_path).exists()
    # orders_plan file name uses target_date (frozen order_planner convention)
    assert Path(res.orders_plan_path).name == f"orders_plan_{D1}.csv"


def test_orders_plan_status_planned_in_journal(tmp_path):
    ds = fk.FakePriceDataSource(D, [fk.cand("AAPL", 1, 1)], fk.regime_on(D), {})
    cfg, res = _run(tmp_path, ds)
    p = jpaths.partition_file(cfg.journal_base_dir, "dry_run", "order_plans",
                              D, res.run_id)
    t = pq.ParquetFile(str(p)).read().to_pylist()
    assert t and all(r["status"] == "PLANNED" for r in t)


# ---------------------------------------------------------------- fail-closed
def test_fail_closed_missing_close(tmp_path):
    # pre-existing state with one open position, but no close available at D
    pos = Position(ticker="AAPL", conid=1, shares=10.0, entry_date="2026-07-01",
                   entry_price=200.0, planned_exit_date="2026-08-01",
                   signal_rank=1)
    st = PortfolioState(cash=5000.0, equity=5000.0, positions=(pos,),
                        last_updated_date="2026-07-14")
    cfg = _cfg(tmp_path)
    portfolio_state.save_state(st, cfg.state_path)
    ds = fk.FakePriceDataSource(D, [], fk.regime_on(D), {"AAPL": None})
    runner = DailyOfflineRunner(cfg, ds, next_session_fn=NEXT,
                                journal_factory=_journal_factory)
    res = runner.run()
    assert res.status == RunStatus.STOPPED
    assert "AAPL" in (res.reason or "")
    # no orders_plan written on STOP
    assert not (Path(cfg.order_plans_dir) / f"orders_plan_{D1}.csv").exists()


def test_regime_date_mismatch_stops(tmp_path):
    ds = fk.FakePriceDataSource(D, [], fk.regime_on("2026-07-14"), {})
    _cfg_, res = _run(tmp_path, ds)
    assert res.status == RunStatus.STOPPED


# ---------------------------------------------------------------- parity
def test_resolver_passthrough_parity(tmp_path):
    cands = [fk.cand("AAPL", 1, 1), fk.cand("MSFT", 2, 2)]
    ds = fk.FakePriceDataSource(D, cands, fk.regime_on(D), {})
    cfg, res = _run(tmp_path, ds)

    # reconstruct the exact inputs the runner used and call resolve directly
    st = rs.bootstrap_state(cfg.starting_equity)
    st = portfolio_state.mark_to_market(st, {}, D)
    direct = decision_resolver.resolve(cands, fk.regime_on(D), st, D1)
    direct_dir = tmp_path / "direct"
    direct_path = write_orders_plan(direct, direct_dir)

    runner_rows = list(csv.DictReader(open(res.orders_plan_path, encoding="utf-8")))
    direct_rows = list(csv.DictReader(open(direct_path, encoding="utf-8")))

    # ZMENENO: plan nove nese i strojova plan-reference pole (ref_price,
    # ref_price_date, max_price_for_qty, planned_exit_if_filled) a u BUY
    # i quantity z feasibility. Ta NEPOCHAZEJI z resolveru, takze porovnavat
    # cele radky by uz netestovalo to, co ma - tedy ze runner nemeni
    # strategicke rozhodnuti. Porovnavaji se proto resolverova pole.
    RESOLVER_FIELDS = ("date", "ticker", "conid", "action", "target_value",
                       "reason", "price_source")

    def resolver_view(rows):
        out = []
        for r in rows:
            v = {k: r[k] for k in RESOLVER_FIELDS}
            if r["action"] != "BUY":
                v["quantity"] = r["quantity"]   # EXIT qty je z resolveru
            out.append(v)
        return out

    assert resolver_view(runner_rows) == resolver_view(direct_rows)
    # a pro jistotu: stejna jmena ve stejnem poradi
    assert [r["ticker"] for r in runner_rows] == [r["ticker"] for r in direct_rows]


# ---------------------------------------------------------------- manual report
def test_manual_report_mirrors_decisions(tmp_path):
    ds = fk.FakePriceDataSource(
        D, [fk.cand("AAPL", 1, 1), fk.cand("NVDA", 3, 3)], fk.regime_on(D), {})
    cfg, res = _run(tmp_path, ds, write_manual_ticket=True)
    text = Path(res.manual_report_path).read_text(encoding="utf-8")
    assert "# Daily Trade Plan" in text
    for h in ("## 1. Header", "## 2. Account", "## 3. Regime",
              "## 4. BUY orders", "## 5. EXIT orders", "## 6. HOLD positions",
              "## 7. Capital Feasibility", "## 8. Manual execution checklist",
              "## 9. Processing the actual executions"):
        assert h in text
    assert "AAPL" in text and "NVDA" in text
    assert "BUY = target_date OPEN" in text
    assert "EXIT = planned_exit_date CLOSE" in text
    assert "MOO" not in text and "MOC" not in text
    ticket = Path(cfg.order_plans_dir) / f"manual_order_ticket_{D1}.csv"
    assert ticket.exists()
    header = next(csv.reader(open(ticket, encoding="utf-8")))
    for col in ("ticker", "side", "planned_quantity", "actual_fill_price",
                "timestamp", "commission_fees", "order_id", "status"):
        assert col in header


# ---------------------------------------------------------------- journal ss
def test_journal_source_system_per_table(tmp_path):
    ds = fk.FakePriceDataSource(D, [fk.cand("AAPL", 1, 1)], fk.regime_on(D), {})
    cfg, res = _run(tmp_path, ds)
    expect = {"signals": "DATA06", "decisions": "DAILY_RUNNER",
              "order_plans": "DAILY_RUNNER", "daily_state": "DAILY_RUNNER"}
    for table, ss in expect.items():
        p = jpaths.partition_file(cfg.journal_base_dir, "dry_run", table,
                                  D, res.run_id)
        rows = pq.ParquetFile(str(p)).read().to_pylist()
        assert rows, f"{table} empty"
        assert all(r["source_system"] == ss for r in rows), \
            f"{table} source_system != {ss}"


# ---------------------------------------------------------------- MDSM guard
# (The former test_mdsm_not_ready_fails_closed is obsolete: MdsmPriceSource is
# now implemented. Current MDSM behaviour — the runner refuses a plan on a
# freshness FAIL — is covered by tests/test_mdsm_source.py with injected fakes,
# without depending on a real MDSM-Lite install path.)


# ---------------------------------------------------------------- no broker
def test_no_broker_import():
    import ast
    pkg = Path(__file__).resolve().parents[1]
    forbidden = {"broker", "ib_insync", "ibapi", "ibkr", "tws", "execution"}
    runner_files = ["daily_runner.py", "data_source.py", "runner_config.py",
                    "runtime_state.py", "manual_report.py", "calendar_util.py"]
    for fn in runner_files:
        tree = ast.parse((pkg / fn).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                assert n.split(".")[0] not in forbidden, f"{fn} imports {n}"
