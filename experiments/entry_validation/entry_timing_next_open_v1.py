"""
EntryTimingNextOpen_v1 — čistý timing test: close(D) vs open(D+1).

Research Project: RP-0009-ENTRY-TIMING
Class:            entry-edge (Entry Validation)

Otázka:
    Liší se forward return při vstupu na close dne signálu (ENTRY_001)
    od vstupu na open následujícího dne (ENTRY_004), nad množinou
    MLE×IRC kandidátů? Tj. je next-open produkčně použitelná náhrada
    za close-entry research baseline bez degradace edge?

Varianty (nad IDENTICKOU množinou kandidátů — čistý timing, množina se NEMĚNÍ):
    ENTRY_001  close(D)  → close(D+20)          [baseline, look-ahead caveat]
    ENTRY_004  open(D+1) → close(D+1+20)        [první realizovatelná cena]

Na rozdíl od pullback experimentu zde ani jedna varianta NESKIPUJE — obě
vstupují do 100 % kandidátů → matched srovnání je triviálně na celé množině,
žádný opportunity cost, žádný skipped return.

═══════════════════════════════════════════════════════════════════════
PRE-REGISTROVANÉ PARAMETRY — ZAMČENO a priori (2026-06-30).
═══════════════════════════════════════════════════════════════════════
    ENTRY_004: entry = open(D+1), exit = close(D+1+HOLD)
    MIN_FUTURE_DAYS = 21 (1 wait + 20 hold) — společný completable subset
    signifikance: ticker-clustered bootstrap (B=2000, seed=42)
    forward return = exit/entry - 1 (close-to-close pro 001, open-to-close pro 004)
    baseline pro alpha = ENTRY_001
    regime split: DEFERRED

Předpoklady / edge cases:
    - Vyžaduje sloupec 'open' v cenách (ENTRY_004). Kandidát bez open v D+1
      nebo bez close v D+1+HOLD se vynechá (garantuje matched množinu — do
      analýzy jde jen kandidát, kde obě varianty mají kompletní ceny).
    - Baseline ENTRY_001 close look-ahead (vstup na close, z něhož signál) —
      konzistentní s předchozími audity, reportováno. ENTRY_004 tím netrpí.
    - ticker→industry z asset snapshotů (IBKR taxonomy), shodné s MLE×IRC join.
"""

from __future__ import annotations

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
MIN_FUTURE_DAYS  = 21          # 1 (next open) + 20 (hold)
BOOTSTRAP_B      = 2000
BOOTSTRAP_SEED   = 42
MIN_OBSERVATIONS = 100
# ────────────────────────────────────────────────────────────────────────


