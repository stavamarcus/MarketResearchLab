"""
Cap02MarketCapPerformance_v1 — MRL-CAP-02 signal-level performance
comparison MLE × IRC candidate-days podle market-cap bucketu.

Protokol: docs/MRL_CAP02_PERFORMANCE_PROTOCOL.md (CAP-00, ACCEPTED).
NENÍ portfolio strategie — žádné náklady, sizing, portfolio konstrukce,
Sharpe/CAGR/drawdown jako závěr.

Design: čistá dekompozice baseline (celý MLE × IRC vzorek) podle
market-cap bucketu. Žádné filtry navíc. Buckety z CAP-01B
market_cap_output.csv (bucket source = candidate-date market cap).

Forward returns: close-to-close, kalendářní 5/10/20 d + nearest trading
day do +5 d — konvence FUND-05/MLEBucketsIRCGrid. SPY-relative =
sekundární diagnostika. Primární: median 20D raw forward return.

Per-bucket status vs. celkový vzorek: PASS (robustní diferenciace) /
FAIL / INCONCLUSIVE (N<30 nebo <10 unique conidů) / STOP (data integrity).
UNBUCKETED reportován, neinterpretuje se. Small = NO DATA (N=0).
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult

SPY_CONID = 756733
WINDOWS = [5, 10, 20]
PRIMARY_WINDOW = 20
MIN_N = 30
MIN_UNIQUE_CONIDS = 10
NONOVERLAP_GAP = 20
NEAREST_MAX_OFFSET = 5

# buckety hodnocené v CAP-02 (UNBUCKETED reportován, neinterpretován;
# Small = NO DATA)
VALID_BUCKETS = ["Mega", "Large-high", "Large-low", "Mid"]
ALL_BUCKETS = VALID_BUCKETS + ["Small", "UNBUCKETED"]


# ------------------------------------------------------- forward returns
# Sdíleno s FUND-05 konvencí (close-to-close, kalendářní offset + nearest).

def nearest_forward_ts(price_df, target, max_offset=NEAREST_MAX_OFFSET):
    for i in range(max_offset + 1):
        ts = pd.Timestamp(target + timedelta(days=i))
        if ts in price_df.index:
            return ts
    return None


def compute_forward_returns(rows, prices, spy_prices):
    """Per-row 5/10/20D raw + SPY-relative forward returns (v %).
    Chybějící entry/forward → NaN + počítadlo, žádný drop."""
    counters = {"entry_price_missing": 0,
                **{f"fwd_missing_{w}d": 0 for w in WINDOWS}}
    out = {f"ret_fwd_{w}d": [] for w in WINDOWS}
    out.update({f"spyrel_fwd_{w}d": [] for w in WINDOWS})
    for row in rows.itertuples(index=False):
        cand = row.candidate_date
        pdf = prices.get(int(row.conid))
        ts = pd.Timestamp(cand)
        entry = (float(pdf.loc[ts, "close"])
                 if pdf is not None and not pdf.empty and ts in pdf.index
                 else None)
        spy_entry = (float(spy_prices.loc[ts, "close"])
                     if ts in spy_prices.index else None)
        if entry is None or entry <= 0 or spy_entry is None:
            counters["entry_price_missing"] += 1
            for w in WINDOWS:
                out[f"ret_fwd_{w}d"].append(np.nan)
                out[f"spyrel_fwd_{w}d"].append(np.nan)
            continue
        for w in WINDOWS:
            fwd = nearest_forward_ts(pdf, cand + timedelta(days=w))
            sfw = nearest_forward_ts(spy_prices, cand + timedelta(days=w))
            if fwd is None or sfw is None:
                counters[f"fwd_missing_{w}d"] += 1
                out[f"ret_fwd_{w}d"].append(np.nan)
                out[f"spyrel_fwd_{w}d"].append(np.nan)
                continue
            r = (float(pdf.loc[fwd, "close"]) / entry - 1) * 100
            s = (float(spy_prices.loc[sfw, "close"]) / spy_entry - 1) * 100
            out[f"ret_fwd_{w}d"].append(round(r, 4))
            out[f"spyrel_fwd_{w}d"].append(round(r - s, 4))
    return pd.DataFrame(out, index=rows.index), counters


def nonoverlap_selection(rows, gap=NONOVERLAP_GAP):
    """Deterministický non-overlap: max 1 candidate-day/conid/gap
    obchodních dní. Kalendář = seřazené unikátní candidate dates.
    First-occurrence, bez returns."""
    dates = sorted(rows["candidate_date"].unique())
    pos = {d: i for i, d in enumerate(dates)}
    keep, last = [], {}
    for idx, row in zip(rows.sort_values(["candidate_date", "conid"]).index,
                        rows.sort_values(["candidate_date", "conid"])
                        .itertuples(index=False)):
        p = pos[row.candidate_date]
        lp = last.get(int(row.conid))
        if lp is None or p - lp >= gap:
            keep.append(idx)
            last[int(row.conid)] = p
    return pd.Index(keep)


def group_stats(returns, mask):
    """Metriky skupiny: per okno N/mean/median/hit (raw i SPY-relative)."""
    sub = returns[mask]
    st = {"n_rows": int(mask.sum())}
    for w in WINDOWS:
        r = sub[f"ret_fwd_{w}d"].dropna()
        s = sub[f"spyrel_fwd_{w}d"].dropna()
        st[f"n_ret_{w}d"] = int(len(r))
        st[f"mean_{w}d"] = round(float(r.mean()), 4) if len(r) else None
        st[f"median_{w}d"] = round(float(r.median()), 4) if len(r) else None
        st[f"hit_{w}d"] = round(float((r > 0).mean()), 4) if len(r) else None
        st[f"spyrel_median_{w}d"] = (round(float(s.median()), 4)
                                     if len(s) else None)
    return st


def bucket_status(bucket, st, base, nono_b, nono_all, unique_conids):
    """PASS/FAIL/INCONCLUSIVE dle protokolu. Diferenciace = robustní
    odchylka od celkového vzorku (nad i pod), konzistentní směr."""
    if bucket in ("Small", "UNBUCKETED"):
        return "NOT_INTERPRETED", f"{bucket} se neinterpretuje"
    n = st[f"n_ret_{PRIMARY_WINDOW}d"]
    if n < MIN_N:
        return "INCONCLUSIVE", f"N_20d={n} < {MIN_N}"
    if unique_conids < MIN_UNIQUE_CONIDS:
        return "INCONCLUSIVE", f"unique_conids={unique_conids} < {MIN_UNIQUE_CONIDS}"
    md_b, md_a = st[f"median_{PRIMARY_WINDOW}d"], base[f"median_{PRIMARY_WINDOW}d"]
    if md_b is None or md_a is None:
        return "INCONCLUSIVE", "median_20d nevyhodnotitelný"
    direction = np.sign(md_b - md_a)
    if direction == 0:
        return "FAIL", "median_20d shodný s baseline"
    # konzistence směru na 5/10D
    short_consistent = all(
        np.sign((st[f"median_{w}d"] or 0) - (base[f"median_{w}d"] or 0))
        == direction for w in (5, 10))
    # non-overlap nesmí být v rozporu se směrem
    nono_ok = True
    if (nono_b.get("median_20d") is not None
            and nono_all.get("median_20d") is not None):
        nono_dir = np.sign(nono_b["median_20d"] - nono_all["median_20d"])
        nono_ok = (nono_dir == direction) or (nono_dir == 0)
    else:
        return "INCONCLUSIVE", "non-overlap nevyhodnotitelný"
    diff = round(md_b - md_a, 4)
    detail = (f"median20 {md_b} vs vzorek {md_a} (diff {diff:+.4f}); "
              f"5/10D konzist={short_consistent}; "
              f"non-overlap {nono_b.get('median_20d')} vs "
              f"{nono_all.get('median_20d')}")
    if short_consistent and nono_ok:
        return "PASS", detail   # robustní diferenciace (i horší = poznatek)
    return "FAIL", detail


class Cap02MarketCapPerformance_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="Cap02MarketCapPerformance",
            version="1.0.0",
            hypothesis=(
                "Market-cap bucket MLE × IRC candidate-days diferencuje "
                "forward returns (median 20D) oproti celkovému vzorku."),
            description=(
                "Signal-level dekompozice MLE × IRC baseline podle "
                "market-cap bucketu (CAP-01B). Per-bucket vs celkový "
                "vzorek, dependence + non-overlap. NENÍ strategie."),
            required_data=["prices", "benchmark:SPY"],
            parameters={
                "windows": WINDOWS, "primary_window": PRIMARY_WINDOW,
                "min_n": MIN_N, "min_unique_conids": MIN_UNIQUE_CONIDS,
                "nonoverlap_gap": NONOVERLAP_GAP,
                "valid_buckets": VALID_BUCKETS,
            },
            tags=["cap_validation", "market_cap", "MLE", "IRC",
                  "signal_level", "CAP-02"],
            author="MRL Framework",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        p = context.config.parameters
        if "market_cap_output_csv" not in p:
            return ValidationResult.failed(
                "parameters.market_cap_output_csv chybí")
        if SPY_CONID not in context.prices:
            return ValidationResult.failed("SPY není v context.prices")
        try:
            mc = self._load_market_cap(p["market_cap_output_csv"])
        except Exception as e:  # noqa: BLE001
            return ValidationResult.failed(f"market_cap load fail: {e}")
        if mc.empty:
            return ValidationResult.failed("market_cap prázdné")
        return ValidationResult.ok()

    @staticmethod
    def _load_market_cap(path) -> pd.DataFrame:
        """CAP-01B output jako governance vstup (hash v manifestu).
        Forbidden-column guard (žádné forward-return sloupce)."""
        from run_fundamental_coverage_audit import FORBIDDEN_INPUT_COLUMNS
        df = pd.read_csv(path)
        forbidden = [c for c in df.columns
                     if c.lower() in FORBIDDEN_INPUT_COLUMNS]
        if forbidden:
            raise ValueError(f"zakázané sloupce v market_cap CSV: {forbidden}")
        need = {"conid", "candidate_date", "market_cap_bucket",
                "market_cap_reason_code"}
        if not need.issubset(df.columns):
            raise ValueError(f"chybí sloupce: {need - set(df.columns)}")
        df = df.copy()
        df["conid"] = df["conid"].astype(int)
        df["candidate_date"] = pd.to_datetime(df["candidate_date"]).dt.date
        return df

    def run(self, context: ExperimentContext) -> ExperimentResult:
        p = context.config.parameters
        mc = self._load_market_cap(p["market_cap_output_csv"])

        spy = context.prices[SPY_CONID]
        rets, price_counters = compute_forward_returns(mc, context.prices, spy)

        # baseline = celý vzorek (analogie FUND-05 varianta A)
        all_mask = pd.Series(True, index=mc.index)
        base = group_stats(rets, all_mask)
        nono_all_idx = nonoverlap_selection(mc)

        def nono_stats(mask):
            m = mask & mask.index.isin(nono_all_idx)
            r = rets.loc[m, f"ret_fwd_{PRIMARY_WINDOW}d"].dropna()
            return {"n": int(len(r)),
                    "median_20d": round(float(r.median()), 4)
                    if len(r) else None}

        nono_all = nono_stats(all_mask)

        # per bucket
        summary_rows, statuses = [], {}
        for b in ALL_BUCKETS:
            mask = mc["market_cap_bucket"] == b
            st = group_stats(rets, mask)
            uc = int(mc.loc[mask, "conid"].nunique())
            nb = nono_stats(mask)
            status, detail = bucket_status(b, st, base, nb, nono_all, uc)
            statuses[b] = (status, detail)
            summary_rows.append({
                "bucket": b, "status": status,
                "n_rows": st["n_rows"], "unique_conids": uc,
                "unique_dates": int(mc.loc[mask, "candidate_date"].nunique()),
                "n_ret_20d": st["n_ret_20d"],
                "median_20d": st["median_20d"], "mean_20d": st["mean_20d"],
                "hit_20d": st["hit_20d"],
                "spyrel_median_20d": st["spyrel_median_20d"],
                "median_5d": st["median_5d"], "median_10d": st["median_10d"],
                "nonoverlap_n": nb["n"],
                "nonoverlap_median_20d": nb["median_20d"],
                "detail": detail,
            })
        # baseline řádek
        summary_rows.insert(0, {
            "bucket": "ALL (baseline)", "status": "BASELINE",
            "n_rows": int(all_mask.sum()),
            "unique_conids": int(mc["conid"].nunique()),
            "unique_dates": int(mc["candidate_date"].nunique()),
            "n_ret_20d": base["n_ret_20d"], "median_20d": base["median_20d"],
            "mean_20d": base["mean_20d"], "hit_20d": base["hit_20d"],
            "spyrel_median_20d": base["spyrel_median_20d"],
            "median_5d": base["median_5d"], "median_10d": base["median_10d"],
            "nonoverlap_n": nono_all["n"],
            "nonoverlap_median_20d": nono_all["median_20d"],
            "detail": "referenční celý vzorek",
        })
        summary = pd.DataFrame(summary_rows).set_index("bucket")

        # dependence per valid bucket
        dep_rows = []
        for b in VALID_BUCKETS:
            g = mc[mc["market_cap_bucket"] == b]
            if g.empty:
                continue
            per_conid = g.groupby("conid").size()
            top = per_conid.sort_values(ascending=False).head(3)
            tick = g.drop_duplicates("conid").set_index("conid")["ticker"] \
                if "ticker" in g else pd.Series(dtype=object)
            dep_rows.append({
                "bucket": b, "nominal_N": len(g),
                "unique_conids": int(g["conid"].nunique()),
                "avg_per_conid": round(float(per_conid.mean()), 2),
                "top_conids": ", ".join(
                    f"{tick.get(c, c)}({n})" for c, n in top.items()),
            })
        dependence = pd.DataFrame(dep_rows)

        fwd_table = pd.concat([
            mc[["conid", "candidate_date", "market_cap_bucket"]]
            .reset_index(drop=True),
            rets.reset_index(drop=True)], axis=1)

        overall = "COMPLETED"
        return ExperimentResult(
            metrics={
                "overall_result": overall,
                "candidate_days": int(len(mc)),
                "baseline_median_20d": base["median_20d"],
                "baseline_hit_20d": base["hit_20d"],
                "entry_price_missing": price_counters["entry_price_missing"],
                **{f"status_{b}": statuses[b][0] for b in ALL_BUCKETS},
                **{f"median_20d_{b}":
                   next((r["median_20d"] for r in summary_rows
                         if r["bucket"] == b), None)
                   for b in VALID_BUCKETS},
            },
            tables={
                "bucket_performance": summary,
                "dependence": dependence,
                "forward_returns": fwd_table,
            },
            artifacts={
                "cap02_performance_report.md": self._report(
                    p, mc, base, summary, statuses, dependence,
                    price_counters, overall),
            },
            summary=self._summary_text(statuses, overall),
        )

    def _report(self, p, mc, base, summary, statuses, dependence,
                counters, overall) -> str:
        from run_cap01_market_cap_audit import df_to_markdown
        lines = [
            "# CAP-02 Market Cap Performance Report",
            "",
            "**Signal-level research. NENÍ obchodovatelná strategie** — "
            "žádné náklady, slippage, sizing, portfolio konstrukce.",
            "",
            f"- market_cap source: `{p.get('market_cap_output_csv')}`",
            f"- candidate-days: {len(mc)}",
            "- forward return method: close-to-close, kalendářní "
            f"{WINDOWS} d + nearest ≤ +{NEAREST_MAX_OFFSET}d "
            "(konvence FUND-05)",
            "- SPY-relative: sekundární diagnostika, ne acceptance",
            f"- entry_price_missing: {counters['entry_price_missing']}",
            f"- baseline median 20D: {base['median_20d']} | "
            f"hit 20D: {base['hit_20d']}",
            "",
            "## Per-bucket performance", "",
            df_to_markdown(summary.reset_index()),
            "",
            "## Dependence (valid buckets)", "",
            df_to_markdown(dependence),
            "",
            "## Statusy", "",
        ]
        lines += [f"- {b}: **{st}** — {det}"
                  for b, (st, det) in statuses.items()]
        lines += [
            "", f"## Overall RESULT: {overall}", "",
            "PASS bucket = robustní diferenciace (nad i pod baseline) "
            "hodná samostatného DR výzkumu. NESMÍ automaticky měnit "
            "Decision Resolver. UNBUCKETED se neinterpretuje; Small = "
            "NO DATA; Mid pravděpodobně INCONCLUSIVE (N<30). "
            "Zakázáno: edge confirmed / tradable strategy.", "",
        ]
        return "\n".join(lines)

    def _summary_text(self, statuses, overall) -> str:
        parts = [f"{b}:{statuses[b][0]}" for b in VALID_BUCKETS]
        return (f"CAP-02 signal-level — {overall}. " + "; ".join(parts)
                + ". Není strategie; PASS = kandidát na DR výzkum.")
