"""
mle_bt_03_drawdown_control.py — MLE-BT-03.

READ-ONLY. Testuje PREDEM DANE (ne-optimalizovane) drawdown kontroly nad
MLE-only momentum strategii z MLE-BT-02. Cil: snizit maxDD -39% pri co
nejmensi ztrate CAGR.

*** ZADNA OPTIMALIZACE PARAMETRU. Hodnoty jsou konvencni defaulty: ***
    - stop-loss 8% (O'Neil / CAN SLIM standard -7/-8%, uzivatelova metodika)
    - regime filtr 200D MA (standardni long-term trend filtr)
    Nejsou ladene na tato data -> vyhyba se curve-fittingu.

*** SURVIVORSHIP BIAS: current 503 universe. NENI survivorship-free. ***

NEDELA: parameter optimization/sweep, Decision Resolver, bot/TWS,
live/paper, API/TWS, MLE archive overwrite.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\mle_bt_03_drawdown_control.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Varianty (predem dane):
    baseline           : bez kontroly (= MLE-BT-02)
    stop8              : stop-loss 8% (close-based)
    regime200          : nove pozice jen kdyz index > 200D MA
    stop8_regime200    : obe kombinovane

Signal: MLE rank_10d <= 10 (fresh z DATA-06), pocitan JEDNOU, sdilen.
Obdobi: default 2021-07-01 .. 2026-07-02 (~5 let).
Portfolio: max 10 pozic, 10% equity, entry next open, exit close po H dni
    NEBO stop-loss (co driv). Cash ucet, MTM, windowed equity.
Naklady: 0, 5, 15, 25 bps.

Edge cases / predpoklady:
    - stop-loss CLOSE-BASED: pokud close[t] <= entry*(1-0.08), exit na
      close[t] (konzervativni, bez intraday lookahead/fill predpokladu).
      Realny intraday stop by exit dal driv/jinde -> toto je aproximace.
    - regime index = equal-weight universe (cumprod mean daily return) z
      FULL historie -> MA200 dostupne od sim_start (jen minula data).
    - regime blokuje NOVE vstupy; drzene pozice pokracuji do exit/stop.
    - stop preskocen pokud close chybi (drzi dal).
    - signaly pocitany jednou -> varianty se lisi jen portfolio vrstvou.
    - survivorship: 503 soucasnych.
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
STOP_LOSS = 0.08       # 8% O'Neil/CAN SLIM (predem dane)
REGIME_MA = 200        # 200D trend filtr (predem dane)

VARIANTS = ["baseline", "stop8", "regime200", "stop8_regime200"]


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


def build_regime(close_m, full_idx):
    """Equal-weight universe index + MA200. regime_ok[dstr] = index>MA."""
    daily_ret = close_m.pct_change().mean(axis=1)
    idx_level = (1 + daily_ret.fillna(0)).cumprod()
    ma = idx_level.rolling(REGIME_MA, min_periods=REGIME_MA).mean()
    regime_ok = {}
    for ts in idx_level.index:
        dstr = str(ts.date())
        lvl = idx_level.loc[ts]; m = ma.loc[ts]
        # pokud MA neni (zacatek historie) -> povolit (neblokovat)
        regime_ok[dstr] = True if pd.isna(m) else bool(lvl > m)
    return regime_ok


def run_variant(signal_by_date, sim_dates, close_m, open_m, hold, cost_bps,
                t2i, t2s, use_stop, use_regime, regime_ok):
    n = len(sim_dates)
    cost_half = cost_bps / 2.0 / 10000.0
    cash = INITIAL_CAPITAL
    positions = {}
    trades = []
    daily = []
    av = []
    stop_exits = 0

    def price_at(matrix, tk, dstr):
        if tk not in matrix.columns:
            return None
        try:
            return matrix.at[pd.Timestamp(dstr), tk]
        except KeyError:
            return None

    for si, dstr in enumerate(sim_dates):
        # 1a) STOP-LOSS check (close-based) — pred planovanymi exity
        if use_stop:
            stop_hit = []
            for tk, p in positions.items():
                px = price_at(close_m, tk, dstr)
                if px is not None and not pd.isna(px):
                    if px <= p["entry_price"] * (1 - STOP_LOSS):
                        stop_hit.append((tk, px))
            for tk, px in stop_hit:
                p = positions.pop(tk)
                proceeds = p["shares"] * px * (1 - cost_half)
                cash += proceeds
                cost_in = p["shares"] * p["entry_price"] * (1 + cost_half)
                trades.append({"ticker": tk, "entry_date": p["entry_date"],
                               "exit_date": dstr, "exit_reason": "stop",
                               "gross_ret": round((px / p["entry_price"] - 1) * 100, 4),
                               "net_ret": round((proceeds / cost_in - 1) * 100, 4),
                               "pnl": round(proceeds - cost_in, 2),
                               "industry": t2i.get(tk, ""), "sector": t2s.get(tk, "")})
                stop_exits += 1
        # 1b) planovane EXITY
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
                           "exit_date": dstr, "exit_reason": "time",
                           "gross_ret": round((px / p["entry_price"] - 1) * 100, 4),
                           "net_ret": round((proceeds / cost_in - 1) * 100, 4),
                           "pnl": round(proceeds - cost_in, 2),
                           "industry": t2i.get(tk, ""), "sector": t2s.get(tk, "")})
        # 2) ENTRIES
        prev = sim_dates[si - 1] if si > 0 else None
        regime_allows = (not use_regime) or regime_ok.get(dstr, True)
        if prev in signal_by_date and regime_allows:
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
                    positions[tk] = {"shares": shares, "entry_price": op,
                                     "entry_date": dstr,
                                     "exit_sim_pos": min(si + hold, n - 1)}
        # 3) MTM
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
    return trades, daily, av, stop_exits


def stats(trades, daily, hold, av, sim_days, stop_exits):
    if not daily:
        return {"n_trades": 0}
    eq = np.array([d["equity"] for d in daily])
    dr = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([])
    total = (eq[-1] / INITIAL_CAPITAL - 1) * 100
    years = sim_days / 252.0
    cagr = ((eq[-1] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else None
    rm = np.maximum.accumulate(eq)
    max_dd = float(((eq - rm) / rm).min()) * 100
    sharpe = (float(dr.mean() / dr.std() * np.sqrt(252))
              if len(dr) > 1 and dr.std() > 0 else None)
    expo = np.array([d["exposure"] for d in daily])
    npos = np.array([d["n_positions"] for d in daily])
    s = {"total_return_pct": round(total, 4),
         "cagr_pct": round(cagr, 4) if cagr is not None else None,
         "final_equity": round(float(eq[-1]), 2),
         "sharpe_annualized": round(sharpe, 3) if sharpe else None,
         "max_drawdown_pct": round(max_dd, 4),
         "avg_exposure": round(float(expo.mean()), 4),
         "avg_n_positions": round(float(npos.mean()), 2),
         "days_in_market": int((npos > 0).sum()), "sim_days": len(daily),
         "n_trades": len(trades), "stop_exits": stop_exits,
         "audit_clean": len(av) == 0}
    if trades:
        net = np.array([t["net_ret"] for t in trades])
        s["avg_trade_net"] = round(float(net.mean()), 4)
        s["win_rate"] = round(float((net > 0).mean()), 4)
        # calmar = cagr / |maxDD|
        if cagr is not None and max_dd != 0:
            s["calmar"] = round(cagr / abs(max_dd), 3)
    return s


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
    ap.add_argument("--max-signal-days", dest="maxsig", default="0")
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
    maxsig = int(args.maxsig)
    if maxsig > 0:
        signal_dates = signal_dates[:maxsig]
    print(f"signal_dates: {len(signal_dates)}")

    sim_start_pos = full_pos[signal_dates[0]]
    last_sig_pos = full_pos[signal_dates[-1]]
    sim_end_pos = min(last_sig_pos + max(HOLD_VARIANTS) + 1, len(full_idx) - 1)
    sim_dates = full_idx[sim_start_pos:sim_end_pos + 1]
    print(f"sim window: {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)} dni)")

    # regime index (z full historie)
    regime_ok = build_regime(close_m, full_idx)

    # MLE signaly JEDNOU
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

    var_cfg = {"baseline": (False, False), "stop8": (True, False),
               "regime200": (False, True), "stop8_regime200": (True, True)}

    results = {}
    for hold in HOLD_VARIANTS:
        results[f"hold_{hold}D"] = {}
        for cost in COST_BPS:
            results[f"hold_{hold}D"][f"cost_{cost}bps"] = {}
            for var, (us, ur) in var_cfg.items():
                tr, dl, avv, se = run_variant(
                    mle_sig, sim_dates, close_m, open_m, hold, cost,
                    t2i, t2s, us, ur, regime_ok)
                results[f"hold_{hold}D"][f"cost_{cost}bps"][var] = stats(
                    tr, dl, hold, avv, len(sim_dates), se)

    payload = {"sim_start": sim_dates[0], "sim_end": sim_dates[-1],
               "sim_days": len(sim_dates), "signal_days": len(signal_dates),
               "period": [args.dfrom, args.dto],
               "params_predefined": {"stop_loss": STOP_LOSS, "regime_ma": REGIME_MA,
                                     "note": "konvencni defaulty, NEladene na data"},
               "SURVIVORSHIP_WARNING": ("current-universe test, MAY CONTAIN "
                                        "SURVIVORSHIP BIAS. NOT survivorship-free."),
               "results": results}
    _write(payload, mrl, args.out)

    print(f"\n==== MLE-BT-03: {sim_dates[0]}..{sim_dates[-1]} ====")
    for hold in HOLD_VARIANTS:
        print(f"\n-- hold {hold}D, 15bps --")
        blk = results[f"hold_{hold}D"]["cost_15bps"]
        print(f"  {'variant':<18} {'CAGR%':>8} {'maxDD%':>8} {'Sharpe':>7} "
              f"{'Calmar':>7} {'trades':>7} {'stops':>6} {'expo':>6}")
        for var in VARIANTS:
            s = blk[var]
            print(f"  {var:<18} {s.get('cagr_pct'):>8} {s.get('max_drawdown_pct'):>8} "
                  f"{str(s.get('sharpe_annualized')):>7} {str(s.get('calmar')):>7} "
                  f"{s.get('n_trades'):>7} {s.get('stop_exits'):>6} "
                  f"{s.get('avg_exposure'):>6}")
    return 0


def _write(payload, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-BT-03_drawdown_control.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    pp = payload["params_predefined"]
    L = ["# MLE-BT-03 — Drawdown Control (MLE-only)", "",
         f"## !!! SURVIVORSHIP WARNING", "", payload["SURVIVORSHIP_WARNING"], "",
         "## Predem dane parametry (NEoptimalizovane)", "",
         f"- stop_loss: {pp['stop_loss']} (8%, O'Neil/CAN SLIM standard)",
         f"- regime_ma: {pp['regime_ma']} (200D trend filtr)",
         f"- {pp['note']}", "",
         f"## Simulacni okno", "",
         f"- {payload['sim_start']}..{payload['sim_end']} "
         f"({payload['sim_days']} dni), signal_days {payload['signal_days']}", "",
         "## Varianty", "",
         "- baseline: bez kontroly (= MLE-BT-02)",
         "- stop8: stop-loss 8% (close-based)",
         "- regime200: nove pozice jen kdyz index > 200D MA",
         "- stop8_regime200: obe kombinovane", ""]
    for hold in HOLD_VARIANTS:
        L.append(f"## hold {hold}D")
        L.append("")
        for cost in COST_BPS:
            L.append(f"### {cost} bps")
            L.append("")
            L.append("| variant | CAGR% | total% | maxDD% | Sharpe | Calmar | "
                     "trades | stops | avg_expo | win_rate |")
            L.append("|---|---|---|---|---|---|---|---|---|---|")
            blk = payload["results"][f"hold_{hold}D"][f"cost_{cost}bps"]
            for var in VARIANTS:
                s = blk[var]
                L.append(f"| {var} | {s.get('cagr_pct')} | {s.get('total_return_pct')} | "
                         f"{s.get('max_drawdown_pct')} | {s.get('sharpe_annualized')} | "
                         f"{s.get('calmar')} | {s.get('n_trades')} | "
                         f"{s.get('stop_exits')} | {s.get('avg_exposure')} | "
                         f"{s.get('win_rate')} |")
            L.append("")
    L += ["## Jak cist (Calmar = CAGR / |maxDD|)", "",
          "- Calmar vyssi = lepsi pomer vynos/drawdown.",
          "- cil: snizit maxDD pri co nejmensi ztrate CAGR -> nejvyssi Calmar.", "",
          "## Klicove otazky", "",
          "- ktera varianta ma nejvyssi Calmar (nejlepsi vynos/DD pomer)?",
          "- kolik CAGR se obetuje za snizeni maxDD?",
          "- whipsaw: kolik stop_exits (vysoke = stop uriznul hodne pozic)?", "",
          "## Vyhrady (souhrn)", "",
          "- **SURVIVORSHIP BIAS: current 503 universe.**",
          "- parametry PREDEM dane (8%, 200D), NEladene -> ale i tak IN-SAMPLE",
          "  na jednom 5letem okne. Ne out-of-sample dukaz.",
          "- stop CLOSE-based (aproximace, ne intraday fill).",
          "- regime index = equal-weight universe (ne SPY).",
          "- Sharpe/DD orientacni; bez kapacity/likvidity/slippage nad bps.", ""]
    (out_dir / "MLE-BT-03_drawdown_control.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
