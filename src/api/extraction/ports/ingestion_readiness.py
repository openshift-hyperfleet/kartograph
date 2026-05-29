"""Port for reading ingestion prepare readiness without importing Management."""

from __future__ import annotations

from typing import Protocol

from extraction.domain.value_objects import IngestionReadinessSnapshot


class IIngestionReadinessReader(Protocol):
    """Read-only ingestion prepare counts for JobPackage gating."""

    async def read_for_knowledge_graph(
        self, *, knowledge_graph_id: str
    ) -> IngestionReadinessSnapshot:
        """Return data source totals and prepared counts for one knowledge graph."""
        ...
