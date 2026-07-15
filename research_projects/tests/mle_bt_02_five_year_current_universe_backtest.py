"""
mle_bt_02_five_year_current_universe_backtest.py — MLE-BT-02.

READ-ONLY. 5lety extended proof-of-concept: MLE-only momentum strategie
na SOUCASNEM 503 universe, Sharadar DATA-06 ceny. Rozsireni EDGE-BT-01C
(opraveny windowed equity accounting) na delsi historii, bez IRC.

*** SURVIVORSHIP BIAS: current-universe test. NENI survivorship-free
historicky dukaz. Universe = 503 SOUCASNYCH tickeru -> prezivsi. ***

NEDELA: parameter optimization, Decision Resolver, bot/TWS, live/paper,
API/TWS, MLE archive overwrite.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\mle_bt_02_five_year_current_universe_backtest.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Signal: MLE rank_10d <= 10 (fresh z DATA-06). ZADNE IRC.
Obdobi: default 2021-07-01 .. 2026-07-02 (~5 let), parametr --from/--to.

Portfolio pravidla (shodne s EDGE-BT-01C):
    entry next open, exit close po H dni (H=10, 20)
    max 10 pozic, 10% aktualni equity per pozice
    cash ucet, MTM denne, bez duplicit, long only
Naklady: 0, 5, 15, 25 bps round-trip.

Benchmarky:
    equal_weight_universe (denni rebal, vsechny tickery)
    buy_and_hold_universe (equal-weight, drzeno cele okno)
    SPY: NENI v DATA-06 -> proxy = equal_weight_universe.

Windowed equity: iterace JEN pres sim okno (obdobi + exit buffer),
NE cely close_matrix (oprava z 01B potvrzena v 01C).

Edge cases / predpoklady:
    - 5 let x compute_rank_matrix(503) = ~1250 dni -> pomalejsi (minuty).
    - DATA-06 zacina ruzne per ticker; recent IPO nemaji 2021 data ->
      pred jejich prvnim datem nedostanou rank (spravne).
    - survivorship: 503 soucasnych; delistovane/vypadle akcie chybi.
    - sizing 10% aktualni equity, cash ucet.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None

DEFAULT_FROM, DEFAULT_TO = "2021-07-01", "2026-07-02"
LOOKBACKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
MLE_GATE_LB = 10
MAX_POSITIONS = 10
INITIAL_CAPITAL = 100000.0
TARGET_WEIGHT = 1.0 / MAX_POSITIONS
HOLD_VARIANTS = [10, 20]
COST_BPS = [0, 5, 15, 25]
START_BUFFER = 45


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_universe(ucsv):
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    icol = cols.get("industry"); scol = cols.get("sector")
    instruments, t2c, t2i, t2s = [], {}, {}, {}
    for _, r in df.iterrows():
        if not is_active(r[acol]):
            continue
        tk = str(r[tcol]).strip().upper()
        instruments.append({"conid": int(float(r[ccol])), "ticker": tk,
                            "sector": str(r[scol]).strip() if scol else "",
                            "industry": str(r[icol]).strip() if icol else "",
                            "subcategory": ""})
        t2c[tk] = str(r[ccol]); t2i[tk] = str(r[icol]).strip() if icol else ""
        t2s[tk] = str(r[scol]).strip() if scol else ""
    return instruments, t2c, t2i, t2s


def load_ohlc(view_dir, conid):
    f = view_dir / f"{conid}_D1.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)
    df.index = pd.to_datetime(df.index).normalize()
    return df.sort_index()


def run_windowed(signal_by_date, sim_dates, close_m, open_m, hold, cost_bps,
                 t2i, t2s):
    n = len(sim_dates)
    cost_half = cost_bps / 2.0 / 10000.0
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    daily = []
    av = []

    def price_at(matrix, tk, dstr):
        if tk not in matrix.columns:
            return None
        try:
            return matrix.at[pd.Timestamp(dstr), tk]
        except KeyError:
            return None

    for si, dstr in enumerate(sim_dates):
        to_close = [tk for tk, p in positions.items() if p["exit_sim_pos"] == si]
        for tk in to_close:
            p = positions.pop(tk)
            px = price_at(close_m, tk, dstr)
            if px is None or pd.isna(px):
                px = p["entry_price"]
            proceeds = p["shares"] * px * (1 - cost_half)
            cash += proceeds
            cost_in = p["shares"] * p["entry_price"] * (1 + cost_half)
            trades.append({"ticker": tk, "entry_date": p["entry_date"],
                           "exit_date": dstr, "hold_days": hold,
                           "gross_ret": round((px / p["entry_price"] - 1) * 100, 4),
                           "net_ret": round((proceeds / cost_in - 1) * 100, 4),
                           "pnl": round(proceeds - cost_in, 2),
                           "industry": t2i.get(tk, ""), "sector": t2s.get(tk, "")})
        prev = sim_dates[si - 1] if si > 0 else None
        if prev in signal_by_date:
            free = MAX_POSITIONS - len(positions)
            if free > 0:
                mv_prev = 0.0
                if si > 0:
                    for tk, p in positions.items():
                        pxp = price_at(close_m, tk, sim_dates[si - 1])
                        mv_prev += p["shares"] * (pxp if pxp is not None
                                                  and not pd.isna(pxp)
                                                  else p["entry_price"])
                equity_now = cash + mv_prev
                cands = [tk for tk, _ in signal_by_date[prev]
                         if tk not in positions]
                for tk in cands[:free]:
                    op = price_at(open_m, tk, dstr)
                    if op is None or pd.isna(op) or op == 0:
                        continue
                    spend = min(TARGET_WEIGHT * equity_now, cash / (1 + cost_half))
                    if spend <= 0:
                        continue
                    shares = spend / (op * (1 + cost_half))
                    cost_total = shares * op * (1 + cost_half)
                    if shares <= 0 or cost_total > cash + 1e-6:
                        continue
                    cash -= cost_total
                    exit_sim_pos = min(si + hold, n - 1)
                    positions[tk] = {"shares": shares, "entry_price": op,
                                     "entry_date": dstr, "exit_sim_pos": exit_sim_pos}
        mv = 0.0
        for tk, p in positions.items():
            px = price_at(close_m, tk, dstr)
            mv += p["shares"] * (px if px is not None and not pd.isna(px)
                                 else p["entry_price"])
        equity = cash + mv
        exposure = mv / equity if equity > 0 else 0.0
        daily.append({"date": dstr, "equity": round(equity, 2),
                      "exposure": round(exposure, 4), "n_positions": len(positions)})
        if cash < -1e-6:
            av.append(f"{dstr}: cash {cash:.2f}")
        if exposure > 1.0 + 1e-6:
            av.append(f"{dstr}: expo {exposure:.4f}")
    return trades, daily, av


def stats(trades, daily, hold, av, sim_days):
    if not daily:
        return {"n_trades": 0}
    eq = np.array([d["equity"] for d in daily])
    dr = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([])
    total = (eq[-1] / INITIAL_CAPITAL - 1) * 100
    years = sim_days / 252.0
    cagr = ((eq[-1] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else None
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    sharpe = (float(dr.mean() / dr.std() * np.sqrt(252))
              if len(dr) > 1 and dr.std() > 0 else None)
    expo = np.array([d["exposure"] for d in daily])
    npos = np.array([d["n_positions"] for d in daily])
    s = {"total_return_pct": round(total, 4),
         "cagr_pct": round(cagr, 4) if cagr is not None else None,
         "final_equity": round(float(eq[-1]), 2),
         "sharpe_annualized": round(sharpe, 3) if sharpe else None,
         "max_drawdown_pct": round(float(dd.min()) * 100, 4),
         "daily_vol_pct": round(float(dr.std()) * 100, 4) if len(dr) else None,
         "avg_exposure": round(float(expo.mean()), 4),
         "avg_n_positions": round(float(npos.mean()), 2),
         "days_in_market": int((npos > 0).sum()), "sim_days": len(daily),
         "n_trades": len(trades),
         "audit_clean": len(av) == 0, "audit_violations": av[:10]}
    if trades:
        net = np.array([t["net_ret"] for t in trades])
        s["avg_trade_net"] = round(float(net.mean()), 4)
        s["median_trade_net"] = round(float(np.median(net)), 4)
        s["win_rate"] = round(float((net > 0).mean()), 4)
        s["best_trade"] = max(trades, key=lambda t: t["net_ret"])
        s["worst_trade"] = min(trades, key=lambda t: t["net_ret"])
        by_ind = {}
        for t in trades:
            by_ind[t["industry"]] = by_ind.get(t["industry"], 0) + 1
        s["trades_by_industry_top"] = dict(sorted(by_ind.items(),
                                                   key=lambda x: -x[1])[:10])
    return s


def benchmark_stats(close_m, sim_dates, sim_days):
    """equal-weight universe (denni rebal) + buy-and-hold."""
    ts = [pd.Timestamp(d) for d in sim_dates if pd.Timestamp(d) in close_m.index]
    sub = close_m.loc[ts]
    # equal-weight denni rebal
    daily_ret = sub.pct_change().mean(axis=1)
    eq_ew = (1 + daily_ret.fillna(0)).cumprod()
    # buy-and-hold: equal weight od zacatku, drzeno
    first = sub.iloc[0]
    valid = first.notna()
    norm = sub.loc[:, valid].div(first[valid])
    eq_bh = norm.mean(axis=1)

    def curve_stats(eq):
        eq = eq.dropna().values
        if len(eq) < 2:
            return {}
        dr = np.diff(eq) / eq[:-1]
        total = (eq[-1] / eq[0] - 1) * 100
        years = sim_days / 252.0
        cagr = ((eq[-1] / eq[0]) ** (1 / years) - 1) * 100 if years > 0 else None
        rm = np.maximum.accumulate(eq)
        dd = ((eq - rm) / rm).min() * 100
        sharpe = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else None
        return {"total_return_pct": round(total, 4),
                "cagr_pct": round(cagr, 4) if cagr else None,
                "max_drawdown_pct": round(float(dd), 4),
                "sharpe_annualized": round(sharpe, 3) if sharpe else None}
    return {"equal_weight_universe": curve_stats(eq_ew),
            "buy_and_hold_universe": curve_stats(eq_bh)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mle-root",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--from", dest="dfrom", default=DEFAULT_FROM)
    ap.add_argument("--to", dest="dto", default=DEFAULT_TO)
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--max-signal-days", type=int, default=0,
                    help="omezeni poctu signalnich dni (0=vse), rychly test")
    ap.add_argument("--out", default=None)
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

    mrl = Path(args.mrl_root) if args.mrl_root else Path(__file__).resolve().parent.parent.parent
    view_dir = Path(args.view_dir)
    instruments, t2c, t2i, t2s = load_universe(Path(args.universe_csv))
    print(f"universe {len(instruments)}")

    close_series, open_series = {}, {}
    for inst in instruments:
        df = load_ohlc(view_dir, t2c[inst["ticker"]])
        if df is not None and "close" in df.columns:
            close_series[inst["ticker"]] = df["close"]
            if "open" in df.columns:
                open_series[inst["ticker"]] = df["open"]
    close_m = pd.DataFrame(close_series).sort_index()
    open_m = pd.DataFrame(open_series).sort_index()
    full_idx = [str(x.date()) for x in close_m.index]
    print(f"close matrix {close_m.shape}")

    full_pos = {s: i for i, s in enumerate(full_idx)}
    signal_dates = [d for d in full_idx if args.dfrom <= d <= args.dto]
    if args.max_signal_days > 0:
        signal_dates = signal_dates[:args.max_signal_days]
    print(f"signal_dates: {len(signal_dates)} ({args.dfrom}..{args.dto})")

    # sim okno: prvni signal .. posledni signal + max_hold
    sim_start_pos = full_pos[signal_dates[0]]
    last_sig_pos = full_pos[signal_dates[-1]]
    sim_end_pos = min(last_sig_pos + max(HOLD_VARIANTS) + 1, len(full_idx) - 1)
    sim_dates = full_idx[sim_start_pos:sim_end_pos + 1]
    print(f"sim window: {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)} dni)")

    # MLE signaly (fresh)
    mle_sig = {}
    for i, tdate in enumerate(signal_dates):
        run_date = date.fromisoformat(tdate)
        ws = pd.Timestamp(run_date - timedelta(days=START_BUFFER))
        we = pd.Timestamp(run_date)
        cp = {}
        for tk in close_m.columns:
            s = close_m[tk]
            sub = s[(s.index >= ws) & (s.index <= we)]
            if not sub.empty:
                cp[tk] = sub
        inst = [x for x in instruments if x["ticker"] in cp]
        try:
            rm = compute_rank_matrix(cp, inst, run_date, LOOKBACKS).set_index("ticker")
        except Exception:
            continue
        lst = [(tk, int(rm.loc[tk, f"rank_{MLE_GATE_LB}d"]))
               for tk in rm.index
               if not pd.isna(rm.loc[tk, f"rank_{MLE_GATE_LB}d"])
               and int(rm.loc[tk, f"rank_{MLE_GATE_LB}d"]) <= 10]
        lst.sort(key=lambda x: x[1])
        mle_sig[tdate] = lst
        if (i + 1) % 250 == 0:
            print(f"  ... {i+1}/{len(signal_dates)} signalnich dni")

    bench = benchmark_stats(close_m, sim_dates, len(sim_dates))

    results = {}
    for hold in HOLD_VARIANTS:
        results[f"hold_{hold}D"] = {}
        for cost in COST_BPS:
            tr, dl, avv = run_windowed(mle_sig, sim_dates, close_m, open_m,
                                       hold, cost, t2i, t2s)
            results[f"hold_{hold}D"][f"cost_{cost}bps"] = stats(
                tr, dl, hold, avv, len(sim_dates))

    payload = {"sim_start": sim_dates[0], "sim_end": sim_dates[-1],
               "sim_days": len(sim_dates), "signal_days": len(signal_dates),
               "period_requested": [args.dfrom, args.dto],
               "initial_capital": INITIAL_CAPITAL, "max_positions": MAX_POSITIONS,
               "SURVIVORSHIP_WARNING": ("This is a current-universe extended "
                                        "test and MAY CONTAIN SURVIVORSHIP BIAS. "
                                        "Universe = 503 CURRENT tickers. NOT the "
                                        "final survivorship-free historical proof."),
               "benchmarks": bench, "results": results}
    _write(payload, mrl, args.out)

    print(f"\n==== MLE-BT-02: {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)} dni) ====")
    print(f"benchmarks: {bench}")
    for hold in HOLD_VARIANTS:
        print(f"\n-- hold {hold}D --")
        for cost in [0, 15]:
            s = results[f"hold_{hold}D"][f"cost_{cost}bps"]
            print(f"  {cost}bps: tot_ret {s['total_return_pct']}% CAGR {s['cagr_pct']}% "
                  f"sharpe {s['sharpe_annualized']} maxDD {s['max_drawdown_pct']}% "
                  f"expo {s['avg_exposure']} trades {s['n_trades']} "
                  f"avg_net {s['avg_trade_net']} wr {s['win_rate']} "
                  f"audit {'OK' if s['audit_clean'] else 'FAIL'}")
    return 0


def _write(payload, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-BT-02_five_year_current_universe_backtest.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    b = payload["benchmarks"]
    L = ["# MLE-BT-02 — Five-Year Current-Universe Backtest (MLE-only)", "",
         f"## !!! SURVIVORSHIP WARNING", "",
         f"{payload['SURVIVORSHIP_WARNING']}", "",
         f"## Simulacni okno", "",
         f"- period_requested: {payload['period_requested'][0]}.."
         f"{payload['period_requested'][1]}",
         f"- sim_start: {payload['sim_start']}",
         f"- sim_end: {payload['sim_end']}",
         f"- sim_days: {payload['sim_days']}",
         f"- signal_days: {payload['signal_days']}",
         f"- initial_capital: {payload['initial_capital']}, "
         f"max_positions: {payload['max_positions']}", "",
         "## Benchmarky", "",
         f"- equal_weight_universe: {b.get('equal_weight_universe')}",
         f"- buy_and_hold_universe: {b.get('buy_and_hold_universe')}",
         "- SPY: NENI v DATA-06 (universe=S&P clenove, ne ETF); "
         "proxy = equal_weight_universe.", "",
         "## MLE-only strategie", ""]
    for hold in HOLD_VARIANTS:
        L.append(f"### hold {hold}D")
        L.append("")
        L.append("| cost | tot_ret% | CAGR% | sharpe | maxDD% | avg_expo | "
                 "avg_pos | days_mkt/sim | trades | avg_net | median_net | "
                 "win_rate | audit |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cost in COST_BPS:
            s = payload["results"][f"hold_{hold}D"][f"cost_{cost}bps"]
            L.append(f"| {cost}bps | {s.get('total_return_pct')} | {s.get('cagr_pct')} | "
                     f"{s.get('sharpe_annualized')} | {s.get('max_drawdown_pct')} | "
                     f"{s.get('avg_exposure')} | {s.get('avg_n_positions')} | "
                     f"{s.get('days_in_market')}/{s.get('sim_days')} | "
                     f"{s.get('n_trades')} | {s.get('avg_trade_net')} | "
                     f"{s.get('median_trade_net')} | {s.get('win_rate')} | "
                     f"{'OK' if s.get('audit_clean') else 'FAIL'} |")
        L.append("")
        # detail 15bps
        s = payload["results"][f"hold_{hold}D"]["cost_15bps"]
        L.append(f"#### hold{hold} 15bps detail")
        L.append(f"- final_equity: {s.get('final_equity')} "
                 f"(z {payload['initial_capital']})")
        L.append(f"- CAGR: {s.get('cagr_pct')}% | maxDD: {s.get('max_drawdown_pct')}% "
                 f"| sharpe: {s.get('sharpe_annualized')}")
        bt = s.get("best_trade", {}); wt = s.get("worst_trade", {})
        L.append(f"- best_trade: {bt.get('ticker')} {bt.get('net_ret')}% pnl={bt.get('pnl')}")
        L.append(f"- worst_trade: {wt.get('ticker')} {wt.get('net_ret')}% pnl={wt.get('pnl')}")
        L.append(f"- trades_by_industry_top: {s.get('trades_by_industry_top')}")
        L.append("")
    L += ["## Klicove otazky", "",
          "- zustane MLE edge silny i mimo posledni rok (5 let)?",
          "- porazi MLE-only equal-weight universe a buy-and-hold?",
          "- jak vysoky je maxDD pres vice rezimu (5 let vc. 2022 bear)?", "",
          "## Audit", "",
          f"- sim okno: {payload['sim_days']} dni (windowed, ne cela historie)",
          "- cash/exposure audit: viz audit sloupec", "",
          "## Vyhrady (souhrn)", "",
          "- **SURVIVORSHIP BIAS: current 503 universe, prezivsi tickery.**",
          "- NENI survivorship-free historicky dukaz (chybi delistovane/vypadle).",
          "- windowed equity (oprava 01B/01C), cash ucet, MTM.",
          "- entry open[t+1], exit close[entry+H], konec okna -> partial.",
          "- Sharpe/DD orientacni; bez kapacity/likvidity/fillu.",
          "- recent IPO tickery bez 2021 dat -> rank az od jejich prvniho data.", ""]
    (out_dir / "MLE-BT-02_five_year_current_universe_backtest.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
