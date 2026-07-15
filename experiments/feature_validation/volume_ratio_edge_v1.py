"""
VolumeRatioEdge_v1 — první Feature Validation experiment.

Research Project: RP-0010-FEATURE-VOLUME
Class:            feature-validation (technical)

FEATURE_001 — Volume Ratio (PRE-REGISTROVÁNO, zamčeno 2026-06-30):
    feature = Volume(D) / mean(Volume[D-19 … D])   # 20-barové okno KONČÍ dnem D
    zdroj   = D1 parquet "volume" (v tisících — pro ratio neškodné)
    universe= MLE TOP10 × IRC TOP10
    target  = 20D forward return, close[D+20]/close[D]-1  (SPOJITÝ, ne buckety)
    metoda  = Spearman rho + kvantilové koše (interpretace); ticker-clustered bootstrap CI
    warmup  = vynechat kandidáta bez 20 předchozích volume barů (vol_ratio == NaN)

    H0: Volume Ratio nepřidává inkrementální prediktivní hodnotu nad MLE×IRC.
    H1: vyšší Volume Ratio koreluje s vyšším 20D forward return.
    regime split: DEFERRED.

    ZÁMEK: žádný binární práh (žádné "vol_ratio > 1.5"). Pouze spojitý vztah.
    Kvantilové koše jsou JEN pro interpretaci, ne pro definici edge.

Předpoklady / edge cases:
    - volume as-of-close (D1 batch po close, GDU). Pokud by vznikl intraday update
      téhož D1 souboru, feature nutno re-auditovat (viz KR Q2).
    - MLE archiv volume NEobsahuje → feature z context.prices["volume"], ne ze signálu.
    - vol_ratio v prvních 19 barech = NaN (rolling warmup) → kandidát vynechán.
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
VOL_WINDOW       = 20          # SMA okno pro volume, končí dnem D
MIN_FUTURE_DAYS  = 20
N_QUANTILES      = 5           # jen interpretace
BOOTSTRAP_B      = 2000
BOOTSTRAP_SEED   = 42
MIN_OBSERVATIONS = 100
# ────────────────────────────────────────────────────────────────────────


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rho bez scipy (rank-based Pearson). NaN-safe caller."""
    if len(x) < 3:
        return np.nan
    rx = pd.Series(x).rank().values
    ry = pd.Series(y).rank().values
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = np.sqrt((rx**2).sum() * (ry**2).sum())
    return float((rx * ry).sum() / denom) if denom > 0 else np.nan


