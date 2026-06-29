"""
MomentumEdge_v1 — Reference Experiment #1

Hypotéza:
    Akcie S&P 500 v TOP decilu podle 20D price momentum vykazují
    vyšší median 10D forward return než akcie v BOTTOM decilu.

Účel:
    Primárně ověřit Architecture Candidate v1.0 end-to-end.
    Sekundárně změřit základní momentum edge v S&P 500.

Data:
    Pouze EOD prices + universe z MDSM-Lite.
    Žádné signály z produkčních modulů.

Logika:
    Pro každý obchodní den v rozsahu:
        1. Spočítat 20D momentum = (close / close[20D ago]) - 1
        2. Rozdělit universe do decilů
        3. Zaznamenat 10D forward return
    Agregovat přes všechny dny a decily.
    Porovnat TOP vs BOTTOM decil.

Research Project: RP-2026-06-REF-MOMENTUM
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult


class MomentumEdge_v1(BaseExperiment):

    # ------------------------------------------------------------------
    # Konstanty — neměnit bez změny verze
    # ------------------------------------------------------------------
    LOOKBACK_DAYS  = 20    # délka momentum okna
    FORWARD_DAYS   = 10    # délka forward return okna
    N_DECILES      = 10    # počet decilů
    MIN_UNIVERSE   = 100   # minimální počet akcií pro validní decil
    MIN_PERIODS    = 50    # minimální počet obchodních dní v rozsahu

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MomentumEdge",
            version="1.0.0",
            hypothesis=(
                "Akcie S&P 500 v TOP decilu podle 20D price momentum "
                "vykazují vyšší median 10D forward return "
                "než akcie v BOTTOM decilu."
            ),
            description=(
                "Reference Experiment #1. Základní momentum edge test "
                "na S&P 500 EOD datech. Ověřuje MRL Architecture Candidate v1.0 "
                "end-to-end."
            ),
            required_data=["prices"],
            parameters={
                "lookback_days":  self.LOOKBACK_DAYS,
                "forward_days":   self.FORWARD_DAYS,
                "n_deciles":      self.N_DECILES,
                "min_universe":   self.MIN_UNIVERSE,
                "min_periods":    self.MIN_PERIODS,
            },
            tags=["edge_validation", "momentum", "reference"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        n_prices = len(context.prices)
        if n_prices < self.MIN_UNIVERSE:
            return ValidationResult.failed(
                f"Příliš málo instrumentů s cenami: {n_prices} < {self.MIN_UNIVERSE}"
            )

        close = context.close_matrix()
        total_days = close.shape[0]
        required = self.LOOKBACK_DAYS + self.FORWARD_DAYS + self.MIN_PERIODS
        if total_days < required:
            return ValidationResult.failed(
                f"Příliš málo obchodních dní: {total_days} < {required} "
                f"(lookback={self.LOOKBACK_DAYS} + forward={self.FORWARD_DAYS} "
                f"+ min_periods={self.MIN_PERIODS})"
            )

        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        """
        Čistá funkce — žádné side effects.

        Algoritmus:
            close_matrix: DataFrame(date × conid)
            momentum = close / close.shift(lookback) - 1       (20D)
            forward  = close.shift(-forward_days) / close - 1  (10D)

            Pro každý den: rozdělit do decilů podle momentum,
            zaznamenat forward return každé akcie.
            Agregovat přes všechny dny.
        """
        p = self.define().parameters

        close = context.close_matrix()
        lookback = p["lookback_days"]
        forward  = p["forward_days"]
        n_dec    = p["n_deciles"]

        # --- Výpočet momentum a forward return ---
        momentum = close / close.shift(lookback) - 1
        fwd_ret  = close.shift(-forward) / close - 1

        # --- Cross-sectional decile ranking per den ---
        records = []

        for date, mom_row in momentum.iterrows():
            fwd_row = fwd_ret.loc[date]

            # Jen akcie s platným momentum i forward return
            valid = mom_row.dropna().index.intersection(fwd_row.dropna().index)
            if len(valid) < p["min_universe"]:
                continue

            mom_valid = mom_row[valid]
            fwd_valid = fwd_row[valid]

            # Decile: 1 = BOTTOM, n_dec = TOP
            try:
                deciles = pd.qcut(mom_valid, q=n_dec, labels=False, duplicates="drop")
            except ValueError:
                continue

            for conid in valid:
                dec = deciles.get(conid)
                if dec is None or pd.isna(dec):
                    continue
                records.append({
                    "date":    date,
                    "conid":   conid,
                    "decile":  int(dec) + 1,          # 1-based
                    "momentum": mom_valid[conid],
                    "fwd_ret":  fwd_valid[conid],
                })

        if not records:
            return ExperimentResult(
                metrics={"error": "no_valid_periods"},
                summary="Žádné validní periody — zkontroluj datový rozsah.",
            )

        df = pd.DataFrame(records)
        n_periods = df["date"].nunique()
        n_obs     = len(df)

        # --- Agregace po decilech ---
        decile_stats = (
            df.groupby("decile")["fwd_ret"]
            .agg(
                median_return="median",
                mean_return="mean",
                win_rate=lambda x: (x > 0).mean(),
                n="count",
            )
            .reset_index()
        )

        top_dec    = decile_stats[decile_stats["decile"] == n_dec].iloc[0]
        bottom_dec = decile_stats[decile_stats["decile"] == 1].iloc[0]
        spread     = float(top_dec["median_return"] - bottom_dec["median_return"])

        # --- Metriky ---
        metrics = {
            "n_periods":              n_periods,
            "n_observations":         n_obs,
            "lookback_days":          lookback,
            "forward_days":           forward,
            "n_deciles":              n_dec,
            "top_decile_median_ret":  round(float(top_dec["median_return"]), 6),
            "top_decile_mean_ret":    round(float(top_dec["mean_return"]), 6),
            "top_decile_win_rate":    round(float(top_dec["win_rate"]), 4),
            "top_decile_n":           int(top_dec["n"]),
            "bottom_decile_median_ret": round(float(bottom_dec["median_return"]), 6),
            "bottom_decile_mean_ret": round(float(bottom_dec["mean_return"]), 6),
            "bottom_decile_win_rate": round(float(bottom_dec["win_rate"]), 4),
            "bottom_decile_n":        int(bottom_dec["n"]),
            "top_minus_bottom_spread": round(spread, 6),
            "hypothesis_supported":   spread > 0.005,
        }

        # --- Summary ---
        direction = "✓ SUPPORTED" if spread > 0.005 else "✗ NOT SUPPORTED"
        summary = (
            f"Momentum Edge ({lookback}D → {forward}D forward), S&P 500\n\n"
            f"TOP decil median return:    {metrics['top_decile_median_ret']:.2%}\n"
            f"BOTTOM decil median return: {metrics['bottom_decile_median_ret']:.2%}\n"
            f"Spread (TOP - BOTTOM):      {spread:.2%}\n\n"
            f"Hypotéza H-001: {direction}\n\n"
            f"N pozorování: {n_obs:,} | N period: {n_periods} obchodních dní\n"
            f"Universe: {context.config.universe} | "
            f"Rozsah: {context.config.date_from} → {context.config.date_to}"
        )

        return ExperimentResult(
            metrics=metrics,
            tables={"decile_stats": decile_stats},
            summary=summary,
        )
