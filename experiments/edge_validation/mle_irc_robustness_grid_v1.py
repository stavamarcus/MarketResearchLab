"""
MLEIRCRobustnessGrid_v1 — MLE x IRC Robustness Grid

Research Project: RP-0004-MLE-IRC-ROBUSTNESS

Otazka:
    Je MLE x IRC edge (KR-2026-06-MLE-IRC-interaction) robustni vuci
    zmene prahu, nebo existuje pouze v jednom konkretnim bode (overfit)?

Grid:
    MLE rank_10d <= {10, 20, 30, 50}
    IRC rank      <= {5, 10, 15, 20}
    = 16 kombinaci

Pro kazdou kombinaci pocitame:
    MLE+IRC_TOP    — MLE TOP{N} a soucasne industry rank <= IRC{M}
    MLE_HEADWIND   — MLE TOP{N} a industry rank > IRC{M}
    diff = alpha(MLE+IRC_TOP) - alpha(MLE_HEADWIND)

Cil neni najit nejlepsi kombinaci. Cil je zjistit, zda je kladny diff
stabilni napric gridem, nebo je izolovany v jednom bode.

Research Project: RP-0004-MLE-IRC-ROBUSTNESS
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

SPY_CONID       = 756733
IRC_LOOKBACK    = 20
FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 30

MLE_THRESHOLDS = [10, 20, 30, 50]
IRC_THRESHOLDS = [5, 10, 15, 20]


class MLEIRCRobustnessGrid_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLEIRCRobustnessGrid",
            version="1.0.0",
            hypothesis=(
                "Diff alpha (MLE+IRC_TOP vs MLE_HEADWIND) je kladny a "
                "stabilni napric grid MLE TOP10/20/30/50 x IRC TOP5/10/15/20, "
                "ne jen v jednom izolovanem bode."
            ),
            description=(
                "Robustness grid pro KR-2026-06-MLE-IRC-interaction. "
                "16 kombinaci prahu, primarni metrika alpha vs SPY 30D."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_10d",
                "signal:IRC",
            ],
            parameters={
                "mle_thresholds":   MLE_THRESHOLDS,
                "irc_thresholds":   IRC_THRESHOLDS,
                "irc_lookback":     IRC_LOOKBACK,
                "forward_windows":  FORWARD_WINDOWS,
                "primary_window":   PRIMARY_WINDOW,
                "primary_metric":   "alpha_vs_spy",
                "spy_conid":        SPY_CONID,
                "min_observations": 10,
            },
            tags=["edge_validation", "MLE", "IRC", "robustness", "grid_search", "signal_interaction"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle_features = context.features.all_for_name("MLE_Rank_10d")
        if len(mle_features) < self.define().parameters["min_observations"]:
            return ValidationResult.failed(f"Prilis malo MLE_Rank_10d: {len(mle_features)}")
        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed("IRC chybi v context.signals.")
        if SPY_CONID not in context.prices:
            return ValidationResult.failed(f"SPY (conid={SPY_CONID}) neni v context.prices.")
        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        query = ResearchQuery(context)

        irc_df = context.signals["IRC"].copy()
        irc_df = irc_df[irc_df["lookback"] == IRC_LOOKBACK]
        irc_df["date"] = pd.to_datetime(irc_df["date"])
        irc_index = irc_df.set_index(["date", "industry"])["rank"].to_dict()

        spy_prices = context.prices[SPY_CONID]

        trading_days = query.dates()
        if not trading_days:
            return ExperimentResult(metrics={"error": "no_trading_days"}, summary="Zadne obchodni dny.")

        cutoff = trading_days[-1] - timedelta(days=PRIMARY_WINDOW + 10)
        eligible_days = [d for d in trading_days if d <= cutoff]

        # Predpocitej vsechny MLE TOP50 (nejsirsi prah) snapshoty + alpha pro vsechny windows
        # Pak filtrujeme uz jen v pameti — vyhneme se opakovanemu pristupu k cenam
        base_records = []

        for signal_date in eligible_days:
            ts = pd.Timestamp(signal_date)
            spy_entry = float(spy_prices.loc[ts, "close"]) if ts in spy_prices.index else None
            if spy_entry is None:
                continue

            # query.assets(mle_rank_max=...) filtruje podle mle_rank_20d.
            # Potrebujeme filtrovat podle mle_rank_10d — manualni filtr.
            all_snaps = query.assets(date=signal_date)
            snaps = [
                s for s in all_snaps
                if s.mle_rank_10d is not None and s.mle_rank_10d <= max(MLE_THRESHOLDS)
            ]
            if not snaps:
                continue

            for snap in snaps:
                irc_rank = irc_index.get((ts, snap.industry))
                rec = self._build_record(
                    snap.conid, snap.ticker, signal_date,
                    snap.mle_rank_10d, irc_rank,
                    context, spy_entry, spy_prices,
                )
                if rec:
                    base_records.append(rec)

        if not base_records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        base_df = pd.DataFrame(base_records)

        # Grid sweep — pro kazdou kombinaci prahu agreguj z base_df
        grid_rows = []
        pw = PRIMARY_WINDOW
        ac = f"alpha_{pw}d"

        for mle_th in MLE_THRESHOLDS:
            for irc_th in IRC_THRESHOLDS:
                subset = base_df[base_df["mle_rank10d"] <= mle_th].copy()
                if subset.empty:
                    continue

                top = subset[(subset["irc_rank"].notna()) & (subset["irc_rank"] <= irc_th)]
                headwind = subset[
                    subset["irc_rank"].isna() | (subset["irc_rank"] > irc_th)
                ]

                top_alpha = round(float(top[ac].dropna().median()), 4) if not top[ac].dropna().empty else None
                head_alpha = round(float(headwind[ac].dropna().median()), 4) if not headwind[ac].dropna().empty else None
                diff = round(top_alpha - head_alpha, 4) if (top_alpha is not None and head_alpha is not None) else None

                grid_rows.append({
                    "mle_threshold": mle_th,
                    "irc_threshold": irc_th,
                    "n_top":         len(top),
                    "n_headwind":    len(headwind),
                    "top_alpha_30d":      top_alpha,
                    "headwind_alpha_30d": head_alpha,
                    "diff":               diff,
                })

        grid_df = pd.DataFrame(grid_rows)

        valid_diffs = grid_df["diff"].dropna()
        n_positive = int((valid_diffs > 0).sum())
        n_total = len(valid_diffs)
        pct_positive = round(n_positive / n_total, 4) if n_total > 0 else None

        h_supported = n_positive >= 10  # podle kriteria potvrzeni: >=10 ze 16

        metrics = {
            "grid_size":          len(grid_df),
            "n_eligible_days":    len(eligible_days),
            "primary_window_d":   pw,
            "primary_metric":     "alpha_vs_spy",
            "n_combinations_positive_diff": n_positive,
            "n_combinations_total":         n_total,
            "pct_combinations_positive":    pct_positive,
            "diff_min":  round(float(valid_diffs.min()), 4) if not valid_diffs.empty else None,
            "diff_max":  round(float(valid_diffs.max()), 4) if not valid_diffs.empty else None,
            "diff_mean": round(float(valid_diffs.mean()), 4) if not valid_diffs.empty else None,
            "diff_median": round(float(valid_diffs.median()), 4) if not valid_diffs.empty else None,
            "h_supported": h_supported,
        }

        # Referencni bod KR-2026-06-MLE-IRC-interaction: MLE20 x IRC10
        ref_row = grid_df[(grid_df["mle_threshold"] == 20) & (grid_df["irc_threshold"] == 10)]
        if not ref_row.empty:
            metrics["reference_point_diff_MLE20_IRC10"] = ref_row["diff"].iloc[0]

        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def sup(v): return "SUPPORTED" if v else "NOT SUPPORTED"

        lines = [
            "MLE x IRC Robustness Grid",
            "Question: Is the MLE+IRC edge stable across thresholds, or isolated to one point?",
            "",
            f"Grid: MLE TOP{MLE_THRESHOLDS} x IRC TOP{IRC_THRESHOLDS} = {len(grid_df)} kombinaci",
            f"Primary: {pw}D alpha vs SPY",
            "",
            "Grid (diff = alpha(MLE+IRC_TOP) - alpha(MLE_HEADWIND)):",
            "",
            f"{'MLE\\IRC':>10}" + "".join(f"{f'TOP{i}':>10}" for i in IRC_THRESHOLDS),
        ]
        for mle_th in MLE_THRESHOLDS:
            row_str = f"{'TOP'+str(mle_th):>10}"
            for irc_th in IRC_THRESHOLDS:
                cell = grid_df[(grid_df["mle_threshold"]==mle_th) & (grid_df["irc_threshold"]==irc_th)]
                if not cell.empty and cell["diff"].iloc[0] is not None:
                    row_str += f"{fmt(cell['diff'].iloc[0]):>10}"
                else:
                    row_str += f"{'N/A':>10}"
            lines.append(row_str)

        lines += [
            "",
            f"Kombinaci s kladnym diff: {n_positive}/{n_total} ({pct_positive*100:.0f}%)" if pct_positive is not None else "N/A",
            f"Diff rozsah: {fmt(metrics['diff_min'])} az {fmt(metrics['diff_max'])} (median: {fmt(metrics['diff_median'])})",
            "",
            f"Referencni bod (MLE TOP20 x IRC TOP10): {fmt(metrics.get('reference_point_diff_MLE20_IRC10'))}",
            "",
            f"H (>=10/16 kombinaci s kladnym diff): {sup(h_supported)}",
            "",
            f"Dny: {len(eligible_days)} | Rozsah: {context.config.date_from} -> {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"grid_results": grid_df},
            summary="\n".join(lines),
        )

    def _build_record(self, conid, ticker, signal_date, mle_rank, irc_rank,
                      context, spy_entry, spy_prices):
        price_df = context.prices.get(conid)
        if price_df is None or price_df.empty:
            return None
        entry_ts = pd.Timestamp(signal_date)
        if entry_ts not in price_df.index:
            return None
        entry_price = float(price_df.loc[entry_ts, "close"])
        if entry_price <= 0:
            return None

        record = {
            "date": signal_date, "conid": conid, "ticker": ticker,
            "mle_rank10d": mle_rank, "irc_rank": irc_rank,
        }
        for w in FORWARD_WINDOWS:
            fwd_ts = self._nearest_date(price_df, signal_date + timedelta(days=w))
            if fwd_ts is None:
                record[f"alpha_{w}d"] = np.nan
                continue
            fwd_ret = (float(price_df.loc[fwd_ts, "close"]) / entry_price - 1) * 100
            spy_fwd_ts = self._nearest_date(spy_prices, signal_date + timedelta(days=w))
            if spy_fwd_ts is not None and spy_entry > 0:
                spy_ret = (float(spy_prices.loc[spy_fwd_ts, "close"]) / spy_entry - 1) * 100
                record[f"alpha_{w}d"] = round(fwd_ret - spy_ret, 4)
            else:
                record[f"alpha_{w}d"] = np.nan
        return record

    @staticmethod
    def _nearest_date(price_df, target, max_offset=5):
        for i in range(max_offset + 1):
            ts = pd.Timestamp(target + timedelta(days=i))
            if ts in price_df.index:
                return ts
        return None
