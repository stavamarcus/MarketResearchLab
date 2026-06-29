"""
IMS Audit — Entry Point
audit/run_audit.py

Spuštění:
    conda run -n institutional_momentum_scanner --no-capture-output python audit/run_audit.py
    conda run -n institutional_momentum_scanner --no-capture-output python audit/run_audit.py --no-csv
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from audit.data_loader import load_audit_data
from audit.forward_returns import compute_forward_returns
from audit.tests.return_analysis import run as run_return_analysis
from audit.tests.relative_performance import run as run_relative_performance
from audit.report_writer import write_audit_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="IMS Audit v1")
    p.add_argument(
        "--no-csv",
        action="store_true",
        help="Nevytvářej CSV výstupy — pouze textový report",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Minimální výstup na stdout",
    )
    return p.parse_args()


def main() -> None:
    args    = parse_args()
    verbose = not args.quiet

    # ── 1. Načti data ─────────────────────────────────────────────────
    data = load_audit_data(verbose=verbose)

    if data.signals.empty:
        print("[CHYBA] Archiv je prázdný — audit nelze spustit.")
        sys.exit(1)

    if not data.close_map:
        print("[CHYBA] Žádná close prices z MDSM cache — audit nelze spustit.")
        sys.exit(1)

    # ── 2. Forward returns ────────────────────────────────────────────
    forward_df = compute_forward_returns(data, verbose=verbose)

    if forward_df.empty:
        print("[CHYBA] Forward returns jsou prázdné — zkontroluj MDSM cache.")
        sys.exit(1)

    # ── 3. Testy ──────────────────────────────────────────────────────
    if verbose:
        print("Spouštím testy...")

    return_df   = run_return_analysis(forward_df)
    relative_df = run_relative_performance(forward_df)

    if verbose:
        print(f"  Return Analysis    : {len(return_df)} řádků")
        print(f"  Relative Perf      : {len(relative_df)} řádků")
        print()

    # ── 4. Report ─────────────────────────────────────────────────────
    report_path = write_audit_report(
        meta=data.meta,
        forward_df=forward_df  if not args.no_csv else forward_df.iloc[0:0],
        return_df=return_df,
        relative_df=relative_df,
        run_date=date.today(),
        verbose=verbose,
    )

    # Vždy vytiskni report na stdout
    print()
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
