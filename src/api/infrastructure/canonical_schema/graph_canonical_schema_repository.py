"""Graph-backed implementation of Management canonical schema port."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from graph.application.services.graph_mutation_service import GraphMutationService
from graph.domain.value_objects import EntityType, MutationOperation
from graph.infrastructure.noop_mutation_applier import NoOpMutationApplier
from graph.infrastructure.postgres_kg_type_definition_store import (
    PostgresKnowledgeGraphTypeDefinitionStore,
)
from graph.infrastructure.type_definition_repository import InMemoryTypeDefinitionRepository
from infrastructure.canonical_schema.ontology_mutation_builder import (
    edge_type_metadata,
    node_type_metadata,
    ontology_config_to_define_operations,
)
from infrastructure.canonical_schema.ontology_projection import (
    stored_definitions_to_ontology_config,
)
from management.domain.ontology_prepopulation import validate_ontology_prepopulation
from management.domain.value_objects import OntologyConfig
from management.ports.canonical_schema import ICanonicalSchemaRepository
from management.ports.exceptions import CanonicalSchemaMutationError


class _CollectingTypeDefinitionRepository(InMemoryTypeDefinitionRepository):
    """In-memory repository used while applying canonical schema mutations."""

    pass


class GraphCanonicalSchemaRepository(ICanonicalSchemaRepository):
    """Persist and read canonical schema through mutation-log DEFINE operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._store = PostgresKnowledgeGraphTypeDefinitionStore(session)

    async def get_ontology(self, kg_id: str) -> OntologyConfig | None:
        rows = await self._store.list_for_kg(kg_id)
        if not rows:
            return None
        return stored_definitions_to_ontology_config(rows)

    async def replace_ontology(self, kg_id: str, config: OntologyConfig) -> None:
        validate_ontology_prepopulation(config)
        await self._store.delete_all_for_kg(kg_id)
        await self._apply_operations(
            kg_id, ontology_config_to_define_operations(config), config
        )

    async def apply_mutation_log(self, kg_id: str, jsonl_content: str) -> None:
        operations = self._parse_jsonl(jsonl_content)
        if not operations:
            return

        existing = await self.get_ontology(kg_id) or OntologyConfig()
        await self._apply_operations(kg_id, operations, existing)

    async def _apply_operations(
        self,
        kg_id: str,
        operations: list[MutationOperation],
        config: OntologyConfig,
    ) -> None:
        metadata_by_key = _metadata_map_for_config(config)
        repo = _CollectingTypeDefinitionRepository()

        for row in await self._store.list_for_kg(kg_id):
            repo.save(self._store.to_type_definition(row))

        service = GraphMutationService(
            mutation_applier=NoOpMutationApplier(),
            type_definition_repository=repo,
        )
        result = service.apply_mutations(operations, knowledge_graph_id=kg_id)
        if not result.success:
            message = "; ".join(result.errors) if result.errors else "mutation failed"
            raise CanonicalSchemaMutationError(message)

        for type_def in repo.get_all():
            metadata = metadata_by_key.get((type_def.label, type_def.entity_type.value))
            await self._store.upsert_type_definition(
                kg_id=kg_id,
                type_def=type_def,
                metadata=metadata,
            )

    @staticmethod
    def _parse_jsonl(jsonl_content: str) -> list[MutationOperation]:
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


def _metadata_map_for_config(
    config: OntologyConfig,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Build lookup for authoring metadata preserved outside graph TypeDefinition."""
    metadata: dict[tuple[str, str], dict[str, Any]] = {}
    for node_type in config.node_types:
        metadata[(node_type.label, EntityType.NODE.value)] = node_type_metadata(node_type)
    for edge_type in config.edge_types:
        metadata[(edge_type.label, EntityType.EDGE.value)] = edge_type_metadata(edge_type)
    return metadata
