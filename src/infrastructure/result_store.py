"""
ResultStore — čtení uložených výsledků a jejich porovnávání.

ArchiveManager píše. ResultStore čte.
"""

import json
from pathlib import Path


class ResultStore:
    """
    Read-only přístup k archivovaným výsledkům experimentů.

    Příklad použití:
        store = ResultStore(results_root=Path("results"))
        metrics = store.load_metrics("IrcEdgeValidation", "1.0.0", run_id)
        diff = store.diff_metrics(run_id_a, run_id_b, experiment_name, version)
    """

    def __init__(self, results_root: Path):
        self.results_root = results_root

    def load_metadata(self, experiment_name: str, version: str, run_id: str) -> dict:
        path = self._run_path(experiment_name, version, run_id) / "metadata.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def load_metrics(self, experiment_name: str, version: str, run_id: str) -> dict:
        path = self._run_path(experiment_name, version, run_id) / "metrics.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def diff_metrics(
        self,
        experiment_name: str,
        version: str,
        run_id_a: str,
        run_id_b: str,
    ) -> dict:
        """
        Porovná metriky dvou běhů stejného experimentu.

        Vrací dict: {metric_key: {"a": val_a, "b": val_b, "delta": delta}}
        delta je None pro nečíselné metriky.
        """
        metrics_a = self.load_metrics(experiment_name, version, run_id_a)
        metrics_b = self.load_metrics(experiment_name, version, run_id_b)

        all_keys = set(metrics_a) | set(metrics_b)
        diff = {}

        for key in sorted(all_keys):
            val_a = metrics_a.get(key)
            val_b = metrics_b.get(key)

            try:
                delta = round(float(val_b) - float(val_a), 6) if val_a is not None and val_b is not None else None
            except (TypeError, ValueError):
                delta = None

            diff[key] = {"a": val_a, "b": val_b, "delta": delta}

        return diff

    def _run_path(self, experiment_name: str, version: str, run_id: str) -> Path:
        path = self.results_root / experiment_name / version / run_id
        if not path.exists():
            raise FileNotFoundError(
                f"Run '{run_id}' nebyl nalezen: {path}"
            )
        return path
