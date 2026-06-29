"""
ReportBuilder — generuje jednotný Markdown report pro každý experiment run.

Struktura reportu je pevná:
    1. Header (název, verze, run_id, datum rozsah)
    2. Hypotéza
    3. Konfigurace
    4. Metriky
    5. Tabulky (pokud existují)
    6. Summary (volný text od autora experimentu)
    7. Reprodukovatelnost (data hashes, environment)

Formát je jednotný pro všechny experimenty.
Obsah dodává ExperimentResult.
"""

from datetime import datetime
from pathlib import Path

from src.core.experiment_config import ExperimentConfig
from src.core.experiment_definition import ExperimentDefinition
from src.core.experiment_result import ExperimentResult
from src.infrastructure.logging_manager import get_logger

logger = get_logger(__name__)


class ReportBuilder:
    """
    Generuje report.md do run_path adresáře.

    Volán Experiment Runnerem po archivaci výsledků.
    """

    def build(
        self,
        definition: ExperimentDefinition,
        config: ExperimentConfig,
        result: ExperimentResult,
        run_path: Path,
    ) -> Path:
        """
        Sestaví a uloží report.md.

        Returns:
            Path k vygenerovanému souboru.
        """
        report_path = run_path / "report.md"
        content = self._render(definition, config, result)
        report_path.write_text(content, encoding="utf-8")
        logger.info(f"Report uložen: {report_path}")
        return report_path

    def _render(
        self,
        definition: ExperimentDefinition,
        config: ExperimentConfig,
        result: ExperimentResult,
    ) -> str:
        lines = []

        # --- Header ---
        lines += [
            f"# {definition.name} — v{definition.version}",
            "",
            f"**Run ID:** `{result.run_id}`",
            f"**Datum spuštění:** {result.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if result.completed_at else 'N/A'}",
            f"**Datový rozsah:** {config.date_from} → {config.date_to}",
            f"**Universum:** {config.universe}",
            "",
        ]

        # --- Hypotéza ---
        lines += [
            "## Hypotéza",
            "",
            definition.hypothesis,
            "",
        ]

        # --- Konfigurace ---
        lines += ["## Konfigurace", ""]
        if config.parameters:
            for k, v in config.parameters.items():
                lines.append(f"- `{k}`: {v}")
        else:
            lines.append("_(žádné parametry)_")
        if config.notes:
            lines += ["", f"**Poznámky:** {config.notes}"]
        lines.append("")

        # --- Metriky ---
        lines += ["## Metriky", ""]
        if result.metrics:
            lines.append("| Metrika | Hodnota |")
            lines.append("|---------|---------|")
            for k, v in result.metrics.items():
                lines.append(f"| {k} | {v} |")
        else:
            lines.append("_(žádné metriky)_")
        lines.append("")

        # --- Tabulky ---
        if result.tables:
            lines += ["## Tabulky", ""]
            for name in result.tables:
                lines.append(f"- `tables/{name}.csv`")
            lines.append("")

        # --- Summary ---
        lines += ["## Summary", ""]
        lines.append(result.summary if result.summary else "_(summary nebylo vyplněno)_")
        lines.append("")

        # --- Reprodukovatelnost ---
        lines += [
            "## Reprodukovatelnost",
            "",
            f"**Result hash:** `{result.result_hash}`",
            "",
        ]

        return "\n".join(lines)
