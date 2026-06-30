"""
MLERankCumulative_v1 — MLE Rank Cumulative Thresholds

Research Project: RP-0007-MLE-RANK-BUCKETS (doplnek k discrete buckets)

Otazka:
    Jak se meni edge, kdyz postupne rozsiruji vyber (rank <= N)?

Na rozdil od MLERankBuckets_v1 (discrete buckety 1-10, 11-20, ...),
tento experiment pocita KUMULATIVNI skupiny: rank <= 10, rank <= 20,
rank <= 30, atd. To odpovida na otazku jako "je TOP20 jako celek dobry
vyber", ne "je bucket 11-20 samostatne dobry".

Thresholdy: TOP10, TOP20, TOP30, TOP50, TOP70, TOP100

Research Project: RP-0007-MLE-RANK-BUCKETS
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
FORWARD_WINDOWS = [10, 20, 30]
PRIMARY_WINDOW  = 30

CUMULATIVE_THRESHOLDS = [10, 20, 30, 50, 70, 100]


class MLERankCumulative_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLERankCumulative",
            version="1.0.0",
            hypothesis=(
                "Median 30D alpha vs SPY klesa s rostoucim kumulativnim "
                "MLE rank thresholdem (TOP10 > TOP20 > TOP30 > TOP50 > "
                "TOP70 > TOP100), protoze sirsi vyber zahrnuje slabsi "
                "kandidaty (viz MLERankBuckets_v1 discrete profil)."
            ),
            description=(
                "Kumulativni doplnek k discrete MLE Rank Buckets. "
                "Testuje TOP-N skupiny (rank <= N), ne izolovane buckety. "
                "Odpovida na otazku relevantni pro Decision Resolver "
                "threshold nastaveni."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_10d",
            ],
            parameters={
                "cumulative_thresholds": CUMULATIVE_THRESHOLDS,
                "forward_windows":   FORWARD_WINDOWS,
                "primary_window":    PRIMARY_WINDOW,
                "primary_metric":    "alpha_vs_spy",
                "spy_conid":         SPY_CONID,
                "min_observations":  10,
            },
            tags=["edge_validation", "MLE", "rank_profile", "cumulative", "alpha"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle_features = context.features.all_for_name("MLE_Rank_10d")
        if len(mle_features) < self.define().parameters["min_observations"]:
            return ValidationResult.failed(f"Prilis malo MLE_Rank_10d: {len(mle_features)}")
        if SPY_CONID not in context.prices:
            return ValidationResult.failed(f"SPY (conid={SPY_CONID}) neni v context.prices.")
        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        query = ResearchQuery(context)
        spy_prices = context.prices[SPY_CONID]

        trading_days = query.dates()
        if not trading_days:
            return ExperimentResult(metrics={"error": "no_trading_days"}, summary="Zadne obchodni dny.")

        cutoff = trading_days[-1] - timedelta(days=PRIMARY_WINDOW + 10)
        eligible_days = [d for d in trading_days if d <= cutoff]

        max_th = max(CUMULATIVE_THRESHOLDS)
        base_records = []

        for signal_date in eligible_days:
            ts = pd.Timestamp(signal_date)
            spy_entry = float(spy_prices.loc[ts, "close"]) if ts in spy_prices.index else None
            if spy_entry is None:
                continue

            all_snaps = query.assets(date=signal_date)
            for snap in all_snaps:
                rank = snap.mle_rank_10d
                if rank is None or rank > max_th:
                    continue
                rec = self._build_record(
                    snap.conid, snap.ticker, signal_date, rank,
                    context, spy_entry, spy_prices,
                )
                if rec:
                    base_records.append(rec)

        if not base_records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        base_df = pd.DataFrame(base_records)

        stats_rows = []
        pw = PRIMARY_WINDOW
        ac = f"alpha_{pw}d"

        for th in CUMULATIVE_THRESHOLDS:
            subset = base_df[base_df["mle_rank10d"] <= th]
            if subset.empty:
                continue
            row = {"threshold": th, "n": len(subset), "unique_tickers": subset["ticker"].nunique()}
            for w in FORWARD_WINDOWS:
                col = f"alpha_{w}d"
                vals = subset[col].dropna()
                if vals.empty:
                    continue
                row[f"median_alpha_{w}d"]   = round(float(vals.median()), 4)
                row[f"mean_alpha_{w}d"]     = round(float(vals.mean()), 4)
                row[f"win_rate_alpha_{w}d"] = round(float((vals > 0).mean()), 4)
                row[f"n_valid_{w}d"]        = len(vals)
            stats_rows.append(row)

        stats_df = pd.DataFrame(stats_rows)
        wc = f"win_rate_alpha_{pw}d"

        alphas = {}
        for th in CUMULATIVE_THRESHOLDS:
            r = stats_df[stats_df["threshold"] == th]
            alphas[th] = float(r[ac.replace("alpha_", "median_alpha_")].iloc[0]) if not r.empty and f"median_alpha_{pw}d" in r.columns and pd.notna(r[f"median_alpha_{pw}d"].iloc[0]) else None

        n_transitions = len(CUMULATIVE_THRESHOLDS) - 1
        n_monotonic = 0
        for i in range(n_transitions):
            a1, a2 = alphas.get(CUMULATIVE_THRESHOLDS[i]), alphas.get(CUMULATIVE_THRESHOLDS[i+1])
            if a1 is not None and a2 is not None and a1 >= a2:
                n_monotonic += 1
        pct_monotonic = round(n_monotonic / n_transitions, 4) if n_transitions > 0 else None
        h_supported = pct_monotonic is not None and n_monotonic >= max(1, n_transitions - 1)

        last_positive = None
        for th in CUMULATIVE_THRESHOLDS:
            if alphas.get(th) is not None and alphas[th] > 0:
                last_positive = th

        metrics = {
            "n_records_total":  len(base_df),
            "n_eligible_days":  len(eligible_days),
            "primary_window_d": pw,
            "primary_metric":   "alpha_vs_spy",
            "n_transitions_monotonic": n_monotonic,
            "n_transitions_total":     n_transitions,
            "pct_monotonic":    pct_monotonic,
            "h_supported":      h_supported,
            "last_positive_alpha_threshold": last_positive,
        }
        for th in CUMULATIVE_THRESHOLDS:
            r = stats_df[stats_df["threshold"] == th]
            if r.empty:
                continue
            metrics[f"TOP{th}_n"] = int(r["n"].iloc[0])
            mac = f"median_alpha_{pw}d"
            if mac in r.columns and pd.notna(r[mac].iloc[0]):
                metrics[f"TOP{th}_median_alpha_30d"] = r[mac].iloc[0]
            if wc in r.columns and pd.notna(r[wc].iloc[0]):
                metrics[f"TOP{th}_wr_alpha_30d"] = r[wc].iloc[0]

        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def sup(v): return "SUPPORTED" if v else "NOT SUPPORTED"

        lines = [
            "MLE Rank Cumulative Thresholds",
            "Question: How does edge change as selection widens (rank <= N)?",
            "",
            f"Metrika: alpha vs SPY  |  Primary window: {pw}D",
            "",
            "Profil (kumulativni, ne discrete buckety):",
        ]
        for th in CUMULATIVE_THRESHOLDS:
            r = stats_df[stats_df["threshold"] == th]
            if r.empty:
                lines.append(f"  TOP{th:<5} N/A")
                continue
            mac = f"median_alpha_{pw}d"
            a = r[mac].iloc[0] if mac in r.columns else None
            w = r[wc].iloc[0] if wc in r.columns else None
            n = int(r["n"].iloc[0])
            if pd.notna(a) and pd.notna(w):
                lines.append(f"  TOP{th:<5} alpha={fmt(a)}  WR={w*100:.1f}%  N={n}")
            else:
                lines.append(f"  TOP{th:<5} N={n}")

        lines += [
            "",
            f"Monotonni prechody: {n_monotonic}/{n_transitions} ({pct_monotonic*100:.0f}%)" if pct_monotonic is not None else "N/A",
            f"Posledni TOP-N s kladnou alfou: TOP{last_positive}" if last_positive else "zadny",
            "",
            f"H: {sup(h_supported)}",
            "",
            f"N celkem (TOP{max(CUMULATIVE_THRESHOLDS)}): {len(base_df):,} | Dny: {len(eligible_days)}",
            f"Rozsah: {context.config.date_from} -> {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"cumulative_stats": stats_df},
            summary="\n".join(lines),
        )

    def _build_record(self, conid, ticker, signal_date, rank,
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

        record = {"date": signal_date, "conid": conid, "ticker": ticker, "mle_rank10d": rank}
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
