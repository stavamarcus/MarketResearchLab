"""
Industry Rank Calendar Audit Phase 4 — Testy 18 + 19
audit/tests/test_18_19_bootstrap.py

Priorita 5: Bootstrap Robustness Test (Test 18)
    1000 bootstrap iterací per kombinace.
    Výstup: 95% CI, mean edge, std, P(edge > 0).

Priorita 6: Randomized Control Test (Test 19)
    Permutuje industry_rank náhodně a opakuje hlavní testy.
    Srovná skutečný edge s distribucí náhodného edge.
    Výstup: P-value (jak pravděpodobné je dostat edge >= skutečný náhodně).
"""

from __future__ import annotations

import pandas as pd
import numpy as np

PRIMARY_WINDOW   = 20
N_BOOTSTRAP      = 1000
N_PERMUTATIONS   = 500
RANDOM_SEED      = 42

MLE_IND_THRESH   = 5
IMS_IND_THRESH   = 10
PERSIST_MED      = 8


# ── Test 18: Bootstrap ────────────────────────────────────────────────────────

def _bootstrap_edge(
    fwd_df:     pd.DataFrame,
    filter_col: str,
    threshold:  int,
    filter_type: str,
    best_label: str,
    base_label: str,
    n_iter:     int = N_BOOTSTRAP,
    seed:       int = RANDOM_SEED,
) -> dict:
    """
    Bootstrap odhad distribuce edge pro danou kombinaci.
    Vzorkuje s nahrazením z celého datasetu.

    Returns:
        dict s mean_edge, std_edge, ci_low, ci_high, p_positive
    """
    col_fwd   = f"fwd_{PRIMARY_WINDOW}d"
    col_alpha = f"alpha_{PRIMARY_WINDOW}d"
    col_use   = f"usable_{PRIMARY_WINDOW}d"

    if col_use not in fwd_df.columns or fwd_df.empty:
        return {}

    usable = fwd_df[fwd_df[col_use] == True].copy()
    if usable.empty:
        return {}

    if filter_type == "rank":
        usable["group"] = usable[filter_col].apply(lambda v: best_label if v <= threshold else base_label)
    else:
        usable["group"] = usable[filter_col].apply(lambda v: best_label if v >= threshold else base_label)

    rng = np.random.default_rng(seed)
    edges = []

    for _ in range(n_iter):
        sample = usable.sample(n=len(usable), replace=True, random_state=rng.integers(0, 2**31))

        best_a = sample[sample["group"] == best_label][col_alpha].dropna()
        base_a = sample[sample["group"] == base_label][col_alpha].dropna()

        if len(best_a) < 2 or len(base_a) < 2:
            continue

        edges.append(float(best_a.mean()) - float(base_a.mean()))

    if not edges:
        return {}

    edges = np.array(edges)

    return {
        "mean_edge":   round(float(edges.mean()), 4),
        "std_edge":    round(float(edges.std()), 4),
        "ci_low_95":   round(float(np.percentile(edges, 2.5)), 4),
        "ci_high_95":  round(float(np.percentile(edges, 97.5)), 4),
        "p_positive":  round(float((edges > 0).mean() * 100), 2),
        "n_iter":      len(edges),
    }


def run_test_18(
    mle_fwd: pd.DataFrame,
    ims_fwd: pd.DataFrame,
) -> dict[str, dict]:
    """
    Spustí bootstrap pro MLE+Industry, IMS+Industry, MLE+Persistence.
    """
    results = {}

    if not mle_fwd.empty:
        print("  Bootstrap: MLE + Industry...")
        results["MLE_IND"]     = _bootstrap_edge(mle_fwd, "industry_rank",    MLE_IND_THRESH, "rank",    "MLE+TOP5_IND",    "MLE_ONLY")
        print("  Bootstrap: MLE + Persistence...")
        results["MLE_PERSIST"] = _bootstrap_edge(mle_fwd, "industry_persist", PERSIST_MED,    "persist", "MLE+PERSIST_MED", "MLE+PERSIST_LOW")

    if not ims_fwd.empty:
        print("  Bootstrap: IMS + Industry...")
        results["IMS_IND"]     = _bootstrap_edge(ims_fwd, "industry_rank",    IMS_IND_THRESH, "rank",    "IMS+TOP10_IND",   "IMS_ONLY")

    return results


