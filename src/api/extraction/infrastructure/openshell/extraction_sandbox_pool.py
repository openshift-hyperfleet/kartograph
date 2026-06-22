"""Dedicated OpenShell sandboxes per extraction worker."""

from __future__ import annotations

import re
from dataclasses import dataclass

from extraction.domain.extraction_job import ExtractionJobRecord
from extraction.infrastructure.openshell.sandbox import sanitize_sandbox_name
from extraction.infrastructure.workload_runtime_settings import (
    ExtractionWorkloadRuntimeSettings,
)

_WORKER_INDEX_RE = re.compile(r"(\d+)\s*$")


@dataclass(frozen=True)
class ExtractionSandboxAssignment:
    """Resolved sandbox identity for one extraction job run."""

    sandbox_name: str
    slot: int | None
    reuse: bool


def worker_index(worker_id: str | None) -> int:
    """Parse worker-01 style identifiers into a 1-based index."""
    if not worker_id:
        return 1
    match = _WORKER_INDEX_RE.search(worker_id.strip())
    if not match:
        return 1
    return max(1, int(match.group(1)))


def resolve_extraction_sandbox_assignment(
    job: ExtractionJobRecord,
    settings: ExtractionWorkloadRuntimeSettings,
) -> ExtractionSandboxAssignment:
    """One reusable OpenShell sandbox per extraction worker for the run."""
    _ = settings
    worker_num = worker_index(job.worker_id)
    kg_token = _knowledge_graph_token(job.knowledge_graph_id)
    name = sanitize_sandbox_name(
        "kartograph-extract-",
        f"{kg_token}-w{worker_num:02d}",
    )
    return ExtractionSandboxAssignment(
        sandbox_name=name,
        slot=worker_num,
        reuse=True,
    )


def _knowledge_graph_token(knowledge_graph_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "", knowledge_graph_id).lower()
    return cleaned[-10:] or "kg"
