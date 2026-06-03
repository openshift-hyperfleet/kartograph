"""Port for reading prepared JobPackage identifiers for sticky session materialization."""

from __future__ import annotations

from typing import Protocol

from extraction.domain.prepared_job_package_source import PreparedJobPackageSource


class IPreparedJobPackageReader(Protocol):
    """Read latest prepared JobPackage snapshots for one knowledge graph."""

    async def list_latest_for_knowledge_graph(
        self, *, knowledge_graph_id: str
    ) -> tuple[PreparedJobPackageSource, ...]:
        """Return latest materializable JobPackages per data source for the knowledge graph."""
        ...
