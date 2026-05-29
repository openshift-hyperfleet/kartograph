"""Port for graph reads performed by extraction workload runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WorkloadGraphNode:
    """Graph node returned to sticky session agent tools."""

    id: str
    entity_type: str
    slug: str | None
    properties: dict


class IWorkloadGraphReader(Protocol):
    """Read-only graph access scoped to a workload token context."""

    async def search_by_slug(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        slug: str,
        entity_type: str | None = None,
    ) -> list[WorkloadGraphNode]:
        """Search nodes by slug within one knowledge graph."""
        ...