class VolumeRatioEdge_v1(BaseExperiment):

    def define(self) -> ExperimentDefinition:
        return ExperimentDefinition(
            name="VolumeRatioEdge",
            version="1.0.0",
            hypothesis=(
                "H1: vyšší Volume Ratio (Volume(D)/SMA20(Volume)) koreluje s vyšším "
                "20D forward return nad MLE×IRC kandidáty. H0: nepřidává edge. "
                "Spojitý vztah (Spearman), žádný binární práh."
            ),
            description=(
                "První Feature Validation experiment. Volume Ratio jako spojitá "
                "technická feature nad MLE TOP10 × IRC TOP10. Spearman rho + kvantily, "
                "ticker-clustered bootstrap. Feature nemění vstup/výstup/množinu."
            ),
            required_data=["prices", "feature:MLE_Rank_10d", "signal:IRC"],
            parameters={
                "mle_top": MLE_TOP, "irc_top": IRC_TOP, "irc_lookback": IRC_LOOKBACK,
                "hold_days": HOLD_DAYS, "vol_window": VOL_WINDOW,
                "min_future_days": MIN_FUTURE_DAYS, "n_quantiles": N_QUANTILES,
                "bootstrap_b": BOOTSTRAP_B, "bootstrap_seed": BOOTSTRAP_SEED,
                "min_observations": MIN_OBSERVATIONS,
            },
            tags=["feature-validation", "technical", "volume", "continuous", "pre-registered"],
            author="MSL/MRL architecture session",
        )

    def validate(self, context: ExperimentContext) -> ValidationResult:
        mle = context.features.all_for_name("MLE_Rank_10d")
        if len(mle) < MIN_OBSERVATIONS:
            return ValidationResult.failed(f"Málo MLE_Rank_10d: {len(mle)}")
        if "IRC" not in context.signals or context.signals["IRC"].empty:
            return ValidationResult.failed("IRC chybí v context.signals.")
        if not context.prices:
            return ValidationResult.failed("Prázdné context.prices.")
        # ověř přítomnost volume alespoň v jednom price df
        sample = next(iter(context.prices.values()), None)
        if sample is not None and "volume" not in sample.columns:
            return ValidationResult.failed("Cenová data neobsahují sloupec 'volume'.")
        return ValidationResult.ok()

    def run(self, context: ExperimentContext) -> ExperimentResult:
        query = ResearchQuery(context)

        irc = context.signals["IRC"].copy()
        irc = irc[irc["lookback"] == IRC_LOOKBACK]
        irc["date"] = pd.to_datetime(irc["date"])
        irc_index = irc.set_index(["date", "industry"])["rank"].to_dict()

        trading_days = query.dates()
        if not trading_days:
            return ExperimentResult(metrics={"error": "no_trading_days"}, summary="Žádné obchodní dny.")
        day_pos = {pd.Timestamp(d): i for i, d in enumerate(trading_days)}
        n_days = len(trading_days)

        vr_cache: dict[int, pd.DataFrame] = {}

        def enriched(conid: int):
            if conid in vr_cache:
                return vr_cache[conid]
            src = context.prices.get(conid)
            if src is None or src.empty or "volume" not in src.columns:
                vr_cache[conid] = None
                return None
            df = src.copy()
            df["vol_sma"] = df["volume"].rolling(VOL_WINDOW).mean()
            df["vol_ratio"] = df["volume"] / df["vol_sma"]
            vr_cache[conid] = df
            return df

        rows = []
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
                df = enriched(s.conid)
                if df is None or ts not in df.index:
                    continue
                vr = df.loc[ts, "vol_ratio"]
                if pd.isna(vr):
                    continue  # warmup: chybí 20 volume barů
                entry = df.loc[ts, "close"]
                exit_ts = pd.Timestamp(trading_days[sig_pos + HOLD_DAYS])
                if exit_ts not in df.index or entry <= 0:
                    continue
                fwd = float(df.loc[exit_ts, "close"]) / float(entry) - 1.0
                rows.append({"ticker": s.ticker, "vol_ratio": float(vr), "fwd": fwd})

        if not rows:
            return ExperimentResult(metrics={"error": "no_records"}, summary="Žádné candidate-days.")

        df = pd.DataFrame(rows)
        N = len(df)
        uniq = df["ticker"].nunique()

        rho = _spearman(df["vol_ratio"].values, df["fwd"].values)

        # ticker-clustered bootstrap na Spearman rho
        rng = np.random.default_rng(BOOTSTRAP_SEED)
        by: dict[str, list] = {}
        for tk, vr, fw in zip(df["ticker"], df["vol_ratio"], df["fwd"]):
            by.setdefault(tk, []).append((vr, fw))
        keys = list(by.keys())
        rs = np.empty(BOOTSTRAP_B)
        for i in range(BOOTSTRAP_B):
            pick = rng.choice(keys, size=len(keys), replace=True)
            pairs = [p for k in pick for p in by[k]]
            arr = np.asarray(pairs)
            rs[i] = _spearman(arr[:, 0], arr[:, 1])
        rs = rs[~np.isnan(rs)]
        lo, hi = np.percentile(rs, [2.5, 97.5])
        significant = not (lo <= 0 <= hi)

        # kvantilové koše — JEN interpretace
        q_rows = []
        try:
            df["q"] = pd.qcut(df["vol_ratio"], N_QUANTILES, labels=False, duplicates="drop")
            for qi, g in df.groupby("q", observed=True):
                q_rows.append({
                    "quantile": int(qi) + 1,
                    "vol_ratio_min": round(float(g["vol_ratio"].min()), 3),
                    "vol_ratio_max": round(float(g["vol_ratio"].max()), 3),
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
            "vol_ratio_min": round(float(df["vol_ratio"].min()), 3),
            "vol_ratio_median": round(float(df["vol_ratio"].median()), 3),
            "vol_ratio_max": round(float(df["vol_ratio"].max()), 3),
        }

        dep_warn = (
            f"DEPENDENCE: nominal N={N}, tickerů={uniq} (poměr {uniq/N:.2f}) → efektivní "
            f"N << nominal. Signifikance jen z ticker-clustered bootstrapu; naivní p ignorovat."
        )
        verdict = "H1 SUPPORTED" if h1_supported else "H1 NOT SUPPORTED (H0 nezamítnuta)"
        summary = (
            f"Volume Ratio vs 20D fwd (spojitý): Spearman rho={metrics['spearman_rho']} "
            f"CI[{metrics['rho_ci_lo']},{metrics['rho_ci_hi']}] sig={significant} → {verdict}. "
            f"Kvantilový spread (Q{N_QUANTILES}-Q1): {spread}pp (JEN interpretace, ne edge definice). "
            f"POZOR: kvantilové jevy jsou exploratorní pozorování — nepromovat bez vlastního "
            f"předregistrovaného testu (data snooping). {dep_warn} REGIME SPLIT DEFERRED."
        )
        return ExperimentResult(
            metrics=metrics,
            tables={"quantile_buckets": q_df},
            summary=summary,
        )
