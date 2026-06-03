"""Graph-backed adapter for extraction workload instance mutations."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from graph.application.services.graph_mutation_service import GraphMutationService
from graph.domain.value_objects import MutationOperation, MutationOperationType
from graph.infrastructure.age_bulk_loading import AgeBulkLoadingStrategy
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.mutation_applier import MutationApplier
from graph.infrastructure.postgres_kg_type_definition_store import (
    PostgresKnowledgeGraphTypeDefinitionStore,
)
from graph.infrastructure.type_definition_repository import InMemoryTypeDefinitionRepository
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.settings import DatabaseSettings
from management.ports.exceptions import CanonicalSchemaMutationError

_INSTANCE_OPS = frozenset(
    {
        MutationOperationType.CREATE,
        MutationOperationType.UPDATE,
        MutationOperationType.DELETE,
    }
)


class GraphWorkloadGraphMutationWriter:
    """Apply CREATE/UPDATE/DELETE mutations to the tenant AGE graph."""

    def __init__(
        self,
        *,
        pool: ConnectionPool,
        settings: DatabaseSettings,
        session: AsyncSession,
    ) -> None:
        self._pool = pool
        self._settings = settings
        self._session = session
        self._type_store = PostgresKnowledgeGraphTypeDefinitionStore(session)

    @staticmethod
    def parse_jsonl(jsonl_content: str) -> list[MutationOperation]:
        operations: list[MutationOperation] = []
        for line_num, line in enumerate(jsonl_content.strip().split("\n"), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                operations.append(MutationOperation(**json.loads(stripped)))
            except json.JSONDecodeError as exc:
                raise CanonicalSchemaMutationError(
                    f"JSON parse error on line {line_num}: {exc}"
                ) from exc
            except ValidationError as exc:
                raise CanonicalSchemaMutationError(
                    f"Validation error on line {line_num}: {exc}"
                ) from exc
        return operations

    @staticmethod
    def split_operations(
        operations: list[MutationOperation],
    ) -> tuple[list[MutationOperation], list[MutationOperation]]:
        define_ops: list[MutationOperation] = []
        instance_ops: list[MutationOperation] = []
        for operation in operations:
            if operation.op == MutationOperationType.DEFINE:
                define_ops.append(operation)
            elif operation.op in _INSTANCE_OPS:
                instance_ops.append(operation)
            else:
                raise CanonicalSchemaMutationError(
                    f"Unsupported mutation operation: {operation.op}"
                )
        return define_ops, instance_ops

    async def apply_instance_operations(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        operations: list[MutationOperation],
    ) -> dict[str, Any]:
        if not operations:
            return {"applied": True, "errors": [], "operations_applied": 0}

        type_repo = InMemoryTypeDefinitionRepository()
        for row in await self._type_store.list_for_kg(knowledge_graph_id):
            type_repo.save(self._type_store.to_type_definition(row))

        return await asyncio.to_thread(
            self._apply_sync,
            tenant_id=tenant_id,
            knowledge_graph_id=knowledge_graph_id,
            operations=operations,
            type_repo=type_repo,
        )

    def _apply_sync(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        operations: list[MutationOperation],
        type_repo: InMemoryTypeDefinitionRepository,
    ) -> dict[str, Any]:
        graph_name = f"tenant_{tenant_id}"
        factory = ConnectionFactory(self._settings, pool=self._pool)
        client = AgeGraphClient(
            self._settings,
            connection_factory=factory,
            graph_name=graph_name,
        )
        client.connect()
        try:
            applier = MutationApplier(
                client=client,
                bulk_loading_strategy=AgeBulkLoadingStrategy(),
            )
            service = GraphMutationService(
                mutation_applier=applier,
                type_definition_repository=type_repo,
            )
            result = service.apply_mutations(
                operations,
                knowledge_graph_id=knowledge_graph_id,
            )
            if not result.success:
                errors = list(result.errors or ["mutation failed"])
                return {"applied": False, "errors": errors, "operations_applied": 0}
            return {
                "applied": True,
                "errors": [],
                "operations_applied": result.operations_applied,
            }
        finally:
            client.disconnect()
