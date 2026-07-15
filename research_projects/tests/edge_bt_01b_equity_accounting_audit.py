"""
edge_bt_01b_equity_accounting_audit.py — EDGE-BT-01B.

READ-ONLY. OPRAVA equity accountingu z EDGE-BT-01. Skutecna denni equity
krivka s EXPLICITNIM cash uctem (ne aproximace trade returns / max_pos).

NEDELA: parameter optimization, Decision Resolver, bot/TWS, live/paper,
API/TWS, MLE archive overwrite.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\edge_bt_01b_equity_accounting_audit.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Ucetni model (opraveny):
    initial_capital = 100000
    entry: koupit za next open, target = 10% AKTUALNI equity
      shares = floor_none(target_value / open_price)  (frakce povoleny)
      cash -= shares * open_price * (1 + cost_half)
    exit: prodat za close[entry+H]
      cash += shares * close * (1 - cost_half)
    denne: equity = cash + sum(shares_i * close_today_i)  [mark-to-market]
    exposure = market_value / equity
    portfolio_daily_return = equity_t / equity_{t-1} - 1
    Sharpe z daily returns, maxDD z equity krivky.

Audit:
    cash >= 0 (nikdy zaporny)
    positions <= 10
    exposure <= 100%
    porovnat s EDGE-BT-01 aproximaci (proc se lisila)

Edge cases / predpoklady:
    - cost_half = cost_bps/2 (half round-trip na kazde strane).
    - target 10% equity, ale pokud cash < target -> koupit za dostupny cash.
    - entry open[t+1]: signal z predchoziho dne (t) -> nakup na open(t+1).
    - exit close[entry_pos+H]: konec dat -> exit na poslednim close (partial).
    - max 10 pozic, plne -> nove signaly zahozeny.
    - zadna duplicitni pozice v drzenem tickeru.
    - MLE fresh z DATA-06 per den (compute_rank_matrix).
    - survivorship 503 soucasnych. Sharpe/DD orientacni (245 dni).
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

OVERLAP_FROM, OVERLAP_TO = "2025-07-09", "2026-06-27"
WEEKEND_ARTIFACTS = {"2026-05-31", "2026-06-06", "2026-06-13"}
LOOKBACKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
MLE_GATE_LB = 10
IRC_GATE_LB = 20
TOP_N = 10
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


def run_portfolio(signal_by_date, cidx_str, close_m, open_m, hold, cost_bps,
                  t2i, t2s):
    """Skutecny cash-based portfolio backtest."""
    n = len(cidx_str)
    cost_half = cost_bps / 2.0 / 10000.0  # bps -> frakce, half na stranu
    cash = INITIAL_CAPITAL
    # pozice: ticker -> {shares, entry_price, entry_date, exit_pos, entry_pos}
    positions = {}
    trades = []
    daily = []  # {date, cash, market_value, equity, exposure, n_positions}
    audit_violations = []

    for di, dstr in enumerate(cidx_str):
        # 1) EXITY (pozice s exit_pos == di) - prodej na dnesni close
        to_close = [tk for tk, p in positions.items() if p["exit_pos"] == di]
        for tk in to_close:
            p = positions.pop(tk)
            px = close_m[tk].iloc[di] if tk in close_m else None
            if px is None or pd.isna(px):
                px = p["entry_price"]  # fallback
            proceeds = p["shares"] * px * (1 - cost_half)
            cash += proceeds
            cost_basis = p["shares"] * p["entry_price"]
            gross = (px / p["entry_price"] - 1) * 100
            net = (proceeds / (p["shares"] * p["entry_price"] *
                              (1 + cost_half)) - 1) * 100
            trades.append({"ticker": tk, "entry_date": p["entry_date"],
                           "exit_date": dstr, "hold_days": hold,
                           "gross_ret": round(gross, 4),
                           "net_ret": round(net, 4),
                           "shares": round(p["shares"], 4),
                           "entry_price": round(p["entry_price"], 4),
                           "exit_price": round(px, 4),
                           "pnl": round(proceeds - p["shares"] * p["entry_price"]
                                        * (1 + cost_half), 2),
                           "industry": t2i.get(tk, ""),
                           "sector": t2s.get(tk, "")})

        # 2) ENTRIES - signal z predchoziho dne, nakup na dnesni open
        prev = cidx_str[di - 1] if di > 0 else None
        if prev in signal_by_date:
            free = MAX_POSITIONS - len(positions)
            if free > 0:
                # aktualni equity pro sizing (cash + MTM po exitech)
                mv_now = 0.0
                for tk, p in positions.items():
                    px = close_m[tk].iloc[di] if tk in close_m else None
                    # pouzij open jako aproximaci intraday? -> pro sizing
                    # pouzijeme predchozi close (di-1) jako znamou hodnotu
                    pxp = close_m[tk].iloc[di - 1] if (tk in close_m and di > 0) else p["entry_price"]
                    if pxp is not None and not pd.isna(pxp):
                        mv_now += p["shares"] * pxp
                equity_now = cash + mv_now
                cands = [tk for tk, _ in signal_by_date[prev]
                         if tk not in positions]
                for tk in cands[:free]:
                    op = open_m[tk].iloc[di] if tk in open_m else None
                    if op is None or pd.isna(op) or op == 0:
                        continue
                    target_value = TARGET_WEIGHT * equity_now
                    # nesmi prekrocit dostupny cash
                    spend = min(target_value, cash / (1 + cost_half))
                    if spend <= 0:
                        continue
                    shares = spend / (op * (1 + cost_half))
                    if shares <= 0:
                        continue
                    cost_total = shares * op * (1 + cost_half)
                    if cost_total > cash + 1e-6:
                        continue  # nedostatek cash
                    cash -= cost_total
                    exit_pos = di + hold
                    if exit_pos >= n:
                        exit_pos = n - 1
                    positions[tk] = {"shares": shares, "entry_price": op,
                                     "entry_date": dstr, "exit_pos": exit_pos,
                                     "entry_pos": di}

        # 3) DENNI MARK-TO-MARKET
        mv = 0.0
        for tk, p in positions.items():
            px = close_m[tk].iloc[di] if tk in close_m else None
            if px is not None and not pd.isna(px):
                mv += p["shares"] * px
            else:
                mv += p["shares"] * p["entry_price"]
        equity = cash + mv
        exposure = mv / equity if equity > 0 else 0.0
        daily.append({"date": dstr, "cash": round(cash, 2),
                      "market_value": round(mv, 2), "equity": round(equity, 2),
                      "exposure": round(exposure, 4),
                      "n_positions": len(positions)})
        # audit
        if cash < -1e-6:
            audit_violations.append(f"{dstr}: cash zaporny {cash:.2f}")
        if len(positions) > MAX_POSITIONS:
            audit_violations.append(f"{dstr}: positions {len(positions)} > 10")
        if exposure > 1.0 + 1e-6:
            audit_violations.append(f"{dstr}: exposure {exposure:.4f} > 1.0")

    return trades, daily, audit_violations


def portfolio_stats(trades, daily, hold, audit_violations):
    if not daily:
        return {"n_trades": 0}
    eq = np.array([d["equity"] for d in daily])
    daily_ret = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([])
    total_return = (eq[-1] / INITIAL_CAPITAL - 1) * 100
    # annualized (245 dni ~ 0.97 roku)
    years = len(daily) / 252.0
    ann = ((eq[-1] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else None
    # maxDD z equity
    running_max = np.maximum.accumulate(eq)
    dd = (eq - running_max) / running_max
    max_dd = float(dd.min()) * 100
    # Sharpe (denni -> ann)
    sharpe = (float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))
              if len(daily_ret) > 1 and daily_ret.std() > 0 else None)
    exposures = np.array([d["exposure"] for d in daily])
    npos = np.array([d["n_positions"] for d in daily])
    days_in_market = int((npos > 0).sum())
    s = {
        "total_return_pct": round(total_return, 4),
        "annualized_return_pct": round(ann, 4) if ann is not None else None,
        "final_equity": round(float(eq[-1]), 2),
        "sharpe_annualized": round(sharpe, 3) if sharpe else None,
        "max_drawdown_pct": round(max_dd, 4),
        "daily_vol_pct": round(float(daily_ret.std()) * 100, 4) if len(daily_ret) else None,
        "avg_exposure": round(float(exposures.mean()), 4),
        "max_exposure": round(float(exposures.max()), 4),
        "avg_n_positions": round(float(npos.mean()), 2),
        "days_in_market": days_in_market,
        "days_total": len(daily),
        "n_trades": len(trades),
        "audit_violations": audit_violations[:20],
        "audit_clean": len(audit_violations) == 0,
    }
    if trades:
        net = np.array([t["net_ret"] for t in trades])
        s["avg_trade_net"] = round(float(net.mean()), 4)
        s["median_trade_net"] = round(float(np.median(net)), 4)
        s["win_rate"] = round(float((net > 0).mean()), 4)
        s["turnover_trades_per_day"] = round(len(trades) / len(daily), 4)
        s["best_trade"] = max(trades, key=lambda t: t["net_ret"])
        s["worst_trade"] = min(trades, key=lambda t: t["net_ret"])
        by_sec, by_ind = {}, {}
        for t in trades:
            by_sec[t["sector"]] = by_sec.get(t["sector"], 0) + 1
            by_ind[t["industry"]] = by_ind.get(t["industry"], 0) + 1
        s["trades_by_sector"] = dict(sorted(by_sec.items(), key=lambda x: -x[1])[:8])
        s["trades_by_industry_top"] = dict(sorted(by_ind.items(), key=lambda x: -x[1])[:8])
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mle-root",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--irc-archive",
                    default=r"C:\Users\stava\Projects\industry_rank_calendar\output\archive\industry_rank_calendar_archive.csv")
    ap.add_argument("--mrl-root", default=None)
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
    cidx_str = [str(x.date()) for x in close_m.index]
    print(f"close matrix {close_m.shape}")

    idf = pd.read_csv(args.irc_archive, dtype=str, low_memory=False)
    cm = {c.lower(): c for c in idf.columns}
    idf[cm["date"]] = idf[cm["date"]].astype(str).str[:10]
    idf["_lb"] = idf[cm["lookback"]].astype(str).str.replace("d", "", regex=False)
    idf["_rank"] = pd.to_numeric(idf[cm["rank"]], errors="coerce")
    irc20 = idf[(idf["_lb"].isin(["20", "20.0"])) & (idf["_rank"] <= TOP_N)]
    irc_top10_by_date = {d: set(g[cm["industry"]].astype(str))
                         for d, g in irc20.groupby(cm["date"])}

    pos_of = {s: i for i, s in enumerate(cidx_str)}
    trading_dates = sorted(
        d for d in irc_top10_by_date
        if OVERLAP_FROM <= d <= OVERLAP_TO and d not in WEEKEND_ARTIFACTS
        and d in pos_of)
    print(f"trading days: {len(trading_dates)}")

    # signaly
    edge_sig, mle_sig = {}, {}
    for tdate in trading_dates:
        run_date = date.fromisoformat(tdate)
        ws = pd.Timestamp(run_date - timedelta(days=START_BUFFER))
        we = pd.Timestamp(run_date)
        cp = {}
        for tk in close_m.columns:
            s = close_m[tk]
            sub = s[(s.index >= ws) & (s.index <= we)]
            if not sub.empty:
                cp[tk] = sub
        inst = [i for i in instruments if i["ticker"] in cp]
        try:
            rm = compute_rank_matrix(cp, inst, run_date, LOOKBACKS).set_index("ticker")
        except Exception:
            continue
        irc_inds = irc_top10_by_date.get(tdate, set())
        mle_list = []
        for tk in rm.index:
            rv = rm.loc[tk, f"rank_{MLE_GATE_LB}d"]
            if not pd.isna(rv) and int(rv) <= 10:
                mle_list.append((tk, int(rv)))
        mle_list.sort(key=lambda x: x[1])
        mle_sig[tdate] = mle_list
        edge_sig[tdate] = [(tk, r) for tk, r in mle_list
                           if t2i.get(tk) in irc_inds]

    # spusť varianty
    results = {}
    for hold in HOLD_VARIANTS:
        results[f"hold_{hold}D"] = {}
        for cost in COST_BPS:
            e_tr, e_dl, e_av = run_portfolio(edge_sig, cidx_str, close_m,
                                             open_m, hold, cost, t2i, t2s)
            m_tr, m_dl, m_av = run_portfolio(mle_sig, cidx_str, close_m,
                                             open_m, hold, cost, t2i, t2s)
            results[f"hold_{hold}D"][f"cost_{cost}bps"] = {
                "edge": portfolio_stats(e_tr, e_dl, hold, e_av),
                "mle_top10_only": portfolio_stats(m_tr, m_dl, hold, m_av)}

    payload = {"overlap": [OVERLAP_FROM, OVERLAP_TO],
               "trading_days": len(trading_dates),
               "initial_capital": INITIAL_CAPITAL,
               "max_positions": MAX_POSITIONS,
               "target_weight": TARGET_WEIGHT,
               "note_vs_bt01": ("EDGE-BT-01 total_return byl aproximace "
                                "(suma trade returns / max_pos), ignoroval cash "
                                "a nizke exposure. Tento audit pouziva skutecnou "
                                "denni equity krivku s cash uctem."),
               "results": results}
    _write(payload, mrl, args.out)

    print(f"\n==== EDGE-BT-01B ====")
    for hold in HOLD_VARIANTS:
        print(f"\n-- hold {hold}D --")
        for cost in [0, 15]:
            e = results[f"hold_{hold}D"][f"cost_{cost}bps"]["edge"]
            m = results[f"hold_{hold}D"][f"cost_{cost}bps"]["mle_top10_only"]
            print(f"  {cost}bps EDGE: tot_ret {e['total_return_pct']}% "
                  f"ann {e.get('annualized_return_pct')}% "
                  f"sharpe {e['sharpe_annualized']} maxDD {e['max_drawdown_pct']}% "
                  f"expo {e['avg_exposure']} trades {e['n_trades']} "
                  f"audit_clean {e['audit_clean']}")
            print(f"  {cost}bps MLE : tot_ret {m['total_return_pct']}% "
                  f"ann {m.get('annualized_return_pct')}% "
                  f"sharpe {m['sharpe_annualized']} maxDD {m['max_drawdown_pct']}% "
                  f"expo {m['avg_exposure']} trades {m['n_trades']}")
    return 0


def _write(payload, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "EDGE-BT-01B_equity_accounting_audit.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    L = ["# EDGE-BT-01B — Equity Accounting Audit", "",
         f"Overlap: {payload['overlap'][0]}..{payload['overlap'][1]} "
         f"({payload['trading_days']} obchodnich dni)",
         f"Initial capital: {payload['initial_capital']}, "
         f"max_positions: {payload['max_positions']}, "
         f"target_weight: {payload['target_weight']}", "",
         f"**Oprava vs EDGE-BT-01:** {payload['note_vs_bt01']}", "",
         "**Vyhrady: skutecna denni equity + cash ucet. Sharpe/DD orientacni "
         "(245 dni). Survivorship 503 soucasnych. Bez kapacity/likvidity/fillu.**",
         ""]
    for hold in HOLD_VARIANTS:
        L.append(f"## hold {hold}D")
        L.append("")
        L.append("| cost | strat | tot_ret% | ann% | sharpe | maxDD% | avg_expo | "
                 "max_expo | avg_pos | days_mkt | trades | avg_net | win_rate | audit |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cost in COST_BPS:
            blk = payload["results"][f"hold_{hold}D"][f"cost_{cost}bps"]
            for strat in ["edge", "mle_top10_only"]:
                s = blk[strat]
                L.append(f"| {cost}bps | {strat} | {s.get('total_return_pct')} | "
                         f"{s.get('annualized_return_pct')} | {s.get('sharpe_annualized')} | "
                         f"{s.get('max_drawdown_pct')} | {s.get('avg_exposure')} | "
                         f"{s.get('max_exposure')} | {s.get('avg_n_positions')} | "
                         f"{s.get('days_in_market')} | {s.get('n_trades')} | "
                         f"{s.get('avg_trade_net')} | {s.get('win_rate')} | "
                         f"{'OK' if s.get('audit_clean') else 'FAIL'} |")
        L.append("")
    # audit detail + koncentrace (hold10 15bps)
    for hold in HOLD_VARIANTS:
        blk = payload["results"][f"hold_{hold}D"]["cost_15bps"]
        for strat in ["edge", "mle_top10_only"]:
            s = blk[strat]
            L.append(f"### {strat} hold{hold} 15bps — detail")
            L.append(f"- final_equity: {s.get('final_equity')}")
            L.append(f"- days_in_market: {s.get('days_in_market')}/{s.get('days_total')}")
            L.append(f"- avg_exposure: {s.get('avg_exposure')} max: {s.get('max_exposure')}")
            L.append(f"- audit_clean: {s.get('audit_clean')}")
            if s.get("audit_violations"):
                L.append(f"- audit_violations: {s['audit_violations'][:5]}")
            bt = s.get("best_trade", {}); wt = s.get("worst_trade", {})
            L.append(f"- best_trade: {bt.get('ticker')} {bt.get('net_ret')}% "
                     f"pnl={bt.get('pnl')}")
            L.append(f"- worst_trade: {wt.get('ticker')} {wt.get('net_ret')}% "
                     f"pnl={wt.get('pnl')}")
            L.append(f"- trades_by_industry_top: {s.get('trades_by_industry_top')}")
            L.append("")
    L += ["## Klicove otazky", "",
          "- porazi EDGE MLE-only po SPRAVNEM cash accountingu? viz tot_ret/sharpe.",
          "- ma EDGE vyssi avg_trade/win_rate? viz tabulky.",
          "- kolik EDGE ztraci nizsi exposure/mene obchody? "
          "porovnej days_in_market + n_trades + avg_exposure.", "",
          "## Vyhrady (souhrn)", "",
          "- skutecna denni equity: cash + MTM pozic. Cash ucet sledovan.",
          "- sizing: 10% aktualni equity na pozici (dle equity_now).",
          "- entry open[t+1], exit close[entry+H], konec dat -> partial.",
          "- naklady: half round-trip na kazde strane (bps/2).",
          "- Sharpe/DD orientacni, kratky sample 245 dni.",
          "- survivorship 503 soucasnych; bez kapacity/likvidity/fillu.", ""]
    (out_dir / "EDGE-BT-01B_equity_accounting_audit.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
