"""
mle_bt_05_hold_sensitivity.py — MLE-BT-05.

HOLD PERIOD SENSITIVITY TEST. Diagnosticky report, NENI zmena frozen
strategie. Pouziva kauzalni engine z MLE-BT-04R (import, zadna duplikace).

Testuje hold = 5,7,8,9,10,11,12,13,14,15,20 pro varianty MLE-only
a MLE+regime200, pri costs 15/30/50 bps round-trip.

Zachovano: MLE rank_10d <= 10, max 10 pozic, 10 % equity target,
fixed 503 universe, BUY open D+1 (signal+regime z close D),
EXIT close planned_exit_date, cash/slot z exitu dostupne az dalsi
obchodni den, zadne nove filtry.

DATA SNOOPING VAROVANI:
  11 hold hodnot na jednom 5letem in-sample okne se survivorship biasem.
  Bodove maximum NENI dukaz. Kriterium robustnosti definovano PREDEM
  (viz verdict v reportu): hold12 prekonava hold10 robustne pouze pokud
  soucasne (1) vyssi CAGR i Sharpe na vsech cost urovnich, (2) vitezi
  ve vetsine let, (3) sousede 11 a 13 jsou take >= hold10 (plateau,
  ne spike). Formalni statisticka signifikance z jedne cesty nelze.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\mle_bt_05_hold_sensitivity.py ^
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Cache signalu: prvni beh spocita MLE signaly (pomale) a ulozi je do
reports/backtests/mle_signals_cache_<from>_<to>.json; dalsi behy je nactou.
Vynuceny prepocet: --recompute-signals.

Vystupy: reports/backtests/MLE-BT-05_hold_sensitivity.{json,md}

Edge cases / predpoklady:
  - sim okno se prodluzuje o 20 dni za posledni signal (dedeno z BT-04),
    hold=20 tedy neni oriznuty; nuceny exit na konci dat zachovan.
  - sanity anchor: hold10 @ 15 bps musi reprodukovat MLE-BT-04R NEW
    (stejny engine, stejne signaly) - kontroluje se a reportuje.
  - signal cache je vazana na okno from..to a universe; pri zmene dat
    ve view NUTNO --recompute-signals.
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

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
bt04 = importlib.import_module("mle_bt_04_yearly_monthly_regime_breakdown")
bt04r = importlib.import_module("mle_bt_04r_causal_execution_correction")

HOLDS = [5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20]
COSTS = [15, 30, 50]
BASE_COST = 15
COST_BPS = bt04.COST_BPS  # 15, sanity anchor


def key_of(name, hold):
    return f"{name}_hold{hold}"


def signals_cache_path(out_dir, dfrom, dto):
    return out_dir / f"mle_signals_cache_{dfrom}_{dto}.json"


def save_signals(path, mle_sig):
    ser = {d: [[tk, int(rk)] for tk, rk in lst] for d, lst in mle_sig.items()}
    path.write_text(json.dumps(ser), encoding="utf-8")


def load_signals(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {d: [(tk, int(rk)) for tk, rk in lst] for d, lst in raw.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mle-root",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--from", dest="dfrom", default=bt04.DEFAULT_FROM)
    ap.add_argument("--to", dest="dto", default=bt04.DEFAULT_TO)
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--max-signal-days", dest="maxsig", default="0")
    ap.add_argument("--out", default=None)
    ap.add_argument("--recompute-signals", action="store_true")
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas/numpy")
        return 2

    mle_root = Path(args.mle_root)
    sys.path.insert(0, str(mle_root))
    try:
        from src.engines.rank_matrix_engine import compute_rank_matrix
    except ImportError as e:
        print(f"FAIL: MLE engine import: {e}")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else \
        Path(__file__).resolve().parent.parent.parent
    out_dir = Path(args.out) if args.out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    view_dir = Path(args.view_dir)

    instruments, t2c, t2i, t2s = bt04.load_universe(Path(args.universe_csv))
    print(f"universe {len(instruments)}")
    print(f"pandas {pd.__version__}, numpy {np.__version__}")

    cs, os_ = {}, {}
    for inst in instruments:
        df = bt04.load_ohlc(view_dir, t2c[inst["ticker"]])
        if df is not None and "close" in df.columns:
            cs[inst["ticker"]] = df["close"]
            if "open" in df.columns:
                os_[inst["ticker"]] = df["open"]
    close_m = pd.DataFrame(cs).sort_index()
    open_m = pd.DataFrame(os_).sort_index()
    if close_m.empty:
        print("FAIL: prazdna cenova matice - zkontroluj --view-dir")
        return 2
    full_idx = [str(x.date()) for x in close_m.index]
    print(f"close matrix {close_m.shape}")

    full_pos = {s: i for i, s in enumerate(full_idx)}
    signal_dates = [d for d in full_idx if args.dfrom <= d <= args.dto]
    if not signal_dates:
        print(f"FAIL: zadne obchodni dny v okne {args.dfrom}..{args.dto}")
        return 2
    maxsig = int(args.maxsig)
    if maxsig > 0:
        signal_dates = signal_dates[:maxsig]
    print(f"signal_dates {len(signal_dates)}")

    sp = full_pos[signal_dates[0]]
    lp = full_pos[signal_dates[-1]]
    ep = min(lp + 20 + 1, len(full_idx) - 1)
    sim_dates = full_idx[sp:ep + 1]
    print(f"sim {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)})")

    regime_new, _, valid_by_day = bt04r.build_regime_causal(close_m)

    # --- signaly: cache nebo vypocet ---
    cpath = signals_cache_path(out_dir, args.dfrom, args.dto)
    if cpath.exists() and not args.recompute_signals and maxsig == 0:
        print(f"signaly: nacitam cache {cpath.name}")
        mle_sig = load_signals(cpath)
    else:
        print("signaly: pocitam (pomala cast)...")
        mle_sig = bt04r.compute_signals(close_m, instruments, signal_dates,
                                        compute_rank_matrix)
        if maxsig == 0:
            save_signals(cpath, mle_sig)
            print(f"signaly: ulozeny do cache {cpath.name}")

    # --- grid behu: hold x varianta x cost ---
    grid = {}
    for cost in COSTS:
        for name, ur in [("mle_only", False), ("regime200", True)]:
            for hold in HOLDS:
                tr, dl, dg = bt04r.run_causal(
                    mle_sig, sim_dates, close_m, open_m, hold, cost,
                    t2i, t2s, ur, regime_new)
                row = bt04r.overall_row(dl, tr)
                entry = {"overall": row, "diagnostics": dg}
                if cost == BASE_COST:
                    entry["yearly"] = bt04.yearly_breakdown(dl, tr, regime_new)
                grid.setdefault(cost, {}).setdefault(name, {})[hold] = entry
                print(f"cost {cost} {name} hold{hold}: "
                      f"cagr {row.get('cagr_pct')}% ret "
                      f"{row.get('total_return_pct')}% dd "
                      f"{row.get('max_drawdown_pct')}% sharpe "
                      f"{row.get('sharpe')} trades {row.get('trades')}")

    # --- sanity anchor vs BT-04R ---
    anchor = grid[BASE_COST]["regime200"][10]["overall"]
    print(f"\nSANITY ANCHOR regime200 hold10 @15bps: "
          f"ret {anchor.get('total_return_pct')}% "
          f"(ocekavano ~337.652% dle MLE-BT-04R)")

    # --- verdict hold12 vs hold10 (kriteria definovana predem) ---
    def beats(name, m):
        return all(
            (grid[c][name][12]["overall"].get(m) or -1e9) >
            (grid[c][name][10]["overall"].get(m) or -1e9) for c in COSTS)

    verdict = {}
    for name in ("mle_only", "regime200"):
        c1 = beats(name, "cagr_pct") and beats(name, "sharpe")
        y12 = grid[BASE_COST][name][12]["yearly"]
        y10 = grid[BASE_COST][name][10]["yearly"]
        years = sorted(set(y12) & set(y10))
        wins = sum(1 for y in years
                   if (y12[y].get("total_return_pct") or 0) >
                      (y10[y].get("total_return_pct") or 0))
        c2 = wins > len(years) / 2
        c3 = all(
            (grid[BASE_COST][name][h]["overall"].get("cagr_pct") or -1e9) >=
            (grid[BASE_COST][name][10]["overall"].get("cagr_pct") or -1e9)
            for h in (11, 13))
        verdict[name] = {
            "C1_cagr_and_sharpe_all_costs": c1,
            "C2_wins_majority_of_years": c2,
            "C2_detail": f"{wins}/{len(years)} let",
            "C3_plateau_neighbors_11_13": c3,
            "ROBUST": bool(c1 and c2 and c3)}
        print(f"verdict {name}: {verdict[name]}")

    vseries = [valid_by_day[d] for d in sim_dates if d in valid_by_day]
    payload = {
        "task": "MLE-BT-05 hold period sensitivity",
        "pandas_version": pd.__version__,
        "sim_start": sim_dates[0], "sim_end": sim_dates[-1],
        "sim_days": len(sim_dates), "signal_days": len(signal_dates),
        "holds": HOLDS, "costs_bps": COSTS,
        "engine": "MLE-BT-04R run_causal (import)",
        "SURVIVORSHIP_WARNING": "current 503 universe, survivorship bias.",
        "DATA_SNOOPING_WARNING": "11 holds x 1 in-sample okno; bodove "
                                 "maximum neni dukaz; viz verdict kriteria.",
        "regime_valid_constituents": {"min": int(min(vseries)),
                                      "max": int(max(vseries)),
                                      "median": float(np.median(vseries))},
        "sanity_anchor_regime200_hold10_15bps":
            anchor.get("total_return_pct"),
        "verdict_hold12_vs_hold10": verdict,
        "grid": grid,
    }
    (out_dir / "MLE-BT-05_hold_sensitivity.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # --- MD report ---
    L = ["# MLE-BT-05 — Hold Period Sensitivity (DIAGNOSTIC)", "",
         "Kauzalni engine z MLE-BT-04R. ZADNA zmena frozen strategie.",
         "", f"Sim: {payload['sim_start']}..{payload['sim_end']} "
         f"({payload['sim_days']} dni), pandas {pd.__version__}", "",
         f"**{payload['SURVIVORSHIP_WARNING']}**", "",
         f"**DATA SNOOPING: {payload['DATA_SNOOPING_WARNING']}**", "",
         f"Sanity anchor: regime200 hold10 @15bps ret "
         f"{anchor.get('total_return_pct')}% "
         f"(MLE-BT-04R NEW: 337.652%)", ""]
    for cost in COSTS:
        for name in ("mle_only", "regime200"):
            L += [f"## {name} @ {cost} bps", "",
                  "| hold | ret% | CAGR% | maxDD% | sharpe | calmar "
                  "| trades | avg_expo |",
                  "|---|---|---|---|---|---|---|---|"]
            for hold in HOLDS:
                o = grid[cost][name][hold]["overall"]
                mark = " **" if hold in (10, 12) else " "
                L.append(f"|{mark}{hold}{mark.rstrip()} "
                         f"| {o.get('total_return_pct')} "
                         f"| {o.get('cagr_pct')} "
                         f"| {o.get('max_drawdown_pct')} "
                         f"| {o.get('sharpe')} | {o.get('calmar')} "
                         f"| {o.get('trades')} | {o.get('avg_exposure')} |")
            L.append("")
    L += ["## Rocni rozklad @ 15 bps", ""]
    for name in ("mle_only", "regime200"):
        years = sorted(grid[BASE_COST][name][10]["yearly"].keys())
        L += [f"### {name} — rocni return% podle hold", "",
              "| hold | " + " | ".join(years) + " |",
              "|---|" + "---|" * len(years)]
        for hold in HOLDS:
            yr = grid[BASE_COST][name][hold]["yearly"]
            L.append(f"| {hold} | " + " | ".join(
                str(yr.get(y, {}).get("total_return_pct")) for y in years)
                + " |")
        L.append("")
    L += ["## Verdict hold12 vs hold10 (kriteria definovana PREDEM)", "",
          "Robustni prekonani vyzaduje SOUCASNE: C1 vyssi CAGR i Sharpe "
          "na vsech cost urovnich, C2 vitezstvi ve vetsine let @15bps, "
          "C3 sousedni holdy 11 a 13 take >= hold10 v CAGR (plateau, "
          "ne spike).", ""]
    for name, v in verdict.items():
        L += [f"### {name}", "",
              f"- C1 (CAGR+Sharpe @ 15/30/50 bps): {v['C1_cagr_and_sharpe_all_costs']}",
              f"- C2 (vetsina let): {v['C2_wins_majority_of_years']} "
              f"({v['C2_detail']})",
              f"- C3 (plateau 11/13): {v['C3_plateau_neighbors_11_13']}",
              f"- **ROBUST: {v['ROBUST']}**", ""]
    L += ["## Vyhrady", "",
          "- Diagnostika, NE zmena frozen strategie (hold10 plati, dokud "
          "nerozhodne PM).",
          "- Jedno in-sample okno, survivorship bias, path dependence - "
          "formalni signifikance nedosazitelna.",
          "- Vysledky pri 30/50 bps jsou stress test citlivosti na "
          "naklady, ne predikce realnych fillu (zmeri Faze 2).", ""]
    (out_dir / "MLE-BT-05_hold_sensitivity.md").write_text(
        "\n".join(L), encoding="utf-8")
    print(f"\nOK: reporty v {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
