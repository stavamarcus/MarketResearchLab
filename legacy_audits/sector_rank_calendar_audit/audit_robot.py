"""
Sector Leadership Audit Robot — Main Entry Point
audit/audit_robot.py

Spuštění:
    python audit/audit_robot.py
    python audit/audit_robot.py --lookback 20
    python audit/audit_robot.py --lookback 30
    python audit/audit_robot.py --test forward_returns
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

# Nastav sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from audit.data_loader import load_audit_data
from audit.tests import (
    forward_returns,
    top3_retention,
    health_decay,
    leadership_cycles,
    component_importance,
    regime_stability,
    health_emergence,
    leadership_transitions,
)

OUTPUT_DIR = _PROJECT_ROOT / "audit" / "output"

ALL_TESTS = [
    ("leadership_cycles",      leadership_cycles),
    ("top3_retention",         top3_retention),
    ("forward_returns",        forward_returns),
    ("health_decay",           health_decay),
    ("component_importance",   component_importance),
    ("regime_stability",       regime_stability),
    ("health_emergence",       health_emergence),
    ("leadership_transitions", leadership_transitions),
]


def run_all(lookback: int = 20) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    print(f"\n{'='*65}")
    print(f"  SECTOR LEADERSHIP AUDIT ROBOT v1.0")
    print(f"  Lookback: {lookback}D")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}\n")

    # Načti data jednou
    data = load_audit_data()
    print()

    report_lines = [
        "=" * 65,
        "  SECTOR LEADERSHIP AUDIT ROBOT v1.0",
        f"  Lookback: {lookback}D",
        f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 65,
        "",
    ]

    csv_results = {}

    for test_name, test_module in ALL_TESTS:
        print(f"[RUN] {test_name}...")
        t1 = time.time()

        try:
            df = test_module.run(data, lookback=lookback)
            elapsed = time.time() - t1
            print(f"      OK ({elapsed:.1f}s, {len(df):,} řádků)")

            # Ulož CSV
            csv_path = OUTPUT_DIR / f"{test_name}.csv"
            df.to_csv(csv_path, index=False)
            csv_results[test_name] = df

            # Přidej do reportu
            report_lines += test_module.format_report(df)
            report_lines.append("")

        except Exception as exc:
            print(f"      CHYBA: {exc}")
            report_lines.append(f"[CHYBA] {test_name}: {exc}")
            report_lines.append("")

    # Ulož report
    total = time.time() - t0
    report_lines += [
        "=" * 65,
        f"  Dokončeno za {total:.1f}s",
        "=" * 65,
        "",
    ]

    report_path = OUTPUT_DIR / "sector_health_audit_report.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"\n{'='*65}")
    print(f"  AUDIT DOKONČEN za {total:.1f}s")
    print(f"  Report: {report_path}")
    print(f"  CSV:    {OUTPUT_DIR}")
    print(f"{'='*65}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sector Leadership Audit Robot")
    parser.add_argument("--lookback", type=int, choices=[20, 30], default=20)
    parser.add_argument("--test", type=str, default=None,
                        help="Spustit pouze jeden test")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.test:
        # Jednotlivý test
        test_map = {name: mod for name, mod in ALL_TESTS}
        if args.test not in test_map:
            print(f"[CHYBA] Neznámý test: {args.test}")
            print(f"Dostupné: {list(test_map.keys())}")
            sys.exit(1)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        data = load_audit_data()
        mod  = test_map[args.test]
        df   = mod.run(data, lookback=args.lookback)
        print("\n".join(mod.format_report(df)))
        df.to_csv(OUTPUT_DIR / f"{args.test}.csv", index=False)
    else:
        run_all(args.lookback)


if __name__ == "__main__":
    main()
