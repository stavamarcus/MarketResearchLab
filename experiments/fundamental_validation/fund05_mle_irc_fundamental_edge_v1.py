"""
Fund05MleIrcFundamentalEdge_v1 — první MLE × IRC × fundamentals
signal-level edge experiment (MRL-FUND-05).

Protokol: docs/MRL_FUND04_EDGE_TEST_PROTOCOL.md (pre-registrovaný,
CLOSED/ACCEPTED). Prahy jsou ZAMČENÉ — po spuštění se nemění.

Varianty (fixní pravidla, žádný optimizer):
    A baseline | B netinc>0 & fcf>0 | C revenue_yoy>0
    D roe>0.15 & equity>0 | E exclude de>2.0 or equity<=0
    F composite >=4/5 (všech 5 komponent evaluovatelných)

Forward returns: close-to-close, kalendářní offset + nearest trading day
do +5 d — konvence shodná s MLEBucketsIRCGrid (srovnatelnost s KR).
SPY-relative return = sekundární diagnostika (ne "alpha").

TOTO NENÍ obchodovatelná strategie — signal-level research only.
Žádná portfolio simulace, sizing, náklady, optimalizace.
"""

from __future__ import annotations

from datetime import date, timedelta

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
PREFERRED_N = 100
NONOVERLAP_GAP = 20          # obchodních dní (index unikátních candidate dates)
PRIOR_YEAR_DAYS = 365
NEAREST_MAX_OFFSET = 5

# Pre-registered fixed thresholds (FUND-04, LOCKED)
ROE_MIN = 0.15
DE_MAX = 2.0
COMPOSITE_MIN = 4

VARIANTS = ["A", "B", "C", "D", "E", "F"]
VARIANT_DESC = {
    "A": "baseline only",
    "B": "netinc > 0 AND fcf > 0",
    "C": "revenue_yoy > 0",
    "D": f"roe > {ROE_MIN} AND equity > 0",
    "E": f"exclude de > {DE_MAX} OR equity <= 0 (sektorově citlivá)",
    "F": f"composite >= {COMPOSITE_MIN}/5",
}

EXPECTED_SNAPSHOT_ID = "sf1art_20260704_005521"


# ------------------------------------------------------------ core logic
# Modulové funkce (testovatelné bez frameworku).

def compute_revenue_yoy(base: pd.DataFrame, prior: pd.DataFrame) -> pd.Series:
    """revenue_yoy = revenue(t)/revenue(PIT t-365) - 1.

    NaN pokud: base revenue NaN/<=0, prior řádek EXCLUDED, prior revenue
    NaN/<=0. Oba lookupy jsou PIT (datekey <= příslušné datum).
    """
    b = base["revenue"]
    p = prior["revenue"].values
    p_ok = (prior["coverage_status"] == "OK").values
    out = pd.Series(np.nan, index=base.index, dtype=float)
    valid = b.notna() & (b > 0) & p_ok & pd.notna(p) & (np.nan_to_num(p) > 0)
    out[valid] = b[valid].values / p[valid] - 1.0
    return out


