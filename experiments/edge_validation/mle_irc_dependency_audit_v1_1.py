"""
MLEIRCDependencyAudit_v1_1 — MLE × IRC Dependency Audit v1.1.0

Cíl:
    Reprodukovat metodiku starého Test 7 (IRC audit test_cross_module.py)
    v MRL frameworku. Ověřit zda MRL dává konzistentní výsledky.

Metodika (identická se starým auditem):
    MLE filtr:  rank_10d <= 20  (TOP20 akcií, 10D lookback)
    IRC filtr:  rank <= 10      (TOP10 industries z 59)
    Metrika:    alpha vs SPY    (excess return, ne absolutní return)
    Window:     30D primary

Skupiny:
    MLE+IRC_TOP10  — MLE TOP20 + industry rank <= 10
    MLE_HEADWIND   — MLE TOP20 + industry rank > 10
    MLE_IRC_MISS   — MLE TOP20 bez IRC mappingu

Srovnání s v1.0.0:
    v1.0.0: rank_20d <= 50, IRC TOP20, absolutní return
    v1.1.0: rank_10d <= 20, IRC TOP10, alpha vs SPY

Research Project: RP-0001-SIGNAL-INTERACTION
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
MLE_RANK_MAX    = 20
MLE_RANK_FIELD  = "MLE_Rank_10d"
IRC_TOP_MAX     = 10
IRC_LOOKBACK    = 20
FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 30


class MLEIRCDependencyAudit_v1_1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLEIRCDependencyAudit",
            version="1.1.0",
            hypothesis=(
                "MLE TOP20 (10D) kandidáti v TOP10 IRC industries dosahují "
                "vyšší median alpha vs SPY (30D) než MLE TOP20 kandidáti "
                "v slabších industries."
            ),
            description=(
                "Reprodukce metodiky IRC Audit Test 7 v MRL. "
                "MLE: rank_10d <= 20. IRC: rank <= 10. Metrika: alpha vs SPY. "
                "Srovnatelné s původním auditem."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_10d",
                "signal:IRC",
            ],
            parameters={
                "mle_rank_field":   MLE_RANK_FIELD,
                "mle_rank_max":     MLE_RANK_MAX,
                "irc_rank_max":     IRC_TOP_MAX,
                "irc_lookback":     IRC_LOOKBACK,
                "forward_windows":  FORWARD_WINDOWS,
                "primary_window":   PRIMARY_WINDOW,
                "primary_metric":   "alpha_vs_spy",
                "spy_conid":        SPY_CONID,
                "min_observations": 10,
            },
            tags=["edge_validation", "MLE", "IRC", "alpha", "reproduction", "signal_interaction"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle_features = context.features.all_for_name(MLE_RANK_FIELD)
        if len(mle_features) < self.define().parameters["min_observations"]:
            return ValidationResult.failed(
                f"Prilis malo {MLE_RANK_FIELD} zaznamu: {len(mle_features)}"
            )
        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed("IRC chybi v context.signals.")
        if SPY_CONID not in context.prices:
            return ValidationResult.failed(
                f"SPY (conid={SPY_CONID}) neni v context.prices. "
                "Pridej SPY conid do universe nebo nacti separatne."
            )
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

        records = []

        for signal_date in eligible_days:
            ts = pd.Timestamp(signal_date)

            # Filtr: MLE rank_10d <= 20 (ne rank_20d jako v query.assets default)
            all_snaps = query.assets(date=signal_date)
            snapshots = [
                s for s in all_snaps
                if s.mle_rank_10d is not None and s.mle_rank_10d <= MLE_RANK_MAX
            ]
            snapshots.sort(key=lambda s: s.mle_rank_10d or 9999)
            if not snapshots:
                continue

            spy_entry = float(spy_prices.loc[ts, "close"]) if ts in spy_prices.index else None

            for snap in snapshots:
                irc_rank = irc_index.get((ts, snap.industry))
                if irc_rank is None:
                    group = "MLE_IRC_MISS"
                elif irc_rank <= IRC_TOP_MAX:
                    group = "MLE+IRC_TOP10"
                else:
                    group = "MLE_HEADWIND"

                rec = self._build_record(
                    snap.conid, snap.ticker, signal_date,
                    snap.industry, irc_rank, group,
                    snap.mle_rank_10d, context, spy_entry, spy_prices,
                )
                if rec:
                    records.append(rec)

        if not records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        df = pd.DataFrame(records)

        groups_order = ["MLE+IRC_TOP10", "MLE_HEADWIND", "MLE_IRC_MISS"]
        stats_rows = []
        for group in groups_order:
            sub = df[df["group"] == group]
            if sub.empty:
                continue
            row = {"group": group, "n": len(sub), "unique_tickers": sub["ticker"].nunique()}
            for w in FORWARD_WINDOWS:
                ac = f"alpha_{w}d"
                fc = f"fwd_{w}d"
                av = sub[ac].dropna()
                fv = sub[fc].dropna()
                if av.empty:
                    continue
                row[f"median_alpha_{w}d"]   = round(float(av.median()), 4)
                row[f"mean_alpha_{w}d"]     = round(float(av.mean()), 4)
                row[f"win_rate_alpha_{w}d"] = round(float((av > 0).mean()), 4)
                row[f"median_fwd_{w}d"]     = round(float(fv.median()), 4) if not fv.empty else None
                row[f"n_valid_{w}d"]        = len(av)
            stats_rows.append(row)

        stats_df = pd.DataFrame(stats_rows)
        pw = PRIMARY_WINDOW
        ac = f"median_alpha_{pw}d"
        wc = f"win_rate_alpha_{pw}d"

        def get(grp, col):
            r = stats_df[stats_df["group"] == grp]
            return float(r[col].iloc[0]) if not r.empty and col in r.columns and pd.notna(r[col].iloc[0]) else None

        top10_alpha = get("MLE+IRC_TOP10", ac)
        head_alpha  = get("MLE_HEADWIND",  ac)
        top10_wr    = get("MLE+IRC_TOP10", wc)
        head_wr     = get("MLE_HEADWIND",  wc)

        all_mle = df[df["group"].isin(["MLE+IRC_TOP10", "MLE_HEADWIND"])]
        mle_all_alpha = round(float(all_mle[f"alpha_{pw}d"].dropna().median()), 4) if not all_mle.empty else None

        diff = round(top10_alpha - head_alpha, 4) if (top10_alpha is not None and head_alpha is not None) else None
        h_supported = diff is not None and diff > 0.5

        metrics = {
            "n_records_total":             len(df),
            "n_eligible_days":             len(eligible_days),
            "mle_rank_field":              MLE_RANK_FIELD,
            "mle_rank_max":                MLE_RANK_MAX,
            "irc_rank_max":                IRC_TOP_MAX,
            "primary_window_d":            pw,
            "primary_metric":              "alpha_vs_spy",
            "mle_all_median_alpha_30d":    mle_all_alpha,
            "mle_irc_top10_median_alpha":  top10_alpha,
            "mle_headwind_median_alpha":   head_alpha,
            "mle_irc_top10_wr_alpha":      top10_wr,
            "mle_headwind_wr_alpha":       head_wr,
            "diff_top10_vs_headwind":      diff,
            "h_supported":                 h_supported,
        }
        for _, row in stats_df.iterrows():
            g = row["group"].replace("+", "_")
            metrics[f"{g}_n"] = int(row["n"])
            if ac in row and pd.notna(row.get(ac)):
                metrics[f"{g}_median_alpha_30d"] = row[ac]
            if wc in row and pd.notna(row.get(wc)):
                metrics[f"{g}_wr_alpha_30d"] = row[wc]

        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def sup(v): return "SUPPORTED" if v else "NOT SUPPORTED"

        lines = [
            "MLE x IRC Dependency Audit v1.1.0",
            "Reprodukce metodiky IRC Audit Test 7",
            "",
            f"MLE: rank_10d <= {MLE_RANK_MAX}  |  IRC: TOP{IRC_TOP_MAX}  |  Metrika: alpha vs SPY",
            f"Primary: {pw}D median alpha",
            "",
            "Skupiny:",
        ]
        for _, row in stats_df.iterrows():
            a = row.get(ac)
            w = row.get(wc)
            n = int(row.get("n", 0))
            if a is not None and w is not None:
                lines.append(f"  {row['group']:<20} alpha={fmt(a)}  WR={w*100:.1f}%  N={n}")
            else:
                lines.append(f"  {row['group']:<20} N={n}")
        lines += [
            "",
            f"MLE all (bez IRC filtru): {fmt(mle_all_alpha)}",
            f"Diff (TOP10 vs HEADWIND): {fmt(diff)}",
            "",
            f"H (TOP10 > HEADWIND + 0.5pp alpha): {sup(h_supported)}",
            "",
            f"N celkem: {len(df):,} | Dny: {len(eligible_days)}",
            f"Rozsah: {context.config.date_from} -> {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"group_stats": stats_df},
            summary="\n".join(lines),
        )

    def _build_record(self, conid, ticker, signal_date, industry,
                      irc_rank, group, mle_rank_10d,
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
            "industry": industry, "irc_rank": irc_rank,
            "group": group, "mle_rank10d": mle_rank_10d,
        }

        for w in FORWARD_WINDOWS:
            fwd_ts = self._nearest_date(price_df, signal_date + timedelta(days=w))
            if fwd_ts is None:
                record[f"fwd_{w}d"] = np.nan
                record[f"alpha_{w}d"] = np.nan
                continue
            fwd_ret = (float(price_df.loc[fwd_ts, "close"]) / entry_price - 1) * 100
            record[f"fwd_{w}d"] = round(fwd_ret, 4)
            if spy_entry and spy_entry > 0:
                spy_fwd_ts = self._nearest_date(spy_prices, signal_date + timedelta(days=w))
                if spy_fwd_ts is not None:
                    spy_ret = (float(spy_prices.loc[spy_fwd_ts, "close"]) / spy_entry - 1) * 100
                    record[f"alpha_{w}d"] = round(fwd_ret - spy_ret, 4)
                else:
                    record[f"alpha_{w}d"] = np.nan
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
