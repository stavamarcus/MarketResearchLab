"""
Decision Simulation Audit (DSA)
market_breadth/audit/decision_simulation_audit.py

Účel:
    Výzkumný audit historických kombinací stavů modulů.
    Framework pro simulaci scénářů bez optimalizace a bez thresholdů.

    Klasifikace stavů: percentile-based (z distribuce dat v průniku).
    Žádné pevné thresholdy. Žádný fitting. Žádný ML.

Vstupy:
    market_breadth/output/breadth_history.csv
    MarketLeadershipEngine/output/archive/rank_matrix_archive.csv
    InstitutionalMomentumScanner/output/archive/ims_candidates_archive.csv
    industry_rank_calendar/output/archive/industry_rank_calendar_archive.csv

Výstupy (market_breadth/audit/output/):
    decision_simulation_summary.txt
    decision_simulation_results.csv

Průnik: 2025-07-09 → 2026-06-26 (244 dní)

Spuštění:
    conda activate market_breadth
    cd C:\\Users\\stava\\Projects\\market_breadth
    python audit\\decision_simulation_audit.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Konfigurace cest
# ---------------------------------------------------------------------------

PROJECTS    = Path(r"C:\Users\stava\Projects")
BREADTH_CSV = PROJECTS / "market_breadth" / "output" / "breadth_history.csv"
MLE_CSV     = PROJECTS / "MarketLeadershipEngine" / "output" / "archive" / "rank_matrix_archive.csv"
IMS_CSV     = PROJECTS / "InstitutionalMomentumScanner" / "output" / "archive" / "ims_candidates_archive.csv"
IRC_CSV     = PROJECTS / "industry_rank_calendar" / "output" / "archive" / "industry_rank_calendar_archive.csv"
OUTPUT_DIR  = Path(__file__).resolve().parent / "output"

INTERSECTION_START = "2025-07-09"
INTERSECTION_END   = "2026-06-26"
MLE_TOP_N          = 20
IRC_LOOKBACKS      = [5, 10, 20, 30]


# ---------------------------------------------------------------------------
# Datová třída pro simulaci
# ---------------------------------------------------------------------------

@dataclass
class Simulation:
    """
    Definice jedné simulace.

    name:        krátký identifikátor
    description: co simulace testuje
    conditions:  list funkcí (row: pd.Series) -> bool
                 Všechny podmínky musí být True (AND logika)
    """
    name:        str
    description: str
    conditions:  list[Callable[[pd.Series], bool]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("DECISION SIMULATION AUDIT (DSA)")
    print("=" * 60)
    print(f"Průnik: {INTERSECTION_START} → {INTERSECTION_END}")
    print()

    # 1. Načti a připrav data
    master = _build_master(  )

    # 2. Klasifikuj stavy (percentile-based)
    master, cutoffs = _classify_states(master)
    print(f"Master dataset: {len(master)} dní")
    print()

    # 3. Definuj simulace
    simulations = _define_simulations()
    print(f"Definováno simulací: {len(simulations)}")
    print()

    # 4. Spusť simulace
    results = []
    for sim in simulations:
        result = _run_simulation(sim, master)
        results.append(result)
        print(f"  [{result['n_days']:3d}d / {result['frequency_pct']:4.1f}%]  {sim.name}")

    print()

    # 5. Ulož výstupy
    results_df = pd.DataFrame(results)
    results_df.to_csv(OUTPUT_DIR / "decision_simulation_results.csv", index=False)
    print(f"Uloženo: decision_simulation_results.csv")

    _write_summary(master, cutoffs, simulations, results)
    print(f"Uloženo: decision_simulation_summary.txt")

    print()
    print(f"Výstupy: {OUTPUT_DIR}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Sestavení master datasetu
# ---------------------------------------------------------------------------

def _build_master() -> pd.DataFrame:
    """
    Spojí všechny moduly do jednoho denního datasetu.
    Jeden řádek = jeden obchodní den.
    """
    print("Načítám data...")

    # Breadth
    breadth = pd.read_csv(BREADTH_CSV, parse_dates=["date"])
    breadth = breadth[
        (breadth["date"] >= INTERSECTION_START) &
        (breadth["date"] <= INTERSECTION_END) &
        breadth["above_ma50_pct"].notna()
    ].reset_index(drop=True)
    print(f"  Breadth: {len(breadth)} dní")

    # MLE — denní agregát
    mle = pd.read_csv(MLE_CSV, parse_dates=["date"], low_memory=False)
    mle = mle[(mle["date"] >= INTERSECTION_START) & (mle["date"] <= INTERSECTION_END)]
    mle["is_top20"] = mle["rank_10d"] <= MLE_TOP_N
    mle_daily = mle.groupby("date").apply(
        lambda x: pd.Series({
            "mle_top20_ret10d": x.loc[x["is_top20"], "ret_10d"].mean(),
            "mle_top20_count":  x["is_top20"].sum(),
        })
    ).reset_index()
    print(f"  MLE: {len(mle_daily)} dní")

    # IMS — denní agregát
    ims = pd.read_csv(IMS_CSV, parse_dates=["date"])
    ims = ims[(ims["date"] >= INTERSECTION_START) & (ims["date"] <= INTERSECTION_END)]
    ims_daily = ims.groupby("date").agg(
        ims_elite_count=("score", lambda x: (x >= 90).sum()),
        ims_high_count=("score",  lambda x: ((x >= 70) & (x < 90)).sum()),
        ims_total=("ticker", "count"),
        ims_avg_score=("score", "mean"),
    ).reset_index()

    # IMS trend flag: current > prior 5D avg
    ims_daily = ims_daily.sort_values("date").reset_index(drop=True)
    ims_daily["ims_elite_5d_avg"] = ims_daily["ims_elite_count"].rolling(5, min_periods=3).mean().shift(1)
    ims_daily["ims_elite_expanding"] = ims_daily["ims_elite_count"] > ims_daily["ims_elite_5d_avg"]
    print(f"  IMS: {len(ims_daily)} dní")

    # IRC — top7 agregát pro každý lookback → pivot na jeden řádek per den
    irc = pd.read_csv(IRC_CSV, parse_dates=["date"])
    irc = irc[(irc["date"] >= INTERSECTION_START) & (irc["date"] <= INTERSECTION_END)]
    irc_parts = []
    for lb in IRC_LOOKBACKS:
        top7 = irc[(irc["lookback"] == lb) & (irc["rank"] <= 7)]
        agg = top7.groupby("date").agg(
            top7_ret=(  "median_return", "mean"),
            top7_adv=("advance_ratio",  "mean"),
        ).reset_index()
        agg.columns = ["date", f"irc_{lb}d_top7_ret", f"irc_{lb}d_top7_adv"]
        irc_parts.append(agg)

    irc_daily = irc_parts[0]
    for part in irc_parts[1:]:
        irc_daily = irc_daily.merge(part, on="date", how="outer")
    print(f"  IRC: {len(irc_daily)} dní")

    # Breadth 5D trend flag
    breadth = breadth.sort_values("date").reset_index(drop=True)
    breadth["breadth_ma50_5d_avg_prior"] = breadth["above_ma50_5d_change_pp"].rolling(5, min_periods=3).mean().shift(1)

    # Spoj vše
    master = breadth.merge(mle_daily, on="date", how="inner")
    master = master.merge(ims_daily, on="date", how="inner")
    master = master.merge(irc_daily, on="date", how="inner")
    master = master.sort_values("date").reset_index(drop=True)

    return master


# ---------------------------------------------------------------------------
# Percentile-based klasifikace stavů
# ---------------------------------------------------------------------------

def _classify_states(master: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Přidá stavové sloupce ke každému řádku.
    Všechny thresholdy jsou odvozeny z percentilů dat v průniku.
    """
    cutoffs: dict = {}

    def add_state(df, col, new_col, labels):
        """
        labels: dict {label: (low_pct, high_pct)}
        Přiřadí label pokud hodnota leží v percentilním rozsahu.
        """
        vals = df[col].dropna()
        p10  = vals.quantile(0.10)
        p25  = vals.quantile(0.25)
        p75  = vals.quantile(0.75)
        p90  = vals.quantile(0.90)
        cutoffs[col] = {"p10": p10, "p25": p25, "p75": p75, "p90": p90}

        def classify(v):
            if pd.isna(v):
                return "unknown"
            if v <= p10:
                return "bottom_decile"
            elif v <= p25:
                return "bottom_quartile"
            elif v >= p90:
                return "top_decile"
            elif v >= p75:
                return "top_quartile"
            else:
                return "middle"

        df[new_col] = df[col].apply(classify)
        return df

    # Breadth evolution — MA50 a MA200
    master = add_state(master, "above_ma50_5d_change_pp",  "breadth_ma50_5d_state",  {})
    master = add_state(master, "above_ma200_5d_change_pp", "breadth_ma200_5d_state", {})

    # MLE
    master = add_state(master, "mle_top20_ret10d", "mle_state", {})

    # IMS elite
    master = add_state(master, "ims_elite_count", "ims_elite_state", {})

    # IMS total
    master = add_state(master, "ims_total", "ims_total_state", {})

    # IRC pro každý lookback
    for lb in IRC_LOOKBACKS:
        master = add_state(master, f"irc_{lb}d_top7_ret", f"irc_{lb}d_state", {})
        master = add_state(master, f"irc_{lb}d_top7_adv", f"irc_{lb}d_adv_state", {})

    # Shorthand aliasy pro podmínky v simulacích
    # Breadth improving/deteriorating
    master["breadth_improving"]             = master["breadth_ma50_5d_state"].isin(["top_quartile", "top_decile"])
    master["breadth_deteriorating"]         = master["breadth_ma50_5d_state"].isin(["bottom_quartile", "bottom_decile"])
    master["breadth_sharply_deteriorating"] = master["breadth_ma50_5d_state"] == "bottom_decile"
    master["breadth_sharply_improving"]     = master["breadth_ma50_5d_state"] == "top_decile"
    master["breadth_neutral"]               = master["breadth_ma50_5d_state"] == "middle"

    # MA200 verze
    master["breadth200_improving"]             = master["breadth_ma200_5d_state"].isin(["top_quartile", "top_decile"])
    master["breadth200_deteriorating"]         = master["breadth_ma200_5d_state"].isin(["bottom_quartile", "bottom_decile"])
    master["breadth200_sharply_deteriorating"] = master["breadth_ma200_5d_state"] == "bottom_decile"

    # MLE
    master["mle_above_median"] = master["mle_state"].isin(["top_quartile", "top_decile", "middle"])
    master["mle_strong"]       = master["mle_state"].isin(["top_quartile", "top_decile"])
    master["mle_weak"]         = master["mle_state"].isin(["bottom_quartile", "bottom_decile"])
    master["mle_stagnating"]   = master["mle_state"] == "bottom_decile"

    # IMS
    master["ims_elite_active"]      = master["ims_elite_state"].isin(["top_quartile", "top_decile"])
    master["ims_elite_very_active"] = master["ims_elite_state"] == "top_decile"
    master["ims_elite_low"]         = master["ims_elite_state"].isin(["bottom_quartile", "bottom_decile"])
    master["ims_total_expanding"]   = master["ims_total_state"].isin(["top_quartile", "top_decile"])
    master["ims_total_contracting"] = master["ims_total_state"].isin(["bottom_quartile", "bottom_decile"])

    # IRC 20D (primární referenční lookback z předchozího auditu)
    master["irc20_strong"]   = master["irc_20d_state"].isin(["top_quartile", "top_decile"])
    master["irc20_weak"]     = master["irc_20d_state"].isin(["bottom_quartile", "bottom_decile"])
    master["irc20_expanding"]= master["irc_20d_adv_state"].isin(["top_quartile", "top_decile"])

    # IRC 5D
    master["irc5_strong"] = master["irc_5d_state"].isin(["top_quartile", "top_decile"])
    master["irc5_weak"]   = master["irc_5d_state"].isin(["bottom_quartile", "bottom_decile"])

    return master, cutoffs


