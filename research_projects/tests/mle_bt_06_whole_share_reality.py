"""
mle_bt_06_whole_share_reality.py — MLE-BT-06.

WHOLE-SHARE EXECUTION REALITY TEST. Diagnosticky report, NENI zmena frozen
strategie. Pouziva kauzalni engine z MLE-BT-04R (import, zadna duplikace pro
fractional baseline). Testuje, zda edge prezije realistickou celociselnou
exekuci (bez frakcnich akcii) napric kapitalovymi urovnemi.

BT-06 nemeni signal, regime ani sizing. Meni JEN fill model:
  fractional  : sh = spend / (open * (1 + ch))            (== MLE-BT-04R)
  whole_share : sh = floor(spend / (open * (1 + ch)))     (Model A)
                sh < 1 -> BUY se preskoci (slot zustane prazdny, zadna
                rank-11 substituce), zbytek cash zustava cash.

Zachovano (zadna zmena strategie): MLE rank_10d <= 10, max 10 pozic, 10 %
equity target, fixed 503 universe, BUY open D+1 (signal+regime z close D),
EXIT close planned_exit_date, cash/slot z exitu az dalsi obchodni den,
15 bps round-trip (7.5 bps/strana). spend = min(target, cash/(1+ch)) je
uz cost-aware v run_causal -> cash nikdy nejde do minusu.

Model A: zbytkova cash po celociselnem flooru se v ramci tehoz dne
NErecykluje (target_value se neprepocitava). Izoluje ciste rozdil
frakce vs cele kusy.

Skip taxonomie (whole_share):
  TOO_EXPENSIVE_FOR_TARGET : floor(target/(open*(1+ch))) < 1 (10 % target
                             ani net-of-cost nekoupi 1 akcii) — hlavni metrika
  INSUFFICIENT_CASH        : target by 1 akcii koupil, ale zbytkova cash ne
  DATA_MISSING             : chybi open D+1

Kapitalovy sweep: 3k, 5k, 10k, 25k, 30k, 50k, 100k, 250k. Kazda uroven bezi
OBA rezimy -> delta = ciste dopad celociselne exekuce na te urovni
(whole@Xk vs fractional@Xk, ne vs fractional@100k).

Validacni gate (sanity anchor, jako MLE-BT-05):
  fractional regime200 hold10 @ 100k MUSI reprodukovat publikovane
  MLE-BT-04R (337.652 % / 34.504 % / -32.700 % / 1.182 / 990 / 0.787),
  vcetne nakladu. Navic run_local(whole_share=False) == bt04r.run_causal
  den-po-dni (dukaz, ze lokalni kopie je verna, nez verime whole_share).
  Gate FAIL -> whole-share matice se nespusti.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\mle_bt_06_whole_share_reality.py ^
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Selftest bez dat (synteticka matice, overi floor/skip + vernost kopie):
    python research_projects\\tests\\mle_bt_06_whole_share_reality.py --selftest

Cache signalu: sdilena s MLE-BT-04R/BT-05
(reports/backtests/mle_signals_cache_<from>_<to>.json); prvni beh pocita,
dalsi nacte. Vynuceny prepocet: --recompute-signals.

Vystupy: reports/backtests/MLE-BT-06_whole_share_reality.{json,md}

DATA SNOOPING / VYHRADY:
  - Jedno 5lete in-sample okno se survivorship biasem (current 503 universe,
    dedeno z BT-04). BT-06 survivorship neresi a neresit nema.
  - Kapitalovy sweep NEni vyber uctu; ukazuje, od jake urovne celociselna
    exekuce prestava nicit edge. Bodova hodnota na jedne ceste neni dukaz.
  - Reprodukce = validace IMPLEMENTACE, ne strategie.

Edge cases / predpoklady:
  - signaly se pocitaji jednou a sdileji vsechny behy -> rozdily vysledku =
    vyhradne fill model (fractional vs whole_share) a kapital.
  - fractional baseline = bt04r.run_causal (import). whole_share = lokalni
    verna kopie s jedinou zmenou: floor + skip taxonomie.
  - cash_drag = 1 - avg_exposure; deployment = avg_exposure (denni MTM equity).
  - rank-ascending nakupy (run_causal bere cands[:free], top10 poradi dle ranku);
    skip nechava slot prazdny, nesubstituuje rank 11.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
except ImportError:
    pd = None

# --- import sourozencu (soubory se NEMENI) ---
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
bt04 = importlib.import_module("mle_bt_04_yearly_monthly_regime_breakdown")
bt04r = importlib.import_module("mle_bt_04r_causal_execution_correction")

MAX_POSITIONS = bt04.MAX_POSITIONS
INITIAL_CAPITAL = bt04.INITIAL_CAPITAL
TARGET_WEIGHT = bt04.TARGET_WEIGHT
COST_BPS = bt04.COST_BPS
DEFAULT_FROM, DEFAULT_TO = bt04.DEFAULT_FROM, bt04.DEFAULT_TO

HOLD = 10
CAPITALS_DEFAULT = [3000, 5000, 10000, 25000, 30000, 50000, 100000, 250000]
SKIP_REASONS = ("TOO_EXPENSIVE_FOR_TARGET", "INSUFFICIENT_CASH", "DATA_MISSING")
PUBLISHED_BT04R = {"total_return_pct": 337.652, "cagr_pct": 34.504,
                   "max_drawdown_pct": -32.700, "sharpe": 1.182,
                   "trades": 990, "avg_exposure": 0.787}


# ----------------------------------------------------------- signal cache
def signals_cache_path(out_dir, dfrom, dto):
    return out_dir / f"mle_signals_cache_{dfrom}_{dto}.json"


def load_signals(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {d: [(t, int(r)) for t, r in v] for d, v in raw.items()}


def save_signals(path, mle_sig):
    Path(path).write_text(
        json.dumps({d: [[t, r] for t, r in v] for d, v in mle_sig.items()}),
        encoding="utf-8")


# ----------------------------------------------------------- engine (copy)
def run_local(signal_by_date, sim_dates, close_m, open_m, hold, cost_bps,
              t2i, t2s, use_regime, regime_ok,
              max_positions=None, initial_capital=None, target_weight=None,
              whole_share=False):
    """Verna kopie bt04r.run_causal. Jedina zmena: whole_share -> floor(sh) +
    skip taxonomie. whole_share=False MUSI dat identicky vysledek jako
    bt04r.run_causal (overuje selftest a gate).
    """
    mp = max_positions if max_positions is not None else MAX_POSITIONS
    ic = initial_capital if initial_capital is not None else INITIAL_CAPITAL
    tw = target_weight if target_weight is not None else TARGET_WEIGHT
    n = len(sim_dates)
    ch = cost_bps / 2.0 / 10000.0
    cash = ic
    min_cash = ic  # audit: cash nesmi nikdy klesnout pod 0
    pos = {}
    trades = []
    daily = []
    diag = {"buys": 0, "regime_off_entry_days": 0,
            "entries_blocked_portfolio_full_with_pending_exit": 0,
            "reentry_candidates_blocked_pending_exit": 0,
            "cash_binding_buys": 0}
    skips = {r: 0 for r in SKIP_REASONS}
    skip_tickers = {}  # ticker -> #TOO_EXPENSIVE_FOR_TARGET (diagnostika)

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
                free = mp - len(pos)
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
                            if whole_share:
                                skips["DATA_MISSING"] += 1
                            continue
                        target = tw * eqn
                        spend = min(target, cash / (1 + ch))
                        if spend <= 0:
                            continue
                        if spend < target - 1e-9:
                            diag["cash_binding_buys"] += 1
                        sh = spend / (op * (1 + ch))
                        if whole_share:
                            sh = math.floor(sh)
                            if sh < 1:
                                if math.floor(target / (op * (1 + ch))) < 1:
                                    skips["TOO_EXPENSIVE_FOR_TARGET"] += 1
                                    skip_tickers[tk] = skip_tickers.get(tk, 0) + 1
                                else:
                                    skips["INSUFFICIENT_CASH"] += 1
                                continue
                        ct = sh * op * (1 + ch)
                        if sh <= 0 or ct > cash + 1e-6:
                            continue
                        cash -= ct
                        min_cash = min(min_cash, cash)
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

    diag["skips"] = skips
    diag["skip_tickers"] = skip_tickers
    diag["min_cash"] = round(min_cash, 6)
    return trades, daily, diag


# ----------------------------------------------------------- metrics
def full_metrics(daily, trades, diag, whole_share, max_positions=MAX_POSITIONS):
    o = dict(bt04r.overall_row(daily, trades))
    expo = o.get("avg_exposure") or 0.0
    o["cash_drag"] = round(1.0 - expo, 4)
    o["deployment_ratio"] = round(expo, 4)
    npos = [d["n_positions"] for d in daily]
    o["days_10_of_10"] = int(sum(1 for x in npos if x >= max_positions))
    o["days_under_10"] = int(sum(1 for x in npos if x < max_positions))
    if whole_share:
        o["skips"] = {r: diag["skips"].get(r, 0) for r in SKIP_REASONS}
        o["skips_total"] = int(sum(o["skips"].values()))
    return o


def delta(whole, frac):
    keys = ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe",
            "trades", "avg_exposure", "cash_drag", "deployment_ratio",
            "avg_positions", "days_10_of_10", "days_under_10"]
    out = {}
    for k in keys:
        a, b = whole.get(k), frac.get(k)
        out[k] = round(a - b, 3) if (isinstance(a, (int, float))
                                     and isinstance(b, (int, float))) else None
    return out


# ----------------------------------------------------------- diagnostika
def annual_breakdown(daily):
    """Rocni return + prumerna exposure/cash_drag z denni MTM equity.
    return[y] = eq(konec y) / eq(konec y-1) - 1 (prvni rok baze = prvni den)."""
    by_year = {}
    for d in daily:
        by_year.setdefault(d["date"][:4], []).append(d)
    out, prev_end = {}, None
    for y in sorted(by_year):
        rows = by_year[y]
        base = prev_end if prev_end is not None else rows[0]["equity"]
        end = rows[-1]["equity"]
        expo = sum(r["exposure"] for r in rows) / len(rows)
        out[y] = {"return_pct": round((end / base - 1) * 100, 3)
                  if base > 0 else None,
                  "avg_exposure": round(expo, 4),
                  "cash_drag": round(1 - expo, 4), "days": len(rows)}
        prev_end = end
    return out


def missed_attribution(frac_trades, whole_trades):
    """Obchody z fractional baseline, ktere whole_share VUBEC nevzal
    (skip), a jejich forgone pnl (prvni-radova atribuce anomalie)."""
    wkeys = {(t["ticker"], t["entry_date"]) for t in whole_trades}
    missed = [t for t in frac_trades
              if (t["ticker"], t["entry_date"]) not in wkeys]
    top = sorted(missed, key=lambda t: -t["pnl"])[:12]
    return {"n_missed": len(missed),
            "missed_pnl_total": round(sum(t["pnl"] for t in missed), 2),
            "top_missed": [(t["ticker"], t["entry_date"], t["exit_date"],
                            t["pnl"]) for t in top]}


def top_skipped(diag, k=15):
    st = diag.get("skip_tickers", {})
    return sorted(st.items(), key=lambda x: -x[1])[:k]


def _ledger(trades):
    """Kanonicky trade ledger pro striktni rovnost (audit): cely obchod,
    ne jen pocet — ticker, entry, exit, net_ret, pnl."""
    return sorted((t["ticker"], t["entry_date"], t["exit_date"],
                   t["net_ret"], t["pnl"]) for t in trades)


# ----------------------------------------------------------- selftest
def _selftest():
    if pd is None:
        print("SELFTEST FAIL: chybi pandas/numpy")
        return 2
    idx = [pd.Timestamp(d) for d in
           ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]]
    sim = [str(x.date()) for x in idx]
    close = pd.DataFrame({"CHEAP": [100.0] * 4, "EXP": [5000.0] * 4,
                          "MID": [40.0] * 4}, index=idx)
    openm = close.copy()
    sig = {sim[0]: [("CHEAP", 1), ("EXP", 2), ("MID", 3)]}
    regime_ok = {d: True for d in sim}
    t2i = {"CHEAP": "i", "EXP": "i", "MID": "i"}
    t2s = {"CHEAP": "s", "EXP": "s", "MID": "s"}

    # 1) vernost kopie: run_local(whole_share=False) == bt04r.run_causal
    a_tr, a_dl, a_dg = run_local(sig, sim, close, openm, HOLD, COST_BPS, t2i,
                                 t2s, True, regime_ok, initial_capital=3000.0,
                                 whole_share=False)
    b_tr, b_dl, _ = bt04r.run_causal(sig, sim, close, openm, HOLD, COST_BPS,
                                     t2i, t2s, True, regime_ok,
                                     initial_capital=3000.0)
    faithful = (a_dl == b_dl and _ledger(a_tr) == _ledger(b_tr))

    # 2) whole_share floor + skip taxonomie @ 3k (target=300)
    w_tr, w_dl, w_dg = run_local(sig, sim, close, openm, HOLD, COST_BPS, t2i,
                                 t2s, True, regime_ok, initial_capital=3000.0,
                                 whole_share=True)
    sk = w_dg["skips"]
    ok_skip = (sk["TOO_EXPENSIVE_FOR_TARGET"] == 1
               and sk["INSUFFICIENT_CASH"] == 0)
    ok_cash = all(d["equity"] > 0 for d in w_dl)
    # AUDIT: min_cash nesmi klesnout pod 0 (fractional i whole_share)
    ok_min_cash = (a_dg.get("min_cash", 0) >= -1e-6
                   and w_dg.get("min_cash", 0) >= -1e-6)

    verdict = faithful and ok_skip and ok_cash and ok_min_cash
    print(f"SELFTEST: faithful_copy={faithful} (full ledger) "
          f"skip_taxonomy={ok_skip} cash_nonneg={ok_cash} "
          f"min_cash_nonneg={ok_min_cash}")
    print(f"SELFTEST: {'PASS' if verdict else 'FAIL'}")
    return 0 if verdict else 1


# ----------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description="MLE-BT-06 Whole-Share Reality")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--mle-root",
                    default=r"C:\Users\stava\Projects\MarketLeadershipEngine")
    ap.add_argument("--universe-csv",
                    default=r"C:\Users\stava\Projects\MDSM-Lite\data\universe\sp500_rank_calendar_universe.csv")
    ap.add_argument("--view-dir",
                    default=r"C:\Users\stava\Projects\sharadar_snapshot_store\snapshots\sharadar_full_equity_v20260705_01\derived\mdsm_price_view")
    ap.add_argument("--from", dest="dfrom", default=DEFAULT_FROM)
    ap.add_argument("--to", dest="dto", default=DEFAULT_TO)
    ap.add_argument("--capitals",
                    default=",".join(str(c) for c in CAPITALS_DEFAULT))
    ap.add_argument("--modes", default="fractional,whole_share")
    ap.add_argument("--mrl-root", default=None)
    ap.add_argument("--maxsig", default="0")
    ap.add_argument("--out", default=None)
    ap.add_argument("--recompute-signals", action="store_true")
    ap.add_argument("--skip-gate", action="store_true")
    ap.add_argument("--diagnostic", action="store_true",
                    help="navic zapise MLE-BT-06_diagnostic_addendum.{json,md}")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
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
    print(f"universe {len(instruments)} | pandas {pd.__version__}")

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
    full_pos = {s: i for i, s in enumerate(full_idx)}
    print(f"close matrix {close_m.shape}")

    signal_dates = [d for d in full_idx if args.dfrom <= d <= args.dto]
    if not signal_dates:
        print(f"FAIL: zadne obchodni dny v okne {args.dfrom}..{args.dto}")
        return 2
    maxsig = int(args.maxsig)
    if maxsig > 0:
        signal_dates = signal_dates[:maxsig]
    sp, lp = full_pos[signal_dates[0]], full_pos[signal_dates[-1]]
    ep = min(lp + 20 + 1, len(full_idx) - 1)
    sim_dates = full_idx[sp:ep + 1]
    print(f"sim {sim_dates[0]}..{sim_dates[-1]} ({len(sim_dates)})")

    regime_ok, _, _ = bt04r.build_regime_causal(close_m)

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

    # ---- validacni gate (sanity anchor) ----
    gate = {"ran": False}
    if not args.skip_gate:
        print("gate: fractional regime200 hold10 @100k -> reprodukce BT-04R...")
        g_tr, g_dl, _ = bt04r.run_causal(mle_sig, sim_dates, close_m, open_m,
                                         HOLD, COST_BPS, t2i, t2s, True,
                                         regime_ok, initial_capital=INITIAL_CAPITAL)
        anchor = bt04r.overall_row(g_dl, g_tr)
        anchor["trades"] = len(g_tr)
        anchor_ok = all(anchor.get(k) == v for k, v in PUBLISHED_BT04R.items())
        l_tr, l_dl, l_dg = run_local(mle_sig, sim_dates, close_m, open_m, HOLD,
                                     COST_BPS, t2i, t2s, True, regime_ok,
                                     initial_capital=INITIAL_CAPITAL,
                                     whole_share=False)
        # AUDIT: striktni rovnost CELEHO trade-ledgeru (ne jen daily+pocet)
        ledger_identical = _ledger(l_tr) == _ledger(g_tr)
        faithful = (l_dl == g_dl and ledger_identical)
        gate = {"ran": True, "anchor_reproduces_bt04r": anchor_ok,
                "local_copy_faithful": faithful,
                "ledger_identical": ledger_identical,
                "min_cash_fractional_100k": l_dg.get("min_cash"),
                "anchor_metrics": {k: anchor.get(k) for k in PUBLISHED_BT04R},
                "PASS": bool(anchor_ok and faithful)}
        print(f"  anchor_ok={anchor_ok} faithful={faithful} "
              f"ledger_identical={ledger_identical} -> gate PASS={gate['PASS']}")
        if not gate["PASS"]:
            (out_dir / "MLE-BT-06_whole_share_reality.json").write_text(
                json.dumps({"gate": gate, "anchor_metrics": anchor,
                            "published": PUBLISHED_BT04R,
                            "VERDICT": "GATE_FAIL"}, indent=2, default=str),
                encoding="utf-8")
            print("  GATE FAIL -> whole-share matice se nespousti.")
            return 1

    # ---- kapitalovy sweep x rezimy ----
    capitals = [int(float(c)) for c in args.capitals.split(",") if c.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    results, deltas, raw = {}, {}, {}
    for cap in capitals:
        results[cap], raw[cap] = {}, {}
        for mode in modes:
            ws = (mode == "whole_share")
            print(f"run: capital={cap} mode={mode} ...")
            tr, dl, dg = run_local(mle_sig, sim_dates, close_m, open_m, HOLD,
                                   COST_BPS, t2i, t2s, True, regime_ok,
                                   initial_capital=float(cap), whole_share=ws)
            results[cap][mode] = full_metrics(dl, tr, dg, ws)
            raw[cap][mode] = (tr, dl, dg)
        if "whole_share" in results[cap] and "fractional" in results[cap]:
            deltas[cap] = delta(results[cap]["whole_share"],
                                results[cap]["fractional"])

    # AUDIT: min_cash napric vsemi behy (whole_share floor nesmi shodit cash <0)
    min_cash_all = min(raw[c][m][2].get("min_cash", 0.0)
                       for c in capitals for m in modes)
    audit = {"gate_ledger_identical":
             gate.get("ledger_identical") if gate.get("ran") else None,
             "min_cash_over_all_runs": round(min_cash_all, 6),
             "min_cash_nonneg": bool(min_cash_all >= -1e-6)}
    print(f"audit: min_cash_over_all_runs={audit['min_cash_over_all_runs']} "
          f"nonneg={audit['min_cash_nonneg']}")

    payload = {"task": "MLE-BT-06 Whole-Share Execution Reality",
               "engine": "MLE-BT-04R run_causal (import) + local whole-share copy",
               "pandas_version": pd.__version__,
               "sim_start": sim_dates[0], "sim_end": sim_dates[-1],
               "sim_days": len(sim_dates), "capitals": capitals,
               "modes": modes, "gate": gate, "audit": audit,
               "results": results,
               "deltas": deltas, "published_bt04r": PUBLISHED_BT04R,
               "VERDICT": "OK"}
    (out_dir / "MLE-BT-06_whole_share_reality.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _write_md(out_dir, payload)

    if args.diagnostic:
        _write_addendum(out_dir, capitals, modes, raw, results, deltas)
        print("diagnostic: MLE-BT-06_diagnostic_addendum.{json,md}")

    print(f"\nVERDICT: OK | reporty v {out_dir}")
    return 0


def _min_operational_bucket(capitals, results, deltas):
    """Nejmensi kapital s malo drahymi skipy a malym poklesem CAGR."""
    for cap in sorted(capitals):
        w = results.get(cap, {}).get("whole_share", {})
        d = deltas.get(cap, {})
        skips = (w.get("skips") or {}).get("TOO_EXPENSIVE_FOR_TARGET", 0)
        dcagr = d.get("cagr_pct")
        if skips <= 5 and dcagr is not None and dcagr >= -1.0:
            return cap
    return None


def _write_addendum(out_dir, capitals, modes, raw, results, deltas):
    add = {"task": "MLE-BT-06 diagnostic addendum",
           "annual": {}, "skipped_tickers": {}, "missed_attribution": {},
           "min_operational_bucket": _min_operational_bucket(
               capitals, results, deltas)}
    for cap in capitals:
        add["annual"][cap] = {}
        for mode in modes:
            tr, dl, dg = raw[cap][mode]
            add["annual"][cap][mode] = annual_breakdown(dl)
        if "whole_share" in raw[cap]:
            add["skipped_tickers"][cap] = top_skipped(raw[cap]["whole_share"][2])
        if "fractional" in raw[cap] and "whole_share" in raw[cap]:
            add["missed_attribution"][cap] = missed_attribution(
                raw[cap]["fractional"][0], raw[cap]["whole_share"][0])
    (out_dir / "MLE-BT-06_diagnostic_addendum.json").write_text(
        json.dumps(add, indent=2, default=str), encoding="utf-8")

    L = ["# MLE-BT-06 — Diagnostic Addendum", "",
         f"Minimalni provozni kapital (TOO_EXPENSIVE <= 5 a ΔCAGR >= -1.0): "
         f"**{add['min_operational_bucket']}**", ""]
    # annual returns whole_share vs fractional (klicove urovne)
    focus = [c for c in [3000, 5000, 10000, 30000, 50000] if c in capitals]
    years = sorted({y for c in focus
                    for y in add["annual"][c].get("whole_share", {})})
    L += ["## Rocni whole-share CAGR/return by capital (%)", "",
          "| rok | " + " | ".join(f"{c//1000}k" for c in focus) + " |",
          "|" + "---|" * (len(focus) + 1)]
    for y in years:
        row = [y]
        for c in focus:
            v = add["annual"][c].get("whole_share", {}).get(y, {})
            row.append(str(v.get("return_pct")))
        L.append("| " + " | ".join(row) + " |")
    L += ["", "## Rocni exposure / cash_drag (whole_share)", ""]
    for c in focus:
        L.append(f"### {c:,}")
        L.append("| rok | return% | avg_exposure | cash_drag | dni |")
        L.append("|---|---|---|---|---|")
        for y, v in add["annual"][c].get("whole_share", {}).items():
            L.append(f"| {y} | {v['return_pct']} | {v['avg_exposure']} | "
                     f"{v['cash_drag']} | {v['days']} |")
        L.append("")
    L += ["## Nejcasteji skipnute tickery (TOO_EXPENSIVE_FOR_TARGET)", ""]
    for cap in capitals:
        st = add["skipped_tickers"].get(cap, [])
        if st:
            names = ", ".join(f"{tk}({n})" for tk, n in st)
            L.append(f"- **{cap:,}**: {names}")
    L += ["", "## 5k anomalie — atribuce minulych obchodu (forgone pnl)", "",
          "Obchody z fractional baseline, ktere whole_share vubec nevzal:", "",
          "| capital | #missed | forgone_pnl | top missed (ticker/entry/pnl) |",
          "|---|---|---|---|"]
    for cap in [c for c in [3000, 5000, 10000] if c in capitals]:
        ma = add["missed_attribution"].get(cap, {})
        top = "; ".join(f"{t[0]} {t[1]} ({t[3]})"
                        for t in ma.get("top_missed", [])[:5])
        L.append(f"| {cap:,} | {ma.get('n_missed')} | "
                 f"{ma.get('missed_pnl_total')} | {top} |")
    L += ["", "## Poznamka", "",
          "- forgone_pnl je prvni-radova atribuce (pnl z fractional behu pro "
          "obchody, ktere whole_share neotevrel); nezahrnuje under-sizing "
          "zachycenych obchodu. Slouzi k vysvetleni, proc konkretni kapital "
          "vysel hur (path-dependence konkretnich jmen).",
          "- Jedno in-sample okno, survivorship (current 503). Bodova hodnota "
          "neni dukaz.", ""]
    (out_dir / "MLE-BT-06_diagnostic_addendum.md").write_text(
        "\n".join(L), encoding="utf-8")


def _write_md(out_dir, p):
    L = ["# MLE-BT-06 — Whole-Share Execution Reality", "",
         f"Sim: {p['sim_start']}..{p['sim_end']} ({p['sim_days']} dni), "
         f"pandas {p['pandas_version']}",
         f"Engine: {p['engine']}", ""]
    g = p["gate"]
    if g.get("ran"):
        L += [f"**Validation gate: {'PASS' if g.get('PASS') else 'FAIL'}** "
              f"(anchor reprodukuje BT-04R: {g.get('anchor_reproduces_bt04r')}, "
              f"lokalni kopie verna: {g.get('local_copy_faithful')}, "
              f"trade-ledger identicky: {g.get('ledger_identical')})", ""]
    a = p.get("audit", {})
    if a:
        L += [f"**Audit:** min_cash napric behy = {a.get('min_cash_over_all_runs')} "
              f"(>=0: {a.get('min_cash_nonneg')}); "
              f"gate trade-ledger identicky: {a.get('gate_ledger_identical')}", ""]
    L += ["## Edge vs capital — headline", "",
          "| capital | frac CAGR% | whole CAGR% | ΔCAGR | whole cash_drag | "
          "whole days<10/10 | TOO_EXPENSIVE skips |",
          "|---|---|---|---|---|---|---|"]
    for cap in p["capitals"]:
        r = p["results"].get(cap, {})
        f = r.get("fractional", {})
        w = r.get("whole_share", {})
        d = p["deltas"].get(cap, {})
        L.append(f"| {cap:,} | {f.get('cagr_pct')} | {w.get('cagr_pct')} | "
                 f"{d.get('cagr_pct')} | {w.get('cash_drag')} | "
                 f"{w.get('days_under_10')} | "
                 f"{w.get('skips', {}).get('TOO_EXPENSIVE_FOR_TARGET')} |")
    L += ["", "## Per-capital detail", ""]
    for cap in p["capitals"]:
        r = p["results"].get(cap, {})
        f = r.get("fractional", {})
        w = r.get("whole_share", {})
        d = p["deltas"].get(cap, {})
        L += [f"### capital = {cap:,}", "",
              "| metric | fractional | whole_share | delta |",
              "|---|---|---|---|"]
        for k in ["total_return_pct", "cagr_pct", "max_drawdown_pct", "sharpe",
                  "trades", "avg_exposure", "cash_drag", "deployment_ratio",
                  "avg_positions", "days_10_of_10", "days_under_10"]:
            L.append(f"| {k} | {f.get(k)} | {w.get(k)} | {d.get(k)} |")
        sk = w.get("skips", {})
        L.append(f"| skips (whole) | — | TOO_EXP {sk.get('TOO_EXPENSIVE_FOR_TARGET')}"
                 f" / INSUF {sk.get('INSUFFICIENT_CASH')}"
                 f" / DATA {sk.get('DATA_MISSING')} | — |")
        L.append("")
    L += ["## Vyhrady", "",
          "- BT-06 nemeni signal, regime ani DecisionResolver.",
          "- fractional = bt04r.run_causal (import). whole_share = lokalni verna "
          "kopie, jedina zmena floor + skip taxonomie (Model A, bez recyklace, "
          "bez rank-11 substituce).",
          "- cash_drag = 1 - avg_exposure; deployment = avg_exposure (denni MTM).",
          "- Jedno in-sample okno, survivorship (current 503). Bodova hodnota "
          "neni dukaz.", ""]
    (out_dir / "MLE-BT-06_whole_share_reality.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
