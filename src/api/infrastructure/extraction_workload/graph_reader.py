"""Graph-backed adapter for extraction workload graph reads."""

from __future__ import annotations

from graph.application.observability import DefaultGraphServiceProbe
from graph.application.services import GraphQueryService
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.graph_repository import GraphExtractionReadOnlyRepository
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings

from extraction.ports.workload_graph import IWorkloadGraphReader, WorkloadGraphNode, WorkloadGraphRelationship


class GraphWorkloadGraphReader(IWorkloadGraphReader):
    """Uses Graph bounded context services via infrastructure composition root."""

    def __init__(
        self,
        *,
        pool: ConnectionPool,
        settings: DatabaseSettings,
    ) -> None:
        self._pool = pool
        self._settings = settings

    async def search_by_slug(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        slug: str,
        entity_type: str | None = None,
    ) -> list[WorkloadGraphNode]:
        graph_name = f"tenant_{tenant_id}"
        factory = ConnectionFactory(self._settings, pool=self._pool)
        client = AgeGraphClient(self._settings, connection_factory=factory, graph_name=graph_name)
        client.connect()
        try:
            repository = GraphExtractionReadOnlyRepository(
                client=client,
                graph_id=graph_name,
            )
            service = GraphQueryService(repository=repository, probe=DefaultGraphServiceProbe())
            nodes = service.search_by_slug(
                slug=slug,
                node_type=entity_type,
                knowledge_graph_id=knowledge_graph_id,
            )
            return [
                WorkloadGraphNode(
                    id=node.id,
                    entity_type=node.label,
                    slug=node.properties.get("slug"),
                    properties=node.properties,
                )
                for node in nodes
            ]
        finally:
            client.disconnect()

    async def list_instances_by_type(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        entity_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[WorkloadGraphNode], int]:
        graph_name = f"tenant_{tenant_id}"
        factory = ConnectionFactory(self._settings, pool=self._pool)
        client = AgeGraphClient(self._settings, connection_factory=factory, graph_name=graph_name)
        client.connect()
        try:
            repository = GraphExtractionReadOnlyRepository(
                client=client,
                graph_id=graph_name,
            )
            service = GraphQueryService(repository=repository, probe=DefaultGraphServiceProbe())
            bounded_limit = max(1, min(limit, 500))
            bounded_offset = max(0, offset)
            total = service.count_by_label(
                entity_type,
                knowledge_graph_id=knowledge_graph_id,
            )
            nodes = service.list_by_label(
                entity_type,
                knowledge_graph_id=knowledge_graph_id,
                limit=bounded_limit,
                offset=bounded_offset,
            )
            serialized = [
                WorkloadGraphNode(
                    id=node.id,
                    entity_type=node.label,
                    slug=node.properties.get("slug"),
                    properties=node.properties,
                )
                for node in nodes
            ]
            return serialized, total
        finally:
            client.disconnect()

    async def count_entity_instances_by_type(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        entity_type: str,
    ) -> int:
        graph_name = f"tenant_{tenant_id}"
        factory = ConnectionFactory(self._settings, pool=self._pool)
        client = AgeGraphClient(self._settings, connection_factory=factory, graph_name=graph_name)
        client.connect()
        try:
            repository = GraphExtractionReadOnlyRepository(
                client=client,
                graph_id=graph_name,
            )
            service = GraphQueryService(repository=repository, probe=DefaultGraphServiceProbe())
            return service.count_by_label(
                entity_type,
                knowledge_graph_id=knowledge_graph_id,
            )
        finally:
            client.disconnect()

    @staticmethod
    def _slug_from_node(node) -> str | None:
        slug = node.properties.get("slug")
        return str(slug) if slug else None

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
        graph_name = f"tenant_{tenant_id}"
        factory = ConnectionFactory(self._settings, pool=self._pool)
        client = AgeGraphClient(self._settings, connection_factory=factory, graph_name=graph_name)
        client.connect()
        try:
            repository = GraphExtractionReadOnlyRepository(
                client=client,
                graph_id=graph_name,
            )
            bounded_limit = max(1, min(limit, 500))
            bounded_offset = max(0, offset)
            total = repository.count_relationship_instances(
                relationship_type,
                knowledge_graph_id=knowledge_graph_id,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
            )
            rows = repository.find_relationship_instances(
                relationship_type,
                knowledge_graph_id=knowledge_graph_id,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
                limit=bounded_limit,
                offset=bounded_offset,
            )
            relationships = [
                WorkloadGraphRelationship(
                    id=edge.id,
                    relationship_type=edge.label,
                    start_id=edge.start_id,
                    end_id=edge.end_id,
                    source_slug=self._slug_from_node(source),
                    target_slug=self._slug_from_node(target),
                    source_entity_type=source.label,
                    target_entity_type=target.label,
                    properties=edge.properties,
                )
                for edge, source, target in rows
            ]
            return relationships, total
        finally:
            client.disconnect()

    async def count_relationship_instances(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        relationship_type: str,
        source_entity_type: str | None = None,
        target_entity_type: str | None = None,
    ) -> int:
        graph_name = f"tenant_{tenant_id}"
        factory = ConnectionFactory(self._settings, pool=self._pool)
        client = AgeGraphClient(self._settings, connection_factory=factory, graph_name=graph_name)
        client.connect()
        try:
            repository = GraphExtractionReadOnlyRepository(
                client=client,
                graph_id=graph_name,
            )
            return repository.count_relationship_instances(
                relationship_type,
                knowledge_graph_id=knowledge_graph_id,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
            )
        finally:
            client.disconnect()
