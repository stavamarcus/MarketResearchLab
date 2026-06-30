"""
MLERankBuckets_v1 — MLE Rank Buckets, kompletni profil 1-150

Research Project: RP-0007-MLE-RANK-BUCKETS

Otazka:
    Jak rychle klesa informacni hodnota MLE ranku? Kde konci edge?

Buckety:
    Elite      1-10
    Strong     11-20
    Good       21-35
    Moderate   36-50
    Watch      51-70
    Weak       71-100
    Tail       101-150

Metrika: alpha vs SPY (standard), 30D primary, 10D/20D sekundarni.

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

RANK_BUCKETS = {
    "Elite":    (1, 10),
    "Strong":   (11, 20),
    "Good":     (21, 35),
    "Moderate": (36, 50),
    "Watch":    (51, 70),
    "Weak":     (71, 100),
    "Tail":     (101, 150),
}
BUCKET_ORDER = list(RANK_BUCKETS.keys())


class MLERankBuckets_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLERankBuckets",
            version="1.0.0",
            hypothesis=(
                "Median 30D alpha vs SPY monotonne klesa s rostoucim MLE "
                "rank_10d bucketem (Elite > Strong > Good > Moderate > "
                "Watch > Weak > Tail)."
            ),
            description=(
                "Kompletni profil MLE rank_10d 1-150. Zjistuje, kde konci "
                "edge a zda je hranice TOP20/TOP50 informovana."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_10d",
            ],
            parameters={
                "rank_buckets":      list(RANK_BUCKETS.keys()),
                "forward_windows":   FORWARD_WINDOWS,
                "primary_window":    PRIMARY_WINDOW,
                "primary_metric":    "alpha_vs_spy",
                "spy_conid":         SPY_CONID,
                "min_observations":  10,
            },
            tags=["edge_validation", "MLE", "rank_profile", "alpha"],
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

        records = []

        for signal_date in eligible_days:
            ts = pd.Timestamp(signal_date)
            spy_entry = float(spy_prices.loc[ts, "close"]) if ts in spy_prices.index else None
            if spy_entry is None:
                continue

            all_snaps = query.assets(date=signal_date)
            for snap in all_snaps:
                rank = snap.mle_rank_10d
                if rank is None or rank > 150:
                    continue
                bucket = self._assign_bucket(rank)
                if bucket is None:
                    continue

                rec = self._build_record(
                    snap.conid, snap.ticker, signal_date, bucket, rank,
                    context, spy_entry, spy_prices,
                )
                if rec:
                    records.append(rec)

        if not records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        df = pd.DataFrame(records)

        stats_rows = []
        for bucket in BUCKET_ORDER:
            sub = df[df["bucket"] == bucket]
            if sub.empty:
                continue
            row = {"bucket": bucket, "n": len(sub), "unique_tickers": sub["ticker"].nunique()}
            for w in FORWARD_WINDOWS:
                ac = f"alpha_{w}d"
                av = sub[ac].dropna()
                if av.empty:
                    continue
                row[f"median_alpha_{w}d"]   = round(float(av.median()), 4)
                row[f"mean_alpha_{w}d"]     = round(float(av.mean()), 4)
                row[f"win_rate_alpha_{w}d"] = round(float((av > 0).mean()), 4)
                row[f"n_valid_{w}d"]        = len(av)
            stats_rows.append(row)

        stats_df = pd.DataFrame(stats_rows)
        pw = PRIMARY_WINDOW
        ac, wc = f"median_alpha_{pw}d", f"win_rate_alpha_{pw}d"

        alphas = {}
        for bucket in BUCKET_ORDER:
            r = stats_df[stats_df["bucket"] == bucket]
            alphas[bucket] = float(r[ac].iloc[0]) if not r.empty and ac in r.columns and pd.notna(r[ac].iloc[0]) else None

        # Monotonie: pocet sousednich prechodu kde alpha[i] >= alpha[i+1]
        present_buckets = [b for b in BUCKET_ORDER if alphas.get(b) is not None]
        n_transitions = len(present_buckets) - 1
        n_monotonic = 0
        for i in range(n_transitions):
            if alphas[present_buckets[i]] >= alphas[present_buckets[i+1]]:
                n_monotonic += 1
        pct_monotonic = round(n_monotonic / n_transitions, 4) if n_transitions > 0 else None
        h_supported = pct_monotonic is not None and n_monotonic >= max(1, n_transitions - 1)

        # Kde edge "konci" — posledni bucket s kladnou alfou
        edge_cutoff = None
        for b in BUCKET_ORDER:
            if alphas.get(b) is not None and alphas[b] > 0:
                edge_cutoff = b

        metrics = {
            "n_records_total":  len(df),
            "n_eligible_days":  len(eligible_days),
            "primary_window_d": pw,
            "primary_metric":   "alpha_vs_spy",
            "n_transitions_monotonic": n_monotonic,
            "n_transitions_total":     n_transitions,
            "pct_monotonic":    pct_monotonic,
            "h_supported":      h_supported,
            "last_positive_alpha_bucket": edge_cutoff,
        }
        for _, row in stats_df.iterrows():
            b = row["bucket"]
            metrics[f"{b}_n"] = int(row["n"])
            if ac in row and pd.notna(row.get(ac)):
                metrics[f"{b}_median_alpha_30d"] = row[ac]
            if wc in row and pd.notna(row.get(wc)):
                metrics[f"{b}_wr_alpha_30d"] = row[wc]

        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def sup(v): return "SUPPORTED" if v else "NOT SUPPORTED"

        lines = [
            "MLE Rank Buckets — kompletni profil 1-150",
            "Question: How fast does MLE rank information value decay?",
            "",
            f"Metrika: alpha vs SPY  |  Primary window: {pw}D",
            "",
            "Profil:",
        ]
        for bucket, (lo, hi) in RANK_BUCKETS.items():
            row = stats_df[stats_df["bucket"] == bucket]
            if row.empty:
                lines.append(f"  {bucket:<10} ({lo}-{hi})  N/A")
                continue
            a = row[ac].iloc[0] if ac in row.columns else None
            w = row[wc].iloc[0] if wc in row.columns else None
            n = int(row["n"].iloc[0])
            if pd.notna(a) and pd.notna(w):
                lines.append(f"  {bucket:<10} ({lo:>3}-{hi:<3}) alpha={fmt(a)}  WR={w*100:.1f}%  N={n}")
            else:
                lines.append(f"  {bucket:<10} ({lo:>3}-{hi:<3}) N={n}")

        lines += [
            "",
            f"Monotonni prechody: {n_monotonic}/{n_transitions} ({pct_monotonic*100:.0f}%)" if pct_monotonic is not None else "N/A",
            f"Posledni bucket s kladnou alfou: {edge_cutoff or 'zadny'}",
            "",
            f"H (alespon {max(1, n_transitions-1)}/{n_transitions} prechodu monotonnich): {sup(h_supported)}",
            "",
            f"N celkem: {len(df):,} | Dny: {len(eligible_days)}",
            f"Rozsah: {context.config.date_from} -> {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"bucket_stats": stats_df},
            summary="\n".join(lines),
        )

    def _assign_bucket(self, rank: int) -> str | None:
        for bucket_name, (lo, hi) in RANK_BUCKETS.items():
            if lo <= rank <= hi:
                return bucket_name
        return None

    def _build_record(self, conid, ticker, signal_date, bucket, rank,
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
            "bucket": bucket, "mle_rank10d": rank,
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
