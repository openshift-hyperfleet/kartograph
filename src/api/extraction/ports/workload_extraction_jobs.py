"""Port for extraction job configuration via workload runtime tokens."""

from __future__ import annotations

from typing import Any, Protocol


class IWorkloadExtractionJobsService(Protocol):
    """Read and write extraction job sets scoped to one knowledge graph."""

    async def get_document(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> dict[str, Any]:
        """Return saved job sets plus live entity type instance counts."""
        ...

    async def save_document(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate, persist job sets, and regenerate pending materialized jobs."""
        ...

    async def get_plan_summary(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> dict[str, Any]:
        """Return projected job counts per configured job set."""
        ...

    async def get_database_status(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
    ) -> dict[str, Any]:
        """Return materialized job queue and run metrics."""
        ...
