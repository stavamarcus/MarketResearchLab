"""
ExitTimingEdge_v1 — validace EXIT komponenty (trade-level, bez portfolia).

Research Project: RP-0011-EXIT-TIMING
Class:            exit-edge (první experiment třídy Exit Validation)

Otázka:
    Realizuje dynamický exit (close < EMA20, fill next open) větší část
    validovaného MLE×IRC selection edge UVNITŘ fixního 20D okna než
    baseline fixed 20D hold?

═══════════════════════════════════════════════════════════════════════
PRE-REGISTROVANÉ PARAMETRY — ZAMČENO 2026-07-02 (PM approval).
Neupravovat podle výsledku.
═══════════════════════════════════════════════════════════════════════

Hypotéza H1a (PRIMÁRNÍ, jediné rozhodovací kritérium):
    EMA20 exit vs TIME_20 baseline; matched comparison, stejní kandidáti,
    stejné fixní okno D→D+20, po exitu cash 0 %. Paired diff, ticker-
    clustered bootstrap (B=10000, seed=42). PASS ⇔ 95% CI celé > 0.

Sensitivity (NE hypotézy): EMA10, EMA30 — pouze robustnost směru.
H1b (EXPLORATORNÍ, bez rozhodovacího kritéria): uncapped EMA20 exit
    s time-stop 60D; return/den; cenzorované vyloučeny a reportovány.

Metodické zámky:
    - entry = close(D) (konzistence s RP-0009 baseline / STR-0001)
    - MIN_FUTURE_DAYS = 22 (D+20 close + fill open(D+20) pro signál D+19)
    - EMA: alpha=2/(n+1), SMA seed, warmup >= 3× perioda barů PŘED entry
      z price provideru; kandidát bez warmupu vyřazen ze VŠECH variant
      i baseline (matched set) — počet reportován
    - signal na close, fill next open (engine); baseline TIME_20 fill
      close(D+20) dle definice close-to-close
    - CACHE_ONLY; žádný window sweep; regime split DEFERRED
    - baseline i varianty běží IDENTICKÝM enginem (žádná impl. asymetrie)

Předpoklady / edge cases:
    - candidate-day = jednotka pozorování; překryvy 20D oken + opakované
      tickery → clustered bootstrap, dependence warning (viz RP-0009).
    - Baseline close look-ahead: entry na close signálního dne —
      konzistentní caveat s RP-0009 (obě větve páru sdílí entry → paired
      diff jím není zkreslen).
    - Ticker-lokální bar série (halty → chybějící bary): okno definováno
      lokálními bary; kandidát s chybějícím close(D)/close(D+20) vyřazen.
    - EMA whipsaw: signál na close < EMA a gap-down open fill →
      realizovaný exit horší než signální close. Záměrně (realismus).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult
from src.query.research_query import ResearchQuery

from experiments.exit_validation.exit_engine import simulate_trade
from experiments.exit_validation.exit_rules import EMAExit, TimeExit

# ── PRE-REGISTERED (locked 2026-07-02) ──────────────────────────────────
MLE_TOP          = 10
IRC_TOP          = 10
IRC_LOOKBACK     = 20
HOLD_DAYS        = 20          # fixní comparison window D→D+20
MIN_FUTURE_DAYS  = 22

PRIMARY_EMA      = 20          # H1a — jediné rozhodovací kritérium
SENSITIVITY_EMAS = (10, 30)    # NE hypotézy

H1B_TIME_STOP    = 60          # exploratorní: uncapped + time-stop
H1B_MIN_FUTURE   = 62

BOOTSTRAP_B      = 10_000
BOOTSTRAP_SEED   = 42          # fixní → reprodukovatelný result_hash
MIN_OBSERVATIONS = 100
# ────────────────────────────────────────────────────────────────────────

LOCKED_PARAMS = {
    "mle_top": MLE_TOP, "irc_top": IRC_TOP, "irc_lookback": IRC_LOOKBACK,
    "hold_days": HOLD_DAYS, "min_future_days": MIN_FUTURE_DAYS,
    "primary_ema": PRIMARY_EMA, "sensitivity_emas": list(SENSITIVITY_EMAS),
    "h1b_time_stop": H1B_TIME_STOP, "h1b_min_future": H1B_MIN_FUTURE,
    "bootstrap_b": BOOTSTRAP_B, "bootstrap_seed": BOOTSTRAP_SEED,
    "min_observations": MIN_OBSERVATIONS,
    "entry": "close(D)", "ema_seed": "SMA", "ema_alpha": "2/(n+1)",
    "warmup_mult": 3,
}


class ExitTimingEdge_v1(BaseExperiment):

    # ---------------- define ----------------
    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="ExitTimingEdge",
            version="1.0.0",
            hypothesis=(
                "H1a: EMA20 exit (signal close<EMA20, fill next open) zvyšuje "
                "mean return uvnitř fixního 20D okna proti fixed 20D hold, "
                "nad MLE×IRC kandidáty — matched comparison, po exitu cash 0 %."
            ),
            description=(
                "Exit-edge validace (první experiment třídy). Baseline TIME_20 "
                "a EMA varianty přes identický exit_engine. Primární: EMA20 "
                "paired diff + clustered bootstrap. EMA10/30 sensitivity. "
                "H1b uncapped/60D time-stop exploratorně. Regime split deferred."
            ),
            required_data=["prices", "feature:MLE_Rank_10d", "signal:IRC"],
            parameters=dict(LOCKED_PARAMS),
            tags=["exit-edge", "matched-comparison", "ema", "pre-registered"],
            author="MRL RP-0011 session (PM approved 2026-07-02)",
        )

    # ---------------- validate ----------------
    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle = context.features.all_for_name("MLE_Rank_10d")
        if len(mle) < MIN_OBSERVATIONS:
            return ValidationResult.failed(f"Málo MLE_Rank_10d: {len(mle)}")
        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed("IRC chybí v context.signals.")
        if not context.prices:
            return ValidationResult.failed("Prázdné context.prices.")
        sample = next(iter(context.prices.values()))
        for col in ("open", "close"):
            if col not in sample.columns:
                return ValidationResult.failed(
                    f"Price frame postrádá sloupec '{col}' (nutný pro exit fill)."
                )
        return ValidationResult.ok()

    # ---------------- run ----------------
    def run(self, context: ExperimentContext) -> ExperimentResult:
        query = ResearchQuery(context)

        irc = context.signals["IRC"].copy()
        irc = irc[irc["lookback"] == IRC_LOOKBACK]
        irc["date"] = pd.to_datetime(irc["date"])
        irc_index = irc.set_index(["date", "industry"])["rank"].to_dict()

        trading_days = query.dates()
        if not trading_days:
            return ExperimentResult(metrics={"error": "no_trading_days"},
                                    summary="Žádné obchodní dny.")
        day_pos = {pd.Timestamp(d): i for i, d in enumerate(trading_days)}
        n_days = len(trading_days)

        # ── ticker-lokální bar cache: (dates_index, opens, closes) ──
        bar_cache: dict[int, tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]] = {}

        def bars(conid: int):
            b = bar_cache.get(conid)
            if b is None:
                df = context.prices.get(conid)
                if df is None or df.empty:
                    b = (pd.DatetimeIndex([]), np.empty(0), np.empty(0))
                else:
                    b = (df.index,
                         df["open"].to_numpy(dtype=float),
                         df["close"].to_numpy(dtype=float))
                bar_cache[conid] = b
            return b

        variants = [TimeExit(HOLD_DAYS), EMAExit(PRIMARY_EMA)] + \
                   [EMAExit(p) for p in SENSITIVITY_EMAS]
        baseline_name = variants[0].name          # TIME_20
        primary_name = variants[1].name           # EMA_20
        max_warmup = max(v.min_history() for v in variants)  # 90 barů (EMA30)

        # ── sestav trades (common completable + common computable subset) ──
        rows: list[dict] = []
        excl_warmup = 0
        excl_price = 0
        h1b_rows: list[dict] = []
        h1b_censored = 0
        h1b_rule = EMAExit(PRIMARY_EMA)

        for d in trading_days:
            ts = pd.Timestamp(d)
            sig_pos = day_pos[ts]
            if sig_pos + MIN_FUTURE_DAYS >= n_days:
                continue  # completable subset (globální kalendář)
            snaps = [
                s for s in query.assets(date=d)
                if s.mle_rank_10d is not None and s.mle_rank_10d <= MLE_TOP
            ]
            for s in snaps:
                irc_rank = irc_index.get((ts, s.industry))
                if irc_rank is None or irc_rank > IRC_TOP:
                    continue  # industry headwind → není kandidát

                idx, opens, closes = bars(s.conid)
                loc = idx.get_indexer([ts])[0]
                if loc < 0:
                    excl_price += 1
                    continue
                entry_pos = int(loc)
                window_end = entry_pos + HOLD_DAYS
                if window_end >= len(idx):
                    excl_price += 1
                    continue
                seg = closes[entry_pos:window_end + 1]
                if not np.all(np.isfinite(seg)) or seg[0] <= 0:
                    excl_price += 1
                    continue
                # společný warmup pro VŠECHNY varianty → identický matched set
                if entry_pos < max_warmup:
                    excl_warmup += 1
                    continue

                rec: dict = {"date": ts, "ticker": s.ticker, "conid": s.conid}
                ok = True
                for rule in variants:
                    rule.prepare(closes)
                    out = simulate_trade(rule, entry_pos, window_end,
                                         opens, closes)
                    if out is None:
                        ok = False
                        break
                    v = rule.name
                    rec[f"ret_{v}"] = out.ret
                    rec[f"hold_{v}"] = out.hold_days
                    rec[f"early_{v}"] = out.exited_early
                    rec[f"gap_{v}"] = out.fill_gap
                    rec[f"gapunres_{v}"] = out.fill_gap_unresolved
                    if out.exited_early and rule.fill.name == "NEXT_OPEN":
                        # zbytek okna podkladu po exitu (avoided/missed)
                        rem = closes[window_end] / (
                            opens[out.exit_pos]
                            if np.isfinite(opens[out.exit_pos]) and opens[out.exit_pos] > 0
                            else closes[out.exit_pos]
                        ) - 1.0
                        rec[f"rem_{v}"] = float(rem)
                if not ok:
                    excl_price += 1
                    continue
                rows.append(rec)

                # ── H1b exploratorní (uncapped, time-stop 60D) ──
                if (sig_pos + H1B_MIN_FUTURE < n_days
                        and entry_pos + H1B_TIME_STOP < len(idx)):
                    seg60 = closes[entry_pos:entry_pos + H1B_TIME_STOP + 1]
                    if np.all(np.isfinite(seg60)):
                        h1b_rule.prepare(closes)
                        out = simulate_trade(h1b_rule, entry_pos,
                                             entry_pos + H1B_TIME_STOP,
                                             opens, closes)
                        if out is not None:
                            h1b_rows.append({
                                "date": ts, "ticker": s.ticker,
                                "ret": out.ret, "hold": out.hold_days,
                                "timestop": out.signal_pos is None,
                            })
                    else:
                        h1b_censored += 1
                else:
                    h1b_censored += 1

        if not rows:
            return ExperimentResult(metrics={"error": "no_records"},
                                    summary="Žádné candidate-days.")

        df = pd.DataFrame(rows)
        N = len(df)
        uniq = df["ticker"].nunique()
        rng = np.random.default_rng(BOOTSTRAP_SEED)

        # ── clustered bootstrap paired diff (varianta − baseline) ──
        def clustered_ci(col_v: str):
            diffs = (df[col_v] - df[f"ret_{baseline_name}"]).to_numpy()
            by: dict[str, list] = {}
            for tk, dv in zip(df["ticker"].to_numpy(), diffs):
                by.setdefault(tk, []).append(dv)
            arrays = {k: np.asarray(v) for k, v in by.items()}
            keys = list(arrays.keys())
            means = np.empty(BOOTSTRAP_B)
            for i in range(BOOTSTRAP_B):
                pick = rng.choice(keys, size=len(keys), replace=True)
                means[i] = np.concatenate([arrays[k] for k in pick]).mean()
            lo, hi = np.percentile(means, [2.5, 97.5])
            return float(diffs.mean()), float(lo), float(hi)

        def stats(col: str):
            s = df[col]
            w = s[s > 0]
            l = s[s <= 0]
            return {
                "mean_pct": round(s.mean() * 100, 3),
                "median_pct": round(s.median() * 100, 3),
                "win_pct": round(100.0 * (s > 0).mean(), 2),
                "avg_winner_pct": round(w.mean() * 100, 3) if len(w) else None,
                "avg_loser_pct": round(l.mean() * 100, 3) if len(l) else None,
                "expectancy_pct": round(s.mean() * 100, 3),
            }

        metrics: dict = {
            "N_candidate_days": N,
            "unique_tickers": uniq,
            "excluded_warmup": excl_warmup,
            "excluded_price_data": excl_price,
            "common_warmup_bars": int(max_warmup),
        }

        variant_rows = []
        for rule in variants:
            v = rule.name
            st = stats(f"ret_{v}")
            early = df[f"early_{v}"].mean() * 100 if f"early_{v}" in df else 0.0
            hold = df[f"hold_{v}"].mean()
            row = {"variant": v, "N": N, **st,
                   "early_exit_pct": round(float(early), 2),
                   "hold_mean_d": round(float(hold), 2)}
            if v != baseline_name:
                a, lo, hi = clustered_ci(f"ret_{v}")
                row.update({
                    "paired_diff_pp": round(a * 100, 3),
                    "ci_lo_pp": round(lo * 100, 3),
                    "ci_hi_pp": round(hi * 100, 3),
                    "significant": bool(lo > 0 or hi < 0),
                })
                # avoided losers / missed winners (jen realizované early exity)
                if f"rem_{v}" in df.columns:
                    rem = df[f"rem_{v}"].dropna()
                    row["avoided_losers"] = int((rem < 0).sum())
                    row["missed_winners"] = int((rem > 0).sum())
                    row["missed_winner_mean_pct"] = (
                        round(rem[rem > 0].mean() * 100, 2)
                        if (rem > 0).any() else None)
                    row["avoided_loser_mean_pct"] = (
                        round(rem[rem < 0].mean() * 100, 2)
                        if (rem < 0).any() else None)
                row["fill_gap_n"] = int(df[f"gap_{v}"].sum())
                row["fill_gap_unresolved_n"] = int(df[f"gapunres_{v}"].sum())
            variant_rows.append(row)

        per_variant = pd.DataFrame(variant_rows)

        # ── H1a rozhodnutí (POUZE EMA20) ──
        prim = per_variant[per_variant["variant"] == primary_name].iloc[0]
        h1a_pass = bool(prim["ci_lo_pp"] > 0)
        metrics.update({
            "H1a_paired_diff_pp": float(prim["paired_diff_pp"]),
            "H1a_ci_lo_pp": float(prim["ci_lo_pp"]),
            "H1a_ci_hi_pp": float(prim["ci_hi_pp"]),
            "H1a_pass": h1a_pass,
            "baseline_mean_pct": float(per_variant[
                per_variant["variant"] == baseline_name]["mean_pct"].iloc[0]),
        })
        for _, r in per_variant.iterrows():
            if r["variant"] == baseline_name:
                continue
            p = r["variant"].lower()
            metrics[f"{p}_paired_diff_pp"] = float(r["paired_diff_pp"])
            metrics[f"{p}_early_exit_pct"] = float(r["early_exit_pct"])
            metrics[f"{p}_hold_mean_d"] = float(r["hold_mean_d"])

        # ── H1b deskriptivní ──
        tables = {"per_variant": per_variant, "trades": df}
        if h1b_rows:
            hdf = pd.DataFrame(h1b_rows)
            metrics.update({
                "H1b_N": len(hdf),
                "H1b_censored_excluded": h1b_censored,
                "H1b_ret_mean_pct": round(hdf["ret"].mean() * 100, 3),
                "H1b_ret_per_day_bps": round(
                    (hdf["ret"] / hdf["hold"]).mean() * 10_000, 2),
                "H1b_hold_mean_d": round(hdf["hold"].mean(), 2),
                "H1b_hold_median_d": round(hdf["hold"].median(), 1),
                "H1b_timestop_pct": round(hdf["timestop"].mean() * 100, 2),
            })
            tables["h1b_trades"] = hdf
        else:
            metrics["H1b_N"] = 0
            metrics["H1b_censored_excluded"] = h1b_censored

        # ── warnings / caveats ──
        eff = uniq / N if N else 0
        dep_warn = (
            f"DEPENDENCE WARNING: nominal N={N} candidate-days, {uniq} unikátních "
            f"tickerů (poměr {eff:.2f}). Efektivní N << nominal N (překrývající se "
            f"okna). Signifikance výhradně ticker-clustered bootstrap."
        )
        regime_note = (
            "REGIME SPLIT DEFERRED: exit pravidla jsou režimově citlivější než "
            "selection (EMA exit systematicky vyhrává v choppy/klesajícím trhu, "
            "prohrává v trendu). Výsledek vázán na období běhu. Re-run po Regime Engine."
        )
        caveats = (
            "CAVEATS: (1) Entry close(D) look-ahead — sdílený oběma větvemi páru, "
            "paired diff nezkresluje. (2) Sensitivity EMA10/30 NEJSOU hypotézy — "
            "žádný a-posteriori výběr periody. (3) H1b čistě deskriptivní. "
            "(4) Fixed-window design: exit realokuje kapitál do cash 0 % — "
            "reinvestiční hodnota uvolněného kapitálu patří do MSL STR-0002, ne sem."
        )

        summary = self._summary(metrics, per_variant, primary_name,
                                dep_warn, regime_note, caveats)
        return ExperimentResult(metrics=metrics, tables=tables, summary=summary)

    @staticmethod
    def _summary(m, pv, primary, dep_warn, regime_note, caveats) -> str:
        verdict = ("H1a PASS — EMA20 exit zvyšuje return ve fixním 20D okně"
                   if m["H1a_pass"] else
                   "H1a NOT SUPPORTED — EMA20 exit nezlepšuje fixní 20D okno")
        sens = "; ".join(
            f"{r['variant']}: {r['paired_diff_pp']}pp"
            for _, r in pv.iterrows() if r["variant"] not in ("TIME_20",)
        )
        return (
            f"{verdict}. Primární paired diff {m['H1a_paired_diff_pp']}pp "
            f"CI[{m['H1a_ci_lo_pp']}, {m['H1a_ci_hi_pp']}] "
            f"(baseline mean {m['baseline_mean_pct']}%). "
            f"Sensitivity: {sens}. "
            f"H1b (exploratorní): N={m.get('H1b_N')}, "
            f"ret/den {m.get('H1b_ret_per_day_bps')}bps, "
            f"hold mean {m.get('H1b_hold_mean_d')}d, "
            f"time-stop {m.get('H1b_timestop_pct')}%. "
            f"{dep_warn} {regime_note} {caveats}"
        )
