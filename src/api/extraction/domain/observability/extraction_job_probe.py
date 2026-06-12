"""Domain observability probes for extraction job execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ExtractionJobMaterializationObservation:
    job_id: str
    knowledge_graph_id: str
    files_written: int
    packages_requested: int
    packages_missing: tuple[str, ...]
    paths_requested: tuple[str, ...]
    warnings: tuple[str, ...]


class ExtractionJobProbe(Protocol):
    def repository_files_materialized(self, observation: ExtractionJobMaterializationObservation) -> None:
        """Emit when a job workspace repository-files tree is prepared."""


class LoggingExtractionJobProbe:
    """Default probe that records materialization outcomes for operators."""

    def __init__(self, *, sink: Any | None = None) -> None:
        import logging

        self._logger = sink or logging.getLogger("kartograph.extraction.jobs")

    def repository_files_materialized(self, observation: ExtractionJobMaterializationObservation) -> None:
        if observation.files_written > 0:
            self._logger.info(
                "extraction_job_repository_files_materialized job_id=%s kg_id=%s files=%s paths_requested=%s",
                observation.job_id,
                observation.knowledge_graph_id,
                observation.files_written,
                len(observation.paths_requested),
            )
            return
        self._logger.warning(
            "extraction_job_repository_files_empty job_id=%s kg_id=%s packages_requested=%s packages_missing=%s warnings=%s",
            observation.job_id,
            observation.knowledge_graph_id,
            observation.packages_requested,
            list(observation.packages_missing),
            list(observation.warnings),
        )
