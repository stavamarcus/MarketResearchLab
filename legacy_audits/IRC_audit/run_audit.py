"""
Industry Rank Calendar Audit v1 — Entry Point
audit/run_audit.py

Spuštění:
    conda run -n industry_rank_calendar --no-capture-output python audit/run_audit.py

Testy:
    A — Industry Rank Bucket Effect       (R1-5 vs R6-10 vs R11-20 vs R31+)
    B — Persistence Effect                (HIGH 15-20/20 vs NONE 0-4/20)
    C — Tailwind Effect na IMS/MLE        (industry R1-10 vs R11+)
    D — New Entrant Effect                (nový vstup do TOP10 vs ustálený)
    E — Breadth Effect                    (Adv% >= 90% vs < 50%)
    F — Edge Leaderboard                  (souhrnný žebříček)

Výstupy:
    output/audit/industry_audit_v1_report_YYYY-MM-DD.txt
    output/audit/industry_audit_test_a.csv  — rank buckets
    output/audit/industry_audit_test_b.csv  — persistence
    output/audit/industry_audit_test_c_raw.csv
    output/audit/industry_audit_test_c_summary.csv
    output/audit/industry_audit_test_d.csv  — new entrant
    output/audit/industry_audit_test_e.csv  — breadth
    output/audit/industry_audit_test_f.csv  — edge leaderboard
    output/audit/industry_audit_forward_raw.csv  (volitelně — velký soubor)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from audit.data_loader import load_audit_data
from audit.forward_returns import compute_forward_returns
from audit.tests.test_a_rank_buckets  import run as run_a, format_report as fmt_a
from audit.tests.test_b_persistence   import run as run_b, format_report as fmt_b
from audit.tests.test_c_tailwind      import (
    load_candidate_signals, run as run_c_raw, aggregate as run_c_agg, format_report as fmt_c
)
from audit.tests.test_d_new_entrant   import run as run_d, format_report as fmt_d
from audit.tests.test_e_breadth       import run as run_e, format_report as fmt_e
from audit.tests.test_f_edge_leaderboard import build_leaderboard, format_report as fmt_f
from audit.tests.test_cross_module    import (
    load_cross_signals,
    run_test_7, run_test_8, run_test_9, run_test_10,
    format_report as fmt_cross,
    compute_fwd,
)
from audit.tests.test_11_rolling      import run as run_11, format_report as fmt_11
from audit.tests.test_12_threshold    import run as run_12, format_report as fmt_12
from audit.tests.test_13_triple       import run as run_13, format_report as fmt_13
from audit.tests.test_14_rolling_extended import run as run_14, format_report as fmt_14
from audit.tests.test_15_market_regime    import run as run_15, format_report as fmt_15
from audit.tests.test_16_17_thresholds   import (
    run_test_16, run_test_17, format_report as fmt_16_17
)
from audit.tests.test_18_19_bootstrap    import (
    run_test_18, run_test_19, format_report as fmt_18_19
)

AUDIT_DIR    = PROJECT_ROOT / "output" / "audit"
SAVE_RAW_CSV = False   # True = ulož forward_raw.csv (~100MB), False = přeskoč


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    run_date = date.today()

    print("=" * 60)
    print("INDUSTRY RANK CALENDAR AUDIT v1")
    print(f"Datum: {run_date}")
    print("=" * 60)

    # ── 1. Načti data ─────────────────────────────────────────────────
    print("\nNačítám data...")
    data = load_audit_data(verbose=True)

    # ── 2. Forward returns ────────────────────────────────────────────
    print("\nPočítám forward returns...")
    forward_df = compute_forward_returns(data, verbose=True)

    if SAVE_RAW_CSV:
        _save(forward_df, "industry_audit_forward_raw.csv")

    # ── 3. Test A ─────────────────────────────────────────────────────
    print("\nTest A — Industry Rank Bucket Effect...")
    test_a = run_a(forward_df)
    _save(test_a, "industry_audit_test_a.csv")

    # ── 4. Test B ─────────────────────────────────────────────────────
    print("Test B — Persistence Effect...")
    test_b = run_b(forward_df)
    _save(test_b, "industry_audit_test_b.csv")

    # ── 5. Test C ─────────────────────────────────────────────────────
    print("Test C — Tailwind Effect na IMS/MLE kandidátech...")
    candidates = load_candidate_signals(verbose=True)
    if candidates.empty:
        print("  [WARN] Žádní kandidáti — IMS/MLE archiv prázdný nebo bez industry_rank.")
        test_c_raw = pd.DataFrame()
        test_c_agg = pd.DataFrame()
    else:
        test_c_raw = run_c_raw(candidates, data.close_map, data.spy_close)
        test_c_agg = run_c_agg(test_c_raw)
        _save(test_c_raw, "industry_audit_test_c_raw.csv")
        _save(test_c_agg, "industry_audit_test_c_summary.csv")

    # ── 6. Test D ─────────────────────────────────────────────────────
    print("Test D — New Entrant Effect...")
    test_d = run_d(forward_df)
    _save(test_d, "industry_audit_test_d.csv")

    # ── 7. Test E ─────────────────────────────────────────────────────
    print("Test E — Breadth (Adv%) Effect...")
    test_e = run_e(forward_df)
    _save(test_e, "industry_audit_test_e.csv")

    # ── 8. Test F — Edge Leaderboard ──────────────────────────────────
    print("Test F — Edge Leaderboard...")
    test_f = build_leaderboard(test_a, test_b, test_c_agg, test_d, test_e)
    _save(test_f, "industry_audit_test_f.csv")

    # ── 9. Testy 7–10 — Cross-module ──────────────────────────────────
    print("\nNačítám IMS/MLE signály pro cross-module testy...")
    ims_signals, mle_signals = load_cross_signals(verbose=True)

    print("Test 7 — MLE × Industry...")
    test_7 = run_test_7(mle_signals, data.close_map, data.spy_close)
    _save(test_7, "industry_audit_test_7.csv")

    print("Test 8 — IMS × Industry...")
    test_8 = run_test_8(ims_signals, data.close_map, data.spy_close)
    _save(test_8, "industry_audit_test_8.csv")

    print("Test 9 — MLE × Persistence...")
    test_9 = run_test_9(mle_signals, data.close_map, data.spy_close)
    _save(test_9, "industry_audit_test_9.csv")

    print("Test 10 — IMS × Persistence...")
    test_10 = run_test_10(ims_signals, data.close_map, data.spy_close)
    _save(test_10, "industry_audit_test_10.csv")

    # ── 10. Testy 11–13 — potřebují fwd DataFramy ─────────────────────
    print("\nPočítám forward returns pro MLE/IMS signály (pro testy 11-13)...")
    mle_fwd = compute_fwd(mle_signals, data.close_map, data.spy_close)
    ims_fwd = compute_fwd(ims_signals, data.close_map, data.spy_close)

    print("Test 11 — Rolling validace...")
    mle_rolling, ims_rolling = run_11(mle_fwd, ims_fwd)
    _save(mle_rolling, "industry_audit_test_11_mle.csv")
    _save(ims_rolling, "industry_audit_test_11_ims.csv")

    print("Test 12 — Threshold optimalizace...")
    mle_thresh, ims_thresh = run_12(mle_fwd, ims_fwd)
    _save(mle_thresh, "industry_audit_test_12_mle.csv")
    _save(ims_thresh, "industry_audit_test_12_ims.csv")

    print("Test 13 — Trojité kombinace...")
    mle_triple, ims_triple, quad = run_13(mle_fwd, ims_fwd, data.close_map, data.spy_close)
    _save(mle_triple, "industry_audit_test_13_mle.csv")
    _save(ims_triple, "industry_audit_test_13_ims.csv")
    _save(quad,       "industry_audit_test_13_quad.csv")

    # ── Phase 4 ────────────────────────────────────────────────────────
    print("\n── PHASE 4 ──────────────────────────────────────────────────────")

    print("Test 14 — Rozšířená rolling validace...")
    rolling14 = run_14(mle_fwd, ims_fwd)
    for key, df in rolling14.items():
        _save(df, f"industry_audit_test_14_{key.lower()}.csv")

    print("Test 15 — Market Regime Analysis...")
    regime15 = run_15(mle_fwd, ims_fwd, data.spy_close)
    for key, df in regime15.items():
        _save(df, f"industry_audit_test_15_{key.lower()}.csv")

    print("Test 16 — Persistence Threshold Optimization...")
    test_16 = run_test_16(mle_fwd)
    _save(test_16, "industry_audit_test_16.csv")

    print("Test 17 — Industry Threshold Optimization...")
    mle_17, ims_17 = run_test_17(mle_fwd, ims_fwd)
    _save(mle_17, "industry_audit_test_17_mle.csv")
    _save(ims_17, "industry_audit_test_17_ims.csv")

    print("Test 18 — Bootstrap Robustness...")
    bootstrap18 = run_test_18(mle_fwd, ims_fwd)

    print("Test 19 — Randomized Control...")
    permutation19 = run_test_19(mle_fwd, ims_fwd)

    # ── Report ────────────────────────────────────────────────────────
    lines = _build_report(
        data, test_a, test_b, test_c_agg, test_d, test_e, test_f,
        test_7, test_8, test_9, test_10,
        mle_rolling, ims_rolling,
        mle_thresh, ims_thresh,
        mle_triple, ims_triple, quad,
        rolling14, regime15,
        test_16, mle_17, ims_17,
        bootstrap18, permutation19,
        run_date,
    )
    report_path = AUDIT_DIR / f"industry_audit_v4_report_{run_date}.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nReport uložen: {report_path}")
    print()
    print("\n".join(lines))


def _build_report(
    data, test_a, test_b, test_c, test_d, test_e, test_f,
    test_7, test_8, test_9, test_10,
    mle_rolling, ims_rolling,
    mle_thresh, ims_thresh,
    mle_triple, ims_triple, quad,
    rolling14, regime15,
    test_16, mle_17, ims_17,
    bootstrap18, permutation19,
    run_date,
) -> list[str]:
    lines = []
    lines.append("=" * 70)
    lines.append("INDUSTRY RANK CALENDAR AUDIT v4")
    lines.append(f"Datum: {run_date}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("DATASET")
    lines.append("-" * 70)
    for k, v in data.meta.items():
        lines.append(f"  {k:<35}: {v}")
    lines.append("")

    lines += fmt_a(test_a)
    lines += fmt_b(test_b)
    lines += fmt_c(test_c)
    lines += fmt_d(test_d)
    lines += fmt_e(test_e)
    lines += fmt_f(test_f)
    lines += fmt_cross(test_7, test_8, test_9, test_10)
    lines += fmt_11(mle_rolling, ims_rolling)
    lines += fmt_12(mle_thresh, ims_thresh)
    lines += fmt_13(mle_triple, ims_triple, quad)
    lines += fmt_14(rolling14)
    lines += fmt_15(regime15)
    lines += fmt_16_17(test_16, mle_17, ims_17)
    lines += fmt_18_19(bootstrap18, permutation19)

    lines.append("=" * 70)
    lines.append("KONEC AUDITU")
    lines.append("=" * 70)
    return lines


def _save(df: pd.DataFrame, filename: str) -> None:
    if df.empty:
        print(f"  [SKIP] {filename} — prázdný")
        return
    path = AUDIT_DIR / filename
    try:
        df.to_csv(path, index=False)
        print(f"  CSV: {filename}  ({len(df)} řádků)")
    except Exception as exc:
        print(f"  [WARN] {filename}: {exc}")


if __name__ == "__main__":
    main()
