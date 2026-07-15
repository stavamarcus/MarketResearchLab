"""
mle_diag_01_loser_characteristics.py — MLE-DIAG-01.

READ-ONLY DIAGNOSTIC EDA. Analyzuje nejvetsi losery (a winnery) z 5leteho
MLE backtestu a hleda spolecne charakteristiky pri VSTUPU do pozice.

Testuje hypotezu: "maji losery mensi cenu akcie? nebo neco spolecneho?"

*** POZOR: hledani spolecneho rysu loseru na historii = IN-SAMPLE.
    Je to POPIS, ne hotovy filtr. Co odlisi losery zpetne nemusi platit
    dopredu. Survivorship: losery = akcie ktere klesly ale PREZILY. ***

NEDELA: build filtr z nalezu (to by byl overfit), optimalizace, live/paper.

Spusteni (MRL env):
    conda activate market_research_lab
    cd C:\\Users\\stava\\Projects\\MarketResearchLab
    python research_projects\\tests\\mle_diag_01_loser_characteristics.py \\
        --mle-root C:\\Users\\stava\\Projects\\MarketLeadershipEngine

Varianta: regime200 hold10 (primarni). Obdobi 2021-07..2026-07, 15bps.

Pri vstupu do kazde pozice zachyti:
    - entry_price (nominalni open cena) -> test "mensi cena"
    - momentum_rank (1-10) -> byl loser slabsi rank?
    - vol_20d (20denni volatilita returnu) -> byl loser volatilnejsi?
    - hist_days (delka historie pred vstupem) -> recent IPO?
    - sector, industry
Porovna:
    - losery (spodni kvintil dle net_ret) vs winnery (horni kvintil)
    - korelace entry_price <-> net_ret (odpovi na "mensi cena")
    - korelace vol_20d, rank, hist_days <-> net_ret

Edge cases / predpoklady:
    - entry features z DATA-06 pri vstupnim dni.
    - vol_20d = std poslednich 20 dennich returnu pred vstupem.
    - hist_days = pocet obchodnich dni tickeru pred vstupem (proxy pro IPO).
    - regime200 hold10 (primarni), 15bps.
    - korelace = Spearman (robustni na outliery), i Pearson.
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
HOLD = 10
COST_BPS = 15
REGIME_MA = 200


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
    dr = close_m.pct_change().mean(axis=1)
    idx = (1 + dr.fillna(0)).cumprod()
    ma = idx.rolling(REGIME_MA, min_periods=REGIME_MA).mean()
    ok = {}
    for ts in idx.index:
        m = ma.loc[ts]
        ok[str(ts.date())] = True if pd.isna(m) else bool(idx.loc[ts] > m)
    return ok


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
    ret_m = close_m.pct_change()
    full_idx = [str(x.date()) for x in close_m.index]
    full_pos = {s: i for i, s in enumerate(full_idx)}
    print(f"close matrix {close_m.shape}")

    # per ticker: prvni datum (pro hist_days)
    first_date = {}
    for tk in close_m.columns:
        s = close_m[tk].dropna()
        if not s.empty:
            first_date[tk] = str(s.index.min().date())

    regime_ok = build_regime(close_m)

    signal_dates = [d for d in full_idx if args.dfrom <= d <= args.dto]
    maxsig = int(args.maxsig)
    if maxsig > 0:
        signal_dates = signal_dates[:maxsig]
    print(f"signal_dates {len(signal_dates)}")

    sp = full_pos[signal_dates[0]]; lp = full_pos[signal_dates[-1]]
    ep = min(lp + HOLD + 1, len(full_idx) - 1)
    sim_dates = full_idx[sp:ep + 1]

    # MLE signaly + zachytit rank
    mle_sig = {}
    for i, td in enumerate(signal_dates):
        rd = date.fromisoformat(td)
        ws = pd.Timestamp(rd - timedelta(days=45)); we = pd.Timestamp(rd)
        cp = {}
        for tk in close_m.columns:
            s = close_m[tk]; sub = s[(s.index >= ws) & (s.index <= we)]
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

    # backtest regime200 hold10 + zachytit entry features per trade
    ch = COST_BPS / 2.0 / 10000.0
    cash = INITIAL_CAPITAL
    pos = {}
    trades = []
    n = len(sim_dates)

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
            net = (proceeds / ci - 1) * 100
            trades.append({**p["feat"], "ticker": tk, "entry_date": p["ed"],
                           "exit_date": dstr, "net_ret": round(net, 4),
                           "pnl": round(proceeds - ci, 2)})
        prev = sim_dates[si - 1] if si > 0 else None
        if prev in mle_sig and regime_ok.get(dstr, True):
            free = MAX_POSITIONS - len(pos)
            if free > 0:
                mvp = sum(p["sh"] * (px(close_m, tk, sim_dates[si-1]) or p["ep"])
                          for tk, p in pos.items()) if si > 0 else 0
                eqn = cash + mvp
                for tk, rank in [(t, r) for t, r in mle_sig[prev] if t not in pos][:free]:
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
                    # ENTRY FEATURES
                    entry_ts = pd.Timestamp(dstr)
                    r20 = ret_m[tk][ret_m.index <= entry_ts].tail(20) if tk in ret_m else None
                    vol20 = float(r20.std()) * 100 if r20 is not None and len(r20) > 5 else None
                    fd = first_date.get(tk)
                    hist_days = (len([d for d in full_idx if fd <= d < dstr])
                                 if fd else None)
                    feat = {"entry_price": round(float(op), 2),
                            "mom_rank": rank,
                            "vol_20d_pct": round(vol20, 3) if vol20 else None,
                            "hist_days": hist_days,
                            "sector": t2s.get(tk, ""), "industry": t2i.get(tk, "")}
                    pos[tk] = {"sh": sh, "ep": op, "ed": dstr,
                               "exit": min(si + HOLD, n - 1), "feat": feat}

    print(f"trades: {len(trades)}")

    # analyza: losery vs winnery
    trades_sorted = sorted(trades, key=lambda t: t["net_ret"])
    n_tr = len(trades)
    q = max(int(n_tr * 0.2), 10)
    losers = trades_sorted[:q]
    winners = trades_sorted[-q:]

    def summarize(group, label):
        prices = [t["entry_price"] for t in group if t["entry_price"]]
        vols = [t["vol_20d_pct"] for t in group if t["vol_20d_pct"]]
        ranks = [t["mom_rank"] for t in group if t["mom_rank"]]
        hists = [t["hist_days"] for t in group if t["hist_days"]]
        secs = defaultdict(int); inds = defaultdict(int)
        for t in group:
            secs[t["sector"]] += 1; inds[t["industry"]] += 1
        return {"label": label, "n": len(group),
                "entry_price_mean": round(float(np.mean(prices)), 2) if prices else None,
                "entry_price_median": round(float(np.median(prices)), 2) if prices else None,
                "vol_20d_mean": round(float(np.mean(vols)), 3) if vols else None,
                "mom_rank_mean": round(float(np.mean(ranks)), 2) if ranks else None,
                "hist_days_mean": round(float(np.mean(hists)), 0) if hists else None,
                "hist_days_median": round(float(np.median(hists)), 0) if hists else None,
                "top_sectors": dict(sorted(secs.items(), key=lambda x: -x[1])[:5]),
                "top_industries": dict(sorted(inds.items(), key=lambda x: -x[1])[:5]),
                "avg_net_ret": round(float(np.mean([t["net_ret"] for t in group])), 3),
                "worst_examples": [(t["ticker"], t["net_ret"], t["entry_price"],
                                    t["vol_20d_pct"], t["hist_days"])
                                   for t in group[:10]]}

    losers_sum = summarize(losers, "losers_bottom20pct")
    winners_sum = summarize(winners, "winners_top20pct")

    # korelace pres VSECHNY trades
    def corr(field):
        pairs = [(t[field], t["net_ret"]) for t in trades
                 if t.get(field) is not None]
        if len(pairs) < 10:
            return None
        x = np.array([p[0] for p in pairs], dtype=float)
        y = np.array([p[1] for p in pairs], dtype=float)
        pear = float(np.corrcoef(x, y)[0, 1])
        # spearman
        rx = pd.Series(x).rank().values; ry = pd.Series(y).rank().values
        spear = float(np.corrcoef(rx, ry)[0, 1])
        return {"pearson": round(pear, 4), "spearman": round(spear, 4), "n": len(pairs)}

    correlations = {f: corr(f) for f in
                    ["entry_price", "vol_20d_pct", "mom_rank", "hist_days"]}

    # kvintily dle entry_price -> avg return (test "mensi cena")
    price_bins = None
    valid_price = [t for t in trades if t["entry_price"]]
    if len(valid_price) >= 25:
        vp = sorted(valid_price, key=lambda t: t["entry_price"])
        k = len(vp) // 5
        price_bins = []
        for i in range(5):
            seg = vp[i*k:(i+1)*k] if i < 4 else vp[i*k:]
            price_bins.append({
                "quintile": i + 1,
                "price_range": [round(seg[0]["entry_price"], 2),
                                round(seg[-1]["entry_price"], 2)],
                "avg_net_ret": round(float(np.mean([t["net_ret"] for t in seg])), 3),
                "win_rate": round(float(np.mean([t["net_ret"] > 0 for t in seg])), 3),
                "n": len(seg)})

    payload = {"variant": "regime200_hold10", "n_trades": len(trades),
               "sim": [sim_dates[0], sim_dates[-1]],
               "losers": losers_sum, "winners": winners_sum,
               "correlations_with_net_ret": correlations,
               "price_quintiles": price_bins,
               "WARNING": ("IN-SAMPLE deskripce, NE filtr. Survivorship: "
                           "losery=prezivsi klesajici akcie. Nominalni cena "
                           "obvykle neni prima pricina rizika.")}
    _write(payload, mrl, args.out)

    print(f"\n==== MLE-DIAG-01 (regime200 hold10, {len(trades)} trades) ====")
    print(f"\nLOSERS (bottom 20%): avg_ret {losers_sum['avg_net_ret']}%")
    print(f"  entry_price: mean {losers_sum['entry_price_mean']} median {losers_sum['entry_price_median']}")
    print(f"  vol_20d mean: {losers_sum['vol_20d_mean']}")
    print(f"  mom_rank mean: {losers_sum['mom_rank_mean']}")
    print(f"  hist_days: mean {losers_sum['hist_days_mean']} median {losers_sum['hist_days_median']}")
    print(f"  top sectors: {losers_sum['top_sectors']}")
    print(f"\nWINNERS (top 20%): avg_ret {winners_sum['avg_net_ret']}%")
    print(f"  entry_price: mean {winners_sum['entry_price_mean']} median {winners_sum['entry_price_median']}")
    print(f"  vol_20d mean: {winners_sum['vol_20d_mean']}")
    print(f"  mom_rank mean: {winners_sum['mom_rank_mean']}")
    print(f"  hist_days: mean {winners_sum['hist_days_mean']} median {winners_sum['hist_days_median']}")
    print(f"  top sectors: {winners_sum['top_sectors']}")
    print(f"\nKORELACE s net_ret (Pearson/Spearman):")
    for f, c in correlations.items():
        print(f"  {f}: {c}")
    if price_bins:
        print(f"\nCENOVE KVINTILY (test 'mensi cena'):")
        for b in price_bins:
            print(f"  Q{b['quintile']} cena {b['price_range']}: avg_ret {b['avg_net_ret']}% wr {b['win_rate']}")
    return 0


def _write(payload, mrl, out):
    out_dir = Path(out) if out else mrl / "reports" / "backtests"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "MLE-DIAG-01_loser_characteristics.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8")
    L = ["# MLE-DIAG-01 — Loser Characteristics (DIAGNOSTIC EDA)", "",
         f"## WARNING", "", payload["WARNING"], "",
         f"Varianta: {payload['variant']}, trades: {payload['n_trades']}",
         f"Sim: {payload['sim'][0]}..{payload['sim'][1]}", "",
         "## Losers vs Winners", "",
         "| metrika | losers (bottom 20%) | winners (top 20%) |",
         "|---|---|---|"]
    ls, ws = payload["losers"], payload["winners"]
    for k, lab in [("avg_net_ret", "avg net return %"),
                   ("entry_price_mean", "entry price mean"),
                   ("entry_price_median", "entry price median"),
                   ("vol_20d_mean", "volatilita 20D mean %"),
                   ("mom_rank_mean", "momentum rank mean"),
                   ("hist_days_mean", "historie dni mean"),
                   ("hist_days_median", "historie dni median")]:
        L.append(f"| {lab} | {ls.get(k)} | {ws.get(k)} |")
    L += ["", f"- losers top sectors: {ls['top_sectors']}",
          f"- winners top sectors: {ws['top_sectors']}",
          f"- losers top industries: {ls['top_industries']}",
          f"- winners top industries: {ws['top_industries']}", "",
          "### 10 nejvetsich loseru (ticker, net%, entry_price, vol20d, hist_days)", ""]
    for e in ls["worst_examples"]:
        L.append(f"- {e}")
    L += ["", "## Korelace s net_ret", "",
          "| feature | Pearson | Spearman | n |", "|---|---|---|---|"]
    for f, c in payload["correlations_with_net_ret"].items():
        if c:
            L.append(f"| {f} | {c['pearson']} | {c['spearman']} | {c['n']} |")
    L += ["", "- Pearson/Spearman blizko 0 = zadny vztah.",
          "- zaporny = vyssi hodnota -> nizsi return.",
          "- kladny = vyssi hodnota -> vyssi return.", "",
          "## Cenove kvintily (test hypotezy 'mensi cena = loser')", ""]
    if payload["price_quintiles"]:
        L.append("| kvintil | cenove pasmo | avg net% | win_rate | n |")
        L.append("|---|---|---|---|---|")
        for b in payload["price_quintiles"]:
            L.append(f"| Q{b['quintile']} | {b['price_range']} | {b['avg_net_ret']} | "
                     f"{b['win_rate']} | {b['n']} |")
        L += ["", "- Q1 = nejlevnejsi akcie, Q5 = nejdrazsi.",
              "- pokud Q1 avg_ret << Q5 -> nizka cena koreluje s horsim vysledkem.",
              "- pokud podobne -> nominalni cena NENI faktor (mytus)."]
    L += ["", "## Interpretace", "",
          "- pokud losery maji vyssi VOLATILITU (ne nizsi cenu) -> skutecny",
          "  faktor je volatilita, ne cena.",
          "- pokud losery maji kratsi HISTORII -> recent IPO riziko (SNDK-like).",
          "- pokud zadny rozdil -> losery nemaji spolecny viditelny rys",
          "  (jsou to jen nahodne propady momentum akcii).", "",
          "## Vyhrady", "",
          "- **IN-SAMPLE deskripce, NE hotovy filtr. Overfit riziko pri",
          "  stavbe filtru z techto nalezu.**",
          "- SURVIVORSHIP: losery = prezivsi klesajici akcie.",
          "- nominalni cena obvykle neni prima pricina (mytus); vol/velikost je.",
          "- diagnostic only.", ""]
    (out_dir / "MLE-DIAG-01_loser_characteristics.md").write_text(
        "\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
