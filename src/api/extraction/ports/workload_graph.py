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


@dataclass(frozen=True)
class WorkloadGraphRelationship:
    """Graph relationship returned to sticky session agent tools."""

    id: str
    relationship_type: str
    start_id: str
    end_id: str
    source_slug: str | None
    target_slug: str | None
    source_entity_type: str
    target_entity_type: str
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

    async def list_instances_by_type(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        entity_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[WorkloadGraphNode], int]:
        """List entity instances for one type; returns (page, total_count)."""
        ...

    async def count_entity_instances_by_type(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        entity_type: str,
    ) -> int:
        """Count live entity instances for one type."""
        ...

    async def list_relationship_instances(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        relationship_type: str,
        source_entity_type: str | None = None,
        target_entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[WorkloadGraphRelationship], int]:
        """List relationship instances; returns (page, total_count)."""
        ...

    async def count_relationship_instances(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        relationship_type: str,
        source_entity_type: str | None = None,
        target_entity_type: str | None = None,
    ) -> int:
        """Count live relationship instances for one relationship type."""
        ...

    async def find_existing_node_ids(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        node_ids: tuple[str, ...],
    ) -> frozenset[str]:
        """Return node IDs that already exist in the knowledge graph."""
        ...

    async def find_existing_edge_ids(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        edge_ids: tuple[str, ...],
    ) -> frozenset[str]:
        """Return edge IDs that already exist in the knowledge graph."""
        ...

    async def find_existing_slugs_for_entity_type(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        entity_type: str,
        slugs: tuple[str, ...],
    ) -> frozenset[str]:
        """Return slugs that already exist for one entity type."""
        ...

    async def partition_slugs_by_existence(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        entity_type: str,
        slugs: tuple[str, ...],
    ) -> tuple[list[str], list[str]]:
        """Return (existing_slugs, missing_slugs) sorted for one entity type."""
        ...

    async def fetch_nodes_by_ids(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        node_ids: tuple[str, ...],
    ) -> dict[str, WorkloadGraphNode]:
        """Return node snapshots keyed by application id."""
        ...

    async def fetch_edges_by_ids(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        edge_ids: tuple[str, ...],
    ) -> dict[str, WorkloadGraphRelationship]:
        """Return edge snapshots keyed by application id."""
        ...