# ── Test 19: Randomized Control ───────────────────────────────────────────────

def _permutation_edge(
    fwd_df:      pd.DataFrame,
    filter_col:  str,
    threshold:   int,
    filter_type: str,
    best_label:  str,
    base_label:  str,
    n_perm:      int = N_PERMUTATIONS,
    seed:        int = RANDOM_SEED,
) -> dict:
    """
    Permutuje filter_col náhodně a zjistí distribuci edge při náhodném ranku.
    Srovná s reálným edge → P-value.

    Returns:
        dict s real_edge, mean_perm_edge, std_perm, p_value
    """
    col_fwd   = f"fwd_{PRIMARY_WINDOW}d"
    col_alpha = f"alpha_{PRIMARY_WINDOW}d"
    col_use   = f"usable_{PRIMARY_WINDOW}d"

    if col_use not in fwd_df.columns or fwd_df.empty:
        return {}

    usable = fwd_df[fwd_df[col_use] == True].copy()
    if usable.empty:
        return {}

    # Reálný edge
    if filter_type == "rank":
        usable["group"] = usable[filter_col].apply(lambda v: best_label if v <= threshold else base_label)
    else:
        usable["group"] = usable[filter_col].apply(lambda v: best_label if v >= threshold else base_label)

    best_real = usable[usable["group"] == best_label][col_alpha].dropna()
    base_real = usable[usable["group"] == base_label][col_alpha].dropna()

    if len(best_real) < 2 or len(base_real) < 2:
        return {}

    real_edge = float(best_real.mean()) - float(base_real.mean())

    # Permutační distribuce
    rng  = np.random.default_rng(seed)
    perm_edges = []

    rank_values = usable[filter_col].values.copy()

    for _ in range(n_perm):
        shuffled = rng.permutation(rank_values)
        usable_perm = usable.copy()
        usable_perm[filter_col] = shuffled

        if filter_type == "rank":
            usable_perm["group"] = usable_perm[filter_col].apply(lambda v: best_label if v <= threshold else base_label)
        else:
            usable_perm["group"] = usable_perm[filter_col].apply(lambda v: best_label if v >= threshold else base_label)

        best_p = usable_perm[usable_perm["group"] == best_label][col_alpha].dropna()
        base_p = usable_perm[usable_perm["group"] == base_label][col_alpha].dropna()

        if len(best_p) < 2 or len(base_p) < 2:
            continue

        perm_edges.append(float(best_p.mean()) - float(base_p.mean()))

    if not perm_edges:
        return {}

    perm_edges = np.array(perm_edges)

    # P-value: jak często náhodný edge >= reálný edge
    p_value = float((perm_edges >= real_edge).mean())

    return {
        "real_edge":      round(real_edge, 4),
        "mean_perm_edge": round(float(perm_edges.mean()), 4),
        "std_perm":       round(float(perm_edges.std()), 4),
        "p_value":        round(p_value, 4),
        "significant":    p_value < 0.05,
        "n_perm":         len(perm_edges),
    }


def run_test_19(
    mle_fwd: pd.DataFrame,
    ims_fwd: pd.DataFrame,
) -> dict[str, dict]:
    results = {}

    if not mle_fwd.empty:
        print("  Permutation: MLE + Industry...")
        results["MLE_IND"]     = _permutation_edge(mle_fwd, "industry_rank",    MLE_IND_THRESH, "rank",    "MLE+TOP5_IND",    "MLE_ONLY")
        print("  Permutation: MLE + Persistence...")
        results["MLE_PERSIST"] = _permutation_edge(mle_fwd, "industry_persist", PERSIST_MED,    "persist", "MLE+PERSIST_MED", "MLE+PERSIST_LOW")

    if not ims_fwd.empty:
        print("  Permutation: IMS + Industry...")
        results["IMS_IND"]     = _permutation_edge(ims_fwd, "industry_rank",    IMS_IND_THRESH, "rank",    "IMS+TOP10_IND",   "IMS_ONLY")

    return results


