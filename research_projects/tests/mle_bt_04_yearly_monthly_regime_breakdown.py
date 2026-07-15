"""
mle_bt_04_yearly_monthly_regime_breakdown.py — MLE-BT-04.

READ-ONLY DIAGNOSTIC. Rozlozi 5lety MLE-only backtest podle roku/mesicu
a analyzuje, PROC regime200 funguje. NENI optimalizace.

*** SURVIVORSHIP BIAS: current 503 universe. ***

NEDELA: parameter optimization, alt MA hodnoty, stop-loss retest,
regime ML, Decision Resolver, bot/TWS, live/paper.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\mle_bt_04_yearly_monthly_regime_breakdown.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Varianty: baseline hold10, regime200 hold10, baseline hold20, regime200 hold20.
Cost: primarne 15 bps. Obdobi: 2021-07-01..2026-07-02.

regime200: nove pozice jen kdyz equal-weight universe index > MA200.
    NE SPY. NEoptimalizovat MA200.

Edge cases / predpoklady:
    - signaly + regime pocitany jednou, sdileny.
    - rocni/mesicni rozklad = segmentace denni equity krivky.
    - DD epizody: peak->trough->recovery z equity. recovery = navrat na peak.
    - attribution: top/worst tickery z pnl trades v obdobi.
    - benchmark = equal-weight universe (denni), stejny segment.
    - regime status per den z build_regime.
    - survivorship: 503 soucasnych.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
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
COST_BPS = 15
REGIME_MA = 200
SPECIAL_TICKERS = ["CVNA", "SMCI", "SNDK", "INTC"]

VARIANTS = [("baseline", 10, False), ("regime200", 10, True),
            ("baseline", 20, False), ("regime200", 20, True)]


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


def build_regime(close_m):
    daily_ret = close_m.pct_change().mean(axis=1)
    idx = (1 + daily_ret.fillna(0)).cumprod()
    ma = idx.rolling(REGIME_MA, min_periods=REGIME_MA).mean()
    ok = {}
    for ts in idx.index:
        m = ma.loc[ts]
        ok[str(ts.date())] = True if pd.isna(m) else bool(idx.loc[ts] > m)
    return ok, idx


def run(signal_by_date, sim_dates, close_m, open_m, hold, cost_bps,
        t2i, t2s, use_regime, regime_ok):
    n = len(sim_dates)
    ch = cost_bps / 2.0 / 10000.0
    cash = INITIAL_CAPITAL
    pos = {}
    trades = []
    daily = []

    def px(m, tk, d):
        if tk not in m.columns:
            return None
        try:
            return m.at[pd.Timestamp(d), tk]
        except KeyError:
            return None

    for si, dstr in enumerate(sim_dates):
        for tk in [t for t, p in pos.items() if p["exit"] == si]:
            p = pos.pop(tk)
            pr = px(close_m, tk, dstr)
            if pr is None or pd.isna(pr):
                pr = p["ep"]
            proceeds = p["sh"] * pr * (1 - ch)
            cash += proceeds
            ci = p["sh"] * p["ep"] * (1 + ch)
            trades.append({"ticker": tk, "entry_date": p["ed"], "exit_date": dstr,
                           "net_ret": round((proceeds / ci - 1) * 100, 4),
                           "pnl": round(proceeds - ci, 2),
                           "industry": t2i.get(tk, ""), "sector": t2s.get(tk, "")})
        prev = sim_dates[si - 1] if si > 0 else None
        allow = (not use_regime) or regime_ok.get(dstr, True)
        if prev in signal_by_date and allow:
            free = MAX_POSITIONS - len(pos)
            if free > 0:
                mvp = 0.0
                if si > 0:
                    for tk, p in pos.items():
                        pp = px(close_m, tk, sim_dates[si - 1])
                        mvp += p["sh"] * (pp if pp is not None and not pd.isna(pp) else p["ep"])
                eqn = cash + mvp
                cands = [tk for tk, _ in signal_by_date[prev] if tk not in pos]
                for tk in cands[:free]:
                    op = px(open_m, tk, dstr)
                    if op is None or pd.isna(op) or op == 0:
                        continue
                    spend = min(TARGET_WEIGHT * eqn, cash / (1 + ch))
                    if spend <= 0:
                        continue
                    sh = spend / (op * (1 + ch))
                    ct = sh * op * (1 + ch)
                    if sh <= 0 or ct > cash + 1e-6:
                        continue
                    cash -= ct
                    pos[tk] = {"sh": sh, "ep": op, "ed": dstr, "exit": min(si + hold, n - 1)}
        mv = 0.0
        for tk, p in pos.items():
            pr = px(close_m, tk, dstr)
            mv += p["sh"] * (pr if pr is not None and not pd.isna(pr) else p["ep"])
        eq = cash + mv
        daily.append({"date": dstr, "equity": round(eq, 2),
                      "exposure": round(mv / eq if eq > 0 else 0, 4),
                      "n_positions": len(pos)})
    return trades, daily


def segment_stats(daily_seg, trades_seg, days_per_year=252):
    if not daily_seg or len(daily_seg) < 2:
        return {}
    eq = np.array([d["equity"] for d in daily_seg])
    r = eq / eq[0]  # normalizovany return v segmentu
    dr = np.diff(eq) / eq[:-1]
    total = (r[-1] - 1) * 100
    rm = np.maximum.accumulate(eq)
    dd = ((eq - rm) / rm).min() * 100
    sharpe = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else None
    vol = float(dr.std()) * np.sqrt(252) * 100
    expo = np.mean([d["exposure"] for d in daily_seg])
    npos = np.mean([d["n_positions"] for d in daily_seg])
    out = {"total_return_pct": round(total, 3),
           "max_drawdown_pct": round(float(dd), 3),
           "sharpe": round(sharpe, 3) if sharpe else None,
           "volatility_pct": round(vol, 3),
           "calmar": round(total / abs(dd), 3) if dd != 0 else None,
           "avg_exposure": round(float(expo), 3),
           "avg_positions": round(float(npos), 2),
           "n_days": len(daily_seg)}
    if trades_seg:
        net = np.array([t["net_ret"] for t in trades_seg])
        out["trades"] = len(trades_seg)
        out["avg_trade_net"] = round(float(net.mean()), 3)
        out["median_trade_net"] = round(float(np.median(net)), 3)
        out["win_rate"] = round(float((net > 0).mean()), 3)
        bt = max(trades_seg, key=lambda t: t["pnl"])
        wt = min(trades_seg, key=lambda t: t["pnl"])
        out["best_trade"] = f"{bt['ticker']} {bt['net_ret']}% (pnl {bt['pnl']})"
        out["worst_trade"] = f"{wt['ticker']} {wt['net_ret']}% (pnl {wt['pnl']})"
        by_tk, by_ind = defaultdict(float), defaultdict(float)
        for t in trades_seg:
            by_tk[t["ticker"]] += t["pnl"]
            by_ind[t["industry"]] += t["pnl"]
        out["top_contrib_tickers"] = [(k, round(v, 0)) for k, v in
                                      sorted(by_tk.items(), key=lambda x: -x[1])[:5]]
        out["worst_contrib_tickers"] = [(k, round(v, 0)) for k, v in
                                        sorted(by_tk.items(), key=lambda x: x[1])[:5]]
        out["top_industries"] = [(k, round(v, 0)) for k, v in
                                 sorted(by_ind.items(), key=lambda x: -x[1])[:5]]
        out["worst_industries"] = [(k, round(v, 0)) for k, v in
                                   sorted(by_ind.items(), key=lambda x: x[1])[:5]]
    else:
        out["trades"] = 0
    return out


def yearly_breakdown(daily, trades, regime_ok):
    by_year_d = defaultdict(list)
    for d in daily:
        by_year_d[d["date"][:4]].append(d)
    by_year_t = defaultdict(list)
    for t in trades:
        by_year_t[t["exit_date"][:4]].append(t)
    out = {}
    for y in sorted(by_year_d):
        st = segment_stats(by_year_d[y], by_year_t.get(y, []))
        # regime % ON
        yd = [d["date"] for d in by_year_d[y]]
        on = sum(1 for dd in yd if regime_ok.get(dd, True))
        st["regime_pct_on"] = round(on / len(yd), 3) if yd else None
        out[y] = st
    return out


def monthly_breakdown(daily, trades, regime_ok):
    by_m_d = defaultdict(list)
    for d in daily:
        by_m_d[d["date"][:7]].append(d)
    by_m_t = defaultdict(list)
    for t in trades:
        by_m_t[t["exit_date"][:7]].append(t)
    out = {}
    for m in sorted(by_m_d):
        seg = by_m_d[m]
        eq = np.array([d["equity"] for d in seg])
        ret = (eq[-1] / eq[0] - 1) * 100 if len(eq) > 1 else 0
        rm = np.maximum.accumulate(eq)
        intramax_dd = ((eq - rm) / rm).min() * 100 if len(eq) > 1 else 0
        tr = by_m_t.get(m, [])
        wr = float((np.array([t["net_ret"] for t in tr]) > 0).mean()) if tr else None
        md = [d["date"] for d in seg]
        on = sum(1 for dd in md if regime_ok.get(dd, True))
        out[m] = {"return_pct": round(float(ret), 3),
                  "intramonth_max_dd_pct": round(float(intramax_dd), 3),
                  "trades": len(tr),
                  "win_rate": round(wr, 3) if wr is not None else None,
                  "avg_exposure": round(float(np.mean([d["exposure"] for d in seg])), 3),
                  "regime_pct_on": round(on / len(md), 3) if md else None}
    return out


def benchmark_monthly_yearly(close_m, sim_dates):
    ts = [pd.Timestamp(d) for d in sim_dates if pd.Timestamp(d) in close_m.index]
    sub = close_m.loc[ts]
    dr = sub.pct_change().mean(axis=1).fillna(0)
    eqb = (1 + dr).cumprod()
    by_y, by_m = {}, {}
    dfb = pd.DataFrame({"eq": eqb.values}, index=[str(x.date()) for x in eqb.index])
    for y in sorted(set(i[:4] for i in dfb.index)):
        seg = dfb[[i.startswith(y) for i in dfb.index]]["eq"].values
        if len(seg) > 1:
            by_y[y] = round((seg[-1] / seg[0] - 1) * 100, 3)
    for m in sorted(set(i[:7] for i in dfb.index)):
        seg = dfb[[i.startswith(m) for i in dfb.index]]["eq"].values
        if len(seg) > 1:
            by_m[m] = round((seg[-1] / seg[0] - 1) * 100, 3)
    return by_y, by_m


def drawdown_episodes(daily, trades, regime_ok, top_n=5):
    eq = np.array([d["equity"] for d in daily])
    dates = [d["date"] for d in daily]
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    episodes = []
    in_dd = False
    peak_i = 0
    for i in range(len(eq)):
        if not in_dd and dd[i] < 0:
            in_dd = True
            peak_i = i - 1 if i > 0 else 0
            trough_i = i
        elif in_dd:
            if eq[i] < eq[trough_i]:
                trough_i = i
            if eq[i] >= rm[peak_i] - 1e-9:  # recovered
                episodes.append((peak_i, trough_i, i))
                in_dd = False
    if in_dd:
        episodes.append((peak_i, trough_i, None))
    # depth
    ep_list = []
    for peak_i, trough_i, rec_i in episodes:
        depth = (eq[trough_i] / eq[peak_i] - 1) * 100
        dur = (rec_i - peak_i) if rec_i else (len(eq) - 1 - peak_i)
        # trades entered during peak..trough
        p_date, t_date = dates[peak_i], dates[trough_i]
        seg_tr = [t for t in trades if p_date <= t["entry_date"] <= t_date]
        by_tk, by_ind = defaultdict(float), defaultdict(float)
        for t in seg_tr:
            by_tk[t["ticker"]] += t["pnl"]
            by_ind[t["industry"]] += t["pnl"]
        loss_tk = sorted(by_tk.items(), key=lambda x: x[1])[:5]
        loss_ind = sorted(by_ind.items(), key=lambda x: x[1])[:5]
        # regime status during entry window
        entry_dates = [dates[j] for j in range(peak_i, trough_i + 1)]
        on = sum(1 for dd_ in entry_dates if regime_ok.get(dd_, True))
        ep_list.append({
            "start_date": dates[peak_i], "trough_date": dates[trough_i],
            "recovery_date": dates[rec_i] if rec_i else None,
            "depth_pct": round(float(depth), 3),
            "duration_days": int(dur),
            "recovered": rec_i is not None,
            "regime_pct_on_during_dd": round(on / len(entry_dates), 3) if entry_dates else None,
            "loss_tickers": [(k, round(v, 0)) for k, v in loss_tk],
            "loss_industries": [(k, round(v, 0)) for k, v in loss_ind]})
    ep_list.sort(key=lambda e: e["depth_pct"])
    return ep_list[:top_n]


def special_checks(all_trades_by_variant):
    out = {}
    for vk, trades in all_trades_by_variant.items():
        by_tk = defaultdict(float)
        total_pnl = 0.0
        for t in trades:
            by_tk[t["ticker"]] += t["pnl"]
            total_pnl += t["pnl"]
        spec = {}
        for tk in SPECIAL_TICKERS:
            pnl = by_tk.get(tk, 0.0)
            spec[tk] = {"pnl": round(pnl, 0),
                        "pct_of_total": round(pnl / total_pnl * 100, 2)
                        if total_pnl != 0 else None}
        # top ticker share
        top = sorted(by_tk.items(), key=lambda x: -x[1])[:5]
        out[vk] = {"special_tickers": spec, "total_pnl": round(total_pnl, 0),
                   "top5_tickers_pnl": [(k, round(v, 0)) for k, v in top],
                   "top5_share_pct": round(sum(v for _, v in top) / total_pnl * 100, 2)
                   if total_pnl != 0 else None}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mle-root", default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv", default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir", default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
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

    cs, os_ = {}, {}
    for inst in instruments:
        df = load_ohlc(view_dir, t2c[inst["ticker"]])
        if df is not None and "close" in df.columns:
            cs[inst["ticker"]] = df["close"]
            if "open" in df.columns:
                os_[inst["ticker"]] = df["open"]
    close_m = pd.DataFrame(cs).sort_index()
    open_m = pd.DataFrame(os_).sort_index()
    full_idx = [str(x.date()) for x in close_m.index]
    print(f"close matrix {close_m.shape}")

    full_pos = {s: i for i, s in enumerate(full_idx)}
    signal_dates = [d for d in full_idx if args.dfrom <= d <= args.dto]
    maxsig = int(args.maxsig)
    if maxsig > 0:
        signal_dates = signal_dates[:maxsig]
    print(f"signal_dates {len(signal_dates)}")

    sp = full_pos[signal_dates[0]]
    lp = full_pos[signal_dates[-1]]
    ep = min(lp + 20 + 1, len(full_idx) - 1)
    sim_dates = full_idx[sp:ep + 1]
    print(f"sim {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)})")

    regime_ok, _ = build_regime(close_m)

    mle_sig = {}
    for i, td in enumerate(signal_dates):
        rd = date.fromisoformat(td)
        ws = pd.Timestamp(rd - timedelta(days=45)); we = pd.Timestamp(rd)
        cp = {}
        for tk in close_m.columns:
            s = close_m[tk]
            sub = s[(s.index >= ws) & (s.index <= we)]
            if not sub.empty:
                cp[tk] = sub
        inst = [x for x in instruments if x["ticker"] in cp]
        try:
            rm = compute_rank_matrix(cp, inst, rd, LOOKBACKS).set_index("ticker")
        except Exception:
            continue
        lst = [(tk, int(rm.loc[tk, f"rank_{MLE_GATE_LB}d"])) for tk in rm.index
               if not pd.isna(rm.loc[tk, f"rank_{MLE_GATE_LB}d"])
               and int(rm.loc[tk, f"rank_{MLE_GATE_LB}d"]) <= 10]
        lst.sort(key=lambda x: x[1])
        mle_sig[td] = lst
        if (i + 1) % 250 == 0:
            print(f"  ... {i+1}/{len(signal_dates)}")

    bench_y, bench_m = benchmark_monthly_yearly(close_m, sim_dates)

    variants_out = {}
    all_trades = {}
    for name, hold, ur in VARIANTS:
        key = f"{name}_hold{hold}"
        tr, dl = run(mle_sig, sim_dates, close_m, open_m, hold, COST_BPS,
                     t2i, t2s, ur, regime_ok)
        all_trades[key] = tr
        variants_out[key] = {
            "overall": segment_stats(dl, tr),
            "yearly": yearly_breakdown(dl, tr, regime_ok),
            "monthly": monthly_breakdown(dl, tr, regime_ok),
            "drawdown_episodes": drawdown_episodes(dl, tr, regime_ok)}

    # regime effectiveness: baseline vs regime200 per year (hold10, hold20)
    eff = {}
    for hold in [10, 20]:
        b = variants_out[f"baseline_hold{hold}"]
        r = variants_out[f"regime200_hold{hold}"]
        yearly_cmp = {}
        for y in b["yearly"]:
            by = b["yearly"][y]; ry = r["yearly"].get(y, {})
            yearly_cmp[y] = {
                "baseline_return": by.get("total_return_pct"),
                "regime_return": ry.get("total_return_pct"),
                "baseline_maxdd": by.get("max_drawdown_pct"),
                "regime_maxdd": ry.get("max_drawdown_pct"),
                "regime_pct_on": ry.get("regime_pct_on"),
                "return_diff": round((ry.get("total_return_pct") or 0) -
                                     (by.get("total_return_pct") or 0), 3),
                "dd_improvement": round((ry.get("max_drawdown_pct") or 0) -
                                        (by.get("max_drawdown_pct") or 0), 3)}
        # monthly: good months missed / bad months avoided
        good_missed = bad_avoided = 0
        for m in b["monthly"]:
            bm = b["monthly"][m]; rm_ = r["monthly"].get(m, {})
            r_on = (rm_.get("regime_pct_on") or 1) < 0.5  # regime mostly OFF
            if r_on:  # regime byl OFF (v cash)
                if (bm.get("return_pct") or 0) > 1:
                    good_missed += 1
                if (bm.get("return_pct") or 0) < -1:
                    bad_avoided += 1
        eff[f"hold{hold}"] = {
            "yearly_comparison": yearly_cmp,
            "good_months_missed_by_regime": good_missed,
            "bad_months_avoided_by_regime": bad_avoided,
            "baseline_overall": {k: b["overall"].get(k) for k in
                                 ["total_return_pct", "max_drawdown_pct", "sharpe", "calmar", "avg_exposure"]},
            "regime_overall": {k: r["overall"].get(k) for k in
                               ["total_return_pct", "max_drawdown_pct", "sharpe", "calmar", "avg_exposure"]}}

    special = special_checks(all_trades)

    payload = {"sim_start": sim_dates[0], "sim_end": sim_dates[-1],
               "sim_days": len(sim_dates), "signal_days": len(signal_dates),
               "cost_bps": COST_BPS,
               "SURVIVORSHIP_WARNING": "current 503 universe, survivorship bias.",
               "benchmark_yearly": bench_y, "benchmark_monthly": bench_m,
               "variants": variants_out,
               "regime_effectiveness": eff,
               "special_checks": special}
    _write(payload, mrl, args.out)

    print(f"\n==== MLE-BT-04 ({len(sim_dates)} dni) ====")
    for key in ["baseline_hold10", "regime200_hold10", "baseline_hold20", "regime200_hold20"]:
        o = variants_out[key]["overall"]
        print(f"\n{key}: ret {o.get('total_return_pct')}% maxDD {o.get('max_drawdown_pct')}% "
              f"sharpe {o.get('sharpe')} calmar {o.get('calmar')}")
        print("  yearly:")
        for y, ys in variants_out[key]["yearly"].items():
            print(f"    {y}: ret {ys.get('total_return_pct')}% dd {ys.get('max_drawdown_pct')}% "
                  f"bench {bench_y.get(y)}% regime_on {ys.get('regime_pct_on')}")
    print("\nregime effectiveness:")
    for h, e in eff.items():
        print(f"  {h}: good_missed {e['good_months_missed_by_regime']} "
              f"bad_avoided {e['bad_months_avoided_by_regime']}")
    return 0


def _write(payload, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-BT-04_yearly_monthly_regime_breakdown.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    L = ["# MLE-BT-04 — Yearly/Monthly/Regime Breakdown (DIAGNOSTIC)", "",
         f"## SURVIVORSHIP WARNING", "", payload["SURVIVORSHIP_WARNING"], "",
         f"Sim: {payload['sim_start']}..{payload['sim_end']} "
         f"({payload['sim_days']} dni), cost {payload['cost_bps']}bps", "",
         "## Overall (4 varianty)", "",
         "| variant | return% | maxDD% | sharpe | calmar | avg_expo |",
         "|---|---|---|---|---|---|"]
    for key in ["baseline_hold10", "regime200_hold10", "baseline_hold20", "regime200_hold20"]:
        o = payload["variants"][key]["overall"]
        L.append(f"| {key} | {o.get('total_return_pct')} | {o.get('max_drawdown_pct')} | "
                 f"{o.get('sharpe')} | {o.get('calmar')} | {o.get('avg_exposure')} |")
    # yearly per variant
    for key in ["baseline_hold10", "regime200_hold10", "baseline_hold20", "regime200_hold20"]:
        L += ["", f"## {key} — rocni rozklad", "",
              "| rok | strat_ret% | bench_ret% | excess% | maxDD% | sharpe | calmar | "
              "vol% | expo | pos | trades | avg_net | med_net | win_rate | regime_on% |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for y, s in payload["variants"][key]["yearly"].items():
            bench = payload["benchmark_yearly"].get(y)
            excess = round((s.get("total_return_pct") or 0) - (bench or 0), 2) if bench is not None else None
            L.append(f"| {y} | {s.get('total_return_pct')} | {bench} | {excess} | "
                     f"{s.get('max_drawdown_pct')} | {s.get('sharpe')} | {s.get('calmar')} | "
                     f"{s.get('volatility_pct')} | {s.get('avg_exposure')} | "
                     f"{s.get('avg_positions')} | {s.get('trades')} | {s.get('avg_trade_net')} | "
                     f"{s.get('median_trade_net')} | {s.get('win_rate')} | {s.get('regime_pct_on')} |")
        # yearly contrib detail
        for y, s in payload["variants"][key]["yearly"].items():
            if s.get("top_contrib_tickers"):
                L.append(f"- **{y}** best_trade: {s.get('best_trade')} | worst_trade: {s.get('worst_trade')}")
                L.append(f"  - top tickers: {s.get('top_contrib_tickers')}")
                L.append(f"  - worst tickers: {s.get('worst_contrib_tickers')}")
                L.append(f"  - top industries: {s.get('top_industries')}")
                L.append(f"  - worst industries: {s.get('worst_industries')}")
    # drawdown episodes
    for key in ["baseline_hold10", "regime200_hold10", "baseline_hold20", "regime200_hold20"]:
        L += ["", f"## {key} — TOP 5 drawdown epizod", ""]
        for i, e in enumerate(payload["variants"][key]["drawdown_episodes"], 1):
            L.append(f"{i}. depth {e['depth_pct']}% | {e['start_date']} -> trough {e['trough_date']} "
                     f"-> recovery {e['recovery_date']} | dur {e['duration_days']}d | "
                     f"recovered {e['recovered']} | regime_on {e['regime_pct_on_during_dd']}")
            L.append(f"   loss_tickers: {e['loss_tickers']}")
            L.append(f"   loss_industries: {e['loss_industries']}")
    # regime effectiveness
    L += ["", "## Regime200 effectiveness", ""]
    for h, e in payload["regime_effectiveness"].items():
        L += [f"### {h}", "",
              f"- baseline overall: {e['baseline_overall']}",
              f"- regime overall: {e['regime_overall']}",
              f"- good_months_missed_by_regime: {e['good_months_missed_by_regime']}",
              f"- bad_months_avoided_by_regime: {e['bad_months_avoided_by_regime']}", "",
              "| rok | base_ret | regime_ret | ret_diff | base_dd | regime_dd | dd_improve | regime_on% |",
              "|---|---|---|---|---|---|---|---|"]
        for y, c in e["yearly_comparison"].items():
            L.append(f"| {y} | {c['baseline_return']} | {c['regime_return']} | {c['return_diff']} | "
                     f"{c['baseline_maxdd']} | {c['regime_maxdd']} | {c['dd_improvement']} | {c['regime_pct_on']} |")
        L.append("")
    # special checks
    L += ["## Special checks (ticker koncentrace)", ""]
    for vk, s in payload["special_checks"].items():
        L.append(f"### {vk}")
        L.append(f"- total_pnl: {s['total_pnl']}")
        L.append(f"- top5_tickers_pnl: {s['top5_tickers_pnl']} (share {s['top5_share_pct']}%)")
        for tk, d in s["special_tickers"].items():
            L.append(f"- {tk}: pnl {d['pnl']} ({d['pct_of_total']}% of total)")
        L.append("")
    L += ["## Vyhrady", "",
          "- **SURVIVORSHIP: current 503 universe.**",
          "- diagnostic only, NE optimalizace.",
          "- regime index = equal-weight universe (ne SPY).",
          "- DD epizoda recovery = navrat na predchozi peak.",
          "- attribution z pnl trades v obdobi.",
          "- Sharpe/DD orientacni; in-sample jeden 5lety window.", ""]
    (out_dir / "MLE-BT-04_yearly_monthly_regime_breakdown.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
