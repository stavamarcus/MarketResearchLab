"""
LeadershipLossEdge_v1 — validace EXIT komponenty (trade-level, bez portfolia).

Research Project: RP-0012-LEADERSHIP-LOSS-EXIT
Class:            exit-edge (druhý experiment třídy Exit Validation)

Otázka:
    Realizuje exit podmíněný ztrátou leadership statusu
    (MLE_Rank_10d > 50, fill next open) větší část validovaného MLE×IRC
    selection edge UVNITŘ fixního 20D okna než fixed 20D hold?

═══════════════════════════════════════════════════════════════════════
PRE-REGISTROVANÉ PARAMETRY — ZAMČENO 2026-07-02 (PM approval).
Neupravovat podle výsledku.
═══════════════════════════════════════════════════════════════════════

H1a (PRIMÁRNÍ): RANK_50 vs TIME_20; matched comparison, fixní okno
    D→D+20, cash 0 % po exitu; ticker-clustered bootstrap (B=10000,
    seed=42). PASS ⇔ 95% CI celé > 0.
Sensitivity (NE hypotézy): RANK_25, RANK_100. IRC varianty VYLOUČENY
    (jiný mechanismus → samostatný RP). Práh 30 se NEPŘIDÁVÁ.
Survival statistika (deskriptivní, povinná): přežití v TOP{25,50,100}
    po 5/10/15/20 dnech + median time-to-loss.

Metodické zámky:
    - rank série = MLE_Rank_10d (TÁŽ jako selekce)
    - rank as-of close(k) (D1 batch po close), signal close, fill next open
    - MISSING RANK = CENSORED: trade s chybějícím rankem KDEKOLIV v signal
      window D+1..D+19 vyloučen ze VŠECH variant i baseline (žádná
      imputace). Kontrola pokrytí je variantově NEZÁVISLÁ → identický
      matched set. Report n + pct; pct > 1 % → investigace.
    - žádný price warmup (rank rule) → plný candidate pool
    - min_future_days = 22; CACHE_ONLY; žádný threshold sweep;
      regime split DEFERRED; deterministic result_hash

Edge cases:
    - rank může existovat pro den, kdy ticker nemá price bar (halt):
      rank série se mapuje NA lokální bary — rank bez baru se nepoužije,
      bar bez ranku = missing → censoring kontrola.
    - survival měřeno na included trades (plné rank pokrytí) — bez
      vnitřního censoringu, Kaplan-Meier není nutný.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult
from src.query.research_query import ResearchQuery

from experiments.exit_validation.exit_engine import simulate_trade
from experiments.exit_validation.exit_rules import RankLossExit, TimeExit

# ── PRE-REGISTERED (locked 2026-07-02) ──────────────────────────────────
MLE_TOP           = 10
IRC_TOP           = 10
IRC_LOOKBACK      = 20
HOLD_DAYS         = 20
MIN_FUTURE_DAYS   = 22

RANK_FEATURE      = "MLE_Rank_10d"
PRIMARY_THRESHOLD = 50
SENS_THRESHOLDS   = (25, 100)
SURVIVAL_DAYS     = (5, 10, 15, 20)

CENSOR_INVESTIGATE_PCT = 1.0   # podíl censored > 1 % → investigace

BOOTSTRAP_B       = 10_000
BOOTSTRAP_SEED    = 42
MIN_OBSERVATIONS  = 100
# ────────────────────────────────────────────────────────────────────────

LOCKED_PARAMS = {
    "mle_top": MLE_TOP, "irc_top": IRC_TOP, "irc_lookback": IRC_LOOKBACK,
    "hold_days": HOLD_DAYS, "min_future_days": MIN_FUTURE_DAYS,
    "rank_feature": RANK_FEATURE,
    "primary_threshold": PRIMARY_THRESHOLD,
    "sensitivity_thresholds": list(SENS_THRESHOLDS),
    "survival_days": list(SURVIVAL_DAYS),
    "missing_rank_policy": "censored",
    "censor_investigate_pct": CENSOR_INVESTIGATE_PCT,
    "bootstrap_b": BOOTSTRAP_B, "bootstrap_seed": BOOTSTRAP_SEED,
    "min_observations": MIN_OBSERVATIONS,
    "entry": "close(D)",
}


class LeadershipLossEdge_v1(BaseExperiment):

    # ---------------- define ----------------
    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="LeadershipLossEdge",
            version="1.0.0",
            hypothesis=(
                "H1a: exit při ztrátě leadership statusu (MLE_Rank_10d > 50, "
                "signal close, fill next open) zvyšuje mean return uvnitř "
                "fixního 20D okna proti fixed 20D hold, nad MLE×IRC kandidáty."
            ),
            description=(
                "Exit-edge validace, signálově nativní pravidlo (rank z téže "
                "série jako selekce). RANK_50 primární, RANK_25/100 sensitivity. "
                "Missing rank = censored (bez imputace). Leadership survival "
                "statistika deskriptivně. Regime split deferred."
            ),
            required_data=["prices", f"feature:{RANK_FEATURE}", "signal:IRC"],
            parameters=dict(LOCKED_PARAMS),
            tags=["exit-edge", "matched-comparison", "rank-loss", "pre-registered"],
            author="MRL RP-0012 session (PM approved 2026-07-02)",
        )

    # ---------------- validate ----------------
    def validate(self, context: ExperimentContext) -> ValidationResult:
        feats = context.features.all_for_name(RANK_FEATURE)
        if len(feats) < MIN_OBSERVATIONS:
            return ValidationResult.failed(f"Málo {RANK_FEATURE}: {len(feats)}")
        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed("IRC chybí v context.signals.")
        if not context.prices:
            return ValidationResult.failed("Prázdné context.prices.")
        sample = next(iter(context.prices.values()))
        for col in ("open", "close"):
            if col not in sample.columns:
                return ValidationResult.failed(f"Price frame postrádá '{col}'.")
        return ValidationResult.ok()

    # ---------------- run ----------------
    def run(self, context: ExperimentContext) -> ExperimentResult:
        query = ResearchQuery(context)

        irc = context.signals["IRC"].copy()
        irc = irc[irc["lookback"] == IRC_LOOKBACK]
        irc["date"] = pd.to_datetime(irc["date"])
        irc_index = irc.set_index(["date", "industry"])["rank"].to_dict()

        # rank lookup: (Timestamp, conid) -> rank
        rank_index: dict[tuple[pd.Timestamp, int], float] = {}
        for f in context.features.all_for_name(RANK_FEATURE):
            rank_index[(pd.Timestamp(f.date), f.conid)] = float(f.value)

        trading_days = query.dates()
        if not trading_days:
            return ExperimentResult(metrics={"error": "no_trading_days"},
                                    summary="Žádné obchodní dny.")
        day_pos = {pd.Timestamp(d): i for i, d in enumerate(trading_days)}
        n_days = len(trading_days)

        bar_cache: dict[int, tuple[pd.DatetimeIndex, np.ndarray, np.ndarray]] = {}

        def bars(conid: int):
            b = bar_cache.get(conid)
            if b is None:
                df = context.prices.get(conid)
                if df is None or df.empty:
                    b = (pd.DatetimeIndex([]), np.empty(0), np.empty(0))
                else:
                    b = (df.index,
                         df["open"].to_numpy(dtype=float),
                         df["close"].to_numpy(dtype=float))
                bar_cache[conid] = b
            return b

        thresholds = (PRIMARY_THRESHOLD,) + SENS_THRESHOLDS
        baseline_name = f"TIME_{HOLD_DAYS}"
        primary_name = f"RANK_{PRIMARY_THRESHOLD}"

        rows: list[dict] = []
        excl_price = 0
        censored_missing_rank = 0

        for d in trading_days:
            ts = pd.Timestamp(d)
            sig_pos = day_pos[ts]
            if sig_pos + MIN_FUTURE_DAYS >= n_days:
                continue
            snaps = [
                s for s in query.assets(date=d)
                if s.mle_rank_10d is not None and s.mle_rank_10d <= MLE_TOP
            ]
            for s in snaps:
                irc_rank = irc_index.get((ts, s.industry))
                if irc_rank is None or irc_rank > IRC_TOP:
                    continue

                idx, opens, closes = bars(s.conid)
                loc = idx.get_indexer([ts])[0]
                if loc < 0:
                    excl_price += 1
                    continue
                entry_pos = int(loc)
                window_end = entry_pos + HOLD_DAYS
                if window_end >= len(idx):
                    excl_price += 1
                    continue
                seg = closes[entry_pos:window_end + 1]
                if not np.all(np.isfinite(seg)) or seg[0] <= 0:
                    excl_price += 1
                    continue

                # rank série zarovnaná na lokální bary entry..window_end
                ranks = np.full(len(closes), np.nan)
                for p in range(entry_pos, window_end + 1):
                    ranks[p] = rank_index.get((idx[p], s.conid), np.nan)

                # ── CENSORING (variantově NEZÁVISLÉ): signal window
                #    D+1..D+19 musí mít plné rank pokrytí ──
                sig_window = ranks[entry_pos + 1:window_end]
                if np.isnan(sig_window).any():
                    censored_missing_rank += 1
                    continue

                rec: dict = {"date": ts, "ticker": s.ticker, "conid": s.conid}

                # baseline
                t_rule = TimeExit(HOLD_DAYS)
                t_rule.prepare(closes)
                out_b = simulate_trade(t_rule, entry_pos, window_end,
                                       opens, closes)
                if out_b is None:
                    excl_price += 1
                    continue
                rec[f"ret_{baseline_name}"] = out_b.ret
                rec[f"hold_{baseline_name}"] = out_b.hold_days
                rec[f"early_{baseline_name}"] = out_b.exited_early

                # rank varianty
                for th in thresholds:
                    rule = RankLossExit(th)
                    rule.set_series(ranks)
                    rule.prepare(closes)
                    out = simulate_trade(rule, entry_pos, window_end,
                                         opens, closes)
                    v = rule.name
                    rec[f"ret_{v}"] = out.ret
                    rec[f"hold_{v}"] = out.hold_days
                    rec[f"early_{v}"] = out.exited_early
                    rec[f"gap_{v}"] = out.fill_gap
                    rec[f"gapunres_{v}"] = out.fill_gap_unresolved
                    if out.exited_early:
                        base_px = (opens[out.exit_pos]
                                   if np.isfinite(opens[out.exit_pos])
                                   and opens[out.exit_pos] > 0
                                   else closes[out.exit_pos])
                        rec[f"rem_{v}"] = float(
                            closes[window_end] / base_px - 1.0)

                # ── survival: první breach prahu v D+1..D+20 ──
                # (rank na D+20 = ranks[window_end]; pro survival po 20d
                #  je potřeba i poslední den okna — plné pokrytí ranks
                #  entry+1..window_end kontrolováno níže jen deskriptivně)
                for th in thresholds:
                    breach = None
                    for k in range(1, HOLD_DAYS + 1):
                        r = ranks[entry_pos + k]
                        if np.isnan(r):
                            break  # D+20 rank chybí → survival 20d neurčitelný
                        if r > th:
                            breach = k
                            break
                    rec[f"tloss_{th}"] = breach  # None = bez breachu (v pokrytém rozsahu)
                    rec[f"cov20_{th}"] = not np.isnan(ranks[window_end])

                rows.append(rec)

        if not rows:
            return ExperimentResult(metrics={"error": "no_records"},
                                    summary="Žádné candidate-days.")

        df = pd.DataFrame(rows)
        N = len(df)
        uniq = df["ticker"].nunique()
        total_considered = N + censored_missing_rank
        censored_pct = (100.0 * censored_missing_rank / total_considered
                        if total_considered else 0.0)
        rng = np.random.default_rng(BOOTSTRAP_SEED)

        def clustered_ci(col_v: str):
            diffs = (df[col_v] - df[f"ret_{baseline_name}"]).to_numpy()
            by: dict[str, list] = {}
            for tk, dv in zip(df["ticker"].to_numpy(), diffs):
                by.setdefault(tk, []).append(dv)
            arrays = {k: np.asarray(v) for k, v in by.items()}
            keys = list(arrays.keys())
            means = np.empty(BOOTSTRAP_B)
            for i in range(BOOTSTRAP_B):
                pick = rng.choice(keys, size=len(keys), replace=True)
                means[i] = np.concatenate([arrays[k] for k in pick]).mean()
            lo, hi = np.percentile(means, [2.5, 97.5])
            return float(diffs.mean()), float(lo), float(hi)

        def stats(col: str):
            s = df[col]
            w, l = s[s > 0], s[s <= 0]
            return {
                "mean_pct": round(float(s.mean()) * 100, 3),
                "median_pct": round(float(s.median()) * 100, 3),
                "win_pct": round(100.0 * float((s > 0).mean()), 2),
                "avg_winner_pct": round(float(w.mean()) * 100, 3) if len(w) else None,
                "avg_loser_pct": round(float(l.mean()) * 100, 3) if len(l) else None,
                "expectancy_pct": round(float(s.mean()) * 100, 3),
            }

        metrics: dict = {
            "N_candidate_days": N,
            "unique_tickers": uniq,
            "censored_missing_rank_n": censored_missing_rank,
            "censored_missing_rank_pct": round(censored_pct, 3),
            "censoring_investigate": bool(censored_pct > CENSOR_INVESTIGATE_PCT),
            "excluded_price_data": excl_price,
        }

        variant_rows = []
        all_variants = [baseline_name] + [f"RANK_{t}" for t in thresholds]
        for v in all_variants:
            st = stats(f"ret_{v}")
            row = {"variant": v, "N": N, **st,
                   "early_exit_pct": round(float(df[f"early_{v}"].mean()) * 100, 2),
                   "hold_mean_d": round(float(df[f"hold_{v}"].mean()), 2)}
            if v != baseline_name:
                a, lo, hi = clustered_ci(f"ret_{v}")
                row.update({
                    "paired_diff_pp": round(a * 100, 3),
                    "ci_lo_pp": round(lo * 100, 3),
                    "ci_hi_pp": round(hi * 100, 3),
                    "significant": bool(lo > 0 or hi < 0),
                })
                if f"rem_{v}" in df.columns:
                    rem = df[f"rem_{v}"].dropna()
                    row["avoided_losers"] = int((rem < 0).sum())
                    row["missed_winners"] = int((rem > 0).sum())
                    row["missed_winner_mean_pct"] = (
                        round(float(rem[rem > 0].mean()) * 100, 2)
                        if (rem > 0).any() else None)
                    row["avoided_loser_mean_pct"] = (
                        round(float(rem[rem < 0].mean()) * 100, 2)
                        if (rem < 0).any() else None)
                else:
                    row["avoided_losers"] = 0
                    row["missed_winners"] = 0
                row["fill_gap_n"] = int(df[f"gap_{v}"].sum())
                row["fill_gap_unresolved_n"] = int(df[f"gapunres_{v}"].sum())
            variant_rows.append(row)
        per_variant = pd.DataFrame(variant_rows)

        # ── H1a rozhodnutí (POUZE RANK_50) ──
        prim = per_variant[per_variant["variant"] == primary_name].iloc[0]
        h1a_pass = bool(prim["ci_lo_pp"] > 0)
        metrics.update({
            "H1a_paired_diff_pp": float(prim["paired_diff_pp"]),
            "H1a_ci_lo_pp": float(prim["ci_lo_pp"]),
            "H1a_ci_hi_pp": float(prim["ci_hi_pp"]),
            "H1a_pass": h1a_pass,
            "baseline_mean_pct": float(per_variant[
                per_variant["variant"] == baseline_name]["mean_pct"].iloc[0]),
        })
        for _, r in per_variant.iterrows():
            if r["variant"] == baseline_name:
                continue
            p = r["variant"].lower()
            metrics[f"{p}_paired_diff_pp"] = float(r["paired_diff_pp"])
            metrics[f"{p}_early_exit_pct"] = float(r["early_exit_pct"])
            metrics[f"{p}_hold_mean_d"] = float(r["hold_mean_d"])

        # ── survival statistika (deskriptivní) ──
        surv_rows = []
        for th in thresholds:
            tl = df[f"tloss_{th}"]
            cov = df[f"cov20_{th}"]
            row = {"threshold": th, "N": N}
            for k in SURVIVAL_DAYS:
                if k < HOLD_DAYS:
                    surv = float((tl.isna() | (tl > k)).mean())
                else:
                    # 20d přežití vyžaduje rank pokrytí i na D+20
                    sub = df[cov]
                    surv = (float((sub[f"tloss_{th}"].isna()
                                   | (sub[f"tloss_{th}"] > k)).mean())
                            if len(sub) else float("nan"))
                row[f"surv_{k}d_pct"] = round(surv * 100, 2)
            losses = tl.dropna()
            row["loss_n"] = int(len(losses))
            row["loss_pct"] = round(100.0 * len(losses) / N, 2)
            row["median_time_to_loss_d"] = (
                float(losses.median()) if len(losses) else None)
            surv_rows.append(row)
        survival = pd.DataFrame(surv_rows)
        p50 = survival[survival["threshold"] == PRIMARY_THRESHOLD].iloc[0]
        metrics.update({
            "surv50_after_5d_pct": float(p50["surv_5d_pct"]),
            "surv50_after_10d_pct": float(p50["surv_10d_pct"]),
            "surv50_after_15d_pct": float(p50["surv_15d_pct"]),
            "surv50_after_20d_pct": float(p50["surv_20d_pct"]),
            "surv50_loss_pct": float(p50["loss_pct"]),
            "surv50_median_time_to_loss_d": (
                float(p50["median_time_to_loss_d"])
                if p50["median_time_to_loss_d"] is not None else None),
        })

        tables = {"per_variant": per_variant, "survival": survival, "trades": df}

        eff = uniq / N if N else 0
        dep_warn = (
            f"DEPENDENCE WARNING: nominal N={N}, {uniq} unikátních tickerů "
            f"(poměr {eff:.2f}). Signifikance výhradně ticker-clustered bootstrap."
        )
        regime_note = (
            "REGIME SPLIT DEFERRED: leadership loss frekvence je režimově "
            "závislá (rotace vs trvalý trend). Výsledek vázán na období běhu."
        )
        censor_note = (
            f"CENSORING: {censored_missing_rank} trades ({censored_pct:.2f} %) "
            f"vyloučeno pro chybějící rank (bez imputace). "
            + ("INVESTIGACE NUTNÁ (>1 %)." if censored_pct > CENSOR_INVESTIGATE_PCT
               else "Pod prahem investigace.")
        )
        caveats = (
            "CAVEATS: (1) Entry close(D) look-ahead — sdílený párem. "
            "(2) RANK_25/100 sensitivity, NE hypotézy. (3) Survival = "
            "deskriptivní interpretace, bez kritéria. (4) Reinvestice "
            "uvolněného kapitálu → MSL, ne sem."
        )

        summary = self._summary(metrics, per_variant, survival,
                                dep_warn, regime_note, censor_note, caveats)
        return ExperimentResult(metrics=metrics, tables=tables, summary=summary)

    @staticmethod
    def _summary(m, pv, surv, dep_warn, regime_note, censor_note, caveats) -> str:
        verdict = ("H1a PASS — Leadership Loss exit zvyšuje return ve fixním 20D okně"
                   if m["H1a_pass"] else
                   "H1a NOT SUPPORTED — Leadership Loss exit nezlepšuje fixní 20D okno")
        sens = "; ".join(
            f"{r['variant']}: {r['paired_diff_pp']}pp (early {r['early_exit_pct']}%)"
            for _, r in pv.iterrows() if str(r["variant"]).startswith("RANK_")
        )
        return (
            f"{verdict}. Primární paired diff {m['H1a_paired_diff_pp']}pp "
            f"CI[{m['H1a_ci_lo_pp']}, {m['H1a_ci_hi_pp']}] "
            f"(baseline mean {m['baseline_mean_pct']}%). Varianty: {sens}. "
            f"SURVIVAL TOP50: 5d {m['surv50_after_5d_pct']}% | "
            f"10d {m['surv50_after_10d_pct']}% | 15d {m['surv50_after_15d_pct']}% | "
            f"20d {m['surv50_after_20d_pct']}% | loss {m['surv50_loss_pct']}% "
            f"(median t-to-loss {m['surv50_median_time_to_loss_d']}d). "
            f"{censor_note} {dep_warn} {regime_note} {caveats}"
        )
