"""
IMSScoreBucketEdge_v1 — Reference Experiment #2

Research Project: RP-2026-06-IMS-SCORE-EDGE

Hypotéza H-001:
    Akcie s IMS skóre >= 90 (ELITE bucket) dosahují vyššího
    median 30D forward returnu než akcie s IMS skóre 60–69 (RADAR bucket).

Výpočetní logika:
    Adaptována z legacy_audits/IMS_audit/tests/return_analysis.py
    Infrastruktura: MRL framework (ExperimentContext, ResearchQuery, ArchiveManager)

Účel:
    Ověřit MRL end-to-end pipeline s reálnými IMS signály přes ResearchQuery API:
    Research Project → Experiment → ResearchQuery → Result → Report → Registry
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult
from src.query.research_query import ResearchQuery

# Score buckety — přesně jako v legacy return_analysis.py
SCORE_BUCKETS: dict[str, tuple[float, float]] = {
    "RADAR":  (60.0, 70.0),
    "H70-79": (70.0, 80.0),
    "H80-89": (80.0, 90.0),
    "H90-94": (90.0, 95.0),
    "H95+":   (95.0, 101.0),
}

FORWARD_WINDOWS = [5, 10, 20, 30]
SPY_CONID = 756733


class IMSScoreBucketEdge_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="IMSScoreBucketEdge",
            version="1.0.0",
            hypothesis=(
                "Akcie s IMS skóre >= 90 (ELITE bucket) dosahují vyššího "
                "median 30D forward returnu než akcie s IMS skóre 60–69 (RADAR bucket)."
            ),
            description=(
                "Reference Experiment #2. Migrace IMS return_analysis logiky do MRL. "
                "Testuje zda IMS score predikuje forward return napříč score buckety."
            ),
            required_data=["prices", "feature:IMS_Score", "feature:IMS_Priority_Group"],
            parameters={
                "forward_windows":   FORWARD_WINDOWS,
                "score_buckets":     list(SCORE_BUCKETS.keys()),
                "min_observations":  20,
                "hypothesis_window": 30,
                "hypothesis_spread": 0.5,
            },
            tags=["edge_validation", "IMS", "reference", "score_bucket"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        if context.features.is_empty():
            return ValidationResult.failed("FeatureSet je prázdný — chybí IMS signály.")

        ims_features = context.features.all_for_name("IMS_Score")
        if len(ims_features) < self.define().parameters["min_observations"]:
            return ValidationResult.failed(
                f"Příliš málo IMS_Score záznamů: "
                f"{len(ims_features)} < {self.define().parameters['min_observations']}"
            )

        if SPY_CONID not in context.prices:
            return ValidationResult.warning(
                f"SPY (conid={SPY_CONID}) není v cenách — alpha vs SPY nebude počítána."
            )

        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        """
        Výpočetní logika adaptována z return_analysis.py.

        Pipeline:
            1. ResearchQuery.assets() — IMS signály per den
            2. forward return z context.prices
            3. agregace per score bucket a forward window
            4. porovnání ELITE vs RADAR (H-001)
        """
        query = ResearchQuery(context)
        params = self.define().parameters

        # Obchodní dny dostupné v context
        trading_days = query.dates()
        if not trading_days:
            return ExperimentResult(
                metrics={"error": "no_trading_days"},
                summary="Žádné obchodní dny v context.prices.",
            )

        # SPY close pro alpha výpočet
        spy_close = context.prices.get(SPY_CONID)
        spy_index = set(spy_close.index.date) if spy_close is not None else set()

        # === HLAVNÍ LOOP ===
        # Pro každý obchodní den: načti IMS snapshots, spočítej forward returns
        records = []
        max_window = max(FORWARD_WINDOWS)

        # Pracujeme jen s dny kde máme dost prostoru pro forward return
        cutoff = trading_days[-1] - timedelta(days=max_window + 10)
        eligible_days = [d for d in trading_days if d <= cutoff]

        for signal_date in eligible_days:
            # IMS snapshots pro daný den přes ResearchQuery
            snapshots = query.assets(
                date=signal_date,
                ims_score_min=60.0,  # pouze IMS kandidáti
            )
            if not snapshots:
                continue

            for snap in snapshots:
                conid = snap.conid
                score = snap.ims_score
                if score is None:
                    continue

                # Entry price
                price_df = context.prices.get(conid)
                if price_df is None or price_df.empty:
                    continue

                entry_ts = pd.Timestamp(signal_date)
                if entry_ts not in price_df.index:
                    continue
                entry_price = float(price_df.loc[entry_ts, "close"])
                if entry_price <= 0:
                    continue

                # SPY entry
                spy_entry = None
                if spy_close is not None and entry_ts in spy_close.index:
                    spy_entry = float(spy_close.loc[entry_ts, "close"])

                row = {
                    "date":     signal_date,
                    "conid":    conid,
                    "ticker":   snap.ticker,
                    "score":    score,
                    "priority": snap.ims_priority_group,
                    "sector":   snap.sector,
                    "industry": snap.industry,
                }

                # Forward returns pro každý window
                for window in FORWARD_WINDOWS:
                    fwd_date = signal_date + timedelta(days=window)
                    # Najdi nejbližší obchodní den >= fwd_date
                    fwd_ts = self._nearest_trading_date(
                        price_df, fwd_date
                    )
                    if fwd_ts is None:
                        row[f"fwd_{window}d"] = np.nan
                        row[f"alpha_{window}d"] = np.nan
                        row[f"usable_{window}d"] = False
                        continue

                    fwd_price = float(price_df.loc[fwd_ts, "close"])
                    fwd_ret = (fwd_price / entry_price - 1) * 100

                    # Alpha vs SPY
                    alpha = np.nan
                    if spy_entry and spy_close is not None:
                        spy_fwd_ts = self._nearest_trading_date(spy_close, fwd_date)
                        if spy_fwd_ts is not None:
                            spy_fwd = float(spy_close.loc[spy_fwd_ts, "close"])
                            spy_ret = (spy_fwd / spy_entry - 1) * 100
                            alpha = fwd_ret - spy_ret

                    row[f"fwd_{window}d"]   = round(fwd_ret, 4)
                    row[f"alpha_{window}d"] = round(alpha, 4) if not np.isnan(alpha) else np.nan
                    row[f"usable_{window}d"] = True

                records.append(row)

        if not records:
            return ExperimentResult(
                metrics={"error": "no_records", "n_eligible_days": len(eligible_days)},
                summary="Žádné záznamy — možná příliš krátký datový rozsah.",
            )

        df = pd.DataFrame(records)

        # === AGREGACE PER SCORE BUCKET ===
        bucket_stats = []
        for bucket_name, (lo, hi) in SCORE_BUCKETS.items():
            subset = df[(df["score"] >= lo) & (df["score"] < hi)]
            if subset.empty:
                continue
            for window in FORWARD_WINDOWS:
                col_fwd = f"fwd_{window}d"
                col_alpha = f"alpha_{window}d"
                col_use = f"usable_{window}d"
                usable = subset[subset[col_use] == True]
                if usable.empty:
                    continue
                fwd_vals = usable[col_fwd].dropna()
                alpha_vals = usable[col_alpha].dropna()
                if fwd_vals.empty:
                    continue
                bucket_stats.append({
                    "bucket":         bucket_name,
                    "window":         window,
                    "n":              len(fwd_vals),
                    "median_return":  round(float(fwd_vals.median()), 4),
                    "mean_return":    round(float(fwd_vals.mean()), 4),
                    "win_rate":       round(float((fwd_vals > 0).mean()), 4),
                    "median_alpha":   round(float(alpha_vals.median()), 4) if len(alpha_vals) > 0 else None,
                    "mean_alpha":     round(float(alpha_vals.mean()), 4) if len(alpha_vals) > 0 else None,
                })

        stats_df = pd.DataFrame(bucket_stats)

        # === HYPOTÉZA H-001 ===
        hw = params["hypothesis_window"]
        spread_threshold = params["hypothesis_spread"]

        elite_row   = stats_df[(stats_df["bucket"] == "H90-94") & (stats_df["window"] == hw)]
        radar_row   = stats_df[(stats_df["bucket"] == "RADAR")  & (stats_df["window"] == hw)]
        h95_row     = stats_df[(stats_df["bucket"] == "H95+")   & (stats_df["window"] == hw)]

        elite_med = float(elite_row["median_return"].iloc[0]) if not elite_row.empty else None
        radar_med = float(radar_row["median_return"].iloc[0]) if not radar_row.empty else None
        h95_med   = float(h95_row["median_return"].iloc[0])   if not h95_row.empty   else None
        spread    = round(elite_med - radar_med, 4) if (elite_med is not None and radar_med is not None) else None
        h001_supported = (spread is not None and spread > spread_threshold)

        # === METRIKY ===
        metrics: dict = {
            "n_signals_total":       len(df),
            "n_eligible_days":       len(eligible_days),
            "n_unique_tickers":      int(df["conid"].nunique()),
            "hypothesis_window_d":   hw,
            "hypothesis_spread_threshold": spread_threshold,
            "elite_median_ret_30d":  elite_med,
            "radar_median_ret_30d":  radar_med,
            "h95_median_ret_30d":    h95_med,
            "elite_minus_radar_30d": spread,
            "h001_supported":        h001_supported,
        }

        # Per bucket metriky do metrics flat dict
        for _, row in stats_df.iterrows():
            prefix = f"{row['bucket']}_{row['window']}d"
            metrics[f"{prefix}_n"]              = int(row["n"])
            metrics[f"{prefix}_median_ret"]     = row["median_return"]
            metrics[f"{prefix}_win_rate"]       = row["win_rate"]
            if row.get("median_alpha") is not None:
                metrics[f"{prefix}_median_alpha"] = row["median_alpha"]

        # === SUMMARY ===
        direction = "✓ SUPPORTED" if h001_supported else "✗ NOT SUPPORTED"
        lines = [
            f"IMS Score Bucket Edge — {hw}D forward return",
            "",
            f"Hypotéza H-001: {direction}",
        ]
        if spread is not None:
            lines.append(f"  ELITE (90–94) median {hw}D: {elite_med:+.2f}%")
            lines.append(f"  RADAR (60–69) median {hw}D: {radar_med:+.2f}%")
            lines.append(f"  Spread (ELITE–RADAR):       {spread:+.2f}% (threshold: {spread_threshold:+.1f}%)")
        if h95_med is not None:
            lines.append(f"  H95+ median {hw}D:           {h95_med:+.2f}%")
        lines += [
            "",
            f"N signálů celkem: {len(df):,} | Unikátní tickery: {df['conid'].nunique()}",
            f"Datový rozsah: {context.config.date_from} → {context.config.date_to}",
            f"Universe: {context.config.universe}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"bucket_stats": stats_df},
            summary="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # Interní helper
    # ------------------------------------------------------------------

    @staticmethod
    def _nearest_trading_date(
        price_df: pd.DataFrame,
        target: date,
        max_offset_days: int = 5,
    ) -> pd.Timestamp | None:
        """Vrátí nejbližší dostupný obchodní den >= target, nebo None."""
        for offset in range(max_offset_days + 1):
            ts = pd.Timestamp(target + timedelta(days=offset))
            if ts in price_df.index:
                return ts
        return None
