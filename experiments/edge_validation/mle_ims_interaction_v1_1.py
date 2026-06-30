"""
MLEIMSInteraction_v1_1 — IMS as prioritization WITHIN MLE TOP20

Research Project: RP-0003-MLE-CONDITIONED-IMS

Otazka:
    Pomaha IMS radit kandidaty UVNITR MLE TOP20?

Na rozdil od v1.0.0:
    v1.0.0 srovnaval MLE_ONLY vs MLE+IMS_bucket jako oddelene skupiny
    (MLE_ONLY = MLE TOP20 BEZ IMS bucketu, tedy IMS<70 nebo chybi).
    To byla otazka "prekryv dvou nezavislych mnozin".

    v1.1.0 bere VSECHNY MLE TOP20 kandidaty (fixni zakladni mnozina)
    a uvnitr ni rozdeluje podle IMS skore. Kazda skupina je PODMNOZINA
    stejne zakladni mnoziny MLE TOP20 — primo srovnatelne.

Skupiny (vsechny UVNITR MLE rank_10d <= 20):
    IMS_MISSING  — MLE TOP20, IMS signal vubec neexistuje
    IMS_<70      — MLE TOP20, IMS score < 70
    IMS_70_79    — MLE TOP20, IMS score 70-79
    IMS_80_89    — MLE TOP20, IMS score 80-89
    IMS_90_94    — MLE TOP20, IMS score 90-94
    IMS_95plus   — MLE TOP20, IMS score >= 95

Metrika: alpha vs SPY (standard), 30D primary.

Research Project: RP-0003-MLE-CONDITIONED-IMS
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

# Skupiny, v poradi od nejnizsiho k nejvyssimu IMS — pro kontrolu monotonie
GROUPS_ORDER = ["IMS_MISSING", "IMS_<70", "IMS_70_79", "IMS_80_89", "IMS_90_94", "IMS_95plus"]


class MLEIMSInteraction_v1_1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLEIMSInteraction",
            version="1.1.0",
            hypothesis=(
                "MLE TOP20 kandidati s vyssim IMS skore maji vyssi 30D "
                "alpha vs SPY nez MLE TOP20 kandidati s nizkym nebo "
                "chybejicim IMS skore."
            ),
            description=(
                "IMS jako prioritizace UVNITR MLE TOP20 — ne prekryv "
                "nezavislych mnozin (viz v1.0.0). Vsechny skupiny jsou "
                "podmnoziny stejne zakladni mnoziny MLE TOP20."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_10d",
                "feature:IMS_Score",
            ],
            parameters={
                "mle_rank_max":      MLE_RANK_MAX,
                "groups_order":      GROUPS_ORDER,
                "forward_windows":   FORWARD_WINDOWS,
                "primary_window":    PRIMARY_WINDOW,
                "primary_metric":    "alpha_vs_spy",
                "spy_conid":         SPY_CONID,
                "min_observations":  10,
                "hypothesis_threshold": 0.5,
            },
            tags=["edge_validation", "MLE", "IMS", "alpha", "prioritization", "signal_interaction"],
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

            # ZAKLADNI MNOZINA: vsichni MLE TOP20 kandidati pro tento den
            all_snaps = query.assets(date=signal_date)
            mle_snaps = [
                s for s in all_snaps
                if s.mle_rank_10d is not None and s.mle_rank_10d <= MLE_RANK_MAX
            ]
            if not mle_snaps:
                continue

            for snap in mle_snaps:
                group = self._assign_group(snap.ims_score)
                rec = self._build_record(
                    snap.conid, snap.ticker, signal_date, group,
                    snap.mle_rank_10d, snap.ims_score,
                    context, spy_entry, spy_prices,
                )
                if rec:
                    records.append(rec)

        if not records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        df = pd.DataFrame(records)

        stats_rows = []
        for group in GROUPS_ORDER:
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

        alphas_by_group = {g: get(g, ac) for g in GROUPS_ORDER}
        lowest  = alphas_by_group.get("IMS_<70")
        # HLAVNI HYPOTEZA: IMS_<70 vs IMS_90_94 (oba buckety maji rozumne N)
        # IMS_95plus je EXPLORATORNI ONLY — N typicky < 10, nelze stavet hypotezu na nem
        # (viz KR-2026-06-IMS-missing-diagnosis, doporuceni architekta 2026-06-30)
        highest = alphas_by_group.get("IMS_90_94")

        threshold = self.define().parameters["hypothesis_threshold"]
        h_supported = (
            lowest is not None and highest is not None
            and (highest - lowest) > threshold
        )

        # IMS_95plus je vzdy exploratory-only kvuli malemu N — nikdy nevstupuje do H
        n_95plus = None
        row_95 = stats_df[stats_df["group"] == "IMS_95plus"]
        if not row_95.empty:
            n_95plus = int(row_95["n"].iloc[0])

        # Test monotonie: srovnej postupne IMS_<70 < 70_79 < 80_89 < 90_94
        ordered_vals = [alphas_by_group.get(g) for g in
                         ["IMS_<70", "IMS_70_79", "IMS_80_89", "IMS_90_94"]]
        ordered_vals = [v for v in ordered_vals if v is not None]
        is_monotonic = all(
            ordered_vals[i] <= ordered_vals[i+1]
            for i in range(len(ordered_vals)-1)
        ) if len(ordered_vals) >= 2 else False

        metrics = {
            "n_records_total":    len(df),
            "n_eligible_days":    len(eligible_days),
            "mle_rank_max":       MLE_RANK_MAX,
            "primary_window_d":   pw,
            "primary_metric":     "alpha_vs_spy",
            "hypothesis_definition": "IMS_<70 vs IMS_90_94 (IMS_95plus EXCLUDED — exploratory only)",
            "ims_low_median_alpha":   lowest,
            "ims_high_median_alpha":  highest,
            "diff_high_vs_low":   round(highest - lowest, 4) if (highest is not None and lowest is not None) else None,
            "h_supported":        h_supported,
            "is_monotonic":       is_monotonic,
            "ims_95plus_n_exploratory_only": n_95plus,
        }
        for _, row in stats_df.iterrows():
            g = row["group"].replace("<", "lt_")
            metrics[f"{g}_n"] = int(row["n"])
            if ac in row and pd.notna(row.get(ac)):
                metrics[f"{g}_median_alpha_30d"] = row[ac]
            if wc in row and pd.notna(row.get(wc)):
                metrics[f"{g}_wr_alpha_30d"] = row[wc]

        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def sup(v): return "SUPPORTED" if v else "NOT SUPPORTED"

        lines = [
            "MLE x IMS Interaction v1.1.0",
            "Question: Does IMS help RANK candidates WITHIN MLE TOP20?",
            "",
            f"Zakladni mnozina: MLE rank_10d <= {MLE_RANK_MAX}  |  Metrika: alpha vs SPY  |  Window: {pw}D",
            "Vsechny skupiny nize jsou PODMNOZINY teto zakladni mnoziny.",
            "",
            "Skupiny:",
        ]
        for _, row in stats_df.iterrows():
            a, w, n = row.get(ac), row.get(wc), int(row.get("n", 0))
            if a is not None and w is not None:
                lines.append(f"  {row['group']:<14} alpha={fmt(a)}  WR={w*100:.1f}%  N={n}")
            else:
                lines.append(f"  {row['group']:<14} N={n}")
        lines += [
            "",
            "HLAVNI HYPOTEZA: IMS_<70 vs IMS_90_94 (oba buckety N>200)",
            f"Diff (IMS_90_94 vs IMS_<70): {fmt(metrics['diff_high_vs_low'])}",
            f"Monotonni rust pres IMS<70 -> 70-79 -> 80-89 -> 90-94: {is_monotonic}",
            "",
            f"H (IMS_90_94 > IMS_<70 + {threshold}pp alpha): {sup(h_supported)}",
            "",
        ]
        if n_95plus is not None:
            lines.append(
                f"POZNAMKA: IMS_95plus (N={n_95plus}) je EXPLORATORY ONLY — "
                f"nevstupuje do hypotezy kvuli malemu vzorku (viz KR-2026-06-IMS-missing-diagnosis)."
            )
            lines.append("")
        lines += [
            f"N celkem: {len(df):,} | Dny: {len(eligible_days)}",
            f"Rozsah: {context.config.date_from} -> {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"group_stats": stats_df},
            summary="\n".join(lines),
        )

    def _assign_group(self, ims_score) -> str:
        if ims_score is None:
            return "IMS_MISSING"
        if ims_score < 70:
            return "IMS_<70"
        if ims_score < 80:
            return "IMS_70_79"
        if ims_score < 90:
            return "IMS_80_89"
        if ims_score < 95:
            return "IMS_90_94"
        return "IMS_95plus"

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
