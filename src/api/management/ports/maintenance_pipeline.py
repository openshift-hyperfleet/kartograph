"""Port for knowledge-graph maintenance pipeline orchestration."""

from __future__ import annotations

from typing import Protocol

from management.domain.value_objects import KnowledgeGraphMaintenanceRunRecord


class MaintenancePipelinePort(Protocol):
    """Coordinates maintenance ingest, job materialization, and extraction."""

    async def trigger(
        self,
        *,
        user_id: str,
        kg_id: str,
        files_per_job: int = 2,
        worker_count: int = 8,
        start_extraction: bool = True,
    ) -> KnowledgeGraphMaintenanceRunRecord: ...

    async def start_ready_maintenance_jobs(
        self,
        *,
        user_id: str,
        kg_id: str,
        worker_count: int = 8,
    ) -> dict[str, int | str | bool]: ...

    async def regenerate_maintenance_jobs(
        self,
        *,
        user_id: str,
        kg_id: str,
        files_per_job: int = 2,
    ) -> dict[str, int | str | bool]: ...