# ── Formátování ───────────────────────────────────────────────────────────────

def format_report(
    bootstrap_results:   dict[str, dict],
    permutation_results: dict[str, dict],
) -> list[str]:
    lines = []

    # ── Test 18: Bootstrap ─────────────────────────────────────────────────
    lines.append("=" * 70)
    lines.append(f"TEST 18 — BOOTSTRAP ROBUSTNESS ({N_BOOTSTRAP} iteraci)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Je edge statisticky spolehlivy?")
    lines.append(f"Metoda: {N_BOOTSTRAP}x bootstrap vzorkovani s nahrazenim")
    lines.append(f"Primarne okno: {PRIMARY_WINDOW}D alpha")
    lines.append("")

    labels = {
        "MLE_IND":     "MLE + TOP5 Industry",
        "IMS_IND":     "IMS + TOP10 Industry",
        "MLE_PERSIST": "MLE + Persistence MED/HIGH",
    }

    for key, title in labels.items():
        r = bootstrap_results.get(key, {})
        lines.append(f"  {title}")
        if not r:
            lines.append("    Nedostatek dat.")
        else:
            lines.append(f"    Mean edge     : {r.get('mean_edge', 0):>+7.4f}%")
            lines.append(f"    Std edge      : {r.get('std_edge', 0):>7.4f}%")
            lines.append(f"    95% CI        : [{r.get('ci_low_95', 0):>+7.4f}%, {r.get('ci_high_95', 0):>+7.4f}%]")
            lines.append(f"    P(edge > 0)   : {r.get('p_positive', 0):>6.1f}%")
            lines.append(f"    N iteraci     : {r.get('n_iter', 0)}")

            ci_low = r.get("ci_low_95", 0)
            if ci_low > 0:
                lines.append(f"    VERDIKT: CI celé nad 0 — edge je statisticky robustni")
            elif r.get("p_positive", 0) >= 90:
                lines.append(f"    VERDIKT: P(edge>0) >= 90% — edge je pravdepodobny")
            elif r.get("p_positive", 0) >= 75:
                lines.append(f"    VERDIKT: P(edge>0) 75-89% — edge je mozny ale nejisty")
            else:
                lines.append(f"    VERDIKT: P(edge>0) < 75% — nedostatecna statisticka duvera")
        lines.append("")

    # ── Test 19: Permutation ───────────────────────────────────────────────
    lines.append("=" * 70)
    lines.append(f"TEST 19 — RANDOMIZED CONTROL ({N_PERMUTATIONS} permutaci)")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Otazka: Preklona skutecny edge nahodnou distribuci?")
    lines.append(f"Metoda: {N_PERMUTATIONS}x permutace industry_rank")
    lines.append("P-value < 0.05 = edge neni nahodny (statisticky vyznamny)")
    lines.append("")

    for key, title in labels.items():
        r = permutation_results.get(key, {})
        lines.append(f"  {title}")
        if not r:
            lines.append("    Nedostatek dat.")
        else:
            sig_str = "*** STATISTICKY VYZNAMNY ***" if r.get("significant") else "--- NENI STATISTICKY VYZNAMNY ---"
            lines.append(f"    Skutecny edge : {r.get('real_edge', 0):>+7.4f}%")
            lines.append(f"    Mean perm edge: {r.get('mean_perm_edge', 0):>+7.4f}%")
            lines.append(f"    Std perm      : {r.get('std_perm', 0):>7.4f}%")
            lines.append(f"    P-value       : {r.get('p_value', 1):>7.4f}")
            lines.append(f"    N permutaci   : {r.get('n_perm', 0)}")
            lines.append(f"    VERDIKT       : {sig_str}")
        lines.append("")

    lines.append("-" * 70)
    lines.append("INTERPRETACE:")
    lines.append("  Bootstrap CI celé nad 0 = edge existuje s 95% jistotou")
    lines.append("  P-value < 0.05 = edge neni nahodny artefakt")
    lines.append("  Oba testy pozitivni = silný statisticky dukaz pro produkci")
    lines.append("")

    return lines
