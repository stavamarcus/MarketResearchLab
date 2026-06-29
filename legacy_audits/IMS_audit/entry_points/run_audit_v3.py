"""
IMS Audit v3 — Entry Point
audit/run_audit_v3.py

Spuštění:
    conda run -n institutional_momentum_scanner --no-capture-output python audit/run_audit_v3.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from audit.tests.overlap_analysis import (
    load_signals, compute_group_returns,
    aggregate_summary, format_report,
    MLE_ARCHIVE_PATH,
)
from audit.data_loader import load_audit_data

AUDIT_DIR = PROJECT_ROOT / "output" / "audit"


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    run_date = date.today()

    print("=" * 60)
    print("IMS AUDIT v3 — IMS × MLE OVERLAP")
    print("=" * 60)

    # ── 1. Ověř MLE archiv ────────────────────────────────────────────
    if not MLE_ARCHIVE_PATH.exists():
        print(f"[CHYBA] MLE archiv nenalezen: {MLE_ARCHIVE_PATH}")
        sys.exit(1)

    # ── 2. Sestav signálové skupiny ───────────────────────────────────
    print("\nSestavuji signálové skupiny...")
    signals = load_signals(verbose=True)

    if signals.empty:
        print("[CHYBA] Žádné signály.")
        sys.exit(1)

    # ── 3. Načti close prices z MDSM ─────────────────────────────────
    print("\nNačítám close prices z MDSM cache...")
    data = load_audit_data(verbose=False)

    # ── 4. Forward returns ────────────────────────────────────────────
    print("\nVýpočet forward returns...")
    results = compute_group_returns(
        signals=signals,
        close_map=data.close_map,
        spy_close=data.spy_close,
        verbose=True,
    )

    # ── 5. Agregace ───────────────────────────────────────────────────
    summary = aggregate_summary(results)

    # ── 6. CSV výstupy ────────────────────────────────────────────────
    _save(signals, "ims_mle_overlap_signals.csv")
    _save(results, "ims_mle_overlap_results.csv")
    _save(summary, "ims_mle_overlap_summary.csv")

    # ── 7. Textový report ─────────────────────────────────────────────
    lines       = format_report(summary, run_date)
    report_path = AUDIT_DIR / f"ims_mle_overlap_report_{run_date}.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nReport uložen : {report_path}")
    print()
    print("\n".join(lines))


def _save(df: pd.DataFrame, filename: str) -> None:
    import pandas as pd
    path = AUDIT_DIR / filename
    try:
        df.to_csv(path, index=False)
        print(f"CSV uloženo : {filename}  ({len(df)} řádků)")
    except Exception as exc:
        print(f"[WARN] {filename}: {exc}")


if __name__ == "__main__":
    import pandas as pd
    main()
