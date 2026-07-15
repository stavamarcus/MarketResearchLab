"""
mle_bt_04r_causal_execution_correction.py — MLE-BT-04R.

CAUSAL EXECUTION CORRECTION. Auditni oprava MLE-BT-04. NENI optimalizace.
Puvodni MLE-BT-04 soubor se NEMENI a zustava jako auditni dukaz.

Opravovane defekty puvodniho MLE-BT-04:
  D1) regime lookahead: gate pro BUY na open dne D+1 pouzival regime_ok[D+1]
      (close D+1, ktery na open jeste neexistuje). Spravne: regime_ok[D].
  D2) cash/slot chronologie: exity na close se zpracovaly PRED vstupy na open
      tehoz dne -> ranni nakup utracel odpoledni proceeds a pouzival
      odpoledne uvolneny slot. Spravne: vstupy (open) -> exity (close);
      proceeds a slot dostupne az pro open nasledujiciho obchodniho dne.
  D3) regime index: pct_change s explicitnim fill_method=None (zadny
      implicitni forward fill cen), mean s explicitnim skipna=True,
      logovani poctu validnich constituentu per den.

Kauzalni acceptance criterion:
  Kazde rozhodnuti na open dne X smi pouzivat pouze informace zname
  nejpozdeji po close dne X-1.

Zachovano (zadna zmena strategie):
  MLE rank_10d <= 10, fixed active 503 universe, max 10 pozic,
  10 % equity target, hold10, 15 bps round-trip (7.5 bps/strana),
  nuceny exit na konci dat (min(si+hold, n-1)), zadne dalsi filtry.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\mle_bt_04r_causal_execution_correction.py ^
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Selftest bez dat (synteticka matice, overi D1+D2 mechaniku):
    python research_projects\\tests\\mle_bt_04r_causal_execution_correction.py --selftest

Vystupy: reports/backtests/MLE-BT-04R_causal_execution_correction.{json,md}

Edge cases / predpoklady:
  - signaly se pocitaji jednou a sdileji stara i nova smycka -> rozdily
    vysledku = vyhradne exekucni logika + regime handling.
  - stara smycka (bt04.run) i stary regime (bt04.build_regime) se importuji
    z puvodniho souboru, aby srovnani bylo like-for-like v jednom behu.
  - ticker s pending exitem na dnesnim close NENI na dnesnim open
    znovu-koupitelny (stale drzen) - diagnostika to pocita.
  - regime default pri chybejicim dni = True (shodne s originalem);
    sim_dates jsou podmnozinou indexu close_m, takze nenastava.
  - pandas verze se loguje (fill_method chovani se mezi verzemi lisi).
  - SURVIVORSHIP: current 503 universe - dedeno z BT-04, tato oprava
    survivorship neresi a neresit nema.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import pandas as pd
    import numpy as np
except ImportError:
    pd = None

# --- import puvodniho BT-04 jako modulu (soubor se NEMENI) ---
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
bt04 = importlib.import_module("mle_bt_04_yearly_monthly_regime_breakdown")

MAX_POSITIONS = bt04.MAX_POSITIONS
INITIAL_CAPITAL = bt04.INITIAL_CAPITAL
TARGET_WEIGHT = bt04.TARGET_WEIGHT
COST_BPS = bt04.COST_BPS
REGIME_MA = bt04.REGIME_MA
LOOKBACKS = bt04.LOOKBACKS
MLE_GATE_LB = bt04.MLE_GATE_LB
DEFAULT_FROM, DEFAULT_TO = bt04.DEFAULT_FROM, bt04.DEFAULT_TO

VARIANTS_R = [("baseline", 10, False), ("regime200", 10, True)]


def build_regime_causal(close_m):
    """Regime index dle pozadavku D3: fill_method=None, explicitni skipna,
    denni pocet validnich constituentu. Semantika ok[den] = stav PO close
    toho dne (causal pouziti = cist ok[prev])."""
    rets = close_m.pct_change(fill_method=None)
    valid_n = rets.notna().sum(axis=1)
    daily_ret = rets.mean(axis=1, skipna=True)
    idx = (1 + daily_ret.fillna(0)).cumprod()
    ma = idx.rolling(REGIME_MA, min_periods=REGIME_MA).mean()
    ok = {}
    for ts in idx.index:
        m = ma.loc[ts]
        ok[str(ts.date())] = True if pd.isna(m) else bool(idx.loc[ts] > m)
    valid_by_day = {str(ts.date()): int(v) for ts, v in valid_n.items()}
    return ok, idx, valid_by_day


def run_causal(signal_by_date, sim_dates, close_m, open_m, hold, cost_bps,
               t2i, t2s, use_regime, regime_ok,
               max_positions=None, initial_capital=None, target_weight=None):
    """Kauzalne spravna exekucni smycka.

    Poradi v ramci dne X:
      1) OPEN: vstupy. Signal = signal_by_date[X-1], regime = regime_ok[X-1],
         equity pro sizing = cash + market value pozic za close X-1.
         Pozice s exitem na dnesnim close je stale drzena -> slot obsazen,
         jeji cash nedostupny, jeji ticker nekoupitelny.
      2) CLOSE: planned exity za close X; proceeds do cash (dostupne az
         pro open X+1).
      3) EOD: equity mark za close X.
    """
    mp = max_positions if max_positions is not None else MAX_POSITIONS
    ic = initial_capital if initial_capital is not None else INITIAL_CAPITAL
    tw = target_weight if target_weight is not None else TARGET_WEIGHT
    n = len(sim_dates)
    ch = cost_bps / 2.0 / 10000.0
    cash = ic
    pos = {}
    trades = []
    daily = []
    diag = {"buys": 0,
            "regime_off_entry_days": 0,           # dny se signalem, gate OFF
            "entries_blocked_portfolio_full_with_pending_exit": 0,
            "reentry_candidates_blocked_pending_exit": 0,
            "cash_binding_buys": 0}               # spend orezany cashem < target

    def px(m, tk, d):
        if tk not in m.columns:
            return None
        try:
            return m.at[pd.Timestamp(d), tk]
        except KeyError:
            return None

    for si, dstr in enumerate(sim_dates):
        prev = sim_dates[si - 1] if si > 0 else None

        # ---- 1) OPEN: vstupy (pouze informace do close prev) ----
        allow = (not use_regime) or (prev is not None
                                     and regime_ok.get(prev, True))
        if prev in signal_by_date:
            if not allow:
                diag["regime_off_entry_days"] += 1
            else:
                free = mp - len(pos)  # pending-exit pozice stale drzi slot
                pending = {t for t, p in pos.items() if p["exit"] == si}
                diag["reentry_candidates_blocked_pending_exit"] += sum(
                    1 for tk, _ in signal_by_date[prev] if tk in pending)
                if free <= 0:
                    if pending:
                        diag["entries_blocked_portfolio_full_with_pending_exit"] += 1
                else:
                    mvp = 0.0
                    for tk, p in pos.items():
                        pp = px(close_m, tk, prev)
                        mvp += p["sh"] * (pp if pp is not None
                                          and not pd.isna(pp) else p["ep"])
                    eqn = cash + mvp
                    cands = [tk for tk, _ in signal_by_date[prev]
                             if tk not in pos]
                    for tk in cands[:free]:
                        op = px(open_m, tk, dstr)
                        if op is None or pd.isna(op) or op == 0:
                            continue
                        target = tw * eqn
                        spend = min(target, cash / (1 + ch))
                        if spend <= 0:
                            continue
                        if spend < target - 1e-9:
                            diag["cash_binding_buys"] += 1
                        sh = spend / (op * (1 + ch))
                        ct = sh * op * (1 + ch)
                        if sh <= 0 or ct > cash + 1e-6:
                            continue
                        cash -= ct
                        diag["buys"] += 1
                        pos[tk] = {"sh": sh, "ep": op, "ed": dstr,
                                   "exit": min(si + hold, n - 1)}

        # ---- 2) CLOSE: planned exity ----
        for tk in [t for t, p in pos.items() if p["exit"] == si]:
            p = pos.pop(tk)
            pr = px(close_m, tk, dstr)
            if pr is None or pd.isna(pr):
                pr = p["ep"]
            proceeds = p["sh"] * pr * (1 - ch)
            cash += proceeds
            ci = p["sh"] * p["ep"] * (1 + ch)
            trades.append({"ticker": tk, "entry_date": p["ed"],
                           "exit_date": dstr,
                           "net_ret": round((proceeds / ci - 1) * 100, 4),
                           "pnl": round(proceeds - ci, 2),
                           "industry": t2i.get(tk, ""),
                           "sector": t2s.get(tk, "")})

        # ---- 3) EOD equity mark ----
        mv = 0.0
        for tk, p in pos.items():
            pr = px(close_m, tk, dstr)
            mv += p["sh"] * (pr if pr is not None and not pd.isna(pr)
                             else p["ep"])
        eq = cash + mv
        daily.append({"date": dstr, "equity": round(eq, 2),
                      "exposure": round(mv / eq if eq > 0 else 0, 4),
                      "n_positions": len(pos)})
    return trades, daily, diag


def cagr_pct(daily, days_per_year=252):
    if not daily or len(daily) < 2:
        return None
    eq0, eq1 = daily[0]["equity"], daily[-1]["equity"]
    yrs = (len(daily) - 1) / days_per_year
    if yrs <= 0 or eq0 <= 0 or eq1 <= 0:
        return None
    return round(((eq1 / eq0) ** (1 / yrs) - 1) * 100, 3)


def overall_row(daily, trades):
    o = bt04.segment_stats(daily, trades)
    o["cagr_pct"] = cagr_pct(daily)
    return o


def compute_signals(close_m, instruments, signal_dates, compute_rank_matrix):
    """Duplikat signalove smycky z bt04.main() (tam je inline, nelze
    importovat bez zmeny puvodniho souboru). Logika identicka."""
    mle_sig = {}
    for i, td in enumerate(signal_dates):
        rd = date.fromisoformat(td)
        ws = pd.Timestamp(rd - timedelta(days=45))
        we = pd.Timestamp(rd)
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
        col = f"rank_{MLE_GATE_LB}d"
        lst = [(tk, int(rm.loc[tk, col])) for tk in rm.index
               if not pd.isna(rm.loc[tk, col]) and int(rm.loc[tk, col]) <= 10]
        lst.sort(key=lambda x: x[1])
        mle_sig[td] = lst
        if (i + 1) % 250 == 0:
            print(f"  ... signaly {i + 1}/{len(signal_dates)}")
    return mle_sig


# ---------------------------------------------------------------- selftest
def _selftest():
    """Synteticky test kauzalni mechaniky bez DATA-06.

    Casova osa (hold=1): entry si=1 (open d1) -> exit si=2 (close d2).
    Kandidati vzdy jen ze signal_by_date[prev] (shodne s originalem) -
    signal stary 2+ dnu se nepouziva.

    Scenar A — SLOT (max_positions=1, target_weight=1.0):
      d0: signal A; d1: signal B; d2: signal C
      - d1 open: koupi se A (signal d0). exit A = close d2.
      - d2 open: A pending exit na dnesnim close -> slot obsazen
        -> B (signal d1) se NEkoupi. Zaroven cash=0 (vse v A).
      - d3 open: slot volny, cash z proceeds A -> koupi se C (signal d2).
      - B nesmi byt koupeno nikdy.

    Scenar B — CASH (max_positions=2, target_weight=1.0):
      volny slot na d2 existuje, ale cash=0 (proceeds z A prijdou az
      na close d2) -> B se stejne NEkoupi. Izoluje cash chronologii
      od slot chronologie.

    Scenar C — REGIME (max_positions=10):
      regime: d0=True, d1=False, d2=False
      - d1 open (signal d0): gate cte regime[d0]=True -> nakup probehne
        (original by cetl regime[d1]=False a zablokoval -> lookahead)
      - d2 open (signal d1): gate cte regime[d1]=False -> zadny nakup
    """
    dates = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
    ts = [pd.Timestamp(d) for d in dates]
    close_m = pd.DataFrame({"A": [10.0, 11.0, 12.0, 13.0],
                            "B": [20.0, 21.0, 22.0, 23.0],
                            "C": [30.0, 31.0, 32.0, 33.0]}, index=ts)
    open_m = close_m.copy()
    sig = {dates[0]: [("A", 1)], dates[1]: [("B", 1)], dates[2]: [("C", 1)]}

    # --- scenar A: SLOT chronologie ---
    tr, dl, dg = run_causal(sig, dates, close_m, open_m, hold=1, cost_bps=0,
                            t2i={}, t2s={}, use_regime=False, regime_ok={},
                            max_positions=1, initial_capital=1000.0,
                            target_weight=1.0)
    entries = {t["ticker"]: t["entry_date"] for t in tr}
    assert entries.get("A") == dates[1], f"A entry {entries.get('A')}"
    assert "B" not in entries, f"B nesmelo byt koupeno, entry {entries.get('B')}"
    assert entries.get("C") == dates[3], f"C entry {entries.get('C')}"
    assert dg["entries_blocked_portfolio_full_with_pending_exit"] >= 1
    # C koupene za proceeds z A: equity na d3 open = 90.909*12 = ~1090.9
    c_tr = [t for t in tr if t["ticker"] == "C"]
    assert c_tr, "C trade chybi (nuceny exit na konci dat mel probehnout)"
    print("SELFTEST A (slot chronologie): OK")

    # --- scenar B: CASH chronologie (volny slot, ale cash=0) ---
    tr_b, _, dg_b = run_causal(sig, dates, close_m, open_m, hold=1,
                               cost_bps=0, t2i={}, t2s={}, use_regime=False,
                               regime_ok={}, max_positions=2,
                               initial_capital=1000.0, target_weight=1.0)
    entries_b = {t["ticker"]: t["entry_date"] for t in tr_b}
    assert entries_b.get("A") == dates[1]
    assert "B" not in entries_b, \
        f"B koupeno na d2 z penez, ktere prijdou az na close d2 (D2 defekt!)"
    print("SELFTEST B (cash chronologie): OK")

    # --- scenar C: regime bez lookaheadu ---
    regime = {dates[0]: True, dates[1]: False, dates[2]: False,
              dates[3]: False}
    tr2, dl2, dg2 = run_causal(sig, dates, close_m, open_m, hold=2,
                               cost_bps=0, t2i={}, t2s={}, use_regime=True,
                               regime_ok=regime, max_positions=10,
                               initial_capital=1000.0, target_weight=0.5)
    # A: signal d0, entry d1 open, regime[d0]=True -> MUSI probehnout
    # B: signal d1, entry d2 open, regime[d1]=False -> NESMI probehnout
    assert dg2["buys"] == 1, f"ocekavan 1 buy (jen A), je {dg2['buys']}"
    assert dg2["regime_off_entry_days"] >= 1
    print("SELFTEST C (regime kauzalita): OK")
    print("SELFTEST: vse OK")
    return 0


# ---------------------------------------------------------------- main
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
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if pd is None:
        print("SETUP FAIL: chybi pandas/numpy")
        return 2
    if args.selftest:
        return _selftest()

    mle_root = Path(args.mle_root)
    sys.path.insert(0, str(mle_root))
    try:
        from src.engines.rank_matrix_engine import compute_rank_matrix
    except ImportError as e:
        print(f"FAIL: MLE engine import: {e}")
        return 2

    mrl = Path(args.mrl_root) if args.mrl_root else \
        Path(__file__).resolve().parent.parent.parent
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
    full_idx = [str(x.date()) for x in close_m.index]
    print(f"close matrix {close_m.shape}")

    if close_m.empty:
        print("FAIL: prazdna cenova matice - zkontroluj --view-dir "
              "(parquet soubory <conid>_D1.parquet) a universe CSV")
        return 2

    full_pos = {s: i for i, s in enumerate(full_idx)}
    signal_dates = [d for d in full_idx if args.dfrom <= d <= args.dto]
    if not signal_dates:
        print(f"FAIL: zadne obchodni dny v okne {args.dfrom}..{args.dto} "
              "- zkontroluj --from/--to vs rozsah dat ve view")
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

    # regime: stary (originalni handling) i novy (D3)
    regime_old, _ = bt04.build_regime(close_m)
    regime_new, _, valid_by_day = build_regime_causal(close_m)

    vseries = [valid_by_day[d] for d in sim_dates if d in valid_by_day]
    valid_summary = {"min": int(min(vseries)), "max": int(max(vseries)),
                     "median": float(np.median(vseries)),
                     "days_below_400": int(sum(1 for v in vseries if v < 400))}
    print(f"regime valid constituents: {valid_summary}")

    # rozdily regime serii
    timing_shift_days = []      # D1: ok_new[prev] != ok_new[dstr]
    data_handling_days = []     # D3: ok_old[d] != ok_new[d]
    for si in range(1, len(sim_dates)):
        d, p = sim_dates[si], sim_dates[si - 1]
        if regime_new.get(p, True) != regime_new.get(d, True):
            timing_shift_days.append(d)
    for d in sim_dates:
        if regime_old.get(d, True) != regime_new.get(d, True):
            data_handling_days.append(d)

    # signaly jednou, sdilene obema smyckami
    mle_sig = compute_signals(close_m, instruments, signal_dates,
                              compute_rank_matrix)

    results = {}
    for name, hold, ur in VARIANTS_R:
        key = f"{name}_hold{hold}"
        # stara smycka = presne bt04.run se starym regime (auditni referencni beh)
        tr_o, dl_o = bt04.run(mle_sig, sim_dates, close_m, open_m, hold,
                              COST_BPS, t2i, t2s, ur, regime_old)
        # nova kauzalni smycka s novym regime
        tr_n, dl_n, dg = run_causal(mle_sig, sim_dates, close_m, open_m,
                                    hold, COST_BPS, t2i, t2s, ur, regime_new)
        results[key] = {
            "old": {"overall": overall_row(dl_o, tr_o),
                    "yearly": bt04.yearly_breakdown(dl_o, tr_o, regime_old)},
            "new": {"overall": overall_row(dl_n, tr_n),
                    "yearly": bt04.yearly_breakdown(dl_n, tr_n, regime_new),
                    "diagnostics": dg},
        }
        # trade-level diff
        so = {(t["ticker"], t["entry_date"]) for t in tr_o}
        sn = {(t["ticker"], t["entry_date"]) for t in tr_n}
        results[key]["trade_diff"] = {
            "old_trades": len(so), "new_trades": len(sn),
            "only_in_old": len(so - sn), "only_in_new": len(sn - so)}
        o, n_ = results[key]["old"]["overall"], results[key]["new"]["overall"]
        print(f"\n{key}: OLD ret {o.get('total_return_pct')}% "
              f"cagr {o.get('cagr_pct')}% dd {o.get('max_drawdown_pct')}% | "
              f"NEW ret {n_.get('total_return_pct')}% "
              f"cagr {n_.get('cagr_pct')}% dd {n_.get('max_drawdown_pct')}%")
        print(f"  diag: {dg} | trade_diff: {results[key]['trade_diff']}")

    payload = {
        "task": "MLE-BT-04R causal execution correction",
        "pandas_version": pd.__version__,
        "sim_start": sim_dates[0], "sim_end": sim_dates[-1],
        "sim_days": len(sim_dates), "signal_days": len(signal_dates),
        "cost_bps": COST_BPS,
        "SURVIVORSHIP_WARNING": "current 503 universe, survivorship bias "
                                "(dedeno z BT-04, tato oprava neresi).",
        "corrections": {
            "D1_regime_lookahead": "gate cte regime_ok[D] misto regime_ok[D+1]",
            "D2_cash_slot_chronology": "vstupy(open) pred exity(close); "
                                       "proceeds+slot dostupne az open D+1",
            "D3_regime_data_handling": "pct_change(fill_method=None), "
                                       "mean(skipna=True), log valid_n"},
        "regime_valid_constituents": valid_summary,
        "regime_timing_shift_days": {"count": len(timing_shift_days),
                                     "dates": timing_shift_days},
        "regime_data_handling_diff_days": {"count": len(data_handling_days),
                                           "dates": data_handling_days},
        "variants": results,
    }

    out_dir = Path(args.out) if args.out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-BT-04R_causal_execution_correction.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # --- MD report ---
    L = ["# MLE-BT-04R — Causal Execution Correction (AUDIT)", "",
         "Oprava MLE-BT-04: (D1) regime lookahead, (D2) cash/slot "
         "chronologie, (D3) regime data handling. ZADNA zmena strategie.",
         "", f"Sim: {payload['sim_start']}..{payload['sim_end']} "
         f"({payload['sim_days']} dni), cost {COST_BPS} bps, "
         f"pandas {pd.__version__}", "",
         f"**{payload['SURVIVORSHIP_WARNING']}**", "",
         "## Srovnani OLD (BT-04) vs NEW (BT-04R)", "",
         "| variant | run | return% | CAGR% | maxDD% | sharpe | calmar "
         "| trades | avg_expo |",
         "|---|---|---|---|---|---|---|---|---|"]
    for key in results:
        for tag in ("old", "new"):
            o = results[key][tag]["overall"]
            L.append(f"| {key} | {tag.upper()} | {o.get('total_return_pct')} "
                     f"| {o.get('cagr_pct')} | {o.get('max_drawdown_pct')} "
                     f"| {o.get('sharpe')} | {o.get('calmar')} "
                     f"| {o.get('trades')} | {o.get('avg_exposure')} |")
    L += ["", "## Regime rozdily", "",
          f"- D1 timing shift (ok[D] vs ok[D+1]) — dnu s rozdilnym gate: "
          f"{len(timing_shift_days)}",
          f"  - dny: {timing_shift_days}",
          f"- D3 data handling (old vs new regime serie) — rozdilnych dnu: "
          f"{len(data_handling_days)}",
          f"  - dny: {data_handling_days}",
          f"- valid constituents: {valid_summary}", ""]
    for key in results:
        dg = results[key]["new"]["diagnostics"]
        td = results[key]["trade_diff"]
        L += [f"## {key} — diagnostika NEW", "",
              f"- buys: {dg['buys']}",
              f"- dny se signalem zablokovane regime gate (OFF): "
              f"{dg['regime_off_entry_days']}",
              f"- dny s plnym portfoliem vc. pending-exit pozic: "
              f"{dg['entries_blocked_portfolio_full_with_pending_exit']}",
              f"- kandidati nekoupitelni kvuli pending exitu tehoz dne: "
              f"{dg['reentry_candidates_blocked_pending_exit']}",
              f"- buys orezane dostupnym cashem (< 10% target): "
              f"{dg['cash_binding_buys']}",
              f"- trade diff old/new: {td}", ""]
        L += [f"### {key} — rocni rozklad NEW", "",
              "| rok | ret% | maxDD% | sharpe | trades | regime_on% |",
              "|---|---|---|---|---|---|"]
        for y, s in results[key]["new"]["yearly"].items():
            L.append(f"| {y} | {s.get('total_return_pct')} "
                     f"| {s.get('max_drawdown_pct')} | {s.get('sharpe')} "
                     f"| {s.get('trades')} | {s.get('regime_pct_on')} |")
        L.append("")
    L += ["## Vyhrady", "",
          "- Auditni oprava, NE optimalizace. Strategie beze zmeny.",
          "- OLD beh = import puvodniho bt04.run + bt04.build_regime "
          "(soubor BT-04 nezmenen).",
          "- Signaly sdilene obema behy -> rozdil = exekuce + regime.",
          "- SURVIVORSHIP: current 503 universe.",
          "- Nuceny exit na konci dat zachovan (srovnatelnost trades).", ""]
    (out_dir / "MLE-BT-04R_causal_execution_correction.md").write_text(
        "\n".join(L), encoding="utf-8")
    print(f"\nOK: reporty v {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
