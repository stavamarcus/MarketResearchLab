"""
EntryTimingEdge_v1 — validace ENTRY komponenty (forward-return, bez portfolia).

Research Project: RP-0009-ENTRY-TIMING
Class:            entry-edge (NE selection-edge)

Otázka:
    Přidává ZPŮSOB VSTUPU (čekání na cenový pullback) inkrementální
    forward-return edge nad baseline "buy at close v den signálu",
    nad identickou množinou kandidátů MLE×IRC?

Varianty (nad stejnou množinou kandidátů, bez portfolio capu / cash / kolizí):
    ENTRY_001  baseline   — buy close v den signálu,          hold 20D
    ENTRY_002  1 pullback — první den close < prev close       (max wait 5),  hold 20D
    ENTRY_003  2 pullbacks— dva PO SOBĚ jdoucí poklesové dny    (max wait 7),  hold 20D
               (flat den close == prev přerušuje sekvenci)

═══════════════════════════════════════════════════════════════════════
PRE-REGISTROVANÉ PARAMETRY — ZAMČENO a priori (2026-06-30).
Neupravovat podle výsledku. X sweep je samostatný budoucí experiment.
═══════════════════════════════════════════════════════════════════════

Metodické zámky (odsouhlaseno):
    1. Matched comparison POVINNĚ — každá varianta vs ENTRY_001 na SVÉ
       matched množině (S2, S3). Přímé 002 vs 003 jen na průniku S2∩S3.
    2. Opportunity cost = RETURN přeskočených kandidátů (ne počet).
    3. Oddělit: (A) matched entry alpha  (B) strategy-level net effect.
    4. Signifikance = ticker-clustered bootstrap (resample tickerů, ne
       candidate-days). Report nominal N, unique tickers, CI, dependence warning.
    5. Truncation → common completable subset: signal day musí mít
       >= MIN_FUTURE_DAYS budoucích obchodních dní (7 wait + 20 hold = 27).
    6. Regime split DEFERRED — chybí schválené režimové štítky.

Forward return = close[entry+HOLD] / close[entry] - 1  (close-to-close).
Baseline pro alpha = ENTRY_001 (NE SPY).

Předpoklady / edge cases:
    - candidate-day je jednotka pozorování (ticker může být kandidát mnoho
      dní po sobě → korelace → viz dependence warning + clustered bootstrap).
    - Baseline close look-ahead: ENTRY_001 vstupuje na close, z něhož je
      signál počítán. Konzistentní s předchozími MRL/MLE audity — reportováno
      jako caveat. ENTRY_002/003 tím netrpí (vstup je pozdější).
    - ticker→industry z asset snapshotů (context/universe = IBKR taxonomy),
      shodné s MLE×IRC selection joinem.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult
from src.query.research_query import ResearchQuery

# ── PRE-REGISTERED (locked) ─────────────────────────────────────────────
MLE_TOP          = 10
IRC_TOP          = 10
IRC_LOOKBACK     = 20
HOLD_DAYS        = 20

WAIT_002         = 5
WAIT_003         = 7
MIN_FUTURE_DAYS  = 27          # = WAIT_003 + HOLD_DAYS → common completable subset

BOOTSTRAP_B      = 2000
BOOTSTRAP_SEED   = 42          # fixní → reprodukovatelný result_hash
MIN_OBSERVATIONS = 100
# ────────────────────────────────────────────────────────────────────────


class EntryTimingEdge_v1(BaseExperiment):

    # ---------------- define ----------------
    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="EntryTimingEdge",
            version="1.0.0",
            hypothesis=(
                "Čekání na cenový pullback (ENTRY_002 / ENTRY_003) přidává "
                "inkrementální forward-return edge nad baseline close-entry "
                "(ENTRY_001) nad množinou MLE×IRC kandidátů — měřeno matched "
                "i strategy-level, s opportunity cost přeskočených obchodů."
            ),
            description=(
                "Entry-edge validace. 3 varianty vstupu nad identickou množinou "
                "MLE TOP10 × IRC TOP10 kandidátů, forward returns bez portfolia. "
                "Matched alpha (clustered bootstrap) + strategy-level net + "
                "skipped return. Regime split deferred."
            ),
            required_data=["prices", "feature:MLE_Rank_10d", "signal:IRC"],
            parameters={
                "mle_top": MLE_TOP, "irc_top": IRC_TOP, "irc_lookback": IRC_LOOKBACK,
                "hold_days": HOLD_DAYS, "wait_002": WAIT_002, "wait_003": WAIT_003,
                "min_future_days": MIN_FUTURE_DAYS, "bootstrap_b": BOOTSTRAP_B,
                "bootstrap_seed": BOOTSTRAP_SEED, "min_observations": MIN_OBSERVATIONS,
            },
            tags=["entry-edge", "forward-return", "pullback", "pre-registered"],
            author="MSL/MRL architecture session",
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
            return ExperimentResult(metrics={"error": "no_trading_days"}, summary="Žádné obchodní dny.")
        day_pos = {pd.Timestamp(d): i for i, d in enumerate(trading_days)}
        n_days = len(trading_days)

        # cache close sérií
        close_cache: dict[int, pd.Series] = {}

        def close_at(conid: int, pos: int):
            if pos < 0 or pos >= n_days:
                return None
            cs = close_cache.get(conid)
            if cs is None:
                df = context.prices.get(conid)
                if df is None or df.empty:
                    close_cache[conid] = pd.Series(dtype=float)
                    return None
                cs = df["close"]
                close_cache[conid] = cs
            ts = pd.Timestamp(trading_days[pos])
            return float(cs.loc[ts]) if ts in cs.index else None

        def fwd_ret(conid: int, entry_pos: int):
            e = close_at(conid, entry_pos)
            x = close_at(conid, entry_pos + HOLD_DAYS)
            if e is None or x is None or e <= 0:
                return None
            return x / e - 1.0

        def first_pullback(conid: int, sig_pos: int, wait: int):
            for k in range(1, wait + 1):
                a, b = close_at(conid, sig_pos + k), close_at(conid, sig_pos + k - 1)
                if a is not None and b is not None and a < b:
                    return sig_pos + k
            return None

        def first_two_pullbacks(conid: int, sig_pos: int, wait: int):
            # dva PO SOBĚ jdoucí poklesové dny; flat (==) přerušuje
            for k in range(1, wait):
                d1a, d1b = close_at(conid, sig_pos + k), close_at(conid, sig_pos + k - 1)
                d2a = close_at(conid, sig_pos + k + 1)
                if None in (d1a, d1b, d2a):
                    continue
                if d1a < d1b and d2a < d1a:
                    return sig_pos + k + 1
            return None

        # ── sestav candidate-days (common completable subset) ──
        rows = []
        for d in trading_days:
            ts = pd.Timestamp(d)
            sig_pos = day_pos[ts]
            if sig_pos + MIN_FUTURE_DAYS >= n_days:
                continue  # completable subset
            snaps = [
                s for s in query.assets(date=d)
                if s.mle_rank_10d is not None and s.mle_rank_10d <= MLE_TOP
            ]
            for s in snaps:
                irc_rank = irc_index.get((ts, s.industry))
                if irc_rank is None or irc_rank > IRC_TOP:
                    continue  # industry headwind → není kandidát
                r1 = fwd_ret(s.conid, sig_pos)
                if r1 is None:
                    continue
                e2 = first_pullback(s.conid, sig_pos, WAIT_002)
                e3 = first_two_pullbacks(s.conid, sig_pos, WAIT_003)
                rows.append({
                    "date": ts, "ticker": s.ticker, "conid": s.conid,
                    "r1": r1,
                    "r2": fwd_ret(s.conid, e2) if e2 is not None else None,
                    "delay2": (e2 - sig_pos) if e2 is not None else None,
                    "r3": fwd_ret(s.conid, e3) if e3 is not None else None,
                    "delay3": (e3 - sig_pos) if e3 is not None else None,
                })

        if not rows:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Žádné candidate-days.")

        df = pd.DataFrame(rows).dropna(subset=["r1"])
        N = len(df)
        uniq = df["ticker"].nunique()
        S2 = df[df["r2"].notna()]
        S3 = df[df["r3"].notna()]
        K2 = df[df["r2"].isna()]
        K3 = df[df["r3"].isna()]

        rng = np.random.default_rng(BOOTSTRAP_SEED)

        def clustered_bootstrap(sub: pd.DataFrame, col_v: str):
            diffs = (sub[col_v] - sub["r1"]).values
            by: dict[str, list] = {}
            for tk, dv in zip(sub["ticker"].values, diffs):
                by.setdefault(tk, []).append(dv)
            keys = list(by.keys())
            means = np.empty(BOOTSTRAP_B)
            for i in range(BOOTSTRAP_B):
                pick = rng.choice(keys, size=len(keys), replace=True)
                means[i] = np.concatenate([by[k] for k in pick]).mean()
            lo, hi = np.percentile(means, [2.5, 97.5])
            return float(diffs.mean()), float(lo), float(hi)

        def wr(s):
            return round(100.0 * (s > 0).mean(), 2) if len(s) else None

        def pf(s):
            g = s[s > 0].sum(); l = -s[s < 0].sum()
            return round(float(g / l), 3) if l > 0 else None

        # ── matched entry alpha ──
        a2, lo2, hi2 = clustered_bootstrap(S2, "r2")
        a3, lo3, hi3 = clustered_bootstrap(S3, "r3")
        sig2 = not (lo2 <= 0 <= hi2)
        sig3 = not (lo3 <= 0 <= hi3)

        # ── direct 002 vs 003 na průniku S2∩S3 ──
        inter = df[df["r2"].notna() & df["r3"].notna()]
        d23 = float((inter["r3"] - inter["r2"]).mean()) if len(inter) else None

        # ── strategy-level net (mean per candidate-day přes VŠECHNY N; skipped = 0/cash) ──
        base_all = float(df["r1"].mean())
        strat2 = float(S2["r2"].sum() / N)
        strat3 = float(S3["r3"].sum() / N)

        metrics = {
            "N_candidate_days": N,
            "unique_tickers": uniq,
            "S2_filled": len(S2), "K2_skipped": len(K2), "fill_002_pct": round(100 * len(S2) / N, 1),
            "S3_filled": len(S3), "K3_skipped": len(K3), "fill_003_pct": round(100 * len(S3) / N, 1),

            "entry_alpha_002_pp": round(a2 * 100, 3),
            "entry_alpha_002_ci_lo": round(lo2 * 100, 3),
            "entry_alpha_002_ci_hi": round(hi2 * 100, 3),
            "entry_alpha_002_significant": sig2,
            "entry_alpha_003_pp": round(a3 * 100, 3),
            "entry_alpha_003_ci_lo": round(lo3 * 100, 3),
            "entry_alpha_003_ci_hi": round(hi3 * 100, 3),
            "entry_alpha_003_significant": sig3,
            "direct_003_minus_002_pp_on_intersection": round(d23 * 100, 3) if d23 is not None else None,
            "intersection_N": len(inter),

            "strategy_net_baseline_pct": round(base_all * 100, 3),
            "strategy_net_002_pct": round(strat2 * 100, 3),
            "strategy_net_002_delta_pp": round((strat2 - base_all) * 100, 3),
            "strategy_net_003_pct": round(strat3 * 100, 3),
            "strategy_net_003_delta_pp": round((strat3 - base_all) * 100, 3),

            "skipped_K2_baseline_ret_mean_pct": round(K2["r1"].mean() * 100, 2) if len(K2) else None,
            "entered_S2_baseline_ret_mean_pct": round(S2["r1"].mean() * 100, 2),
            "skipped_K3_baseline_ret_mean_pct": round(K3["r1"].mean() * 100, 2) if len(K3) else None,
            "entered_S3_baseline_ret_mean_pct": round(S3["r1"].mean() * 100, 2),

            "win_001_pct": wr(df["r1"]), "win_002_pct": wr(S2["r2"]), "win_003_pct": wr(S3["r3"]),
            "median_001_pct": round(df["r1"].median() * 100, 3),
            "median_002_pct": round(S2["r2"].median() * 100, 3),
            "median_003_pct": round(S3["r3"].median() * 100, 3),
            "pf_001": pf(df["r1"]), "pf_002": pf(S2["r2"]), "pf_003": pf(S3["r3"]),
            "entry_delay_002_days": round(S2["delay2"].mean(), 2),
            "entry_delay_003_days": round(S3["delay3"].mean(), 2),
        }

        tables = {
            "per_variant": pd.DataFrame([
                {"variant": "ENTRY_001", "N": N, "mean_ret_pct": round(df["r1"].mean() * 100, 2),
                 "median_pct": metrics["median_001_pct"], "win_pct": metrics["win_001_pct"],
                 "pf": metrics["pf_001"], "entry_alpha_pp": 0.0, "delay_d": 0.0},
                {"variant": "ENTRY_002", "N": len(S2), "mean_ret_pct": round(S2["r2"].mean() * 100, 2),
                 "median_pct": metrics["median_002_pct"], "win_pct": metrics["win_002_pct"],
                 "pf": metrics["pf_002"], "entry_alpha_pp": metrics["entry_alpha_002_pp"],
                 "delay_d": metrics["entry_delay_002_days"]},
                {"variant": "ENTRY_003", "N": len(S3), "mean_ret_pct": round(S3["r3"].mean() * 100, 2),
                 "median_pct": metrics["median_003_pct"], "win_pct": metrics["win_003_pct"],
                 "pf": metrics["pf_003"], "entry_alpha_pp": metrics["entry_alpha_003_pp"],
                 "delay_d": metrics["entry_delay_003_days"]},
            ]),
        }

        # ── dependence warning ──
        eff_ratio = uniq / N if N else 0
        dep_warn = (
            f"DEPENDENCE WARNING: nominal N={N} candidate-days, ale jen {uniq} unikátních "
            f"tickerů (poměr {eff_ratio:.2f}). Efektivní N << nominal N (překrývající se 20D "
            f"okna + opakovaný výskyt tickeru). Signifikance výhradně z ticker-clustered "
            f"bootstrapu (resample tickerů). Naivní t-test/win-rate NEPOUŽÍVAT."
        )
        regime_note = (
            "REGIME SPLIT DEFERRED: chybí schválené režimové štítky. "
            "Až vznikne schválený Regime Engine / režimové štítky, entry-edge je nutné "
            "stratifikovat (pullback edge je režimově citlivý — v silném trendu míjí movery, "
            "v choppy/mean-reverting režimu se verdikt může obrátit). Tento výsledek je "
            "vázaný na období běhu (pravděpodobně jeden režim)."
        )
        caveats = (
            "CAVEATS: (1) Baseline close look-ahead — ENTRY_001 vstup na close signálu "
            "(konzistentní s předchozími MRL audity, mírně nadhodnocuje baseline). "
            "(2) Jedno běhové období, regime deferred. (3) matched entry alpha a strategy-level "
            "net mohou protiřečit — obojí reportováno odděleně; strategy-level zahrnuje "
            "opportunity cost přeskočených jako 0/cash."
        )

        summary = self._summary(metrics, dep_warn, regime_note, caveats)
        return ExperimentResult(metrics=metrics, tables=tables, summary=summary)

    @staticmethod
    def _summary(m, dep_warn, regime_note, caveats) -> str:
        def verdict(alpha_sig, delta):
            if not alpha_sig and delta < 0:
                return "žádný entry edge + strategy-level horší"
            if alpha_sig and delta < 0:
                return "conditional entry alpha ANO, ale strategy-level HORŠÍ (míjí movery)"
            if alpha_sig and delta >= 0:
                return "entry edge potvrzen (alpha i strategy-level)"
            return "smíšené"
        return (
            f"ENTRY_002: {verdict(m['entry_alpha_002_significant'], m['strategy_net_002_delta_pp'])}. "
            f"ENTRY_003: {verdict(m['entry_alpha_003_significant'], m['strategy_net_003_delta_pp'])}. "
            f"Skipped baseline ret (K3 {m['skipped_K3_baseline_ret_mean_pct']}% vs S3 entered "
            f"{m['entered_S3_baseline_ret_mean_pct']}%) → pullback míjí nejsilnější movery. "
            f"{dep_warn} {regime_note} {caveats}"
        )
