"""
IRCPersistenceEdge_v1 — IRC Persistence Edge (industry-level, bez MLE)

Research Project: RP-0006-IRC-PERSISTENCE

Otazka:
    Maji persistentne silne industries vyssi nasledne alpha nez
    kratkodobe silne nebo slabe industries?

Klicovy rozdil oproti MLE x IRC:
    Toto je CISTE industry-level test. Zadny MLE filtr.
    Jednotka analyzy: industry-den, ne ticker-den.

Persistence buckety:
    NEW_TOP10        — 1-2 dny v IRC TOP10 za poslednich 20 obch. dni
    EMERGING_TOP10    — 3-5 dnu
    PERSISTENT_TOP10   — 6-15 dnu
    EXTENDED_TOP10      — 16-20 dnu

Metrika: industry-level alpha vs SPY (median forward return industry
constituents - SPY return), 30D primary.

Industry-level return = median forward return vsech tickeru v dane
industry k danemu datu (proxy, protoze IRC archiv neobsahuje primy
industry-index return — pouzivame median_return sloupec z IRC archivu
jako tento den, NE forward).

Pro FORWARD alpha potrebujeme vlastni vypocet: vezmeme median_return
sloupec z IRC archivu o forward_window dni pozdeji (IRC archiv jiz
obsahuje median_return = median return constituentu za dany lookback
window KONCICI tim dnem). Proto pouzivame jiny pristup: vezmeme
median_return industry o N dni pozdeji jako proxy pro forward performance.

Research Project: RP-0006-IRC-PERSISTENCE
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult

SPY_CONID    = 756733
IRC_LOOKBACK = 20
IRC_TOP_MAX  = 10
PERSISTENCE_WINDOW = 20  # kolik dni zpet pocitame persistenci

FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 30

PERSISTENCE_BUCKETS = {
    "NEW_TOP10":        (1, 2),
    "EMERGING_TOP10":   (3, 5),
    "PERSISTENT_TOP10": (6, 15),
    "EXTENDED_TOP10":   (16, 20),
}


class IRCPersistenceEdge_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="IRCPersistenceEdge",
            version="1.0.0",
            hypothesis=(
                "Industries persistentne v IRC TOP10 (6-15 dni za poslednich "
                "20 obchodnich dni) maji vyssi median 30D alpha nez nove "
                "vstoupive industries (1-2 dny)."
            ),
            description=(
                "IRC Persistence Edge — cisty industry-level test, bez MLE. "
                "Druhy nezavisly kandidat na robustni edge vedle MLE x IRC. "
                "Pouziva forward industry median return jako proxy pro "
                "industry-level forward performance."
            ),
            required_data=[
                "prices",
                "signal:IRC",
            ],
            parameters={
                "irc_lookback":       IRC_LOOKBACK,
                "irc_top_max":        IRC_TOP_MAX,
                "persistence_window": PERSISTENCE_WINDOW,
                "persistence_buckets": list(PERSISTENCE_BUCKETS.keys()),
                "forward_windows":    FORWARD_WINDOWS,
                "primary_window":     PRIMARY_WINDOW,
                "primary_metric":     "alpha_vs_spy",
                "spy_conid":          SPY_CONID,
                "min_observations":   20,
                "hypothesis_threshold": 0.5,
            },
            tags=["edge_validation", "IRC", "persistence", "industry_level", "alpha"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed("IRC chybi v context.signals.")
        if SPY_CONID not in context.prices:
            return ValidationResult.failed(f"SPY (conid={SPY_CONID}) neni v context.prices.")
        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        irc_df = context.signals["IRC"].copy()
        irc_df = irc_df[irc_df["lookback"] == IRC_LOOKBACK].copy()
        irc_df["date"] = pd.to_datetime(irc_df["date"])

        # Pivot: date x industry -> rank
        rank_pivot = irc_df.pivot_table(index="date", columns="industry", values="rank")
        rank_pivot = rank_pivot.sort_index()

        # Pivot: date x industry -> median_return (pro forward proxy)
        if "median_return" not in irc_df.columns:
            return ExperimentResult(
                metrics={"error": "missing_median_return_column"},
                summary="IRC archiv neobsahuje median_return sloupec.",
            )
        ret_pivot = irc_df.pivot_table(index="date", columns="industry", values="median_return")
        ret_pivot = ret_pivot.sort_index()

        spy_prices = context.prices[SPY_CONID]

        # Persistence: kolik dni z poslednich PERSISTENCE_WINDOW byla industry v TOP10
        is_top10 = (rank_pivot <= IRC_TOP_MAX).astype(int)
        persistence = is_top10.rolling(window=PERSISTENCE_WINDOW, min_periods=PERSISTENCE_WINDOW).sum()

        all_dates = sorted(rank_pivot.index)
        max_window = max(FORWARD_WINDOWS)
        cutoff_date = all_dates[-1] - timedelta(days=max_window + 15)
        eligible_dates = [d for d in all_dates if d <= cutoff_date and pd.notna(persistence.loc[d]).any()]

        records = []

        for signal_date in eligible_dates:
            ts = pd.Timestamp(signal_date)
            spy_entry = float(spy_prices.loc[ts, "close"]) if ts in spy_prices.index else None
            if spy_entry is None:
                continue

            persist_row = persistence.loc[ts]
            rank_row = rank_pivot.loc[ts]

            for industry in rank_pivot.columns:
                p_days = persist_row.get(industry)
                if pd.isna(p_days):
                    continue
                rank_now = rank_row.get(industry)
                if pd.isna(rank_now) or rank_now > IRC_TOP_MAX:
                    continue  # zajima nas jen co je DNES v TOP10

                bucket = self._assign_bucket(int(p_days))
                if bucket is None:
                    continue

                # Forward industry performance — pomoci median_return v ret_pivot
                # o forward_window obchodnich dni pozdeji (jako proxy)
                rec = self._build_record(
                    industry, signal_date, bucket, int(p_days),
                    ret_pivot, all_dates, spy_entry, spy_prices,
                )
                if rec:
                    records.append(rec)

        if not records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        df = pd.DataFrame(records)

        # Agregace per bucket
        stats_rows = []
        for bucket in PERSISTENCE_BUCKETS:
            sub = df[df["bucket"] == bucket]
            if sub.empty:
                continue
            row = {"bucket": bucket, "n": len(sub), "unique_industries": sub["industry"].nunique()}
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

        def get(b, col):
            r = stats_df[stats_df["bucket"] == b]
            return float(r[col].iloc[0]) if not r.empty and col in r.columns and pd.notna(r[col].iloc[0]) else None

        new_alpha = get("NEW_TOP10", ac)
        persist_alpha = get("PERSISTENT_TOP10", ac)

        threshold = self.define().parameters["hypothesis_threshold"]
        h_supported = (
            new_alpha is not None and persist_alpha is not None
            and (persist_alpha - new_alpha) > threshold
        )

        metrics = {
            "n_records_total":   len(df),
            "n_eligible_dates":  len(eligible_dates),
            "n_unique_industries": df["industry"].nunique(),
            "primary_window_d": pw,
            "primary_metric":   "alpha_vs_spy",
            "new_top10_median_alpha":        new_alpha,
            "persistent_top10_median_alpha": persist_alpha,
            "diff_persistent_vs_new": round(persist_alpha - new_alpha, 4) if (persist_alpha is not None and new_alpha is not None) else None,
            "h_supported": h_supported,
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
            "IRC Persistence Edge (industry-level, bez MLE)",
            "Question: Do persistently strong industries have higher forward alpha?",
            "",
            f"IRC TOP{IRC_TOP_MAX} dnes, persistence okno {PERSISTENCE_WINDOW}d  |  Metrika: alpha vs SPY  |  Window: {pw}D",
            "",
            "Buckety:",
        ]
        for _, row in stats_df.iterrows():
            a, w, n = row.get(ac), row.get(wc), int(row.get("n", 0))
            if a is not None and w is not None:
                lines.append(f"  {row['bucket']:<18} alpha={fmt(a)}  WR={w*100:.1f}%  N={n}")
            else:
                lines.append(f"  {row['bucket']:<18} N={n}")
        lines += [
            "",
            f"Diff (PERSISTENT vs NEW): {fmt(metrics['diff_persistent_vs_new'])}",
            "",
            f"H (PERSISTENT_TOP10 > NEW_TOP10 + {threshold}pp alpha): {sup(h_supported)}",
            "",
            f"N celkem: {len(df):,} | Unikatni industries: {df['industry'].nunique()} | Datumy: {len(eligible_dates)}",
            f"Rozsah: {context.config.date_from} -> {context.config.date_to}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"bucket_stats": stats_df},
            summary="\n".join(lines),
        )

    def _assign_bucket(self, persistence_days: int) -> str | None:
        for bucket_name, (lo, hi) in PERSISTENCE_BUCKETS.items():
            if lo <= persistence_days <= hi:
                return bucket_name
        return None

    def _build_record(self, industry, signal_date, bucket, p_days,
                      ret_pivot, all_dates, spy_entry, spy_prices):
        record = {
            "date": signal_date, "industry": industry,
            "bucket": bucket, "persistence_days": p_days,
        }
        ts = pd.Timestamp(signal_date)
        idx = all_dates.index(signal_date) if signal_date in all_dates else None
        if idx is None:
            return None

        for w in FORWARD_WINDOWS:
            fwd_date = signal_date + timedelta(days=w)
            fwd_ts = self._nearest_in_index(ret_pivot.index, fwd_date)
            if fwd_ts is None or industry not in ret_pivot.columns:
                record[f"alpha_{w}d"] = np.nan
                continue
            fwd_ret = ret_pivot.loc[fwd_ts, industry]
            if pd.isna(fwd_ret):
                record[f"alpha_{w}d"] = np.nan
                continue
            spy_fwd_ts = self._nearest_date(spy_prices, fwd_date)
            if spy_fwd_ts is not None and spy_entry > 0:
                spy_fwd = float(spy_prices.loc[spy_fwd_ts, "close"])
                spy_ret = (spy_fwd / spy_entry - 1) * 100
                record[f"alpha_{w}d"] = round(float(fwd_ret) - spy_ret, 4)
            else:
                record[f"alpha_{w}d"] = np.nan
        return record

    @staticmethod
    def _nearest_in_index(index, target, max_offset=5):
        for i in range(max_offset + 1):
            ts = pd.Timestamp(target + timedelta(days=i))
            if ts in index:
                return ts
        return None

    @staticmethod
    def _nearest_date(price_df, target, max_offset=5):
        for i in range(max_offset + 1):
            ts = pd.Timestamp(target + timedelta(days=i))
            if ts in price_df.index:
                return ts
        return None
