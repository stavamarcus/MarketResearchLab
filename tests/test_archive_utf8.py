"""Regres FUND-05: ArchiveManager musí zapsat ne-ASCII string artifact
(Windows cp1252 crash — UnicodeEncodeError na '\u0159')."""

from datetime import date

from src.core.experiment_config import ExperimentConfig
from src.core.experiment_result import ExperimentResult
from src.infrastructure.archive_manager import ArchiveManager


def test_non_ascii_artifact_written_utf8(tmp_path):
    am = ArchiveManager(tmp_path / "results")
    result = ExperimentResult(
        metrics={"x": 1},
        artifacts={"report_cz.md": "příliš žluťoučký kůň \u0159"},
    )
    run_path = am.save(
        experiment_name="X", version="1.0.0", run_id="abcd1234efgh",
        config=ExperimentConfig(date_from=date(2026, 1, 1),
                                date_to=date(2026, 2, 1)),
        result=result, metadata={})
    text = (run_path / "artifacts" / "report_cz.md").read_text(
        encoding="utf-8")
    assert "\u0159" in text
