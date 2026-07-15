"""
edge_bt_01c_windowed_equity_backtest.py — EDGE-BT-01C.

READ-ONLY. OPRAVA simulacniho okna z EDGE-BT-01B. Equity loop bezel pres
cely DATA-06 index (7169 dni od 1997) -> zkreslene portfolio metriky.
Tento skript iteruje POUZE pres simulacni okno (overlap + exit buffer).

Signalni a MLE/IRC logika BEZE ZMENY. Zadna optimalizace.

NEDELA: parameter sensitivity, regime switching, Decision Resolver,
bot/TWS, live/paper, API/TWS, MLE archive overwrite.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\edge_bt_01c_windowed_equity_backtest.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Oprava (jadro):
    sim_start = prvni overlap trading date
    sim_end   = posledni exit date (overlap_to + max_hold buffer, orezano
                na dostupna data)
    sim_dates = close_matrix dny mezi sim_start a sim_end
    iterovat JEN pres sim_dates (ne cely close_m.index)
    initial_capital na sim_start
    equity/Sharpe/maxDD/exposure/annualized POUZE pres sim_dates

Edge cases / predpoklady:
    - signal_dates = overlap trading dates (2025-07-09..2026-06-27, bez
      vikend artefaktu). Signaly se generuji jen zde.
    - entry open[t+1]: entry az DEN PO signalu -> sim okno musi obsahovat
      i den po poslednim signalu.
    - exit close[entry+H]: posledni entry + H -> sim_end. Orezano na
      max dostupne datum (partial exit pokud data konci driv).
    - pozice otevrene na konci sim okna: uzavreny na poslednim sim dni
      (mark-to-final), aby equity byla kompletni.
    - sizing: 10% aktualni equity. cash ucet. MTM denne.
    - naklady half round-trip (bps/2) na stranu.
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


def run_windowed(signal_by_date, sim_dates, sim_pos_of, close_m, open_m,
                 hold, cost_bps, t2i, t2s):
    """Portfolio backtest JEN pres sim_dates. sim_dates = list str dat.
    sim_pos_of: mapa str->pozice v sim_dates."""
    n = len(sim_dates)
    cost_half = cost_bps / 2.0 / 10000.0
    cash = INITIAL_CAPITAL
    positions = {}  # ticker -> {shares, entry_price, entry_date, exit_sim_pos}
    trades = []
    daily = []
    audit_violations = []

    # mapa str date -> close/open Series positional (pro rychlost predpocteme)
    def price_at(matrix, tk, dstr):
        if tk not in matrix.columns:
            return None
        ts = pd.Timestamp(dstr)
        try:
            v = matrix.at[ts, tk]
        except KeyError:
            return None
        return v

    for si, dstr in enumerate(sim_dates):
        # 1) EXITY
        to_close = [tk for tk, p in positions.items() if p["exit_sim_pos"] == si]
        for tk in to_close:
            p = positions.pop(tk)
            px = price_at(close_m, tk, dstr)
            if px is None or pd.isna(px):
                px = p["entry_price"]
            proceeds = p["shares"] * px * (1 - cost_half)
            cash += proceeds
            cost_in = p["shares"] * p["entry_price"] * (1 + cost_half)
            net = (proceeds / cost_in - 1) * 100
            gross = (px / p["entry_price"] - 1) * 100
            trades.append({"ticker": tk, "entry_date": p["entry_date"],
                           "exit_date": dstr, "hold_days": hold,
                           "gross_ret": round(gross, 4), "net_ret": round(net, 4),
                           "pnl": round(proceeds - cost_in, 2),
                           "industry": t2i.get(tk, ""), "sector": t2s.get(tk, "")})

        # 2) ENTRIES (signal z predchoziho sim dne)
        prev = sim_dates[si - 1] if si > 0 else None
        if prev in signal_by_date:
            free = MAX_POSITIONS - len(positions)
            if free > 0:
                # equity_now = cash + MTM (predchozi close)
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
                    target_value = TARGET_WEIGHT * equity_now
                    spend = min(target_value, cash / (1 + cost_half))
                    if spend <= 0:
                        continue
                    shares = spend / (op * (1 + cost_half))
                    cost_total = shares * op * (1 + cost_half)
                    if shares <= 0 or cost_total > cash + 1e-6:
                        continue
                    cash -= cost_total
                    exit_sim_pos = si + hold
                    if exit_sim_pos >= n:
                        exit_sim_pos = n - 1  # partial na konci okna
                    positions[tk] = {"shares": shares, "entry_price": op,
                                     "entry_date": dstr,
                                     "exit_sim_pos": exit_sim_pos}

        # 3) MARK-TO-MARKET
        mv = 0.0
        for tk, p in positions.items():
            px = price_at(close_m, tk, dstr)
            mv += p["shares"] * (px if px is not None and not pd.isna(px)
                                 else p["entry_price"])
        equity = cash + mv
        exposure = mv / equity if equity > 0 else 0.0
        daily.append({"date": dstr, "cash": round(cash, 2),
                      "market_value": round(mv, 2), "equity": round(equity, 2),
                      "exposure": round(exposure, 4), "n_positions": len(positions)})
        if cash < -1e-6:
            audit_violations.append(f"{dstr}: cash {cash:.2f}")
        if len(positions) > MAX_POSITIONS:
            audit_violations.append(f"{dstr}: pos {len(positions)}")
        if exposure > 1.0 + 1e-6:
            audit_violations.append(f"{dstr}: expo {exposure:.4f}")

    # force-close zbyle pozice na poslednim sim dni (uz udelano partial exit)
    return trades, daily, audit_violations


def stats(trades, daily, hold, av, sim_days):
    if not daily:
        return {"n_trades": 0}
    eq = np.array([d["equity"] for d in daily])
    dr = np.diff(eq) / eq[:-1] if len(eq) > 1 else np.array([])
    total = (eq[-1] / INITIAL_CAPITAL - 1) * 100
    years = sim_days / 252.0
    ann = ((eq[-1] / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else None
    rm = np.maximum.accumulate(eq)
    dd = (eq - rm) / rm
    sharpe = (float(dr.mean() / dr.std() * np.sqrt(252))
              if len(dr) > 1 and dr.std() > 0 else None)
    expo = np.array([d["exposure"] for d in daily])
    npos = np.array([d["n_positions"] for d in daily])
    s = {"total_return_pct": round(total, 4),
         "annualized_return_pct": round(ann, 4) if ann is not None else None,
         "final_equity": round(float(eq[-1]), 2),
         "sharpe_annualized": round(sharpe, 3) if sharpe else None,
         "max_drawdown_pct": round(float(dd.min()) * 100, 4),
         "daily_vol_pct": round(float(dr.std()) * 100, 4) if len(dr) else None,
         "avg_exposure": round(float(expo.mean()), 4),
         "max_exposure": round(float(expo.max()), 4),
         "avg_n_positions": round(float(npos.mean()), 2),
         "days_in_market": int((npos > 0).sum()),
         "sim_days": len(daily),
         "n_trades": len(trades),
         "audit_clean": len(av) == 0, "audit_violations": av[:10]}
    if trades:
        net = np.array([t["net_ret"] for t in trades])
        s["avg_trade_net"] = round(float(net.mean()), 4)
        s["median_trade_net"] = round(float(np.median(net)), 4)
        s["win_rate"] = round(float((net > 0).mean()), 4)
        s["turnover_per_day"] = round(len(trades) / len(daily), 4)
        s["best_trade"] = max(trades, key=lambda t: t["net_ret"])
        s["worst_trade"] = min(trades, key=lambda t: t["net_ret"])
        by_ind = {}
        for t in trades:
            by_ind[t["industry"]] = by_ind.get(t["industry"], 0) + 1
        s["trades_by_industry_top"] = dict(sorted(by_ind.items(),
                                                   key=lambda x: -x[1])[:8])
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
    full_idx_str = [str(x.date()) for x in close_m.index]
    print(f"close matrix {close_m.shape} (full history)")

    idf = pd.read_csv(args.irc_archive, dtype=str, low_memory=False)
    cm = {c.lower(): c for c in idf.columns}
    idf[cm["date"]] = idf[cm["date"]].astype(str).str[:10]
    idf["_lb"] = idf[cm["lookback"]].astype(str).str.replace("d", "", regex=False)
    idf["_rank"] = pd.to_numeric(idf[cm["rank"]], errors="coerce")
    irc20 = idf[(idf["_lb"].isin(["20", "20.0"])) & (idf["_rank"] <= TOP_N)]
    irc_top10_by_date = {d: set(g[cm["industry"]].astype(str))
                         for d, g in irc20.groupby(cm["date"])}

    full_pos_of = {s: i for i, s in enumerate(full_idx_str)}
    signal_dates = sorted(
        d for d in irc_top10_by_date
        if OVERLAP_FROM <= d <= OVERLAP_TO and d not in WEEKEND_ARTIFACTS
        and d in full_pos_of)
    print(f"signal_dates (overlap): {len(signal_dates)}")

    # ── OPRAVA: sim okno ──
    # sim_start = prvni signal date (equity start)
    # sim_end = posledni signal date + max_hold + 1 (pro exity), orezano
    sim_start = signal_dates[0]
    last_sig_pos = full_pos_of[signal_dates[-1]]
    max_hold = max(HOLD_VARIANTS)
    sim_end_pos = min(last_sig_pos + max_hold + 1, len(full_idx_str) - 1)
    sim_start_pos = full_pos_of[sim_start]
    sim_dates = full_idx_str[sim_start_pos:sim_end_pos + 1]
    sim_pos_of = {s: i for i, s in enumerate(sim_dates)}
    print(f"sim window: {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)} dni)")

    # signaly (fresh MLE) — jen na signal_dates
    edge_sig, mle_sig = {}, {}
    for tdate in signal_dates:
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
        mle_list = [(tk, int(rm.loc[tk, f"rank_{MLE_GATE_LB}d"]))
                    for tk in rm.index
                    if not pd.isna(rm.loc[tk, f"rank_{MLE_GATE_LB}d"])
                    and int(rm.loc[tk, f"rank_{MLE_GATE_LB}d"]) <= 10]
        mle_list.sort(key=lambda x: x[1])
        mle_sig[tdate] = mle_list
        edge_sig[tdate] = [(tk, r) for tk, r in mle_list
                           if t2i.get(tk) in irc_inds]

    results = {}
    for hold in HOLD_VARIANTS:
        results[f"hold_{hold}D"] = {}
        for cost in COST_BPS:
            e_tr, e_dl, e_av = run_windowed(edge_sig, sim_dates, sim_pos_of,
                                            close_m, open_m, hold, cost, t2i, t2s)
            m_tr, m_dl, m_av = run_windowed(mle_sig, sim_dates, sim_pos_of,
                                            close_m, open_m, hold, cost, t2i, t2s)
            results[f"hold_{hold}D"][f"cost_{cost}bps"] = {
                "edge": stats(e_tr, e_dl, hold, e_av, len(sim_dates)),
                "mle_top10_only": stats(m_tr, m_dl, hold, m_av, len(sim_dates))}

    payload = {"sim_start": sim_dates[0], "sim_end": sim_dates[-1],
               "sim_days": len(sim_dates), "signal_days": len(signal_dates),
               "overlap": [OVERLAP_FROM, OVERLAP_TO],
               "sim_days_not_7169": len(sim_dates) < 500,
               "initial_capital": INITIAL_CAPITAL,
               "max_positions": MAX_POSITIONS,
               "note": ("Oprava vs 01B: equity loop iteruje jen pres sim okno "
                        "(overlap + exit buffer), ne cely close_matrix (7169 "
                        "dni od 1997)."),
               "results": results}
    _write(payload, mrl, args.out)

    print(f"\n==== EDGE-BT-01C ====")
    print(f"sim: {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)} dni), "
          f"signal_days {len(signal_dates)}")
    print(f"sim_days_not_7169: {payload['sim_days_not_7169']}")
    for hold in HOLD_VARIANTS:
        print(f"\n-- hold {hold}D (15bps) --")
        e = results[f"hold_{hold}D"]["cost_15bps"]["edge"]
        m = results[f"hold_{hold}D"]["cost_15bps"]["mle_top10_only"]
        for lbl, s in [("EDGE", e), ("MLE ", m)]:
            print(f"  {lbl}: tot_ret {s['total_return_pct']}% ann {s['annualized_return_pct']}% "
                  f"sharpe {s['sharpe_annualized']} maxDD {s['max_drawdown_pct']}% "
                  f"avg_expo {s['avg_exposure']} avg_pos {s['avg_n_positions']} "
                  f"days_mkt {s['days_in_market']}/{s['sim_days']} "
                  f"trades {s['n_trades']} avg_net {s['avg_trade_net']} "
                  f"wr {s['win_rate']} audit {'OK' if s['audit_clean'] else 'FAIL'}")
    return 0


def _write(payload, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "EDGE-BT-01C_windowed_equity_backtest.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    L = ["# EDGE-BT-01C — Windowed Equity Backtest", "",
         f"## Simulacni okno (OPRAVA)", "",
         f"- sim_start: {payload['sim_start']}",
         f"- sim_end: {payload['sim_end']}",
         f"- sim_days: {payload['sim_days']}",
         f"- signal_days: {payload['signal_days']}",
         f"- **sim_days_not_7169: {payload['sim_days_not_7169']}** "
         f"(overeni, ze okno je overlap, ne cela historie)", "",
         f"Oprava: {payload['note']}", "",
         f"Initial capital: {payload['initial_capital']}, "
         f"max_positions: {payload['max_positions']}", "",
         "**Vyhrady: skutecna denni equity pres SIM okno. Sharpe/DD "
         "orientacni (kratky sample). Survivorship 503 soucasnych. "
         "Bez kapacity/likvidity/fillu.**", ""]
    for hold in HOLD_VARIANTS:
        L.append(f"## hold {hold}D")
        L.append("")
        L.append("| cost | strat | tot_ret% | ann% | sharpe | maxDD% | avg_expo | "
                 "max_expo | avg_pos | days_mkt/sim | trades | avg_net | median_net | "
                 "win_rate | audit |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cost in COST_BPS:
            blk = payload["results"][f"hold_{hold}D"][f"cost_{cost}bps"]
            for strat in ["edge", "mle_top10_only"]:
                s = blk[strat]
                L.append(f"| {cost}bps | {strat} | {s.get('total_return_pct')} | "
                         f"{s.get('annualized_return_pct')} | {s.get('sharpe_annualized')} | "
                         f"{s.get('max_drawdown_pct')} | {s.get('avg_exposure')} | "
                         f"{s.get('max_exposure')} | {s.get('avg_n_positions')} | "
                         f"{s.get('days_in_market')}/{s.get('sim_days')} | "
                         f"{s.get('n_trades')} | {s.get('avg_trade_net')} | "
                         f"{s.get('median_trade_net')} | {s.get('win_rate')} | "
                         f"{'OK' if s.get('audit_clean') else 'FAIL'} |")
        L.append("")
    # detail 15bps
    for hold in HOLD_VARIANTS:
        blk = payload["results"][f"hold_{hold}D"]["cost_15bps"]
        for strat in ["edge", "mle_top10_only"]:
            s = blk[strat]
            L.append(f"### {strat} hold{hold} 15bps — detail")
            L.append(f"- final_equity: {s.get('final_equity')}")
            L.append(f"- days_in_market/sim_days: {s.get('days_in_market')}/{s.get('sim_days')}")
            L.append(f"- avg_exposure: {s.get('avg_exposure')} max: {s.get('max_exposure')} "
                     f"avg_pos: {s.get('avg_n_positions')}")
            L.append(f"- audit_clean: {s.get('audit_clean')}")
            bt = s.get("best_trade", {}); wt = s.get("worst_trade", {})
            L.append(f"- best_trade: {bt.get('ticker')} {bt.get('net_ret')}% pnl={bt.get('pnl')}")
            L.append(f"- worst_trade: {wt.get('ticker')} {wt.get('net_ret')}% pnl={wt.get('pnl')}")
            L.append(f"- trades_by_industry_top: {s.get('trades_by_industry_top')}")
            L.append("")
    L += ["## Audit checks", "",
          f"- sim_days ~244-270 (ne 7169): {payload['sim_days']} -> "
          f"{'OK' if payload['sim_days_not_7169'] else 'FAIL'}",
          "- positions <= 10, cash >= 0, exposure <= 100%: viz audit sloupec",
          "- total_return z final_equity/initial-1",
          "- Sharpe/maxDD z equity krivky POUZE v sim okne", "",
          "## Klicove otazky (po oprave)", "",
          "- ma EDGE vyssi validni portfolio return? viz tot_ret/ann.",
          "- ma EDGE nizsi drawdown / lepsi Sharpe? viz maxDD/sharpe.",
          "- stoji IRC filtr za ztratu breadth? porovnej n_trades + avg_net.",
          "- je IRC lepsi jako vaha nez tvrdy filtr? (indikace z avg_net vs "
          "n_trades trade-off)", "",
          "## Vyhrady (souhrn)", "",
          "- equity loop POUZE pres sim okno (oprava 01B bugu 7169 dni).",
          "- sizing 10% aktualni equity, cash ucet, MTM denne.",
          "- entry open[t+1], exit close[entry+H], konec okna -> partial.",
          "- naklady half round-trip (bps/2) na stranu.",
          "- survivorship 503 soucasnych; kratky sample; bez kapacity/fillu.", ""]
    (out_dir / "EDGE-BT-01C_windowed_equity_backtest.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
