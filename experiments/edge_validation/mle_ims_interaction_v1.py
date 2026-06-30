"""
MLEIMSInteraction_v1 — MLE x IMS Signal Interaction

Research Project: RP-0002-MLE-IMS-INTERACTION

Otazka:
    Je kombinace MLE a IMS lepsi nez kazdy modul samostatne?
    Prida silna institucionalni podpora (IMS) hodnotu k cenovemu
    leadershipu (MLE)?

Metodika:
    MLE filtr:  rank_10d <= 20  (stejne jako MLE x IRC v1.1.0 pro konzistenci)
    IMS buckety: 70-79, 80-89, 90-94 (legacy konvence)
    Metrika:    alpha vs SPY (standard zavedeny KR-2026-06-MLE-IRC-interaction)
    Window:     30D primary

Na rozdil od MLE x IRC:
    Oba signaly (MLE, IMS) jsou asset-level (conid-level).
    Zadny industry join potreba — primy lookup pres FeatureSet.

Skupiny:
    MLE_ONLY        — MLE TOP20, IMS < 70 nebo chybi
    IMS_ONLY        — IMS >= 80, MLE rank_10d > 20
    MLE+IMS_70-79   — MLE TOP20 + IMS 70-79
    MLE+IMS_80-89   — MLE TOP20 + IMS 80-89
    MLE+IMS_90-94   — MLE TOP20 + IMS 90-94 (ELITE)

Research Project: RP-0002-MLE-IMS-INTERACTION
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
FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 30

IMS_BUCKETS = {
    "IMS_70-79": (70.0, 80.0),
    "IMS_80-89": (80.0, 90.0),
    "IMS_90-94": (90.0, 95.0),
}


class MLEIMSInteraction_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLEIMSInteraction",
            version="1.0.0",
            hypothesis=(
                "MLE TOP20 akcie s IMS score >= 90 (ELITE) dosahuji vyssi "
                "median 30D alpha vs SPY nez MLE TOP20 samotne nebo IMS "
                "samotne."
            ),
            description=(
                "Test MLE x IMS interaction. Oba signaly asset-level — "
                "primy lookup bez industry joinu. Alpha vs SPY jako "
                "primarni metrika (standard zavedeny KR-2026-06-MLE-IRC)."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_10d",
                "feature:IMS_Score",
            ],
            parameters={
                "mle_rank_max":     MLE_RANK_MAX,
                "ims_buckets":      list(IMS_BUCKETS.keys()),
                "forward_windows":  FORWARD_WINDOWS,
                "primary_window":   PRIMARY_WINDOW,
                "primary_metric":   "alpha_vs_spy",
                "spy_conid":        SPY_CONID,
                "min_observations": 10,
                "hypothesis_threshold": 0.5,
            },
            tags=["edge_validation", "MLE", "IMS", "alpha", "signal_interaction"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle_features = context.features.all_for_name("MLE_Rank_10d")
        ims_features = context.features.all_for_name("IMS_Score")
        if len(mle_features) < self.define().parameters["min_observations"]:
            return ValidationResult.failed(f"Prilis malo MLE_Rank_10d: {len(mle_features)}")
        if len(ims_features) < self.define().parameters["min_observations"]:
            return ValidationResult.failed(f"Prilis malo IMS_Score: {len(ims_features)}")
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
            if not all_snaps:
                continue

            for snap in all_snaps:
                is_mle = snap.mle_rank_10d is not None and snap.mle_rank_10d <= MLE_RANK_MAX
                ims_score = snap.ims_score

                group = self._assign_group(is_mle, ims_score)
                if group is None:
                    continue  # ani MLE, ani IMS >= 70 — irelevantni

                rec = self._build_record(
                    snap.conid, snap.ticker, signal_date, group,
                    snap.mle_rank_10d, ims_score,
                    context, spy_entry, spy_prices,
                )
                if rec:
                    records.append(rec)

        if not records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        df = pd.DataFrame(records)

        groups_order = [
            "MLE_ONLY", "IMS_ONLY",
            "MLE+IMS_70-79", "MLE+IMS_80-89", "MLE+IMS_90-94",
        ]
        stats_rows = []
        for group in groups_order:
            sub = df[df["group"] == group]
            if sub.empty:
                continue
            row = {"group": group, "n": len(sub), "unique_tickers": sub["ticker"].nunique()}
            for w in FORWARD_WINDOWS:
                ac, fc = f"alpha_{w}d", f"fwd_{w}d"
                av, fv = sub[ac].dropna(), sub[fc].dropna()
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

        def get(grp, col):
            r = stats_df[stats_df["group"] == grp]
            return float(r[col].iloc[0]) if not r.empty and col in r.columns and pd.notna(r[col].iloc[0]) else None

        mle_only_alpha  = get("MLE_ONLY",      ac)
        ims_only_alpha  = get("IMS_ONLY",      ac)
        elite_alpha     = get("MLE+IMS_90-94", ac)
        mid_alpha       = get("MLE+IMS_80-89", ac)
        low_alpha       = get("MLE+IMS_70-79", ac)

        threshold = self.define().parameters["hypothesis_threshold"]

        h001 = (elite_alpha is not None and mle_only_alpha is not None
                and (elite_alpha - mle_only_alpha) > threshold)

        candidates = [v for v in [mle_only_alpha, ims_only_alpha] if v is not None]
        h002 = (elite_alpha is not None and candidates
                and elite_alpha > max(candidates))

        h003 = (elite_alpha is not None and mid_alpha is not None and low_alpha is not None
                and elite_alpha > mid_alpha > low_alpha)

        metrics = {
            "n_records_total":     len(df),
            "n_eligible_days":     len(eligible_days),
            "mle_rank_max":        MLE_RANK_MAX,
            "primary_window_d":    pw,
            "primary_metric":      "alpha_vs_spy",
            "mle_only_median_alpha":   mle_only_alpha,
            "ims_only_median_alpha":   ims_only_alpha,
            "mle_ims_90_94_median_alpha": elite_alpha,
            "mle_ims_80_89_median_alpha": mid_alpha,
            "mle_ims_70_79_median_alpha": low_alpha,
            "h001_supported": h001,
            "h002_supported": h002,
            "h003_supported": h003,
        }
        for _, row in stats_df.iterrows():
            g = row["group"].replace("+", "_").replace("-", "_")
            metrics[f"{g}_n"] = int(row["n"])
            if ac in row and pd.notna(row.get(ac)):
                metrics[f"{g}_median_alpha_30d"] = row[ac]
            if wc in row and pd.notna(row.get(wc)):
                metrics[f"{g}_wr_alpha_30d"] = row[wc]

        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def sup(v): return "SUPPORTED" if v else "NOT SUPPORTED"

        lines = [
            "MLE x IMS Signal Interaction",
            "Question: Does MLE+IMS combination beat each module alone?",
            "",
            f"MLE: rank_10d <= {MLE_RANK_MAX}  |  Metrika: alpha vs SPY  |  Window: {pw}D",
            "",
            "Skupiny:",
        ]
        for _, row in stats_df.iterrows():
            a, w, n = row.get(ac), row.get(wc), int(row.get("n", 0))
            if a is not None and w is not None:
                lines.append(f"  {row['group']:<16} alpha={fmt(a)}  WR={w*100:.1f}%  N={n}")
            else:
                lines.append(f"  {row['group']:<16} N={n}")
        lines += [
            "",
            f"H-001 (MLE+IMS_90-94 > MLE_only + {threshold}pp): {sup(h001)}",
            f"H-002 (kombinace > kazdy modul samostatne):        {sup(h002)}",
            f"H-003 (monotonni rust 70-79 < 80-89 < 90-94):       {sup(h003)}",
            "",
            f"N celkem: {len(df):,} | Dny: {len(eligible_days)}",
            f"Rozsah: {context.config.date_from} -> {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"group_stats": stats_df},
            summary="\n".join(lines),
        )

    def _assign_group(self, is_mle: bool, ims_score) -> str | None:
        """
        Explicitni, jednoznacna pravidla — kazda kombinace (is_mle, ims_score)
        vede na presne jeden vystup. Zadne vedlejsi efekty cyklu.

        OPRAVA (2026-06-30): puvodni verze pouzivala for-cyklus ktery vracel
        None pro is_mle=False uvnitr cyklu pres IMS_BUCKETS, cimz tise
        zahazoval VSECHNY ne-MLE akcie s IMS skore >= 70 (tj. skoro vsechny
        kandidaty pro IMS_ONLY). Dusledek: IMS_ONLY mel N=6 namisto
        ocekavanych stovek zaznamu.
        """
        has_ims = ims_score is not None

        if is_mle:
            # MLE TOP20 — uvnitr rozlisujeme podle IMS bucketu
            if has_ims:
                for bucket_name, (lo, hi) in IMS_BUCKETS.items():
                    if lo <= ims_score < hi:
                        return f"MLE+{bucket_name}"
            # MLE TOP20, IMS < 70 nebo chybi
            return "MLE_ONLY"
        else:
            # Mimo MLE TOP20 — relevantni jen pokud IMS >= 80 (HIGH/ELITE pasmo)
            if has_ims and ims_score >= 80:
                return "IMS_ONLY"
            return None

    def _build_record(self, conid, ticker, signal_date, group,
                      mle_rank, ims_score, context, spy_entry, spy_prices):
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
            "group": group, "mle_rank10d": mle_rank, "ims_score": ims_score,
        }
        for w in FORWARD_WINDOWS:
            fwd_ts = self._nearest_date(price_df, signal_date + timedelta(days=w))
            if fwd_ts is None:
                record[f"fwd_{w}d"] = np.nan
                record[f"alpha_{w}d"] = np.nan
                continue
            fwd_ret = (float(price_df.loc[fwd_ts, "close"]) / entry_price - 1) * 100
            record[f"fwd_{w}d"] = round(fwd_ret, 4)
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
