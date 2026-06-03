"""Graph-backed schema service for extraction workload runtimes."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.canonical_schema.graph_canonical_schema_repository import (
    GraphCanonicalSchemaRepository,
)
from management.domain.value_objects import OntologyConfig
from management.ports.exceptions import CanonicalSchemaMutationError


class GraphWorkloadSchemaService:
    """Read and write canonical schema using the Management graph-native store."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = GraphCanonicalSchemaRepository(session)

    async def get_ontology(self, *, knowledge_graph_id: str) -> OntologyConfig | None:
        return await self._repository.get_ontology(knowledge_graph_id)

    async def replace_ontology(
        self,
        *,
        knowledge_graph_id: str,
        config: OntologyConfig,
    ) -> OntologyConfig:
        await self._repository.replace_ontology(knowledge_graph_id, config)
        await self._session.commit()
        return config

    async def apply_mutation_jsonl(
        self,
        *,
        knowledge_graph_id: str,
        jsonl: str,
    ) -> dict[str, object]:
        try:
            await self._repository.apply_mutation_log(knowledge_graph_id, jsonl)
        except CanonicalSchemaMutationError as exc:
            return {"applied": False, "errors": [str(exc)]}
        await self._session.commit()
        return {"applied": True, "errors": []}
