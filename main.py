"""
Market Research Lab — hlavní vstupní bod.

Použití:
    python main.py list                          # výpis všech registrovaných běhů
    python main.py run <ExperimentClass>         # spuštění experimentu (TODO)
    python main.py compare <run_id_a> <run_id_b> # porovnání dvou běhů

Skeleton — menu a CLI implementovat po dokončení infrastruktury.
"""

import sys
from pathlib import Path

from src.infrastructure.logging_manager import configure_logging, get_logger
from src.core.experiment_registry import ExperimentRegistry

configure_logging()
logger = get_logger("mrl.main")

REGISTRY_PATH = Path("registry/experiment_runs.jsonl")
RESULTS_ROOT = Path("results")


def cmd_list():
    registry = ExperimentRegistry(REGISTRY_PATH)
    summary = registry.summary()
    print(f"\nMarket Research Lab — Registry")
    print(f"  Celkem běhů:       {summary['total_runs']}")
    print(f"  Unikátní exp.:     {summary['unique_experiments']}")
    if summary["experiments"]:
        print("  Experimenty:")
        for name in summary["experiments"]:
            runs = registry.find(experiment_name=name)
            print(f"    {name} ({len(runs)} běhů)")
    else:
        print("  (žádné běhy v registry)")


def cmd_compare(run_id_a: str, run_id_b: str):
    registry = ExperimentRegistry(REGISTRY_PATH)
    try:
        diff = registry.compare_runs(run_id_a, run_id_b)
        print(f"\nPorovnání běhů:")
        print(f"  A: {run_id_a}")
        print(f"  B: {run_id_b}")
        print(f"  Result hash shodný: {diff['result_hash_match']}")
        print(f"\nBěh A: {diff['run_a']}")
        print(f"Běh B: {diff['run_b']}")
    except KeyError as e:
        print(f"Chyba: {e}")
        sys.exit(1)


def main():
    args = sys.argv[1:]

    if not args or args[0] == "list":
        cmd_list()
    elif args[0] == "compare" and len(args) == 3:
        cmd_compare(args[1], args[2])
    else:
        print("Použití:")
        print("  python main.py list")
        print("  python main.py compare <run_id_a> <run_id_b>")


if __name__ == "__main__":
    main()