def variant_membership(rows: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per-row membership A–F + field_null_excluded accounting.

    rows: coverage_status==OK řádky se sloupci netinc, fcf, roe, de,
    equity, revenue_yoy. Vrací (bool DataFrame index=rows.index,
    {varianta: field_null_excluded count}).
    Composite: všech 5 komponent evaluovatelných, jinak null-excluded
    (missing NENÍ automaticky false).
    """
    m = pd.DataFrame(index=rows.index)
    nulls: dict = {}

    ni, fcf = rows["netinc"], rows["fcf"]
    roe, de, eq = rows["roe"], rows["de"], rows["equity"]
    yoy = rows["revenue_yoy"]

    m["A"] = True
    nulls["A"] = 0

    ev_b = ni.notna() & fcf.notna()
    m["B"] = ev_b & (ni > 0) & (fcf > 0)
    nulls["B"] = int((~ev_b).sum())

    ev_c = yoy.notna()
    m["C"] = ev_c & (yoy > 0)
    nulls["C"] = int((~ev_c).sum())

    # D: equity<=0 je evaluovatelné (member=False); NaN roe/equity = null
    ev_d = roe.notna() & eq.notna()
    m["D"] = ev_d & (eq > 0) & (roe > ROE_MIN)
    nulls["D"] = int((~ev_d).sum())

    # E: equity<=0 evaluovatelné (exclude); de NaN při equity>0 = null
    ev_e = eq.notna() & (de.notna() | (eq <= 0))
    weak = (de > DE_MAX) | (eq <= 0)
    m["E"] = ev_e & ~weak.fillna(False)
    nulls["E"] = int((~ev_e).sum())

    ev_f = ev_b & ev_c & ev_d & ev_e
    comp = (
        (ni > 0).astype(int) + (fcf > 0).astype(int)
        + (yoy > 0).fillna(False).astype(int)
        + ((eq > 0) & (roe > ROE_MIN)).astype(int)
        + (~weak.fillna(True)).astype(int)
    )
    m["F"] = ev_f & (comp >= COMPOSITE_MIN)
    nulls["F"] = int((~ev_f).sum())

    for v in VARIANTS:
        m[v] = m[v].fillna(False).astype(bool)
    return m, nulls


def nearest_forward_ts(price_df: pd.DataFrame, target: date,
                       max_offset: int = NEAREST_MAX_OFFSET):
    for i in range(max_offset + 1):
        ts = pd.Timestamp(target + timedelta(days=i))
        if ts in price_df.index:
            return ts
    return None


def compute_forward_returns(rows: pd.DataFrame, prices: dict,
                            spy_prices: pd.DataFrame) -> tuple[pd.DataFrame,
                                                               dict]:
    """Per-row 5/10/20D raw + SPY-relative forward returns (v %).

    Chybějící entry cena / forward cena => NaN + explicitní počítadlo
    (žádný tichý drop; řádky zůstávají).
    """
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


def nonoverlap_selection(rows: pd.DataFrame,
                         gap: int = NONOVERLAP_GAP) -> pd.Index:
    """Deterministický non-overlap subsample: max 1 candidate-day per
    conid per `gap` obchodních dní. Kalendář = seřazené unikátní
    candidate dates ve vzorku. Výběr = první výskyt (bez returns)."""
    dates = sorted(rows["candidate_date"].unique())
    pos = {d: i for i, d in enumerate(dates)}
    keep = []
    last: dict = {}
    ordered = rows.sort_values(["candidate_date", "conid"])
    for idx, row in zip(ordered.index, ordered.itertuples(index=False)):
        p = pos[row.candidate_date]
        lp = last.get(int(row.conid))
        if lp is None or p - lp >= gap:
            keep.append(idx)
            last[int(row.conid)] = p
    return pd.Index(keep)


def variant_stats(returns: pd.DataFrame, member: pd.Series) -> dict:
    """Metriky varianty: per okno N/mean/median/hit (raw i SPY-relative)."""
    sub = returns[member]
    stats = {"n_members": int(member.sum())}
    for w in WINDOWS:
        r = sub[f"ret_fwd_{w}d"].dropna()
        s = sub[f"spyrel_fwd_{w}d"].dropna()
        stats[f"n_ret_{w}d"] = int(len(r))
        stats[f"mean_{w}d"] = round(float(r.mean()), 4) if len(r) else None
        stats[f"median_{w}d"] = round(float(r.median()), 4) if len(r) else None
        stats[f"hit_{w}d"] = round(float((r > 0).mean()), 4) if len(r) else None
        stats[f"spyrel_median_{w}d"] = (round(float(s.median()), 4)
                                        if len(s) else None)
        stats[f"spyrel_hit_{w}d"] = (round(float((s > 0).mean()), 4)
                                     if len(s) else None)
    return stats


def variant_status(v: str, stats: dict, base: dict,
                   nono_v: dict, nono_a: dict) -> tuple[str, str]:
    """PASS/FAIL/INCONCLUSIVE dle FUND-04 §5 (per varianta vs A)."""
    if v == "A":
        return "BASELINE", "referenční"
    n = stats[f"n_ret_{PRIMARY_WINDOW}d"]
    if n < MIN_N:
        return "INCONCLUSIVE", f"N_20d={n} < {MIN_N}"
    md_v, md_a = stats[f"median_{PRIMARY_WINDOW}d"], base[f"median_{PRIMARY_WINDOW}d"]
    hr_v, hr_a = stats[f"hit_{PRIMARY_WINDOW}d"], base[f"hit_{PRIMARY_WINDOW}d"]
    if md_v is None or md_a is None:
        return "INCONCLUSIVE", "median_20d nevyhodnotitelný"
    diff_short = [
        (stats[f"median_{w}d"] or 0) - (base[f"median_{w}d"] or 0)
        for w in (5, 10)]
    directional = sum(1 for d in diff_short if d > 0) >= 1  # alespoň částečně
    nono_ok = True
    detail_extra = ""
    if nono_v.get("median_20d") is None or nono_a.get("median_20d") is None:
        detail_extra = "; non-overlap nevyhodnotitelný"
        nono_ok = None
    else:
        nono_ok = (nono_v["median_20d"] - nono_a["median_20d"]) >= 0 \
            if md_v > md_a else True  # "není v rozporu"
    if nono_ok is None:
        return "INCONCLUSIVE", f"non-overlap sensitivity nelze vyhodnotit{detail_extra}"
    passed = (md_v > md_a) and (hr_v is not None and hr_a is not None
                                and hr_v >= hr_a) and directional and nono_ok
    detail = (f"median20 {md_v} vs A {md_a}; hit20 {hr_v} vs {hr_a}; "
              f"5/10D diff {['%+.2f' % d for d in diff_short]}; "
              f"non-overlap median20 {nono_v.get('median_20d')} "
              f"vs A {nono_a.get('median_20d')}")
    return ("PASS" if passed else "FAIL"), detail


# --------------------------------------------------------------- experiment

class Fund05MleIrcFundamentalEdge_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="Fund05MleIrcFundamentalEdge",
            version="1.0.0",
            hypothesis=(
                "Fundamentální kvalita PIT SF1 snapshotu (quality/growth/"
                "profitability/leverage filtry s fixními pre-registrovanými "
                "prahy) zlepšuje median 20D forward return MLE TOP10 x "
                "IRC TOP10 candidate-days oproti baseline."
            ),
            description=(
                "První signal-level MLE x IRC x fundamentals edge run dle "
                "FUND-04 protokolu. Varianty A-F, fixní prahy, žádný "
                "optimizer, non-overlap sensitivity, dependence reporting. "
                "NENÍ obchodovatelná strategie."
            ),
            required_data=["prices", "benchmark:SPY"],
            parameters={
                "expected_snapshot_id": EXPECTED_SNAPSHOT_ID,
                "windows": WINDOWS, "primary_window": PRIMARY_WINDOW,
                "min_n": MIN_N, "preferred_n": PREFERRED_N,
                "roe_min": ROE_MIN, "de_max": DE_MAX,
                "composite_min": COMPOSITE_MIN,
                "nonoverlap_gap": NONOVERLAP_GAP,
                "prior_year_days": PRIOR_YEAR_DAYS,
                "feature_whitelist": ["netinc", "fcf", "roe", "de",
                                      "revenue", "equity"],
                "whitelist_version": "MRL_FUND04_FEATURE_WHITELIST v1",
            },
            tags=["fundamental_validation", "MLE", "IRC", "fundamentals",
                  "signal_level", "FUND-05"],
            author="MRL Framework",
        )

    # ------------------------------------------------------------ validate

    def validate(self, context: ExperimentContext) -> ValidationResult:
        p = context.config.parameters
        if not context.has_fundamental_source():
            return ValidationResult.failed(
                "context.fundamental_source chybí (sharadar_fundamentals).")
        src = context.fundamental_source
        expected = p.get("expected_snapshot_id", EXPECTED_SNAPSHOT_ID)
        if src.snapshot_id == "latest" or src.snapshot_id != expected:
            return ValidationResult.failed(
                f"snapshot_id {src.snapshot_id!r} != pinned {expected!r}")
        if SPY_CONID not in context.prices:
            return ValidationResult.failed(
                f"SPY (conid={SPY_CONID}) není v context.prices.")
        if "candidate_days_csv" not in p:
            return ValidationResult.failed("parameters.candidate_days_csv chybí.")
        try:
            inp = self._load_candidate_days(p["candidate_days_csv"])
        except Exception as e:  # noqa: BLE001
            return ValidationResult.failed(f"candidate-days load fail: {e}")
        if inp.empty:
            return ValidationResult.failed("candidate-days prázdné.")
        return ValidationResult.ok()

    @staticmethod
    def _load_candidate_days(path) -> pd.DataFrame:
        """Sdílený loader s forbidden-column guardem (FUND-03 modul).

        Vstupní CSV je governance artefakt (hash v parametrech/manifestu);
        jde o schválenou výjimku ze zákazu čtení disku v experimentu —
        NEJDE o price/parquet data.
        """
        from run_fundamental_coverage_audit import load_candidate_days
        return load_candidate_days(path)

    # ----------------------------------------------------------------- run

    def run(self, context: ExperimentContext) -> ExperimentResult:
        p = context.config.parameters
        src = context.fundamental_source
        inp = self._load_candidate_days(p["candidate_days_csv"])

        # --- fundamentals: base + prior-year PIT lookupy ---
        base_out, cov_base = src.get_fundamentals(
            inp[["conid", "candidate_date"]], experiment_id="fund05_base")
        prior_req = pd.DataFrame({
            "conid": inp["conid"].values,
            "candidate_date": [d - timedelta(days=PRIOR_YEAR_DAYS)
                               for d in inp["candidate_date"]],
        })
        prior_out, cov_prior = src.get_fundamentals(
            prior_req, experiment_id="fund05_prior")

        db, dp = cov_base.to_dict(), cov_prior.to_dict()

        # --- STOP kontroly (run-level integrita) ---
        stop_reasons = []
        if db["coverage_pct"] < 95.0:
            stop_reasons.append(f"base coverage {db['coverage_pct']} < 95")
        for label, d in (("base", db), ("prior", dp)):
            rc = d["reason_code_counts"]
            if rc["UNKNOWN_ERROR"] > 0:
                stop_reasons.append(f"{label} UNKNOWN_ERROR={rc['UNKNOWN_ERROR']}")
            if rc["CACHE_MISSING"] > 0 or rc["SCHEMA_MISMATCH"] > 0:
                stop_reasons.append(
                    f"{label} CACHE_MISSING={rc['CACHE_MISSING']} "
                    f"SCHEMA_MISMATCH={rc['SCHEMA_MISMATCH']}")
        # pozn.: prior NO_SF1_ASOF_DATE je očekávaný (starší datum) -> ne STOP

        rows = base_out.copy()
        rows["ticker"] = inp["ticker"].values if "ticker" in inp else None
        rows["revenue_yoy"] = compute_revenue_yoy(base_out, prior_out)

        if stop_reasons:
            return self._stop_result(stop_reasons, db, dp, rows, src, p)

        ok = rows[rows["coverage_status"] == "OK"].copy()

        # --- variant membership + null accounting ---
        member, nulls = variant_membership(ok)

        # --- forward returns ---
        spy = context.prices[SPY_CONID]
        rets, price_counters = compute_forward_returns(ok, context.prices, spy)

        # --- dependence ---
        per_conid = ok.groupby("conid").size()
        per_date = ok.groupby("candidate_date").size()
        top10 = per_conid.sort_values(ascending=False).head(10)
        tick = (ok.drop_duplicates("conid").set_index("conid")["ticker"]
                if "ticker" in ok else pd.Series(dtype=object))
        dep = {
            "nominal_N": int(len(ok)),
            "unique_conids": int(ok["conid"].nunique()),
            "unique_dates": int(ok["candidate_date"].nunique()),
            "avg_candidate_days_per_conid": round(float(per_conid.mean()), 2),
            "per_date_min": int(per_date.min()),
            "per_date_median": float(per_date.median()),
            "per_date_max": int(per_date.max()),
            "window_overlap_note": (
                f"okna {WINDOWS} kalendářních dní se překrývají u conidů "
                "s opakovanými candidate-days; efektivní N < nominální N"),
        }
        nono_idx = nonoverlap_selection(ok, p.get("nonoverlap_gap",
                                                  NONOVERLAP_GAP))

        # --- variant stats + statusy ---
        stats, nono_stats = {}, {}
        for v in VARIANTS:
            stats[v] = variant_stats(rets, member[v])
            stats[v]["field_null_excluded"] = nulls[v]
            nmask = member[v] & member[v].index.isin(nono_idx)
            r = rets.loc[nmask, f"ret_fwd_{PRIMARY_WINDOW}d"].dropna()
            nono_stats[v] = {
                "n": int(len(r)),
                "median_20d": round(float(r.median()), 4) if len(r) else None,
                "hit_20d": round(float((r > 0).mean()), 4) if len(r) else None,
            }
        statuses = {}
        for v in VARIANTS:
            statuses[v] = variant_status(v, stats[v], stats["A"],
                                         nono_stats[v], nono_stats["A"])

        # E: sektorová citlivost — počet financial-like names
        fin_count = None
        if not context.universe.empty and "sector" in context.universe.columns:
            e_conids = ok.loc[member["E"], "conid"].unique()
            sec = context.universe.reindex(e_conids)["sector"].astype(str)
            fin_count = int(sec.str.contains("Financial", case=False,
                                             na=False).sum())

        # --- tabulky / artefakty ---
        summary_rows = []
        for v in VARIANTS:
            s, (st, detail) = stats[v], statuses[v]
            summary_rows.append({
                "variant": v, "rule": VARIANT_DESC[v], "status": st,
                **{k: s[k] for k in s}, 
                "nonoverlap_n": nono_stats[v]["n"],
                "nonoverlap_median_20d": nono_stats[v]["median_20d"],
                "nonoverlap_hit_20d": nono_stats[v]["hit_20d"],
                "detail": detail,
            })
        variant_summary = pd.DataFrame(summary_rows).set_index("variant")

        fwd_table = pd.concat(
            [ok[["conid", "candidate_date", "ticker"]].reset_index(drop=True),
             member.reset_index(drop=True),
             rets.reset_index(drop=True)], axis=1)

        overall = "COMPLETED"
        result = ExperimentResult(
            metrics={
                "overall_result": overall,
                "candidate_days": int(len(inp)),
                "coverage_pct_base": db["coverage_pct"],
                "nominal_N": dep["nominal_N"],
                "unique_conids": dep["unique_conids"],
                "unique_dates": dep["unique_dates"],
                **{f"status_{v}": statuses[v][0] for v in VARIANTS},
                **{f"median_20d_{v}": stats[v]["median_20d"]
                   for v in VARIANTS},
                **{f"spyrel_median_20d_{v}": stats[v]["spyrel_median_20d"]
                   for v in VARIANTS},
                "entry_price_missing": price_counters["entry_price_missing"],
                "financial_like_in_E": fin_count,
            },
            tables={
                "candidate_days": inp,
                "fundamentals_output": rows,
                "variant_membership": fwd_table[
                    ["conid", "candidate_date", "ticker"] + VARIANTS],
                "forward_returns": fwd_table,
                "variant_summary": variant_summary,
                "dependence_top_conids": pd.DataFrame({
                    "count": top10,
                    "ticker": [tick.get(c) for c in top10.index]}),
                "coverage_base": pd.DataFrame([db]),
                "coverage_prior": pd.DataFrame([dp]),
            },
            artifacts={
                "edge_protocol_report.md": self._edge_report(
                    src, p, inp, db, dp, dep, variant_summary, statuses,
                    nono_stats, price_counters, fin_count, overall),
                "dependence_report.md": self._dependence_report(
                    dep, top10, tick, nono_stats),
                "source_manifest.json": self._manifest(src, p, db, dp,
                                                       overall),
            },
            summary=self._summary_text(statuses, stats, overall),
        )
        return result

    # ------------------------------------------------------------- helpers

    def _stop_result(self, reasons, db, dp, rows, src, p) -> ExperimentResult:
        return ExperimentResult(
            metrics={"overall_result": "STOP",
                     "stop_reasons": "; ".join(reasons),
                     "coverage_pct_base": db["coverage_pct"]},
            tables={"fundamentals_output": rows,
                    "coverage_base": pd.DataFrame([db]),
                    "coverage_prior": pd.DataFrame([dp])},
            artifacts={"source_manifest.json": self._manifest(
                src, p, db, dp, "STOP")},
            summary="RESULT: STOP — " + "; ".join(reasons),
        )

    def _manifest(self, src, p, db, dp, overall) -> str:
        import json
        return json.dumps({
            "snapshot_id": src.snapshot_id,
            "snapshot_data_hash": src.snapshot_data_hash,
            "contract_versions": src.contract_versions,
            "candidate_days_csv": p.get("candidate_days_csv"),
            "candidate_days_sha256": p.get("candidate_days_sha256"),
            "extraction_manifest": p.get("extraction_manifest"),
            "whitelist_version": p.get("whitelist_version"),
            "thresholds": {"roe_min": ROE_MIN, "de_max": DE_MAX,
                           "composite_min": COMPOSITE_MIN},
            "coverage_base": db, "coverage_prior": dp,
            "forward_returns_used_in_features": False,
            "overall_result": overall,
        }, indent=2, default=str)

    def _dependence_report(self, dep, top10, tick, nono) -> str:
        lines = ["# FUND-05 Dependence Report", ""]
        lines += [f"- {k}: {v}" for k, v in dep.items()]
        lines += ["", "## Top 10 nejopakovanějších conidů", "",
                  "| conid | ticker | count |", "|---|---|---|"]
        lines += [f"| {c} | {tick.get(c)} | {n} |"
                  for c, n in top10.items()]
        lines += ["", "## Non-overlap subsample (median/hit 20D)", "",
                  "| variant | n | median_20d | hit_20d |", "|---|---|---|---|"]
        lines += [f"| {v} | {s['n']} | {s['median_20d']} | {s['hit_20d']} |"
                  for v, s in nono.items()]
        lines += ["", "Efektivní N < nominální N (opakované conidy, "
                      "překryv oken, regime clustering). Závěry pouze: "
                      "statistically suggestive / not conclusive / "
                      "inconclusive.", ""]
        return "\n".join(lines)

    def _edge_report(self, src, p, inp, db, dp, dep, vs, statuses,
                     nono, price_counters, fin_count, overall) -> str:
        lines = [
            "# FUND-05 Edge Protocol Report",
            "",
            "**Signal-level research. TOTO NENÍ obchodovatelná strategie** "
            "— žádné náklady, slippage, sizing, portfolio konstrukce.",
            "",
            f"- snapshot_id: `{src.snapshot_id}`",
            f"- snapshot_data_hash: `{src.snapshot_data_hash}`",
            f"- candidate-days source: `{p.get('candidate_days_csv')}` "
            f"(sha256 `{p.get('candidate_days_sha256')}`)",
            f"- candidate-days: {len(inp)}",
            f"- feature whitelist: {p.get('whitelist_version')}",
            f"- forward return method: close-to-close, kalendářní offset "
            f"{WINDOWS} dní + nearest trading day do +{NEAREST_MAX_OFFSET}d "
            "(konvence MLEBucketsIRCGrid)",
            "- SPY-relative method: stock_fwd - SPY_fwd (týž postup), "
            "SEKUNDÁRNÍ diagnostika (regime kontrola), ne acceptance metrika",
            f"- entry_price_missing: {price_counters['entry_price_missing']}",
            f"- coverage base: pct={db['coverage_pct']} "
            f"(excluded={db['excluded_candidate_days']})",
            f"- coverage prior-year lookup: pct={dp['coverage_pct']} "
            f"(NO_SF1_ASOF_DATE={dp['reason_code_counts']['NO_SF1_ASOF_DATE']}"
            " — očekávané u starých dat, jde do field_null_excluded C/F)",
            f"- financial-like names ve variantě E: {fin_count} "
            "(E je sektorově citlivá)",
            "",
            "## Variant definitions & výsledky",
            "",
        ]
        cols = ["rule", "status", "n_members", "field_null_excluded",
                "n_ret_20d", "median_20d", "hit_20d", "spyrel_median_20d",
                "median_5d", "median_10d",
                "nonoverlap_n", "nonoverlap_median_20d"]
        lines.append("| v | " + " | ".join(cols) + " |")
        lines.append("|" + "---|" * (len(cols) + 1))
        for v in VARIANTS:
            r = vs.loc[v]
            lines.append("| " + v + " | "
                         + " | ".join(str(r[c]) for c in cols) + " |")
        lines += ["", "## Dependence", ""]
        lines += [f"- {k}: {v}" for k, v in dep.items()]
        lines += ["", "## Statusy", ""]
        lines += [f"- {v}: **{st}** — {det}"
                  for v, (st, det) in statuses.items()]
        lines += ["", f"## Overall RESULT: {overall}", "",
                  "PASS = candidate for OOS/robustness validation, "
                  "nic víc. Zakázaná tvrzení: edge confirmed / "
                  "production-ready / tradable strategy.", ""]
        return "\n".join(lines)

    def _summary_text(self, statuses, stats, overall) -> str:
        parts = [f"{v}:{statuses[v][0]}(med20={stats[v]['median_20d']})"
                 for v in VARIANTS]
        return (f"FUND-05 signal-level run — {overall}. " + "; ".join(parts)
                + ". Není obchodovatelná strategie; PASS = kandidát na "
                  "OOS validaci.")
