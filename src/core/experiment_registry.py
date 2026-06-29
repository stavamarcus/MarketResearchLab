"""
ExperimentRegistry — čtení, filtrování a porovnávání JSONL registry.

Zápis do registry provádí ExperimentRunner (append-only).
Tento modul poskytuje pouze READ operace.
"""

import json
from datetime import date
from pathlib import Path


class ExperimentRegistry:
    """
    Čtení a dotazování nad JSONL registry běhů.

    Každý řádek v experiment_runs.jsonl = jeden ExperimentRun záznam.

    Příklad použití:
        registry = ExperimentRegistry(Path("registry/experiment_runs.jsonl"))
        runs = registry.find(experiment_name="IrcEdgeValidation")
        last = registry.last_run("IrcEdgeValidation")
    """

    def __init__(self, registry_path: Path):
        self.registry_path = registry_path

    def all_runs(self) -> list[dict]:
        """Načte všechny záznamy z registry. Vrátí prázdný seznam, pokud soubor neexistuje."""
        if not self.registry_path.exists():
            return []
        records = []
        with self.registry_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def find(
        self,
        experiment_name: str | None = None,
        version: str | None = None,
        tag: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict]:
        """
        Filtruje běhy podle zadaných kritérií.

        Všechny parametry jsou volitelné a kombinují se jako AND.
        """
        runs = self.all_runs()

        if experiment_name:
            runs = [r for r in runs if r.get("experiment_name") == experiment_name]
        if version:
            runs = [r for r in runs if r.get("experiment_version") == version]
        if tag:
            runs = [r for r in runs if tag in r.get("tags", [])]
        if date_from:
            runs = [r for r in runs if r.get("date_from", "") >= date_from.isoformat()]
        if date_to:
            runs = [r for r in runs if r.get("date_to", "") <= date_to.isoformat()]

        return runs

    def last_run(self, experiment_name: str) -> dict | None:
        """Vrátí poslední běh daného experimentu nebo None."""
        runs = self.find(experiment_name=experiment_name)
        return runs[-1] if runs else None

    def compare_runs(self, run_id_a: str, run_id_b: str) -> dict:
        """
        Porovná dva běhy podle run_id.

        Vrátí dict s oběma záznamy a informací o shodě result_hash.
        Detailní porovnání metrik provádí ReportBuilder.
        """
        all_runs = self.all_runs()
        index = {r["run_id"]: r for r in all_runs}

        run_a = index.get(run_id_a)
        run_b = index.get(run_id_b)

        if not run_a:
            raise KeyError(f"run_id '{run_id_a}' nebyl nalezen v registry.")
        if not run_b:
            raise KeyError(f"run_id '{run_id_b}' nebyl nalezen v registry.")

        return {
            "run_a": run_a,
            "run_b": run_b,
            "result_hash_match": run_a.get("result_hash") == run_b.get("result_hash"),
        }

    def summary(self) -> dict:
        """Souhrn registry: počet běhů, unikátní experimenty, verze."""
        runs = self.all_runs()
        names = {r.get("experiment_name") for r in runs}
        return {
            "total_runs": len(runs),
            "unique_experiments": len(names),
            "experiments": sorted(names),
        }
