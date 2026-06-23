"""Load design artifacts from canonical schema and tenant AGE graph."""

from __future__ import annotations

import asyncio
from typing import Any

from starlette.concurrency import run_in_threadpool

from graph.application.observability import DefaultGraphServiceProbe
from graph.application.services import GraphQueryService
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.graph_repository import GraphExtractionReadOnlyRepository
from graph.infrastructure.tenant_graph_handler import ensure_tenant_graph_operational
from graph.infrastructure.bulk_data_reader import fetch_bulk_graph_data
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings
from management.application.design_artifacts import (
    DEFAULT_INSTANCES_PER_TYPE,
    build_design_artifacts,
    serialize_entity_instance,
    serialize_relationship_instance,
)
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)


class DesignArtifactsService:
    """Compose ontology definitions with live graph instances for the Dev UI."""

    def __init__(
        self,
        *,
        knowledge_graph_service: KnowledgeGraphService,
        connection_pool: ConnectionPool,
        tenant_id: str,
        database_settings: DatabaseSettings | None = None,
    ) -> None:
        self._knowledge_graph_service = knowledge_graph_service
        self._connection_pool = connection_pool
        self._tenant_id = tenant_id
        self._database_settings = database_settings or DatabaseSettings()

    async def get_design_artifacts(
        self,
        *,
        user_id: str,
        kg_id: str,
        limit: int = DEFAULT_INSTANCES_PER_TYPE,
    ) -> dict[str, object] | None:
        ontology = await self._knowledge_graph_service.get_ontology(
            user_id=user_id,
            kg_id=kg_id,
        )
        if ontology is None:
            kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
            if kg is None:
                return None

        graph_name = f"tenant_{self._tenant_id}"
        graph_data = await run_in_threadpool(
            fetch_bulk_graph_data,
            self._connection_pool,
            graph_name,
        )
        bounded_limit = max(1, min(limit, 500))
        return build_design_artifacts(
            knowledge_graph_id=kg_id,
            ontology=ontology,
            graph_data=graph_data,
            limit=bounded_limit,
            instances_per_type=bounded_limit,
        )

    async def list_entity_instances(
        self,
        *,
        user_id: str,
        kg_id: str,
        entity_type: str,
        limit: int = DEFAULT_INSTANCES_PER_TYPE,
        offset: int = 0,
        property_name: str | None = None,
        property_value: str | None = None,
    ) -> dict[str, Any] | None:
        if not await self._ensure_view_access(user_id=user_id, kg_id=kg_id):
            return None

        bounded_limit = max(1, min(limit, 500))
        bounded_offset = max(0, offset)

        def _query() -> dict[str, Any]:
            client = self._connect_for_tenant()
            try:
                repository = GraphExtractionReadOnlyRepository(
                    client=client,
                    graph_id=client.graph_name,
                )
                service = GraphQueryService(
                    repository=repository,
                    probe=DefaultGraphServiceProbe(),
                )
                total = service.count_by_label(
                    entity_type,
                    knowledge_graph_id=kg_id,
                    property_name=property_name,
                    property_value=property_value,
                )
                nodes = service.list_by_label(
                    entity_type,
                    knowledge_graph_id=kg_id,
                    limit=bounded_limit,
                    offset=bounded_offset,
                    property_name=property_name,
                    property_value=property_value,
                )
                instances = [
                    serialize_entity_instance(
                        {
                            "slug": node.properties.get("slug"),
                            "id": node.id,
                            **node.properties,
                        }
                    )
                    for node in nodes
                ]
                return {
                    "entity_type": entity_type,
                    "instances": instances,
                    "count": len(instances),
                    "total": total,
                    "limit": bounded_limit,
                    "offset": bounded_offset,
                    "property_name": property_name,
                    "property_value": property_value,
                }
            finally:
                client.disconnect()

        return await asyncio.to_thread(_query)

    async def list_relationship_instances(
        self,
        *,
        user_id: str,
        kg_id: str,
        relationship_type: str,
        source_entity_type: str | None = None,
        target_entity_type: str | None = None,
        limit: int = DEFAULT_INSTANCES_PER_TYPE,
        offset: int = 0,
        property_name: str | None = None,
        property_value: str | None = None,
    ) -> dict[str, Any] | None:
        if not await self._ensure_view_access(user_id=user_id, kg_id=kg_id):
            return None

        bounded_limit = max(1, min(limit, 500))
        bounded_offset = max(0, offset)

        def _query() -> dict[str, Any]:
            client = self._connect_for_tenant()
            try:
                repository = GraphExtractionReadOnlyRepository(
                    client=client,
                    graph_id=client.graph_name,
                )
                total = repository.count_relationship_instances(
                    relationship_type,
                    knowledge_graph_id=kg_id,
                    source_entity_type=source_entity_type,
                    target_entity_type=target_entity_type,
                    property_name=property_name,
                    property_value=property_value,
                )
                rows = repository.find_relationship_instances(
                    relationship_type,
                    knowledge_graph_id=kg_id,
                    source_entity_type=source_entity_type,
                    target_entity_type=target_entity_type,
                    limit=bounded_limit,
                    offset=bounded_offset,
                    property_name=property_name,
                    property_value=property_value,
                )
                instances = [
                    serialize_relationship_instance(
                        edge={
                            "id": edge.id,
                            **edge.properties,
                        },
                        source_node={
                            "slug": source.properties.get("slug"),
                            "id": source.id,
                            **source.properties,
                        },
                        target_node={
                            "slug": target.properties.get("slug"),
                            "id": target.id,
                            **target.properties,
                        },
                    )
                    for edge, source, target in rows
                ]
                return {
                    "relationship_type": relationship_type,
                    "source_entity_type": source_entity_type,
                    "target_entity_type": target_entity_type,
                    "instances": instances,
                    "count": len(instances),
                    "total": total,
                    "limit": bounded_limit,
                    "offset": bounded_offset,
                    "property_name": property_name,
                    "property_value": property_value,
                }
            finally:
                client.disconnect()

        return await asyncio.to_thread(_query)

    async def _ensure_view_access(self, *, user_id: str, kg_id: str) -> bool:
        kg = await self._knowledge_graph_service.get(user_id=user_id, kg_id=kg_id)
        return kg is not None

    def _connect_for_tenant(self) -> AgeGraphClient:
        factory = ConnectionFactory(self._database_settings, pool=self._connection_pool)
        graph_name = ensure_tenant_graph_operational(factory, self._tenant_id)
        client = AgeGraphClient(
            self._database_settings,
            connection_factory=factory,
            graph_name=graph_name,
        )
        client.connect()
        return client
