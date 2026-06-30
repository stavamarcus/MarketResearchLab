"""
MLEBucketsIRCGrid_v1 — MLE Rank Buckets x IRC Tailwind

Research Project: RP-0008-MLE-BUCKETS-IRC

Otazka:
    Dokaze IRC zachranit slabsi MLE buckety, nebo IRC pomaha hlavne
    uz silnym MLE kandidatum?

Grid:
    MLE buckety: 1-10, 11-20, 21-30, 31-50, 51-70, 71-100
    IRC:         TOP10 / HEADWIND
    = 12 kombinaci

Pro kazdou bunku gridu pocitame median 30D alpha vs SPY.

Klicove otazky (H-001 az H-003):
    1. Ma TOP10 MLE edge i bez IRC?
    2. Potrebuje bucket 11-30 IRC potvrzeni?
    3. Jsou 51+ kandidati mrtvi i s IRC?

Research Project: RP-0008-MLE-BUCKETS-IRC
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
IRC_TOP_MAX     = 10
FORWARD_WINDOWS = [10, 20, 30]
PRIMARY_WINDOW  = 30

MLE_BUCKETS = {
    "MLE_1_10":    (1, 10),
    "MLE_11_20":   (11, 20),
    "MLE_21_30":   (21, 30),
    "MLE_31_50":   (31, 50),
    "MLE_51_70":   (51, 70),
    "MLE_71_100":  (71, 100),
}
BUCKET_ORDER = list(MLE_BUCKETS.keys())


class MLEBucketsIRCGrid_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLEBucketsIRCGrid",
            version="1.0.0",
            hypothesis=(
                "MLE TOP10 ma kladnou alpha i bez IRC. MLE 11-30 potrebuje "
                "IRC TOP10 potvrzeni pro kladnou alpha. MLE 51+ zustava "
                "negativni i s IRC potvrzenim."
            ),
            description=(
                "MLE Rank Buckets x IRC Tailwind grid. Kombinuje "
                "KR-2026-06-MLE-rank-value-decay a KR-2026-06-MLE-IRC-rolling "
                "do jednoho testu — zjistuje, ktere MLE buckety potrebuji "
                "IRC potvrzeni a ktere ne."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_10d",
                "signal:IRC",
            ],
            parameters={
                "mle_buckets":    list(MLE_BUCKETS.keys()),
                "irc_top_max":    IRC_TOP_MAX,
                "irc_lookback":   IRC_LOOKBACK,
                "forward_windows": FORWARD_WINDOWS,
                "primary_window": PRIMARY_WINDOW,
                "primary_metric": "alpha_vs_spy",
                "spy_conid":      SPY_CONID,
                "min_observations": 10,
                "hypothesis_threshold": 0.5,
            },
            tags=["edge_validation", "MLE", "IRC", "rank_profile", "grid_search", "signal_interaction"],
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

        max_rank = max(hi for _, hi in MLE_BUCKETS.values())
        records = []

        for signal_date in eligible_days:
            ts = pd.Timestamp(signal_date)
            spy_entry = float(spy_prices.loc[ts, "close"]) if ts in spy_prices.index else None
            if spy_entry is None:
                continue

            all_snaps = query.assets(date=signal_date)
            for snap in all_snaps:
                rank = snap.mle_rank_10d
                if rank is None or rank > max_rank:
                    continue
                bucket = self._assign_bucket(rank)
                if bucket is None:
                    continue

                irc_rank = irc_index.get((ts, snap.industry))
                irc_group = "IRC_TOP" if (irc_rank is not None and irc_rank <= IRC_TOP_MAX) else "HEADWIND"

                rec = self._build_record(
                    snap.conid, snap.ticker, signal_date, bucket, irc_group, rank,
                    context, spy_entry, spy_prices,
                )
                if rec:
                    records.append(rec)

        if not records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        df = pd.DataFrame(records)

        stats_rows = []
        for bucket in BUCKET_ORDER:
            for irc_group in ["IRC_TOP", "HEADWIND"]:
                sub = df[(df["bucket"] == bucket) & (df["irc_group"] == irc_group)]
                if sub.empty:
                    continue
                row = {"bucket": bucket, "irc_group": irc_group, "n": len(sub)}
                for w in FORWARD_WINDOWS:
                    ac = f"alpha_{w}d"
                    av = sub[ac].dropna()
                    if av.empty:
                        continue
                    row[f"median_alpha_{w}d"]   = round(float(av.median()), 4)
                    row[f"win_rate_alpha_{w}d"] = round(float((av > 0).mean()), 4)
                stats_rows.append(row)

        stats_df = pd.DataFrame(stats_rows)
        pw = PRIMARY_WINDOW
        ac, wc = f"median_alpha_{pw}d", f"win_rate_alpha_{pw}d"

        def get(bucket, irc_group, col):
            r = stats_df[(stats_df["bucket"] == bucket) & (stats_df["irc_group"] == irc_group)]
            return float(r[col].iloc[0]) if not r.empty and col in r.columns and pd.notna(r[col].iloc[0]) else None

        threshold = self.define().parameters["hypothesis_threshold"]

        # H-001: TOP10 ma kladnou alpha i bez IRC (HEADWIND)
        top10_headwind = get("MLE_1_10", "HEADWIND", ac)
        h001 = top10_headwind is not None and top10_headwind > 0

        # H-002: 11-30 (kombinace 11_20 a 21_30) potrebuje IRC
        h002_results = {}
        for b in ["MLE_11_20", "MLE_21_30"]:
            hw = get(b, "HEADWIND", ac)
            irc = get(b, "IRC_TOP", ac)
            h002_results[b] = {
                "headwind": hw, "irc_top": irc,
                "needs_irc": (hw is not None and irc is not None and hw <= 0 and irc > 0),
            }
        h002 = any(v["needs_irc"] for v in h002_results.values())

        # H-003: 51+ zustava negativni i s IRC
        h003_results = {}
        for b in ["MLE_51_70", "MLE_71_100"]:
            irc = get(b, "IRC_TOP", ac)
            h003_results[b] = irc
        h003 = all(v is not None and v <= 0 for v in h003_results.values() if v is not None)

        metrics = {
            "n_records_total":  len(df),
            "n_eligible_days":  len(eligible_days),
            "primary_window_d": pw,
            "primary_metric":   "alpha_vs_spy",
            "h001_top10_positive_without_irc": h001,
            "h001_top10_headwind_alpha": top10_headwind,
            "h002_some_bucket_needs_irc": h002,
            "h003_51plus_dead_even_with_irc": h003,
        }
        for _, row in stats_df.iterrows():
            key = f"{row['bucket']}_{row['irc_group']}"
            metrics[f"{key}_n"] = int(row["n"])
            if ac in row and pd.notna(row.get(ac)):
                metrics[f"{key}_median_alpha_30d"] = row[ac]
            if wc in row and pd.notna(row.get(wc)):
                metrics[f"{key}_wr_alpha_30d"] = row[wc]

        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def yn(v): return "ANO" if v else "NE"

        lines = [
            "MLE Rank Buckets x IRC Tailwind",
            "Question: Can IRC rescue weaker MLE buckets, or does it mainly help strong ones?",
            "",
            f"Metrika: alpha vs SPY  |  Primary: {pw}D  |  IRC TOP{IRC_TOP_MAX}",
            "",
            f"{'Bucket':<14}{'HEADWIND':>14}{'IRC_TOP':>14}{'Diff':>10}",
        ]
        for bucket in BUCKET_ORDER:
            hw = get(bucket, "HEADWIND", ac)
            irc = get(bucket, "IRC_TOP", ac)
            diff = round(irc - hw, 2) if (hw is not None and irc is not None) else None
            lines.append(f"{bucket:<14}{fmt(hw):>14}{fmt(irc):>14}{fmt(diff):>10}")

        lines += [
            "",
            f"H-001 (TOP10 kladna i bez IRC): {yn(h001)}  [{fmt(top10_headwind)}]",
            f"H-002 (11-30 potrebuje IRC):    {yn(h002)}",
        ]
        for b, v in h002_results.items():
            lines.append(f"   {b}: HEADWIND={fmt(v['headwind'])}, IRC_TOP={fmt(v['irc_top'])}, potrebuje_IRC={yn(v['needs_irc'])}")
        lines += [
            f"H-003 (51+ mrtve i s IRC):      {yn(h003)}",
            "",
            f"N celkem: {len(df):,} | Dny: {len(eligible_days)}",
            f"Rozsah: {context.config.date_from} -> {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"grid_stats": stats_df},
            summary="\n".join(lines),
        )

    def _assign_bucket(self, rank: int) -> str | None:
        for bucket_name, (lo, hi) in MLE_BUCKETS.items():
            if lo <= rank <= hi:
                return bucket_name
        return None

    def _build_record(self, conid, ticker, signal_date, bucket, irc_group, rank,
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
            "bucket": bucket, "irc_group": irc_group, "mle_rank10d": rank,
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
