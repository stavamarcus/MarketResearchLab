"""
ExperimentRunner — orchestrace jednoho běhu experimentu.

Zodpovědnosti:
    1. přijmout experiment a konfiguraci
    2. sestavit ExperimentContext (přes ContextBuilder)
    3. zavolat validate() — odmítnout při FAILED
    4. zavolat run(context)
    5. předat výsledek ArchiveManageru
    6. zapsat záznam do JSONL registry
    7. spustit ReportBuilder
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.context.context_builder import ContextBuilder
from src.core.base_experiment import BaseExperiment
from src.core.experiment_config import ExperimentConfig
from src.core.experiment_result import ExperimentResult, ValidationStatus
from src.infrastructure.archive_manager import ArchiveManager
from src.infrastructure.logging_manager import get_logger
from src.providers.provider_factory import ProviderBundle

logger = get_logger(__name__)


class ExperimentRunError(Exception):
    """Chyba během běhu experimentu."""


class ExperimentRunner:
    """
    Orchestrátor jednoho běhu experimentu.

    Příklad použití:
        bundle = ProviderFactory(Path("config")).build()
        runner = ExperimentRunner(
            provider_bundle=bundle,
            archive_manager=ArchiveManager(Path("results")),
            registry_path=Path("registry/experiment_runs.jsonl"),
        )
        result = runner.run(experiment=MyExperiment(), config=config)
    """

    def __init__(
        self,
        provider_bundle: ProviderBundle,
        archive_manager: ArchiveManager,
        registry_path: Path,
        report_builder=None,
    ) -> None:
        self._bundle = provider_bundle
        self._archive = archive_manager
        self._registry_path = registry_path
        self._report_builder = report_builder

        self._context_builder = ContextBuilder(
            price_provider=provider_bundle.price,
            universe_provider=provider_bundle.universe,
            signal_provider=provider_bundle.signal,
            metadata_provider=provider_bundle.metadata,
        )

    def run(
        self,
        experiment: BaseExperiment,
        config: ExperimentConfig,
        git_commit: str | None = None,
    ) -> ExperimentResult:
        """
        Spustí experiment a zajistí archivaci výsledků.

        Raises:
            ExperimentRunError: validate() FAILED nebo run() selhal.
        """
        definition = experiment.define()
        run_id = str(uuid.uuid4())
        started_at = datetime.now(tz=timezone.utc)

        logger.info(
            f"[{run_id}] START {definition.name} v{definition.version} "
            f"| {config.date_from} → {config.date_to} | universe={config.universe}"
        )

        # --- 1. Sestavení ExperimentContext ---
        try:
            context = self._context_builder.build(
                run_id=run_id,
                definition=definition,
                config=config,
            )
        except Exception as exc:
            raise ExperimentRunError(f"ContextBuilder selhal: {exc}") from exc

        # --- 2. Validace ---
        validation = experiment.validate(context)
        if not validation.is_valid():
            msg = f"validate() FAILED: {validation.messages}"
            logger.error(f"[{run_id}] {msg}")
            raise ExperimentRunError(msg)

        if validation.status == ValidationStatus.WARNING:
            logger.warning(f"[{run_id}] validate() WARNING: {validation.messages}")

        # --- 3. Spuštění ---
        try:
            result = experiment.run(context)
        except Exception as exc:
            logger.exception(f"[{run_id}] experiment.run() selhal: {exc}")
            raise ExperimentRunError(f"run() selhal: {exc}") from exc

        completed_at = datetime.now(tz=timezone.utc)
        result.run_id = run_id
        result.completed_at = completed_at
        result.result_hash = self._hash_result(result)

        # --- 4. Archivace ---
        metadata = self._build_metadata(
            definition=definition,
            context=context,
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            validation=validation,
            git_commit=git_commit,
        )

        run_path = self._archive.save(
            experiment_name=definition.name,
            version=definition.version,
            run_id=run_id,
            config=config,
            result=result,
            metadata=metadata,
        )

        # --- 5. Registry ---
        self._append_registry(
            run_id=run_id,
            definition=definition,
            config=config,
            started_at=started_at,
            completed_at=completed_at,
            run_path=run_path,
            result_hash=result.result_hash,
        )

        # --- 6. Report ---
        if self._report_builder is not None:
            self._report_builder.build(
                definition=definition,
                config=config,
                result=result,
                run_path=run_path,
            )

        elapsed = (completed_at - started_at).total_seconds()
        logger.info(f"[{run_id}] DONE — {elapsed:.1f}s | {run_path}")
        return result

    # ------------------------------------------------------------------
    # Interní metody
    # ------------------------------------------------------------------

    def _hash_result(self, result: ExperimentResult) -> str:
        content = json.dumps(result.metrics, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def _build_metadata(
        self, definition, context, run_id,
        started_at, completed_at, validation, git_commit,
    ) -> dict:
        return {
            "run_id": run_id,
            "experiment_name": definition.name,
            "experiment_version": definition.version,
            "hypothesis": definition.hypothesis,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "elapsed_seconds": (completed_at - started_at).total_seconds(),
            "context_summary": context.summary(),
            "source_hashes": context.source_hashes,
            "environment": {
                "python_version": sys.version,
                "platform": platform.platform(),
            },
            "git_commit": git_commit,
            "validation_warnings": (
                validation.messages
                if validation.status == ValidationStatus.WARNING else []
            ),
        }

    def _append_registry(
        self, run_id, definition, config,
        started_at, completed_at, run_path, result_hash,
    ) -> None:
        record = {
            "run_id": run_id,
            "experiment_name": definition.name,
            "experiment_version": definition.version,
            "date_from": config.date_from.isoformat(),
            "date_to": config.date_to.isoformat(),
            "universe": config.universe,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "result_hash": result_hash,
            "run_path": str(run_path),
            "tags": definition.tags,
        }
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self._registry_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")
