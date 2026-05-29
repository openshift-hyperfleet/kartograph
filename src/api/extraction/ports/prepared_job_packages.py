"""Port for reading prepared JobPackage identifiers for sticky session materialization."""

from __future__ import annotations

from typing import Protocol


class IPreparedJobPackageReader(Protocol):
    """Read latest prepared JobPackage ids for one knowledge graph."""

    async def list_latest_for_knowledge_graph(
        self, *, knowledge_graph_id: str
    ) -> tuple[str, ...]:
        """Return latest JobPackage ids per data source for the knowledge graph."""
        ...
