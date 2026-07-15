"""
RSAccelEdge_v1 — druhý Feature Validation experiment: Relative Strength Acceleration.

Research Project: RP-0010-FEATURE-VOLUME (feature validation umbrella)
Class:            feature-validation (technical)

FEATURE_002 — RS Acceleration (PRE-REGISTROVÁNO, zamčeno 2026-06-30):
    RS_Accel(D) = (close[D]/close[D-5]  - SPY[D]/SPY[D-5])
                - (close[D]/close[D-20] - SPY[D]/SPY[D-20])
    Obě RS složky KONČÍ dnem D. Žádné D+1.
    5D  = krátkodobé zrychlení; 20D = swing kontext.

    universe = MLE TOP10 × IRC TOP10
    target   = 20D forward return (close[D+20]/close[D]-1), SPOJITÝ
    metoda   = Spearman + kvantilové koše (interpretace); ticker-clustered bootstrap
    warmup   = ≥20 barů zpět (jinak vynechat)

    H0: RS_Accel nepřidává prediktivní hodnotu nad MLE×IRC.
    H1: vyšší RS_Accel koreluje s vyšším 20D forward returnem.
    regime split: DEFERRED.

    KNOWN LIMITATION: RS_Accel není plně nezávislá feature — částečně se překrývá
    s MLE selection logikou (MLE rank ~10D relativní síla). Pozitivní výsledek se
    NESMÍ automaticky interpretovat jako nový nezávislý edge.
    ZÁMEK: žádný binární práh, žádný window sweep (5D−20D fixní).

Předpoklady / edge cases:
    - Vyžaduje SPY (conid 756733) v context.prices (injektuje launcher).
    - RS složky z close; obě okna končí dnem D → look-ahead-čisté.
    - warmup: potřebuje ≥20 barů zpět pro long RS okno; jinak kandidát vynechán.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.context.experiment_context import ExperimentContext
from src.core.base_experiment import BaseExperiment
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult, ValidationResult
from src.query.research_query import ResearchQuery

# ── PRE-REGISTERED (locked) ─────────────────────────────────────────────
MLE_TOP          = 10
IRC_TOP          = 10
IRC_LOOKBACK     = 20
HOLD_DAYS        = 20
SHORT_WIN        = 5           # krátkodobé RS okno
LONG_WIN         = 20          # swing RS okno
MIN_FUTURE_DAYS  = 20
WARMUP_BARS      = 20
N_QUANTILES      = 5           # jen interpretace
BOOTSTRAP_B      = 2000
BOOTSTRAP_SEED   = 42
MIN_OBSERVATIONS = 100
SPY_CONID        = 756733
# ────────────────────────────────────────────────────────────────────────


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return np.nan
    rx = pd.Series(x).rank().values
    ry = pd.Series(y).rank().values
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = np.sqrt((rx**2).sum() * (ry**2).sum())
    return float((rx * ry).sum() / denom) if denom > 0 else np.nan


class RSAccelEdge_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="RSAccelEdge",
            version="1.0.0",
            hypothesis=(
                "H1: vyšší RS Acceleration (5D RS − 20D RS vs SPY) koreluje s vyšším "
                "20D forward return nad MLE×IRC kandidáty. H0: nepřidává edge. "
                "Spojitý vztah (Spearman), žádný práh, žádný window sweep."
            ),
            description=(
                "Druhý Feature Validation experiment. RS Acceleration jako spojitá "
                "technická feature nad MLE TOP10 × IRC TOP10. Spearman + kvantily, "
                "ticker-clustered bootstrap. KNOWN LIMITATION: překryv s MLE selection."
            ),
            required_data=["prices", "feature:MLE_Rank_10d", "signal:IRC"],
            parameters={
                "mle_top": MLE_TOP, "irc_top": IRC_TOP, "irc_lookback": IRC_LOOKBACK,
                "hold_days": HOLD_DAYS, "short_win": SHORT_WIN, "long_win": LONG_WIN,
                "min_future_days": MIN_FUTURE_DAYS, "warmup_bars": WARMUP_BARS,
                "n_quantiles": N_QUANTILES, "bootstrap_b": BOOTSTRAP_B,
                "bootstrap_seed": BOOTSTRAP_SEED, "min_observations": MIN_OBSERVATIONS,
                "spy_conid": SPY_CONID,
            },
            tags=["feature-validation", "technical", "rs-acceleration", "continuous", "pre-registered"],
            author="MSL/MRL architecture session",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle = context.features.all_for_name("MLE_Rank_10d")
        if len(mle) < MIN_OBSERVATIONS:
            return ValidationResult.failed(f"Málo MLE_Rank_10d: {len(mle)}")
        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed("IRC chybí v context.signals.")
        if SPY_CONID not in context.prices:
            return ValidationResult.failed(f"SPY (conid={SPY_CONID}) není v context.prices.")
        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        query = ResearchQuery(context)

        irc = context.signals["IRC"].copy()
        irc = irc[irc["lookback"] == IRC_LOOKBACK]
        irc["date"] = pd.to_datetime(irc["date"])
        irc_index = irc.set_index(["date", "industry"])["rank"].to_dict()

        spy = context.prices[SPY_CONID]
        spy_close = spy["close"]

        trading_days = query.dates()
        if not trading_days:
            return ExperimentResult(metrics={"error": "no_trading_days"}, summary="Žádné obchodní dny.")
        day_pos = {pd.Timestamp(d): i for i, d in enumerate(trading_days)}
        n_days = len(trading_days)

        rows = []
        for d in trading_days:
            ts = pd.Timestamp(d)
            sig_pos = day_pos[ts]
            if sig_pos + MIN_FUTURE_DAYS >= n_days or sig_pos < WARMUP_BARS:
                continue
            if ts not in spy_close.index:
                continue
            # SPY RS reference (okna končí dnem D)
            spy_now = float(spy_close.loc[ts])
            spy_s_ts = pd.Timestamp(trading_days[sig_pos - SHORT_WIN])
            spy_l_ts = pd.Timestamp(trading_days[sig_pos - LONG_WIN])
            if spy_s_ts not in spy_close.index or spy_l_ts not in spy_close.index:
                continue
            spy_s = float(spy_close.loc[spy_s_ts])
            spy_l = float(spy_close.loc[spy_l_ts])
            if spy_s <= 0 or spy_l <= 0:
                continue

            snaps = [
                s for s in query.assets(date=d)
                if s.mle_rank_10d is not None and s.mle_rank_10d <= MLE_TOP
            ]
            for s in snaps:
                irc_rank = irc_index.get((ts, s.industry))
                if irc_rank is None or irc_rank > IRC_TOP:
                    continue
                pdf = context.prices.get(s.conid)
                if pdf is None or ts not in pdf.index:
                    continue
                c_now = float(pdf.loc[ts, "close"])
                s_ts = pd.Timestamp(trading_days[sig_pos - SHORT_WIN])
                l_ts = pd.Timestamp(trading_days[sig_pos - LONG_WIN])
                if s_ts not in pdf.index or l_ts not in pdf.index:
                    continue
                c_s = float(pdf.loc[s_ts, "close"])
                c_l = float(pdf.loc[l_ts, "close"])
                if c_s <= 0 or c_l <= 0 or c_now <= 0:
                    continue
                rs_short = (c_now / c_s) - (spy_now / spy_s)
                rs_long  = (c_now / c_l) - (spy_now / spy_l)
                rs_accel = rs_short - rs_long

                exit_ts = pd.Timestamp(trading_days[sig_pos + HOLD_DAYS])
                if exit_ts not in pdf.index:
                    continue
                fwd = float(pdf.loc[exit_ts, "close"]) / c_now - 1.0
                rows.append({"ticker": s.ticker, "rs_accel": float(rs_accel), "fwd": fwd})

        if not rows:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Žádné candidate-days.")

        df = pd.DataFrame(rows)
        N = len(df)
        uniq = df["ticker"].nunique()

        rho = _spearman(df["rs_accel"].values, df["fwd"].values)

        rng = np.random.default_rng(BOOTSTRAP_SEED)
        by: dict[str, list] = {}
        for tk, a, fw in zip(df["ticker"], df["rs_accel"], df["fwd"]):
            by.setdefault(tk, []).append((a, fw))
        keys = list(by.keys())
        rs = np.empty(BOOTSTRAP_B)
        for i in range(BOOTSTRAP_B):
            pick = rng.choice(keys, size=len(keys), replace=True)
            arr = np.asarray([p for k in pick for p in by[k]])
            rs[i] = _spearman(arr[:, 0], arr[:, 1])
        rs = rs[~np.isnan(rs)]
        lo, hi = np.percentile(rs, [2.5, 97.5])
        significant = not (lo <= 0 <= hi)

        q_rows = []
        try:
            df["q"] = pd.qcut(df["rs_accel"], N_QUANTILES, labels=False, duplicates="drop")
            for qi, g in df.groupby("q", observed=True):
                q_rows.append({
                    "quantile": int(qi) + 1,
                    "rs_accel_min": round(float(g["rs_accel"].min()), 4),
                    "rs_accel_max": round(float(g["rs_accel"].max()), 4),
                    "mean_fwd_pct": round(float(g["fwd"].mean()) * 100, 3),
                    "N": int(len(g)),
                })
        except Exception:
            pass
        q_df = pd.DataFrame(q_rows)
        spread = None
        if len(q_df) >= 2:
            spread = round(q_df.iloc[-1]["mean_fwd_pct"] - q_df.iloc[0]["mean_fwd_pct"], 3)

        h1_supported = significant and rho > 0

        metrics = {
            "N_candidate_days": N,
            "unique_tickers": uniq,
            "spearman_rho": round(rho, 4),
            "rho_ci_lo": round(float(lo), 4),
            "rho_ci_hi": round(float(hi), 4),
            "rho_significant": significant,
            "H1_supported": h1_supported,
            "H0_rejected": h1_supported,
            "quantile_spread_top_minus_bottom_pp": spread,
            "rs_accel_min": round(float(df["rs_accel"].min()), 4),
            "rs_accel_median": round(float(df["rs_accel"].median()), 4),
            "rs_accel_max": round(float(df["rs_accel"].max()), 4),
        }

        dep_warn = (
            f"DEPENDENCE: nominal N={N}, tickerů={uniq} (poměr {uniq/N:.2f}) → efektivní "
            f"N << nominal. Signifikance jen z ticker-clustered bootstrapu; naivní p ignorovat."
        )
        verdict = "H1 SUPPORTED" if h1_supported else "H1 NOT SUPPORTED (H0 nezamítnuta)"
        sign_note = ""
        if not h1_supported and rho < 0:
            sign_note = (
                f" POZOR: rho je ZÁPORNÉ ({metrics['spearman_rho']}) — náznak jde OPAČNĚ než H1 "
                f"(decelerace → vyšší fwd), ale nesignifikantně (CI přes nulu). Exploratorní, ne nález."
            )
        summary = (
            f"RS Acceleration vs 20D fwd (spojitý): Spearman rho={metrics['spearman_rho']} "
            f"CI[{metrics['rho_ci_lo']},{metrics['rho_ci_hi']}] sig={significant} → {verdict}.{sign_note} "
            f"Kvantilový spread (Q{N_QUANTILES}-Q1): {spread}pp (JEN interpretace, ne edge). "
            f"KNOWN LIMITATION: RS_Accel se překrývá s MLE selection → i případný signifikantní "
            f"výsledek NEčíst automaticky jako nezávislý edge. {dep_warn} REGIME SPLIT DEFERRED."
        )
        return ExperimentResult(
            metrics=metrics,
            tables={"quantile_buckets": q_df},
            summary=summary,
        )
