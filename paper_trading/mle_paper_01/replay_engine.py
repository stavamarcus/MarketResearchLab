"""
replay_engine.py — MLE-PAPER-01 replay + reprodukce MLE-BT-04R (Faze 1B).

Zdroj pravdy: MLE-PAPER-01_STRATEGY_SPEC_v1.1.md §13.1 a §15.

UCEL: prehraje 2021-07-01..2026-07-02 pres CELY paper stack
(SignalSource -> RegimeSource -> DecisionResolver -> fills pres
portfolio_state) a vysledek MUSI reprodukovat MLE-BT-04R
regime200_hold10:
    return 337.652 % | CAGR 34.504 % | maxDD -32.700 % | Sharpe 1.182
    trades 990 | avg_exposure 0.787
Cil neni lepsi vysledek. Cil je STEJNY vysledek. Pri neshode se NELADI
strategie — report automaticky vypise diagnostiku (prvni den rozdilu
equity, rozdily trades/regime/fills/cash/slotu).

Metodika srovnani (dvojite):
  1. IN-PROCESS GOLDEN REFERENCE: engine importuje mle_bt_04r_* z
     research_projects/tests a spusti bt04r.run_causal na IDENTICKYCH
     datech/signalech/regime -> den-po-dni srovnani equity a trades.
  2. SANITY ANCHOR: golden reference musi dat publikovanych 337.652 %
     (kontrola, ze data ve view se nezmenila od BT-04R behu).

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab\\paper_trading
    python -m mle_paper_01.replay_engine ^
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Vystupy: <mrl>/reports/backtests/MLE-PAPER-01_REPLAY_REPRODUCTION.{json,md}
Signal cache: sdilena s BT-05 (mle_signals_cache_<from>_<to>.json).

Edge cases / predpoklady:
  - order_planner se v replayi nevola (1256 CSV planu nema auditni
    hodnotu; planner je pro zivy paper den). Decisions jdou primo na fill.
  - chybejici open na D+1 -> BUY fill se preskoci (warning). ZNAMY
    potencialni zdroj divergence vs golden: resolver rezervoval cash
    pro preskoceny BUY, golden master rezervuje az pri uspesnem fillu.
    V BT-04R behu se pripad nevyskytl; diagnostika by ho odhalila.
  - chybejici close pri exitu/marku -> fallback entry cena + warning
    (§7: POUZE BT-04R-compatible reproduction mechanism).
  - planned_exit_date = sim_dates[min(si+10, n-1)] — vcetne nuceneho
    exitu na konci dat (shodne s golden masterem).
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None

from .models import Action, PortfolioState
from .decision_resolver import resolve
from .portfolio_state import (apply_buy_fill, apply_exit_fill,
                              mark_to_market)
from .regime_source import RegimeSource
from .signal_source import SignalSource, load_price_matrices, load_universe

HOLD = 10
INITIAL_CAPITAL = 100_000.0
TARGETS = {"total_return_pct": 337.652, "cagr_pct": 34.504,
           "max_drawdown_pct": -32.700, "sharpe": 1.182,
           "trades": 990, "avg_exposure": 0.787}


# ------------------------------------------------------------ metriky
def metrics(daily, trades):
    """Bitove shodne formule s BT-04 segment_stats + BT-04R cagr_pct."""
    eq = np.array([d["equity"] for d in daily])
    dr = np.diff(eq) / eq[:-1]
    total = (eq[-1] / eq[0] - 1) * 100
    rm = np.maximum.accumulate(eq)
    dd = ((eq - rm) / rm).min() * 100
    sharpe = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 \
        else None
    yrs = (len(daily) - 1) / 252
    cagr = ((eq[-1] / eq[0]) ** (1 / yrs) - 1) * 100 if yrs > 0 else None
    expo = float(np.mean([d["exposure"] for d in daily]))
    return {"total_return_pct": round(float(total), 3),
            "cagr_pct": round(float(cagr), 3) if cagr is not None else None,
            "max_drawdown_pct": round(float(dd), 3),
            "sharpe": round(sharpe, 3) if sharpe else None,
            "trades": len(trades),
            "avg_exposure": round(expo, 3)}


# ------------------------------------------------------------ replay
def run_replay(signal_source: SignalSource, regime_source: RegimeSource,
               sim_dates, close_m, open_m):
    """Prehraje sim_dates pres paper stack. Vraci (trades, daily, warns)."""
    n = len(sim_dates)
    state = PortfolioState(cash=INITIAL_CAPITAL, equity=INITIAL_CAPITAL,
                           last_updated_date="")
    daily, warns = [], []

    def px(m, tk, d):
        if tk not in m.columns:
            return None
        try:
            v = m.at[pd.Timestamp(d), tk]
        except KeyError:
            return None
        return None if pd.isna(v) else float(v)

    for si, dstr in enumerate(sim_dates):
        prev = sim_dates[si - 1] if si > 0 else None

        if si > 0:
            decisions = resolve(signal_source.candidates(prev),
                                regime_source.state(prev), state, dstr)
            # ---- OPEN: BUY filly ----
            for d in decisions:
                if d.action != Action.BUY:
                    continue
                op = px(open_m, d.ticker, dstr)
                if op is None or op == 0:
                    warns.append(f"{dstr} BUY {d.ticker}: chybi open, skip")
                    continue
                planned_exit = sim_dates[min(si + HOLD, n - 1)]
                state = apply_buy_fill(state, d, fill_price=op,
                                       fill_date=dstr,
                                       planned_exit_date=planned_exit)
            # ---- CLOSE: EXIT filly ----
            for d in decisions:
                if d.action != Action.EXIT:
                    continue
                cp = px(close_m, d.ticker, dstr)
                if cp is None or cp == 0:
                    ep = next(p.entry_price for p in state.open_positions()
                              if p.ticker == d.ticker)
                    warns.append(f"{dstr} EXIT {d.ticker}: chybi close, "
                                 f"fallback entry {ep} (data warning)")
                    cp = ep
                state = apply_exit_fill(state, d, fill_price=cp,
                                        fill_date=dstr)

        # ---- EOD mark (fallback entry cena; shodne s golden) ----
        closes = {p.ticker: (px(close_m, p.ticker, dstr) or p.entry_price)
                  for p in state.open_positions()}
        state = mark_to_market(state, closes, dstr)
        mv = state.equity - state.cash
        daily.append({"date": dstr, "equity": round(state.equity, 2),
                      "exposure": round(mv / state.equity
                                        if state.equity > 0 else 0, 4),
                      "n_positions": len(state.open_positions())})
    trades = [{"ticker": t.ticker, "entry_date": t.entry_date,
               "exit_date": t.exit_date, "pnl": round(t.pnl, 2)}
              for t in state.closed_trades]
    return trades, daily, warns


# ------------------------------------------------------------ srovnani
def compare(rep_daily, rep_trades, gold_daily, gold_trades):
    out = {"equity_identical": True, "first_diff_date": None,
           "max_abs_diff": 0.0, "n_diff_days": 0}
    diffs = []
    for r, g in zip(rep_daily, gold_daily):
        d = abs(r["equity"] - g["equity"])
        if d > 0.005:  # oba zaokrouhluji na 2 des. mista
            diffs.append((r["date"], r["equity"], g["equity"], d))
    if diffs:
        out["equity_identical"] = False
        out["first_diff_date"] = diffs[0][0]
        out["first_diff_detail"] = {"replay": diffs[0][1],
                                    "golden": diffs[0][2]}
        out["max_abs_diff"] = round(max(x[3] for x in diffs), 2)
        out["n_diff_days"] = len(diffs)
    rset = {(t["ticker"], t["entry_date"], t["exit_date"])
            for t in rep_trades}
    gset = {(t["ticker"], t["entry_date"], t["exit_date"])
            for t in gold_trades}
    out["trades_replay"] = len(rset)
    out["trades_golden"] = len(gset)
    out["trades_only_replay"] = sorted(rset - gset)[:20]
    out["trades_only_golden"] = sorted(gset - rset)[:20]
    out["trades_identical"] = rset == gset
    return out


# ------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mle-root",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--tests-dir", default=None,
                    help="adresar s mle_bt_04r_* (default: <mrl>/research_projects/tests)")
    ap.add_argument("--from", dest="dfrom", default="2021-07-01")
    ap.add_argument("--to", dest="dto", default="2026-07-02")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--max-signal-days", dest="maxsig", default="0")
    ap.add_argument("--out", default=None)
    ap.add_argument("--recompute-signals", action="store_true")
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas/numpy")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else \
        Path(__file__).resolve().parent.parent.parent
    out_dir = Path(args.out) if args.out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = Path(args.tests_dir) if args.tests_dir else \
        mrl / "research_projects" / "tests"

    # MLE engine
    sys.path.insert(0, str(Path(args.mle_root)))
    try:
        from src.engines.rank_matrix_engine import compute_rank_matrix
    except ImportError as e:
        print(f"FAIL: MLE engine import: {e}")
        return 2
    # golden reference (BT-04R) — soubor se NEMENI, jen importuje
    sys.path.insert(0, str(tests_dir))
    try:
        bt04r = importlib.import_module(
            "mle_bt_04r_causal_execution_correction")
    except ImportError as e:
        print(f"FAIL: import golden reference BT-04R: {e}")
        return 2

    instruments, t2c, t2i, t2s = load_universe(Path(args.universe_csv))
    print(f"universe {len(instruments)} | pandas {pd.__version__}")
    close_m, open_m = load_price_matrices(Path(args.view_dir),
                                          instruments, t2c)
    print(f"close matrix {close_m.shape}")

    full_idx = [str(x.date()) for x in close_m.index]
    full_pos = {s: i for i, s in enumerate(full_idx)}
    signal_dates = [d for d in full_idx if args.dfrom <= d <= args.dto]
    if not signal_dates:
        print(f"FAIL: zadne dny v okne {args.dfrom}..{args.dto}")
        return 2
    maxsig = int(args.maxsig)
    if maxsig > 0:
        signal_dates = signal_dates[:maxsig]
    sp, lp = full_pos[signal_dates[0]], full_pos[signal_dates[-1]]
    ep = min(lp + 20 + 1, len(full_idx) - 1)
    sim_dates = full_idx[sp:ep + 1]
    print(f"sim {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)})")

    regime_source = RegimeSource(close_m)
    cache = out_dir / f"mle_signals_cache_{args.dfrom}_{args.dto}.json" \
        if maxsig == 0 else None
    signal_source = SignalSource(close_m, instruments, t2c,
                                 compute_rank_matrix, cache_path=cache,
                                 recompute=args.recompute_signals)
    signal_source.compute(signal_dates)

    # ---- 1) replay pres paper stack ----
    print("replay: paper stack...")
    rep_trades, rep_daily, warns = run_replay(signal_source, regime_source,
                                              sim_dates, close_m, open_m)
    rep_m = metrics(rep_daily, rep_trades)
    print(f"replay:  {rep_m}")

    # ---- 2) in-process golden reference (BT-04R run_causal) ----
    print("golden reference: BT-04R run_causal...")
    g_trades, g_daily, g_diag = bt04r.run_causal(
        signal_source.raw_dict(), sim_dates, close_m, open_m, HOLD,
        15, t2i, t2s, True, regime_source.ok_dict())
    gold_m = metrics(g_daily, g_trades)
    print(f"golden:  {gold_m}")

    # ---- 3) srovnani ----
    cmpr = compare(rep_daily, rep_trades, g_daily, g_trades)
    anchor_ok = gold_m["total_return_pct"] == TARGETS["total_return_pct"]
    target_ok = all(rep_m[k] == v for k, v in TARGETS.items())
    verdict = ("PASS" if (cmpr["equity_identical"]
                          and cmpr["trades_identical"] and target_ok)
               else "FAIL")

    payload = {"task": "MLE-PAPER-01 replay reproduction (Faze 1B)",
               "pandas_version": pd.__version__,
               "sim_start": sim_dates[0], "sim_end": sim_dates[-1],
               "sim_days": len(sim_dates),
               "targets_bt04r": TARGETS,
               "replay_metrics": rep_m,
               "golden_metrics": gold_m,
               "sanity_anchor_golden_matches_published": anchor_ok,
               "replay_matches_targets": target_ok,
               "comparison": cmpr,
               "warnings": warns[:50],
               "n_warnings": len(warns),
               "VERDICT": verdict}
    (out_dir / "MLE-PAPER-01_REPLAY_REPRODUCTION.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")

    L = ["# MLE-PAPER-01 — Replay Reproduction Report (Faze 1B)", "",
         f"**VERDICT: {verdict}**", "",
         f"Sim: {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)} dni), "
         f"pandas {pd.__version__}", "",
         "| metrika | target (BT-04R) | replay | golden (in-process) |",
         "|---|---|---|---|"]
    for k, v in TARGETS.items():
        L.append(f"| {k} | {v} | {rep_m.get(k)} | {gold_m.get(k)} |")
    L += ["",
          f"- sanity anchor (golden == publikovane): {anchor_ok}",
          f"- equity identicka den-po-dni: {cmpr['equity_identical']}",
          f"- trades identicke: {cmpr['trades_identical']} "
          f"(replay {cmpr['trades_replay']} / golden "
          f"{cmpr['trades_golden']})",
          f"- warnings: {len(warns)}", ""]
    if not cmpr["equity_identical"]:
        L += ["## DIAGNOSTIKA DIVERGENCE", "",
              f"- prvni den rozdilu: {cmpr['first_diff_date']} "
              f"({cmpr.get('first_diff_detail')})",
              f"- dnu s rozdilem: {cmpr['n_diff_days']}, max abs diff "
              f"{cmpr['max_abs_diff']}",
              f"- trades jen v replay: {cmpr['trades_only_replay']}",
              f"- trades jen v golden: {cmpr['trades_only_golden']}", "",
              "Postup: NELADIT strategii. Zkoumat prvni den rozdilu — "
              "MLE_TOP10, regime_ON, fills open/close, cash, sloty.", ""]
    L += ["## Vyhrady", "",
          "- Reprodukce = validace IMPLEMENTACE, ne strategie.",
          "- Golden reference = import BT-04R (soubor nezmenen).",
          "- Signaly/regime sdilene obema behy.", ""]
    (out_dir / "MLE-PAPER-01_REPLAY_REPRODUCTION.md").write_text(
        "\n".join(L), encoding="utf-8")
    print(f"\nVERDICT: {verdict} | reporty v {out_dir}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