# ---------------------------------------------------------------------------
# Definice simulací
# ---------------------------------------------------------------------------

def _define_simulations() -> list[Simulation]:
    """
    Každá simulace = název + popis + seznam podmínek (AND logika).
    Podmínky jsou lambda funkce nad řádkem master datasetu.
    Přidej nové simulace zde bez změny zbytku kódu.
    """
    return [

        # ------------------------------------------------------------------
        # SIMULACE A — Ideální prostředí (vše zelené)
        # ------------------------------------------------------------------
        Simulation(
            name="A1_all_improving",
            description=(
                "Breadth improving AND MLE strong AND IMS elite active "
                "AND IRC20 strong — ideální momentum prostředí"
            ),
            conditions=[
                lambda r: r["breadth_improving"],
                lambda r: r["mle_strong"],
                lambda r: r["ims_elite_active"],
                lambda r: r["irc20_strong"],
            ],
        ),
        Simulation(
            name="A2_breadth_mle_improving",
            description=(
                "Breadth improving AND MLE strong — bez ohledu na IMS/IRC"
            ),
            conditions=[
                lambda r: r["breadth_improving"],
                lambda r: r["mle_strong"],
            ],
        ),
        Simulation(
            name="A3_breadth_improving_irc_strong",
            description=(
                "Breadth improving AND IRC20 strong — breadth + industry tailwind"
            ),
            conditions=[
                lambda r: r["breadth_improving"],
                lambda r: r["irc20_strong"],
            ],
        ),
        Simulation(
            name="A4_sharply_improving_all",
            description=(
                "Breadth sharply improving (top decile) AND MLE strong AND IRC20 strong"
            ),
            conditions=[
                lambda r: r["breadth_sharply_improving"],
                lambda r: r["mle_strong"],
                lambda r: r["irc20_strong"],
            ],
        ),

        # ------------------------------------------------------------------
        # SIMULACE B — Deteriorace (vše červené)
        # ------------------------------------------------------------------
        Simulation(
            name="B1_all_deteriorating",
            description=(
                "Breadth deteriorating AND MLE weak AND IMS total contracting "
                "— výpadek momentum prostředí"
            ),
            conditions=[
                lambda r: r["breadth_deteriorating"],
                lambda r: r["mle_weak"],
                lambda r: r["ims_total_contracting"],
            ],
        ),
        Simulation(
            name="B2_sharply_deteriorating",
            description=(
                "Breadth sharply deteriorating (bottom decile MA50) "
                "— jak reaguje MLE a IRC?"
            ),
            conditions=[
                lambda r: r["breadth_sharply_deteriorating"],
            ],
        ),
        Simulation(
            name="B3_sharply_det_ma200",
            description=(
                "Breadth sharply deteriorating MA200 (bottom decile) "
                "— přísnější filtr deteriorace"
            ),
            conditions=[
                lambda r: r["breadth200_sharply_deteriorating"],
            ],
        ),
        Simulation(
            name="B4_breadth_det_mle_weak",
            description=(
                "Breadth deteriorating AND MLE weak — dvojitá deteriorace"
            ),
            conditions=[
                lambda r: r["breadth_deteriorating"],
                lambda r: r["mle_weak"],
            ],
        ),
        Simulation(
            name="B5_breadth_det_irc_weak",
            description=(
                "Breadth deteriorating AND IRC20 weak — breadth + industry slabost"
            ),
            conditions=[
                lambda r: r["breadth_deteriorating"],
                lambda r: r["irc20_weak"],
            ],
        ),

        # ------------------------------------------------------------------
        # SIMULACE C — Divergence Breadth vs MLE
        # ------------------------------------------------------------------
        Simulation(
            name="C1_breadth_improving_mle_weak",
            description=(
                "Breadth improving ALE MLE weak — breadth roste ale leadership nefunguje"
            ),
            conditions=[
                lambda r: r["breadth_improving"],
                lambda r: r["mle_weak"],
            ],
        ),
        Simulation(
            name="C2_breadth_deteriorating_mle_strong",
            description=(
                "Breadth deteriorating ALE MLE strong — leadership drží i při slabém breadth"
            ),
            conditions=[
                lambda r: r["breadth_deteriorating"],
                lambda r: r["mle_strong"],
            ],
        ),
        Simulation(
            name="C3_breadth_neutral_mle_strong",
            description=(
                "Breadth neutral (middle 50%) AND MLE strong — momentum bez breadth signálu"
            ),
            conditions=[
                lambda r: r["breadth_neutral"],
                lambda r: r["mle_strong"],
            ],
        ),
        Simulation(
            name="C4_breadth_neutral_mle_weak",
            description=(
                "Breadth neutral AND MLE weak — obě metriky bez signálu"
            ),
            conditions=[
                lambda r: r["breadth_neutral"],
                lambda r: r["mle_weak"],
            ],
        ),

        # ------------------------------------------------------------------
        # SIMULACE D — Narrow leadership (IRC drží při slabém breadth)
        # ------------------------------------------------------------------
        Simulation(
            name="D1_breadth_det_irc_strong",
            description=(
                "Breadth deteriorating ALE IRC20 strong — narrow leadership"
            ),
            conditions=[
                lambda r: r["breadth_deteriorating"],
                lambda r: r["irc20_strong"],
            ],
        ),
        Simulation(
            name="D2_breadth_sharply_det_irc_strong",
            description=(
                "Breadth sharply deteriorating ALE IRC20 strong — extrémní divergence"
            ),
            conditions=[
                lambda r: r["breadth_sharply_deteriorating"],
                lambda r: r["irc20_strong"],
            ],
        ),
        Simulation(
            name="D3_breadth_improving_irc_weak",
            description=(
                "Breadth improving ALE IRC20 weak — breadth roste bez industry tailwindu"
            ),
            conditions=[
                lambda r: r["breadth_improving"],
                lambda r: r["irc20_weak"],
            ],
        ),
        Simulation(
            name="D4_breadth_det_irc5_strong",
            description=(
                "Breadth deteriorating ALE IRC5D strong — krátkodobé industry leadership přežívá"
            ),
            conditions=[
                lambda r: r["breadth_deteriorating"],
                lambda r: r["irc5_strong"],
            ],
        ),

        # ------------------------------------------------------------------
        # SIMULACE E — IMS divergence
        # ------------------------------------------------------------------
        Simulation(
            name="E1_breadth_improving_ims_low",
            description=(
                "Breadth improving ALE IMS elite low — breadth roste bez quality momentum"
            ),
            conditions=[
                lambda r: r["breadth_improving"],
                lambda r: r["ims_elite_low"],
            ],
        ),
        Simulation(
            name="E2_breadth_det_ims_expanding",
            description=(
                "Breadth deteriorating ALE IMS elite expanding — výjimka při deterioraci"
            ),
            conditions=[
                lambda r: r["breadth_deteriorating"],
                lambda r: r["ims_elite_expanding"] == True,
            ],
        ),
        Simulation(
            name="E3_ims_very_active_all_good",
            description=(
                "IMS elite very active (top decile) AND breadth improving AND MLE strong"
            ),
            conditions=[
                lambda r: r["ims_elite_very_active"],
                lambda r: r["breadth_improving"],
                lambda r: r["mle_strong"],
            ],
        ),

        # ------------------------------------------------------------------
        # SIMULACE F — Baseline srovnání
        # ------------------------------------------------------------------
        Simulation(
            name="F1_no_conditions",
            description=(
                "Baseline — všechny dny v průniku (bez podmínek)"
            ),
            conditions=[],
        ),
        Simulation(
            name="F2_breadth_improving_only",
            description=(
                "Breadth improving (top quartile MA50) — samostatně"
            ),
            conditions=[
                lambda r: r["breadth_improving"],
            ],
        ),
        Simulation(
            name="F3_breadth_deteriorating_only",
            description=(
                "Breadth deteriorating (bottom quartile MA50) — samostatně"
            ),
            conditions=[
                lambda r: r["breadth_deteriorating"],
            ],
        ),
        Simulation(
            name="F4_mle_strong_only",
            description=(
                "MLE strong (top quartile) — samostatně"
            ),
            conditions=[
                lambda r: r["mle_strong"],
            ],
        ),
        Simulation(
            name="F5_irc20_strong_only",
            description=(
                "IRC20 strong (top quartile) — samostatně"
            ),
            conditions=[
                lambda r: r["irc20_strong"],
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Spuštění simulace
# ---------------------------------------------------------------------------

def _run_simulation(sim: Simulation, master: pd.DataFrame) -> dict:
    """
    Aplikuje podmínky simulace na master dataset.
    Vrátí statistiky výsledků.
    """
    if not sim.conditions:
        mask = pd.Series([True] * len(master), index=master.index)
    else:
        mask = pd.Series([True] * len(master), index=master.index)
        for cond in sim.conditions:
            mask = mask & master.apply(cond, axis=1)

    subset = master[mask]
    n = len(subset)
    freq = n / len(master) * 100 if len(master) > 0 else 0

    def safe_stats(series: pd.Series) -> dict:
        s = series.dropna()
        if len(s) == 0:
            return {"mean": None, "median": None, "std": None, "p25": None, "p75": None}
        return {
            "mean":   round(s.mean(), 3),
            "median": round(s.median(), 3),
            "std":    round(s.std(), 3),
            "p25":    round(s.quantile(0.25), 3),
            "p75":    round(s.quantile(0.75), 3),
        }

    mle_stats  = safe_stats(subset["mle_top20_ret10d"])
    ims_stats  = safe_stats(subset["ims_elite_count"])
    irc20_stats= safe_stats(subset["irc_20d_top7_ret"])
    irc5_stats = safe_stats(subset["irc_5d_top7_ret"])
    b50_stats  = safe_stats(subset["above_ma50_5d_change_pp"])
    b200_stats = safe_stats(subset["above_ma200_5d_change_pp"])

    return {
        "simulation":        sim.name,
        "description":       sim.description,
        "n_days":            n,
        "frequency_pct":     round(freq, 1),

        # MLE
        "mle_ret10d_mean":   mle_stats["mean"],
        "mle_ret10d_median": mle_stats["median"],
        "mle_ret10d_std":    mle_stats["std"],
        "mle_ret10d_p25":    mle_stats["p25"],
        "mle_ret10d_p75":    mle_stats["p75"],

        # IMS elite
        "ims_elite_mean":    ims_stats["mean"],
        "ims_elite_median":  ims_stats["median"],
        "ims_elite_p75":     ims_stats["p75"],

        # IRC 20D
        "irc20_ret_mean":    irc20_stats["mean"],
        "irc20_ret_median":  irc20_stats["median"],
        "irc20_ret_p75":     irc20_stats["p75"],

        # IRC 5D
        "irc5_ret_mean":     irc5_stats["mean"],
        "irc5_ret_median":   irc5_stats["median"],

        # Breadth kontext
        "breadth_ma50_5d_mean":  b50_stats["mean"],
        "breadth_ma200_5d_mean": b200_stats["mean"],
    }


# ---------------------------------------------------------------------------
# Textový souhrn
# ---------------------------------------------------------------------------

def _write_summary(
    master: pd.DataFrame,
    cutoffs: dict,
    simulations: list[Simulation],
    results: list[dict],
) -> None:

    sep  = "=" * 65
    line = "-" * 65
    lines = []

    lines += [
        "", sep,
        "  DECISION SIMULATION AUDIT (DSA) — VÝSLEDKY",
        f"  Průnik: {INTERSECTION_START} → {INTERSECTION_END}",
        f"  Celkem dní: {len(master)}",
        sep, "",
    ]

    # LIMITATIONS
    lines += [
        line,
        "[ LIMITATIONS ]",
        "",
        "  Analýza provedena na 244 obchodních dnech (převážně bull/neutral).",
        "  Extrémní RISK_OFF podmínky jsou zastoupeny minimálně.",
        "  Klasifikace stavů je percentile-based — odvozena z tohoto období.",
        "  Přenositelnost výsledků na jiná tržní prostředí není ověřena.",
        "  Simulace s N < 15 dní jsou označeny [!] a jsou pouze orientační.",
        "",
    ]

    # Cutoffs tabulka
    lines += [line, "[ PERCENTILOVÉ HRANICE KLASIFIKACE ]", ""]
    lines.append(f"  {'Signál':<35s}  {'p10':>7}  {'p25':>7}  {'p75':>7}  {'p90':>7}")
    lines.append(f"  {'-'*35}  {'-'*7}  {'-'*7}  {'-'*7}  {'-'*7}")
    for col, cuts in cutoffs.items():
        lines.append(
            f"  {col:<35s}  "
            f"{cuts['p10']:>7.2f}  {cuts['p25']:>7.2f}  "
            f"{cuts['p75']:>7.2f}  {cuts['p90']:>7.2f}"
        )
    lines += ["",
        "  Stavy: bottom_decile(≤p10) | bottom_quartile(p10-p25) |",
        "         middle(p25-p75) | top_quartile(p75-p90) | top_decile(≥p90)",
        "",
    ]

    # Baseline (F1)
    baseline = next((r for r in results if r["simulation"] == "F1_no_conditions"), None)
    if baseline:
        lines += [line, "[ BASELINE (všechny dny, bez podmínek) ]", ""]
        lines.append(f"  MLE top20 ret10d  :  mean={baseline['mle_ret10d_mean']:+.2f}%  median={baseline['mle_ret10d_median']:+.2f}%")
        lines.append(f"  IMS elite/den     :  mean={baseline['ims_elite_mean']:.2f}")
        lines.append(f"  IRC 20D top7 ret  :  mean={baseline['irc20_ret_mean']:+.2f}%  median={baseline['irc20_ret_median']:+.2f}%")
        lines.append(f"  IRC  5D top7 ret  :  mean={baseline['irc5_ret_mean']:+.2f}%")
        lines.append("")

    # Výsledky simulací
    lines += [line, "[ VÝSLEDKY SIMULACÍ ]", ""]

    groups = {
        "A — Ideální prostředí":         [r for r in results if r["simulation"].startswith("A")],
        "B — Deteriorace":               [r for r in results if r["simulation"].startswith("B")],
        "C — Divergence Breadth vs MLE": [r for r in results if r["simulation"].startswith("C")],
        "D — Narrow Leadership":         [r for r in results if r["simulation"].startswith("D")],
        "E — IMS Divergence":            [r for r in results if r["simulation"].startswith("E")],
        "F — Baseline srovnání":         [r for r in results if r["simulation"].startswith("F")],
    }

    b_mle    = baseline["mle_ret10d_mean"]   if baseline else 0
    b_irc20  = baseline["irc20_ret_mean"]    if baseline else 0
    b_ims    = baseline["ims_elite_mean"]     if baseline else 0

    for group_name, group_results in groups.items():
        if not group_results:
            continue
        lines += [f"  {group_name}", ""]

        for r in group_results:
            n = r["n_days"]
            flag = " [!]" if n < 15 else ""
            lines.append(f"  {r['simulation']}{flag}")
            lines.append(f"    {r['description']}")
            lines.append(
                f"    Dní: {n} ({r['frequency_pct']:.1f}%)  "
                f"Breadth MA50 5D: {r['breadth_ma50_5d_mean']:+.1f}pp"
            )

            mle_delta = (r["mle_ret10d_mean"] - b_mle) if r["mle_ret10d_mean"] is not None else None
            irc_delta = (r["irc20_ret_mean"]  - b_irc20) if r["irc20_ret_mean"] is not None else None
            ims_delta = (r["ims_elite_mean"]   - b_ims) if r["ims_elite_mean"] is not None else None

            mle_str = f"{r['mle_ret10d_mean']:+.1f}% (Δ{mle_delta:+.1f}%)" if mle_delta is not None else "N/A"
            irc_str = f"{r['irc20_ret_mean']:+.1f}% (Δ{irc_delta:+.1f}%)"  if irc_delta is not None else "N/A"
            ims_str = f"{r['ims_elite_mean']:.2f}/d (Δ{ims_delta:+.2f})"   if ims_delta is not None else "N/A"

            lines.append(f"    MLE ret10d  : {mle_str}")
            lines.append(f"    IRC 20D ret : {irc_str}")
            lines.append(f"    IMS elite/d : {ims_str}")
            lines.append("")

    lines += [sep, "  Výstupy: audit/output/", sep, ""]
    (OUTPUT_DIR / "decision_simulation_summary.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
