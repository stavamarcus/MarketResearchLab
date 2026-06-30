"""
MLEIRCDependencyAudit_v1 — MLE × IRC Dependency Audit

Research Project: RP-0001-SIGNAL-INTERACTION / RP-2026-06-30-MLE-IRC-DEPENDENCY

Otázka:
    Má MLE edge větší hodnotu, když je ticker zároveň v silné industry podle IRC?

Skupiny:
    MLE_only        — MLE signál, industry bez IRC podpory (IRC_MISSING nebo IRC_WEAK)
    MLE + IRC_TOP   — MLE signál + industry rank <= 20
    MLE + IRC_MID   — MLE signál + industry rank 21–60
    MLE + IRC_WEAK  — MLE signál + industry rank > 60
    MLE + IRC_MISS  — MLE signál, ale industry není v IRC k danému datu
    IRC_strong_only — industry v IRC_TOP, ale ticker NENÍ v MLE (kontrolní skupina)

Point-in-time pravidlo:
    IRC rank musí být znám k datu signálu.
    Join: mle.date == irc.date AND ticker_industry == irc.industry
    Industry: MLE ticker → universe.industry (ne MLE.industry — 99.2% NaN)
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

# IRC bucket definice
IRC_TOP_MAX  = 20
IRC_MID_MAX  = 60
IRC_LOOKBACK = 20   # lookback pro IRC rank

FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 30

MLE_RANK_MAX = 50   # MLE TOP50 jako základní filtr


class MLEIRCDependencyAudit_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLEIRCDependencyAudit",
            version="1.0.0",
            hypothesis=(
                "MLE kandidáti v silných IRC industries (rank <= 20) dosahují "
                "vyššího median 30D forward returnu než MLE kandidáti bez IRC podpory."
            ),
            description=(
                "MLE × IRC Dependency Audit. "
                "Testuje zda IRC industry context zvyšuje kvalitu MLE selekce. "
                "Point-in-time join: IRC rank k datu MLE signálu."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_20d",
                "signal:IRC",
            ],
            parameters={
                "mle_rank_max":  MLE_RANK_MAX,
                "irc_lookback":  IRC_LOOKBACK,
                "irc_top_max":   IRC_TOP_MAX,
                "irc_mid_max":   IRC_MID_MAX,
                "forward_windows": FORWARD_WINDOWS,
                "primary_window":  PRIMARY_WINDOW,
                "min_observations": 20,
            },
            tags=["edge_validation", "MLE", "IRC", "dependency", "signal_interaction"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle_features = context.features.all_for_name("MLE_Rank_20d")
        if len(mle_features) < self.define().parameters["min_observations"]:
            return ValidationResult.failed(
                f"Příliš málo MLE_Rank_20d záznamů: {len(mle_features)}"
            )

        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed(
                "IRC signál chybí v context.signals. "
                "Přidej IRC do SignalProvider nebo načti přes load_signals()."
            )

        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        query = ResearchQuery(context)
        params = self.define().parameters

        # IRC DataFrame — point-in-time, lookback 20
        irc_df = context.signals["IRC"].copy()
        irc_df = irc_df[irc_df["lookback"] == params["irc_lookback"]]
        irc_df["date"] = pd.to_datetime(irc_df["date"])

        # Index pro rychlý lookup: (date, industry) → rank
        irc_index = irc_df.set_index(["date", "industry"])["rank"].to_dict()

        # Trading days
        trading_days = query.dates()
        if not trading_days:
            return ExperimentResult(
                metrics={"error": "no_trading_days"},
                summary="Žádné obchodní dny.",
            )

        cutoff = trading_days[-1] - timedelta(days=PRIMARY_WINDOW + 10)
        eligible_days = [d for d in trading_days if d <= cutoff]

        records = []
        max_window = max(FORWARD_WINDOWS)

        for signal_date in eligible_days:
            ts = pd.Timestamp(signal_date)

            # MLE TOP50 k danému datu
            mle_snapshots = query.assets(
                date=signal_date,
                mle_rank_max=params["mle_rank_max"],
            )
            if not mle_snapshots:
                continue

            # Všechny akcie s cenou pro IRC_strong_only skupinu
            all_snapshots = query.assets(date=signal_date)
            mle_conids = {s.conid for s in mle_snapshots}

            # Zpracování MLE signálů
            for snap in mle_snapshots:
                irc_rank = irc_index.get((ts, snap.industry))
                group = self._assign_group(irc_rank, in_mle=True)

                record = self._build_record(
                    snap.conid, snap.ticker, signal_date,
                    snap.industry, irc_rank, group,
                    snap.mle_rank_20d, context,
                )
                if record:
                    records.append(record)

            # IRC_strong_only — v IRC_TOP ale NENÍ v MLE
            irc_top_industries = {
                ind for (dt, ind), rank in irc_index.items()
                if dt == ts and rank <= IRC_TOP_MAX
            }
            for snap in all_snapshots:
                if snap.conid in mle_conids:
                    continue
                if snap.industry not in irc_top_industries:
                    continue
                irc_rank = irc_index.get((ts, snap.industry))
                record = self._build_record(
                    snap.conid, snap.ticker, signal_date,
                    snap.industry, irc_rank, "IRC_strong_only",
                    None, context,
                )
                if record:
                    records.append(record)

        if not records:
            return ExperimentResult(
                metrics={"error": "no_records"},
                summary="Žádné záznamy.",
            )

        df = pd.DataFrame(records)

        # Agregace per skupina
        groups = [
            "MLE+IRC_TOP", "MLE+IRC_MID", "MLE+IRC_WEAK",
            "MLE+IRC_MISS", "IRC_strong_only",
        ]
        stats_rows = []
        for group in groups:
            sub = df[df["group"] == group]
            if sub.empty:
                continue
            row = {
                "group":          group,
                "n":              len(sub),
                "unique_tickers": sub["ticker"].nunique(),
            }
            for w in FORWARD_WINDOWS:
                col = f"fwd_{w}d"
                vals = sub[col].dropna()
                if vals.empty:
                    continue
                row[f"median_return_{w}d"] = round(float(vals.median()), 4)
                row[f"mean_return_{w}d"]   = round(float(vals.mean()), 4)
                row[f"win_rate_{w}d"]      = round(float((vals > 0).mean()), 4)
                row[f"p25_return_{w}d"]    = round(float(vals.quantile(0.25)), 4)
                row[f"p75_return_{w}d"]    = round(float(vals.quantile(0.75)), 4)
            stats_rows.append(row)

        stats_df = pd.DataFrame(stats_rows)

        # Metriky hypotéz
        pw = PRIMARY_WINDOW
        col_med = f"median_return_{pw}d"
        col_wr  = f"win_rate_{pw}d"

        def get(grp, col):
            row = stats_df[stats_df["group"] == grp]
            return float(row[col].iloc[0]) if not row.empty and col in row else None

        mle_irc_top  = get("MLE+IRC_TOP",      col_med)
        mle_irc_weak = get("MLE+IRC_WEAK",      col_med)
        mle_irc_miss = get("MLE+IRC_MISS",      col_med)
        irc_only     = get("IRC_strong_only",   col_med)

        mle_irc_top_wr  = get("MLE+IRC_TOP",    col_wr)
        mle_irc_weak_wr = get("MLE+IRC_WEAK",   col_wr)

        # Referenční hodnota MLE bez IRC filtru
        mle_all_vals = df[df["group"].str.startswith("MLE")][f"fwd_{pw}d"].dropna()
        mle_all_median = round(float(mle_all_vals.median()), 4) if not mle_all_vals.empty else None

        h002 = (
            mle_irc_top is not None and mle_all_median is not None
            and (mle_irc_top - mle_all_median) > 0.5
        )
        h003 = (
            mle_irc_top_wr is not None and mle_irc_weak_wr is not None
            and (mle_irc_top_wr - mle_irc_weak_wr) > 0.03
        )
        h004 = (
            mle_irc_top is not None and irc_only is not None
            and mle_irc_top > irc_only
        )

        metrics = {
            "n_records_total":     len(df),
            "n_eligible_days":     len(eligible_days),
            "mle_rank_max":        params["mle_rank_max"],
            "irc_lookback":        params["irc_lookback"],
            "primary_window_d":    pw,
            "mle_all_median_30d":  mle_all_median,
            "mle_irc_top_median_30d":  mle_irc_top,
            "mle_irc_weak_median_30d": mle_irc_weak,
            "mle_irc_miss_median_30d": mle_irc_miss,
            "irc_strong_only_median_30d": irc_only,
            "mle_irc_top_wr_30d":  mle_irc_top_wr,
            "mle_irc_weak_wr_30d": mle_irc_weak_wr,
            "h002_supported": h002,
            "h003_supported": h003,
            "h004_supported": h004,
        }

        # Per-skupina metriky
        for _, row in stats_df.iterrows():
            g = row["group"].replace("+", "_").replace("-", "_")
            metrics[f"{g}_n"] = int(row["n"])
            if col_med in row:
                metrics[f"{g}_median_30d"] = row[col_med]
            if col_wr in row:
                metrics[f"{g}_wr_30d"] = row[col_wr]

        # Summary
        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def sup(v): return "✓ SUPPORTED" if v else "✗ NOT SUPPORTED"

        lines = [
            "MLE × IRC Dependency Audit",
            "Question: Does IRC context improve MLE forward returns?",
            "",
            f"Primary metric: {pw}D median forward return",
            "",
            "Groups:",
        ]
        for _, row in stats_df.iterrows():
            med = row.get(col_med)
            wr  = row.get(col_wr)
            n   = int(row.get("n", 0))
            lines.append(
                f"  {row['group']:<22} median={fmt(med)}  WR={wr*100:.1f}%  N={n}"
                if med is not None and wr is not None
                else f"  {row['group']:<22} N={n}"
            )
        lines += [
            "",
            f"MLE all (bez IRC filtru): {fmt(mle_all_median)}",
            "",
            f"H-002 (MLE+IRC_TOP > MLE_all + 0.5pp): {sup(h002)}",
            f"         diff={mle_irc_top - mle_all_median:.2f}pp ({mle_irc_top:.2f}% vs {mle_all_median:.2f}%)",
            f"H-003 (WR TOP vs WEAK > 3pp):          {sup(h003)}",
            f"H-004 (MLE+IRC_TOP > IRC_only):        {sup(h004)}",
            "",
            f"N celkem: {len(df):,} | Dny: {len(eligible_days)}",
            f"Rozsah: {context.config.date_from} → {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"group_stats": stats_df},
            summary="\n".join(lines),
        )

    # ------------------------------------------------------------------
    # Interní helpery
    # ------------------------------------------------------------------

    def _assign_group(self, irc_rank, in_mle: bool) -> str:
        if not in_mle:
            return "IRC_strong_only"
        if irc_rank is None:
            return "MLE+IRC_MISS"
        if irc_rank <= IRC_TOP_MAX:
            return "MLE+IRC_TOP"
        if irc_rank <= IRC_MID_MAX:
            return "MLE+IRC_MID"
        return "MLE+IRC_WEAK"

    def _build_record(
        self, conid, ticker, signal_date, industry,
        irc_rank, group, mle_rank, context,
    ) -> dict | None:
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
            "date":     signal_date,
            "conid":    conid,
            "ticker":   ticker,
            "industry": industry,
            "irc_rank": irc_rank,
            "group":    group,
            "mle_rank": mle_rank,
        }

        for w in FORWARD_WINDOWS:
            fwd_ts = self._nearest_date(price_df, signal_date + timedelta(days=w))
            if fwd_ts is None:
                record[f"fwd_{w}d"] = np.nan
            else:
                fwd_price = float(price_df.loc[fwd_ts, "close"])
                record[f"fwd_{w}d"] = round((fwd_price / entry_price - 1) * 100, 4)

        return record

    @staticmethod
    def _nearest_date(price_df, target, max_offset=5):
        for i in range(max_offset + 1):
            ts = pd.Timestamp(target + timedelta(days=i))
            if ts in price_df.index:
                return ts
        return None
