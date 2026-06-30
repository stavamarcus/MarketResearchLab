"""
MLEIRCRollingValidation_v1 — MLE x IRC Rolling Validation

Research Project: RP-0005-MLE-IRC-ROLLING

Otazka:
    Drzi MLE x IRC edge napric casovymi okny, nebo je tazen jednim obdobim?

Konfigurace (primary point, podle KR-2026-06-MLE-IRC-robustness):
    MLE rank_10d <= 20
    IRC rank      <= 10
    Metrika:      alpha vs SPY, 30D primary

Rolling okna:
    Velikost okna: 60 obchodnich dni (~3 mesice)
    Step:          20 obchodnich dni (~1 mesic posun)
    Minimum signalu na okno: 100 (jinak okno preskoceno jako nevalidni)

Pro kazde okno pocitame:
    median_alpha_top, median_alpha_headwind, diff, win_rate_top, win_rate_headwind

Kriteria robustnosti:
    >= 70% validnich oken ma diff > 0
    median window diff > 0.5pp
    zadne okno s extremne negativnim diff bez vysvetleni

Research Project: RP-0005-MLE-IRC-ROLLING
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
IRC_TOP_MAX     = 10
IRC_LOOKBACK    = 20
FORWARD_WINDOWS = [5, 10, 20, 30]
PRIMARY_WINDOW  = 30

WINDOW_SIZE_DAYS = 60   # rolling okno (obchodni dny)
STEP_DAYS        = 20   # posun mezi okny (obchodni dny)
MIN_SIGNALS_PER_WINDOW = 100


class MLEIRCRollingValidation_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="MLEIRCRollingValidation",
            version="1.0.0",
            hypothesis=(
                "Diff alpha (MLE+IRC_TOP10 vs MLE_HEADWIND) je kladny ve "
                "vetsine rolling oken (>=70%) napric dostupnou historii."
            ),
            description=(
                "Rolling validation pro KR-2026-06-MLE-IRC-robustness. "
                "Primary config: MLE TOP20 (rank_10d) x IRC TOP10. "
                "Okno 60D, step 20D, min 100 signalu/okno."
            ),
            required_data=[
                "prices",
                "feature:MLE_Rank_10d",
                "signal:IRC",
            ],
            parameters={
                "mle_rank_max":   MLE_RANK_MAX,
                "irc_rank_max":   IRC_TOP_MAX,
                "irc_lookback":   IRC_LOOKBACK,
                "primary_window": PRIMARY_WINDOW,
                "primary_metric": "alpha_vs_spy",
                "window_size_days": WINDOW_SIZE_DAYS,
                "step_days":        STEP_DAYS,
                "min_signals_per_window": MIN_SIGNALS_PER_WINDOW,
                "robustness_pct_threshold": 0.70,
                "robustness_median_threshold": 0.5,
                "spy_conid": SPY_CONID,
            },
            tags=["edge_validation", "MLE", "IRC", "rolling_validation", "robustness", "signal_interaction"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle_features = context.features.all_for_name("MLE_Rank_10d")
        if len(mle_features) < 10:
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

        # === 1. Predpocitej VSECHNY zaznamy (MLE TOP20 + IRC rank + alpha) ===
        base_records = []
        for signal_date in eligible_days:
            ts = pd.Timestamp(signal_date)
            spy_entry = float(spy_prices.loc[ts, "close"]) if ts in spy_prices.index else None
            if spy_entry is None:
                continue

            all_snaps = query.assets(date=signal_date)
            mle_snaps = [
                s for s in all_snaps
                if s.mle_rank_10d is not None and s.mle_rank_10d <= MLE_RANK_MAX
            ]
            if not mle_snaps:
                continue

            for snap in mle_snaps:
                irc_rank = irc_index.get((ts, snap.industry))
                group = "MLE+IRC_TOP10" if (irc_rank is not None and irc_rank <= IRC_TOP_MAX) else "MLE_HEADWIND"
                rec = self._build_record(
                    snap.conid, snap.ticker, signal_date, group,
                    context, spy_entry, spy_prices,
                )
                if rec:
                    base_records.append(rec)

        if not base_records:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Zadne zaznamy.")

        base_df = pd.DataFrame(base_records)
        base_df["date"] = pd.to_datetime(base_df["date"])

        # === 2. Rolling okna ===
        sorted_days = sorted(eligible_days)
        n_days = len(sorted_days)

        window_results = []
        start_idx = 0
        while start_idx + WINDOW_SIZE_DAYS <= n_days:
            window_days = sorted_days[start_idx : start_idx + WINDOW_SIZE_DAYS]
            w_start, w_end = window_days[0], window_days[-1]

            w_ts_start, w_ts_end = pd.Timestamp(w_start), pd.Timestamp(w_end)
            window_df = base_df[(base_df["date"] >= w_ts_start) & (base_df["date"] <= w_ts_end)]

            top = window_df[window_df["group"] == "MLE+IRC_TOP10"]
            headwind = window_df[window_df["group"] == "MLE_HEADWIND"]

            n_total = len(window_df)
            ac = f"alpha_{PRIMARY_WINDOW}d"

            top_vals = top[ac].dropna()
            head_vals = headwind[ac].dropna()

            valid = n_total >= MIN_SIGNALS_PER_WINDOW and not top_vals.empty and not head_vals.empty

            row = {
                "window_start": w_start.isoformat() if hasattr(w_start, "isoformat") else str(w_start),
                "window_end":   w_end.isoformat() if hasattr(w_end, "isoformat") else str(w_end),
                "n_top":        len(top),
                "n_headwind":   len(headwind),
                "n_total":      n_total,
                "valid":        valid,
            }

            if valid:
                median_top  = round(float(top_vals.median()), 4)
                median_head = round(float(head_vals.median()), 4)
                diff        = round(median_top - median_head, 4)
                wr_top      = round(float((top_vals > 0).mean()), 4)
                wr_head     = round(float((head_vals > 0).mean()), 4)
                row.update({
                    "median_alpha_top":      median_top,
                    "median_alpha_headwind": median_head,
                    "diff":                  diff,
                    "wr_top":                wr_top,
                    "wr_headwind":           wr_head,
                    "supported": diff > self.define().parameters["robustness_median_threshold"],
                })
            else:
                row.update({
                    "median_alpha_top": None, "median_alpha_headwind": None,
                    "diff": None, "wr_top": None, "wr_headwind": None,
                    "supported": None,
                })

            window_results.append(row)
            start_idx += STEP_DAYS

        windows_df = pd.DataFrame(window_results)

        # === 3. Agregace robustnosti ===
        valid_windows = windows_df[windows_df["valid"] == True]
        n_valid = len(valid_windows)
        n_total_windows = len(windows_df)

        diffs = valid_windows["diff"].dropna()
        n_positive = int((diffs > 0).sum())
        pct_positive = round(n_positive / len(diffs), 4) if len(diffs) > 0 else None
        median_diff = round(float(diffs.median()), 4) if not diffs.empty else None
        min_diff = round(float(diffs.min()), 4) if not diffs.empty else None
        max_diff = round(float(diffs.max()), 4) if not diffs.empty else None

        pct_threshold = self.define().parameters["robustness_pct_threshold"]
        median_threshold = self.define().parameters["robustness_median_threshold"]

        h_pct_supported = pct_positive is not None and pct_positive >= pct_threshold
        h_median_supported = median_diff is not None and median_diff > median_threshold
        h_supported = h_pct_supported and h_median_supported

        metrics = {
            "n_windows_total":   n_total_windows,
            "n_windows_valid":   n_valid,
            "n_windows_skipped": n_total_windows - n_valid,
            "window_size_days":  WINDOW_SIZE_DAYS,
            "step_days":         STEP_DAYS,
            "min_signals_per_window": MIN_SIGNALS_PER_WINDOW,
            "n_windows_positive_diff": n_positive,
            "pct_windows_positive":    pct_positive,
            "median_window_diff":      median_diff,
            "min_window_diff":         min_diff,
            "max_window_diff":         max_diff,
            "h_pct_supported":    h_pct_supported,
            "h_median_supported": h_median_supported,
            "h_supported":        h_supported,
        }

        def fmt(v): return f"{v:+.2f}%" if v is not None else "N/A"
        def sup(v): return "SUPPORTED" if v else "NOT SUPPORTED"
        def pct(v): return f"{v*100:.0f}%" if v is not None else "N/A"

        lines = [
            "MLE x IRC Rolling Validation",
            "Question: Does the MLE+IRC edge hold across time windows?",
            "",
            f"Config: MLE TOP{MLE_RANK_MAX} (rank_10d) x IRC TOP{IRC_TOP_MAX}  |  alpha vs SPY 30D",
            f"Rolling: window={WINDOW_SIZE_DAYS}d, step={STEP_DAYS}d, min_signals={MIN_SIGNALS_PER_WINDOW}",
            "",
            f"Okna celkem: {n_total_windows} | Validni: {n_valid} | Preskoceno (malo signalu): {n_total_windows - n_valid}",
            "",
            "Okna (window_start -> diff):",
        ]
        for _, row in windows_df.iterrows():
            if row["valid"]:
                lines.append(f"  {row['window_start']} -> {row['window_end']}: diff={fmt(row['diff'])} (N={row['n_total']})")
            else:
                lines.append(f"  {row['window_start']} -> {row['window_end']}: SKIPPED (N={row['n_total']} < {MIN_SIGNALS_PER_WINDOW})")
        lines += [
            "",
            f"Okna s kladnym diff: {n_positive}/{n_valid} ({pct(pct_positive)})",
            f"Median window diff: {fmt(median_diff)}",
            f"Rozsah diff: {fmt(min_diff)} az {fmt(max_diff)}",
            "",
            f"Kriterium 1 (>={pct_threshold*100:.0f}% oken kladnych): {sup(h_pct_supported)}",
            f"Kriterium 2 (median diff > {median_threshold}pp):       {sup(h_median_supported)}",
            "",
            f"CELKOVY ZAVER: {sup(h_supported)}",
        ]

        return ExperimentResult(
            metrics=metrics,
            tables={"windows": windows_df},
            summary="\n".join(lines),
        )

    def _build_record(self, conid, ticker, signal_date, group,
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

        record = {"date": signal_date, "conid": conid, "ticker": ticker, "group": group}
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
