"""
IMS Audit v4 — Entry Point
audit/run_audit_v4.py

Spuštění:
    conda run -n institutional_momentum_scanner --no-capture-output python audit/run_audit_v4.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from audit.tests.mle_diagnostic import (
    load_mle_diagnostic_data,
    run_test_a, run_test_b, run_test_c, run_test_d,
    aggregate_test_d, format_report,
)
from audit.data_loader import load_audit_data

AUDIT_DIR = PROJECT_ROOT / "output" / "audit"


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    run_date = date.today()

    print("=" * 60)
    print("IMS AUDIT v4 — MLE_only DIAGNOSTIC")
    print("=" * 60)

    # ── 1. Načti data ─────────────────────────────────────────────────
    print("\nNačítám MLE a IMS archivy...")
    mle_top50, ims_df = load_mle_diagnostic_data(verbose=True)

    print("\nNačítám close prices z MDSM cache...")
    data = load_audit_data(verbose=False)

    # ── 2. Testy ──────────────────────────────────────────────────────
    print("\nTest A — ret_10d distribuce...")
    test_a = run_test_a(mle_top50)

    print("Test B — rank profil MLE_in_IMS vs MLE_only...")
    test_b = run_test_b(mle_top50)

    print("Test C — IMS komponenty v MLE TOP50 vs mimo...")
    test_c = run_test_c(mle_top50, ims_df)

    print("Test D — forward returns...")
    test_d_raw = run_test_d(mle_top50, data.close_map, data.spy_close)
    test_d_agg = aggregate_test_d(test_d_raw)

    # ── 3. CSV ────────────────────────────────────────────────────────
    _save(test_a,     "mle_diagnostic_ret10d.csv")
    _save(test_b,     "mle_diagnostic_rank_profile.csv")
    _save(test_c,     "mle_diagnostic_components.csv")
    _save(test_d_raw, "mle_diagnostic_forward_raw.csv")
    _save(test_d_agg, "mle_diagnostic_forward_summary.csv")

    # ── 4. Report ─────────────────────────────────────────────────────
    lines = format_report(test_a, test_b, test_c, test_d_agg, run_date)
    report_path = AUDIT_DIR / f"ims_audit_v4_report_{run_date}.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nReport uložen : {report_path}")
    print()
    print("\n".join(lines))


def _save(df: pd.DataFrame, filename: str) -> None:
    path = AUDIT_DIR / filename
    try:
        df.to_csv(path, index=False)
        print(f"CSV : {filename}  ({len(df)} řádků)")
    except Exception as exc:
        print(f"[WARN] {filename}: {exc}")


if __name__ == "__main__":
    main()
