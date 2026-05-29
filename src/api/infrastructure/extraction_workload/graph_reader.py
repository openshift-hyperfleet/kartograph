"""Graph-backed adapter for extraction workload graph reads."""

from __future__ import annotations

from graph.application.observability import DefaultGraphServiceProbe
from graph.application.services import GraphQueryService
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.graph_repository import GraphExtractionReadOnlyRepository
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings

from extraction.ports.workload_graph import IWorkloadGraphReader, WorkloadGraphNode


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
                graph_id=knowledge_graph_id,
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
