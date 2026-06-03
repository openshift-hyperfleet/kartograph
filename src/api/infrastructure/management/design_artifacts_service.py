"""Load design artifacts from canonical schema and tenant AGE graph."""

from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from graph.infrastructure.bulk_data_reader import fetch_bulk_graph_data
from infrastructure.database.connection_pool import ConnectionPool
from management.application.design_artifacts import build_design_artifacts
from management.application.services.knowledge_graph_service import KnowledgeGraphService


class DesignArtifactsService:
    """Compose ontology definitions with live graph instances for the Dev UI."""

    def __init__(
        self,
        *,
        knowledge_graph_service: KnowledgeGraphService,
        connection_pool: ConnectionPool,
        tenant_id: str,
    ) -> None:
        self._knowledge_graph_service = knowledge_graph_service
        self._connection_pool = connection_pool
        self._tenant_id = tenant_id

    async def get_design_artifacts(
        self,
        *,
        user_id: str,
        kg_id: str,
        limit: int = 500,
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
        bounded_limit = max(1, min(limit, 3000))
        return build_design_artifacts(
            knowledge_graph_id=kg_id,
            ontology=ontology,
            graph_data=graph_data,
            limit=bounded_limit,
        )