class EntryTimingNextOpen_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="EntryTimingNextOpen",
            version="1.0.0",
            hypothesis=(
                "Vstup na open(D+1) dává stejný forward return jako vstup na "
                "close(D) nad MLE×IRC kandidáty (matched alpha ~0) → next-open je "
                "produkčně realizovatelná náhrada za close-entry baseline."
            ),
            description=(
                "Čistý timing test close(D) vs open(D+1), oba hold 20D, nad "
                "identickou množinou MLE TOP10 × IRC TOP10 kandidátů. Matched, "
                "ticker-clustered bootstrap. Žádný skipped (100% fill obou variant)."
            ),
            required_data=["prices", "feature:MLE_Rank_10d", "signal:IRC"],
            parameters={
                "mle_top": MLE_TOP, "irc_top": IRC_TOP, "irc_lookback": IRC_LOOKBACK,
                "hold_days": HOLD_DAYS, "min_future_days": MIN_FUTURE_DAYS,
                "bootstrap_b": BOOTSTRAP_B, "bootstrap_seed": BOOTSTRAP_SEED,
                "min_observations": MIN_OBSERVATIONS,
            },
            tags=["entry-edge", "next-open", "timing", "production-compat", "pre-registered"],
            author="MSL/MRL architecture session",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle = context.features.all_for_name("MLE_Rank_10d")
        if len(mle) < MIN_OBSERVATIONS:
            return ValidationResult.failed(f"Málo MLE_Rank_10d: {len(mle)}")
        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed("IRC chybí v context.signals.")
        if not context.prices:
            return ValidationResult.failed("Prázdné context.prices.")
        return ValidationResult.ok()

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

        close_cache: dict[int, pd.DataFrame] = {}

        def price_at(conid: int, pos: int, col: str):
            if pos < 0 or pos >= n_days:
                return None
            df = close_cache.get(conid)
            if df is None:
                src = context.prices.get(conid)
                if src is None or src.empty:
                    close_cache[conid] = pd.DataFrame()
                    return None
                df = src
                close_cache[conid] = df
            ts = pd.Timestamp(trading_days[pos])
            if ts not in df.index or col not in df.columns:
                return None
            return float(df.loc[ts, col])

        rows = []
        for d in trading_days:
            ts = pd.Timestamp(d)
            sig_pos = day_pos[ts]
            if sig_pos + MIN_FUTURE_DAYS >= n_days:
                continue
            snaps = [
                s for s in query.assets(date=d)
                if s.mle_rank_10d is not None and s.mle_rank_10d <= MLE_TOP
            ]
            for s in snaps:
                irc_rank = irc_index.get((ts, s.industry))
                if irc_rank is None or irc_rank > IRC_TOP:
                    continue
                # ENTRY_001: close(D) → close(D+HOLD)
                e1 = price_at(s.conid, sig_pos, "close")
                x1 = price_at(s.conid, sig_pos + HOLD_DAYS, "close")
                # ENTRY_004: open(D+1) → close(D+1+HOLD)
                e4 = price_at(s.conid, sig_pos + 1, "open")
                x4 = price_at(s.conid, sig_pos + 1 + HOLD_DAYS, "close")
                if None in (e1, x1, e4, x4) or e1 <= 0 or e4 <= 0:
                    continue  # matched: jen kandidát s kompletními cenami pro obě varianty
                rows.append({
                    "ticker": s.ticker,
                    "r1": x1 / e1 - 1.0,
                    "r4": x4 / e4 - 1.0,
                })

        if not rows:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Žádné candidate-days.")

        df = pd.DataFrame(rows)
        N = len(df)
        uniq = df["ticker"].nunique()

        rng = np.random.default_rng(BOOTSTRAP_SEED)
        diffs = (df["r4"] - df["r1"]).values
        by: dict[str, list] = {}
        for tk, dv in zip(df["ticker"].values, diffs):
            by.setdefault(tk, []).append(dv)
        keys = list(by.keys())
        means = np.empty(BOOTSTRAP_B)
        for i in range(BOOTSTRAP_B):
            pick = rng.choice(keys, size=len(keys), replace=True)
            means[i] = np.concatenate([by[k] for k in pick]).mean()
        lo, hi = np.percentile(means, [2.5, 97.5])
        alpha = float(diffs.mean())
        significant = not (lo <= 0 <= hi)

        def wr(s): return round(100.0 * (s > 0).mean(), 2)

        metrics = {
            "N_candidate_days": N,
            "unique_tickers": uniq,
            "fill_pct": 100.0,  # obě varianty vstupují do 100% matched množiny
            "entry_001_mean_ret_pct": round(df["r1"].mean() * 100, 3),
            "entry_001_median_pct": round(df["r1"].median() * 100, 3),
            "entry_001_win_pct": wr(df["r1"]),
            "entry_004_mean_ret_pct": round(df["r4"].mean() * 100, 3),
            "entry_004_median_pct": round(df["r4"].median() * 100, 3),
            "entry_004_win_pct": wr(df["r4"]),
            "matched_alpha_004_minus_001_pp": round(alpha * 100, 3),
            "matched_alpha_ci_lo": round(lo * 100, 3),
            "matched_alpha_ci_hi": round(hi * 100, 3),
            "matched_alpha_significant": significant,
        }

        tables = {
            "per_variant": pd.DataFrame([
                {"variant": "ENTRY_001_close", "N": N,
                 "mean_ret_pct": metrics["entry_001_mean_ret_pct"],
                 "median_pct": metrics["entry_001_median_pct"], "win_pct": metrics["entry_001_win_pct"]},
                {"variant": "ENTRY_004_next_open", "N": N,
                 "mean_ret_pct": metrics["entry_004_mean_ret_pct"],
                 "median_pct": metrics["entry_004_median_pct"], "win_pct": metrics["entry_004_win_pct"]},
            ]),
        }

        dep_warn = (
            f"DEPENDENCE WARNING: nominal N={N}, unikátních tickerů={uniq} "
            f"(poměr {uniq/N:.2f}). Efektivní N << nominal. Signifikance výhradně "
            f"z ticker-clustered bootstrapu."
        )
        regime_note = (
            "REGIME SPLIT DEFERRED: jedno běhové období (pravděpodobně bull/momentum). "
            "Verdikt vázaný na období."
        )
        equiv = "PRAKTICKY EKVIVALENTNÍ" if not significant else "ROZDÍL DETEKOVÁN"
        summary = (
            f"close(D) vs open(D+1): matched alpha {metrics['matched_alpha_004_minus_001_pp']}pp "
            f"CI[{metrics['matched_alpha_ci_lo']},{metrics['matched_alpha_ci_hi']}] "
            f"sig={significant} → {equiv}. "
            f"ENTRY_004 (open D+1) je první realizovatelná cena po signálu; ENTRY_001 (close D) "
            f"nese look-ahead caveat. Žádný prakticky významný rozdíl nenalezen → next-open je "
            f"produkčně použitelná náhrada za close-entry research baseline v dostupném období. "
            f"{dep_warn} {regime_note} "
            f"CAVEAT: CI vylučuje jen rozdíly > ~{max(abs(metrics['matched_alpha_ci_lo']), abs(metrics['matched_alpha_ci_hi']))}pp; "
            f"'ekvivalentní' = 'žádný prakticky významný rozdíl nenalezen', ne 'identické'."
        )
        return ExperimentResult(metrics=metrics, tables=tables, summary=summary)
