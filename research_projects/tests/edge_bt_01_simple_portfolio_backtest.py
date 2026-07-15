"""
edge_bt_01_simple_portfolio_backtest.py — EDGE-BT-01.

READ-ONLY. Jednoduchy obchodovatelny portfolio backtest signalu
MLE TOP10 x IRC TOP10. NENI to signal diagnostic (to byl EDGE-TEST-01).

NEDELA: Decision Resolver, bot/TWS, live/paper trading, optimalizaci,
API/TWS, MLE archive overwrite.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\edge_bt_01_simple_portfolio_backtest.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Signal:
    MLE rank_10d <= 10 (fresh z DATA-06)
    IRC rank_20d <= 10 (z archivu)
    join pres industry

Portfolio pravidla:
    entry: next open po signalnim dni
    exit: fixnich H dni (varianty H=10 a H=20 samostatne)
    equal weight, max 10 pozic
    portfolio plne -> vzit kandidaty s nejlepsim MLE rankem
    zadna duplicitni pozice v drzenem tickeru
    long only, cash bez signalu, bez shortu

Naklady: gross, 5, 15, 25 bps round-trip (odecteno z trade returnu)

Benchmarky:
    1. mle_top10_only (stejna pravidla, bez IRC filtru)
    2. universe_baseline (equal-weight vsech universe tickeru, denni)
    3. SPY/S&P proxy: SPY pravdepodobne NENI v DATA-06 (universe=S&P
       clenove, ne ETF). Pokud chybi -> vynechano s poznamkou, jako
       proxy slouzi universe_baseline.

Edge cases / predpoklady:
    - equity: denni mark-to-market otevrenych pozic (pro DD/Sharpe/vol).
    - entry open[t+1]: pokud open chybi -> pozice se neotevre (skip).
    - exit close[entry_pos+H]: pokud chybi (konec dat) -> pozice uzavrena
      na poslednim dostupnem close (partial), oznaceno.
    - max_positions plne: nove signaly zahozeny (nejlepsi MLE rank ma prednost).
    - naklady: round-trip bps odecteno z trade returnu (entry+exit).
    - Sharpe orientacni: ann. faktor sqrt(252), rf=0. NADHODNOCENY pri
      malem samplu + prekryvne drzeni.
    - survivorship: 503 soucasnych tickeru.
    - t/Sharpe/DD na 245 dnech = kratky sample, orientacni.
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
HOLD_VARIANTS = [10, 20]
COST_BPS = [0, 5, 15, 25]
START_BUFFER = 45
EXCEPTIONS = {"KLAC", "CRWD", "HON", "APTV", "DD", "NWS", "GOOG", "FOX",
              "BDX", "EXE", "PSKY", "Q", "SNDK"}


def is_active(v):
    return str(v).strip().lower() in ("1", "1.0", "true", "yes", "y")


def load_universe(ucsv):
    df = pd.read_csv(ucsv, dtype=str)
    cols = {c.lower(): c for c in df.columns}
    ccol, tcol, acol = cols["conid"], cols["ticker"], cols["active_flag"]
    icol = cols.get("industry")
    scol = cols.get("sector")
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


def run_backtest(signal_by_date, trading_dates, close_m, open_m, cidx_str,
                 pos_of, hold, cost_bps, tick2ind, tick2sec):
    """Simuluj portfolio. signal_by_date: date -> [(ticker, mle_rank)] serazene."""
    n = len(cidx_str)
    # otevrene pozice: ticker -> {entry_pos, entry_price, exit_pos}
    open_pos = {}
    trades = []
    daily_equity = []  # (date, equity_value_relative)
    # equity jako suma 1.0 per pozice (equal weight), cash zbytek
    # zjednoduseni: kazda pozice = 1 slot; hodnota slotu = 1 * (price/entry)
    for di, dstr in enumerate(cidx_str):
        # exity: pozice s exit_pos == di
        to_close = [tk for tk, p in open_pos.items() if p["exit_pos"] == di]
        for tk in to_close:
            p = open_pos.pop(tk)
            exit_price = close_m[tk].iloc[di] if tk in close_m else None
            if exit_price is None or pd.isna(exit_price):
                # fallback posledni dostupny
                exit_price = p["entry_price"]
            gross = (exit_price / p["entry_price"] - 1) * 100
            net = gross - cost_bps / 100.0  # round-trip bps -> %
            trades.append({"ticker": tk, "entry_date": p["entry_date"],
                           "exit_date": dstr, "hold_days": hold,
                           "gross_ret": round(gross, 4),
                           "net_ret": round(net, 4),
                           "industry": tick2ind.get(tk, ""),
                           "sector": tick2sec.get(tk, "")})
        # entries: signal z PREDCHOZIHO dne (entry na dnesnim open)
        prev = cidx_str[di - 1] if di > 0 else None
        if prev in signal_by_date:
            free = MAX_POSITIONS - len(open_pos)
            if free > 0:
                cands = [tk for tk, _ in signal_by_date[prev]
                         if tk not in open_pos]
                for tk in cands[:free]:
                    op = open_m[tk].iloc[di] if tk in open_m else None
                    if op is None or pd.isna(op) or op == 0:
                        continue
                    exit_pos = di + hold
                    if exit_pos >= n:
                        exit_pos = n - 1  # partial na konci
                    open_pos[tk] = {"entry_pos": di, "entry_price": op,
                                    "entry_date": dstr, "exit_pos": exit_pos}
        # denni equity: mark-to-market otevrenych pozic
        if open_pos:
            vals = []
            for tk, p in open_pos.items():
                px = close_m[tk].iloc[di] if tk in close_m else None
                if px is not None and not pd.isna(px):
                    vals.append(px / p["entry_price"])
            mtm = np.mean(vals) if vals else 1.0
            exposure = len(open_pos) / MAX_POSITIONS
        else:
            mtm = 1.0
            exposure = 0.0
        daily_equity.append({"date": dstr, "mtm": mtm, "exposure": exposure,
                             "n_positions": len(open_pos)})
    return trades, daily_equity


def compute_stats(trades, daily_equity, hold):
    if not trades:
        return {"n_trades": 0}
    net = np.array([t["net_ret"] for t in trades])
    gross = np.array([t["gross_ret"] for t in trades])
    # equity krivka z realized trades (chronologicky dle exit_date)
    # aproximace total return: prumer per trade * prumerny pocet soucasnych pozic
    # presneji: build equity z daily exposure-weighted returns
    exposures = np.array([d["exposure"] for d in daily_equity])
    avg_exposure = float(exposures.mean())
    # portfolio denni return aproximace: prumer MTM zmen otevrenych pozic
    # zjednoduseno: total return = suma net trade returns vazena rovnomerne
    # pres pocet slotu (equal weight, max 10)
    total_net = float(net.mean()) * len(trades) / MAX_POSITIONS  # hruby odhad
    stats = {
        "n_trades": len(trades),
        "avg_trade_gross": round(float(gross.mean()), 4),
        "avg_trade_net": round(float(net.mean()), 4),
        "median_trade_net": round(float(np.median(net)), 4),
        "win_rate": round(float((net > 0).mean()), 4),
        "trade_vol": round(float(net.std(ddof=1)), 4) if len(net) > 1 else 0,
        "avg_exposure": round(avg_exposure, 4),
        "avg_holding_days": hold,
        "best_trade": max(trades, key=lambda t: t["net_ret"]),
        "worst_trade": min(trades, key=lambda t: t["net_ret"]),
    }
    # equity krivka pro DD/Sharpe: kumulativni z denniho portfolio returnu
    # denni portfolio return = zmena prumerneho MTM * exposure
    eq = [1.0]
    prev_mtm = {}
    # presnejsi: pouzij per-trade PnL rozlozene na exit dny
    # equity: seradit trades dle exit, pripsat net/MAX_POSITIONS
    by_exit = {}
    for t in trades:
        by_exit.setdefault(t["exit_date"], []).append(t["net_ret"])
    cur = 1.0
    curve = []
    daily_rets = []
    for d in daily_equity:
        r = 0.0
        if d["date"] in by_exit:
            r = sum(by_exit[d["date"]]) / MAX_POSITIONS / 100.0
        cur *= (1 + r)
        curve.append(cur)
        daily_rets.append(r)
    curve = np.array(curve)
    daily_rets = np.array(daily_rets)
    stats["total_return_pct"] = round((curve[-1] - 1) * 100, 4)
    # max drawdown
    running_max = np.maximum.accumulate(curve)
    dd = (curve - running_max) / running_max
    stats["max_drawdown_pct"] = round(float(dd.min()) * 100, 4)
    # Sharpe orientacni (denni -> ann)
    if daily_rets.std() > 0:
        stats["sharpe_annualized_orientacni"] = round(
            float(daily_rets.mean() / daily_rets.std() * np.sqrt(252)), 3)
    else:
        stats["sharpe_annualized_orientacni"] = None
    stats["daily_vol_pct"] = round(float(daily_rets.std()) * 100, 4)
    # turnover: pocet trades / dni
    stats["turnover_trades_per_day"] = round(
        len(trades) / max(len(daily_equity), 1), 4)
    # koncentrace
    by_sec = {}
    for t in trades:
        by_sec[t["sector"]] = by_sec.get(t["sector"], 0) + 1
    stats["trades_by_sector"] = dict(
        sorted(by_sec.items(), key=lambda x: -x[1])[:8])
    by_ind = {}
    for t in trades:
        by_ind[t["industry"]] = by_ind.get(t["industry"], 0) + 1
    stats["trades_by_industry_top"] = dict(
        sorted(by_ind.items(), key=lambda x: -x[1])[:8])
    return stats


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
    pos_of = {s: i for i, s in enumerate(cidx_str)}
    print(f"close matrix {close_m.shape}")

    # IRC TOP10 industries per den
    idf = pd.read_csv(args.irc_archive, dtype=str, low_memory=False)
    cm = {c.lower(): c for c in idf.columns}
    idf[cm["date"]] = idf[cm["date"]].astype(str).str[:10]
    idf["_lb"] = idf[cm["lookback"]].astype(str).str.replace("d", "", regex=False)
    idf["_rank"] = pd.to_numeric(idf[cm["rank"]], errors="coerce")
    irc20 = idf[(idf["_lb"].isin(["20", "20.0"])) & (idf["_rank"] <= TOP_N)]
    irc_top10_by_date = {d: set(g[cm["industry"]].astype(str))
                         for d, g in irc20.groupby(cm["date"])}

    trading_dates = sorted(
        d for d in irc_top10_by_date
        if OVERLAP_FROM <= d <= OVERLAP_TO and d not in WEEKEND_ARTIFACTS
        and d in pos_of)
    print(f"trading days: {len(trading_dates)}")

    # signaly per den: MLE fresh + IRC filtr
    def build_signals(exclude_exceptions):
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
                if pd.isna(rv):
                    continue
                if exclude_exceptions and tk in EXCEPTIONS:
                    continue
                if int(rv) <= 10:
                    mle_list.append((tk, int(rv)))
            mle_list.sort(key=lambda x: x[1])
            mle_sig[tdate] = mle_list
            edge_list = [(tk, r) for tk, r in mle_list
                         if t2i.get(tk) in irc_inds]
            edge_sig[tdate] = edge_list
        return edge_sig, mle_sig

    print("signaly (vsechny) ...")
    edge_sig, mle_sig = build_signals(False)
    print("signaly (bez exceptions) ...")
    edge_sig_ex, mle_sig_ex = build_signals(True)

    # universe baseline: equal-weight denni return vsech tickeru
    def universe_baseline_stats():
        rets = close_m.pct_change().loc[
            [pd.Timestamp(d) for d in trading_dates if pd.Timestamp(d) in close_m.index]]
        daily = rets.mean(axis=1)  # equal weight
        cur = (1 + daily.fillna(0)).cumprod()
        total = (cur.iloc[-1] - 1) * 100 if len(cur) else 0
        dd = ((cur - cur.cummax()) / cur.cummax()).min() * 100
        sharpe = (daily.mean() / daily.std() * np.sqrt(252)
                  if daily.std() > 0 else None)
        return {"total_return_pct": round(float(total), 4),
                "max_drawdown_pct": round(float(dd), 4),
                "sharpe_annualized_orientacni": round(float(sharpe), 3)
                if sharpe else None,
                "daily_vol_pct": round(float(daily.std()) * 100, 4)}

    baseline = universe_baseline_stats()

    # spusť varianty
    results = {}
    for label, esig, msig in [("all", edge_sig, mle_sig),
                              ("ex_exceptions", edge_sig_ex, mle_sig_ex)]:
        results[label] = {}
        for hold in HOLD_VARIANTS:
            results[label][f"hold_{hold}D"] = {}
            for cost in COST_BPS:
                edge_tr, edge_eq = run_backtest(
                    esig, trading_dates, close_m, open_m, cidx_str, pos_of,
                    hold, cost, t2i, t2s)
                mle_tr, mle_eq = run_backtest(
                    msig, trading_dates, close_m, open_m, cidx_str, pos_of,
                    hold, cost, t2i, t2s)
                results[label][f"hold_{hold}D"][f"cost_{cost}bps"] = {
                    "edge": compute_stats(edge_tr, edge_eq, hold),
                    "mle_top10_only": compute_stats(mle_tr, mle_eq, hold)}

    payload = {"overlap": [OVERLAP_FROM, OVERLAP_TO],
               "trading_days": len(trading_dates),
               "max_positions": MAX_POSITIONS,
               "universe_baseline": baseline,
               "spy_benchmark": "NENI v DATA-06 (universe=S&P clenove, ne ETF); "
                                "proxy = universe_baseline",
               "results": results}
    _write(payload, mrl, args.out)

    print(f"\n==== EDGE-BT-01 ====")
    print(f"trading_days: {len(trading_dates)}")
    print(f"universe_baseline: {baseline}")
    for hold in HOLD_VARIANTS:
        print(f"\n-- hold {hold}D (all, edge) --")
        for cost in COST_BPS:
            e = results["all"][f"hold_{hold}D"][f"cost_{cost}bps"]["edge"]
            m = results["all"][f"hold_{hold}D"][f"cost_{cost}bps"]["mle_top10_only"]
            print(f"  cost {cost}bps: EDGE total_ret {e.get('total_return_pct')}% "
                  f"maxDD {e.get('max_drawdown_pct')}% sharpe {e.get('sharpe_annualized_orientacni')} "
                  f"trades {e.get('n_trades')} | MLE total_ret {m.get('total_return_pct')}%")
    return 0


def _write(payload, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "tests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "EDGE-BT-01_simple_portfolio_backtest.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    L = ["# EDGE-BT-01 — Simple Portfolio Backtest", "",
         f"Overlap: {payload['overlap'][0]}..{payload['overlap'][1]} "
         f"({payload['trading_days']} obchodnich dni)",
         f"Max positions: {payload['max_positions']}", "",
         f"Universe baseline: {payload['universe_baseline']}",
         f"SPY: {payload['spy_benchmark']}", "",
         "**Vyhrady: signal->tradable aproximace. Sharpe/DD orientacni "
         "(kratky sample 245 dni, prekryvne drzeni). Survivorship 503 "
         "soucasnych. Bez kapacity/likvidity.**", ""]
    for label in ["all", "ex_exceptions"]:
        L.append(f"## Varianta: {label}")
        L.append("")
        for hold in HOLD_VARIANTS:
            L.append(f"### hold {hold}D")
            L.append("")
            L.append("| cost | strat | total_ret% | avg_trade_net | win_rate | "
                     "maxDD% | sharpe | n_trades | avg_expo | turnover |")
            L.append("|---|---|---|---|---|---|---|---|---|---|")
            for cost in COST_BPS:
                blk = payload["results"][label][f"hold_{hold}D"][f"cost_{cost}bps"]
                for strat in ["edge", "mle_top10_only"]:
                    s = blk[strat]
                    L.append(f"| {cost}bps | {strat} | {s.get('total_return_pct')} | "
                             f"{s.get('avg_trade_net')} | {s.get('win_rate')} | "
                             f"{s.get('max_drawdown_pct')} | "
                             f"{s.get('sharpe_annualized_orientacni')} | "
                             f"{s.get('n_trades')} | {s.get('avg_exposure')} | "
                             f"{s.get('turnover_trades_per_day')} |")
            L.append("")
        # koncentrace + best/worst (z 15bps hold10 edge)
        try:
            e = payload["results"][label]["hold_10D"]["cost_15bps"]["edge"]
            L.append(f"#### {label} hold10 15bps edge — koncentrace")
            L.append(f"- trades_by_sector: {e.get('trades_by_sector')}")
            L.append(f"- trades_by_industry_top: {e.get('trades_by_industry_top')}")
            bt = e.get("best_trade", {}); wt = e.get("worst_trade", {})
            L.append(f"- best_trade: {bt.get('ticker')} {bt.get('net_ret')}% "
                     f"({bt.get('entry_date')}->{bt.get('exit_date')})")
            L.append(f"- worst_trade: {wt.get('ticker')} {wt.get('net_ret')}% "
                     f"({wt.get('entry_date')}->{wt.get('exit_date')})")
            L.append("")
        except (KeyError, TypeError):
            pass
    L += ["## Vyhrady (souhrn)", "",
          "- total_return aproximace: equity z realized trades / MAX_POSITIONS.",
          "- Sharpe/DD orientacni, kratky sample.",
          "- entry open[t+1], exit close[entry+H]; konec dat -> partial exit.",
          "- naklady odectene jako round-trip bps z trade returnu.",
          "- SPY chybi v DATA-06; proxy universe_baseline.",
          "- survivorship: 503 soucasnych tickeru.",
          "- bez kapacity, likvidity, realneho fillu.", ""]
    (out_dir / "EDGE-BT-01_simple_portfolio_backtest.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
