"""
ArchiveManager — immutable archivace výsledků experimentů.

Pravidla:
- Každý běh dostane vlastní adresář: results/{name}/{version}/{run_id}/
- Existující výsledky se NIKDY nepřepisují.
- Pokud run_id již existuje, vyhodí výjimku.

Struktura běhu:
    results/
    └── {experiment_name}/
        └── {version}/
            └── {run_id}/
                ├── metadata.json   ← reprodukovatelnost
                ├── config.yaml     ← parametry běhu
                ├── metrics.json    ← číselné výstupy
                ├── tables/         ← DataFrame výstupy (CSV)
                ├── artifacts/      ← libovolné výstupy
                └── report.md       ← generuje ReportBuilder
"""

import json
from pathlib import Path

import yaml

from src.core.experiment_config import ExperimentConfig
from src.core.experiment_result import ExperimentResult
from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)


class ArchiveConflictError(Exception):
    """Pokus o přepsání existujícího run_id."""
    pass


class ArchiveManager:
    """
    Zajišťuje immutable uložení výsledků každého běhu.

    results_root: kořenový adresář pro všechny výsledky (typicky Path("results"))
    """

    def __init__(self, results_root: Path):
        self.results_root = results_root

    def save(
        self,
        experiment_name: str,
        version: str,
        run_id: str,
        config: ExperimentConfig,
        result: ExperimentResult,
        metadata: dict,
    ) -> Path:
        """
        Uloží výsledky běhu do immutable adresáře.

        Returns:
            Path adresáře run_id — předána do registry a report builderu.

        Raises:
            ArchiveConflictError: pokud run_id již existuje.
        """
        run_path = self.results_root / experiment_name / version / run_id

        if run_path.exists():
            raise ArchiveConflictError(
                f"Run '{run_id}' již existuje v: {run_path}. "
                "Výsledky nelze přepsat."
            )

        run_path.mkdir(parents=True, exist_ok=False)
        (run_path / "tables").mkdir()
        (run_path / "artifacts").mkdir()

        logger.info(f"Archivuji run '{run_id}' → {run_path}")

        # metadata.json
        (run_path / "metadata.json").write_text(
            json.dumps(metadata, indent=2, default=str), encoding="utf-8"
        )

        # config.yaml
        config_dict = {
            "date_from": config.date_from.isoformat(),
            "date_to": config.date_to.isoformat(),
            "universe": config.universe,
            "parameters": config.parameters,
            "random_seed": config.random_seed,
            "notes": config.notes,
        }
        (run_path / "config.yaml").write_text(
            yaml.dump(config_dict, allow_unicode=True), encoding="utf-8"
        )

        # metrics.json
        (run_path / "metrics.json").write_text(
            json.dumps(result.metrics, indent=2, default=str), encoding="utf-8"
        )

        # tables/ — každý DataFrame uložen jako CSV
        for table_name, table_data in result.tables.items():
            table_path = run_path / "tables" / f"{table_name}.csv"
            if hasattr(table_data, "to_csv"):
                table_data.to_csv(table_path, index=True)
            else:
                # fallback: JSON
                table_path.with_suffix(".json").write_text(
                    json.dumps(table_data, default=str), encoding="utf-8"
                )

        # artifacts/ — libovolné výstupy
        for artifact_name, artifact_data in result.artifacts.items():
            artifact_path = run_path / "artifacts" / artifact_name
            if isinstance(artifact_data, (str, bytes)):
                mode = "wb" if isinstance(artifact_data, bytes) else "w"
                artifact_path.open(mode).write(artifact_data)
            else:
                artifact_path.with_suffix(".json").write_text(
                    json.dumps(artifact_data, default=str), encoding="utf-8"
                )

        return run_path

    def run_path(self, experiment_name: str, version: str, run_id: str) -> Path:
        """Vrátí cestu k archivu konkrétního běhu (neověřuje existenci)."""
        return self.results_root / experiment_name / version / run_id

    def list_runs(self, experiment_name: str, version: str | None = None) -> list[Path]:
        """Vypíše archivy pro daný experiment, volitelně filtruje podle verze."""
        base = self.results_root / experiment_name
        if not base.exists():
            return []
        if version:
            base = base / version
        return sorted(p for p in base.glob("*/*" if not version else "*") if p.is_dir())
