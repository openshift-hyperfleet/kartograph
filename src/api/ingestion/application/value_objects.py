"""Application-layer value objects for the Ingestion bounded context."""

from __future__ import annotations

from dataclasses import dataclass

from shared_kernel.job_package.value_objects import JobPackageId


@dataclass(frozen=True)
class IngestionRunResult:
    """Outcome of a successful ingestion pipeline run."""

    job_package_id: JobPackageId
    entry_count: int
    branch_file_count: int | None
    prepared_commit_sha: str | None
