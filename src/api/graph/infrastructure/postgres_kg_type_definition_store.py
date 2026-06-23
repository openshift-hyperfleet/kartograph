"""Postgres-backed canonical schema storage for knowledge graphs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ulid import ULID

from graph.domain.value_objects import EntityType, TypeDefinition
from graph.infrastructure.models.knowledge_graph_type_definition import (
    KnowledgeGraphTypeDefinitionModel,
)


@dataclass(frozen=True)
class StoredKnowledgeGraphTypeDefinition:
    """Canonical type definition row projected for cross-context mapping."""

    label: str
    entity_type: str
    description: str
    required_properties: tuple[str, ...]
    optional_properties: tuple[str, ...]
    metadata: dict[str, Any]


class PostgresKnowledgeGraphTypeDefinitionStore:
    """Async persistence for KG-scoped canonical type definitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def delete_all_for_kg(self, kg_id: str) -> None:
        """Remove all type definitions for a knowledge graph."""
        stmt = delete(KnowledgeGraphTypeDefinitionModel).where(
            KnowledgeGraphTypeDefinitionModel.knowledge_graph_id == kg_id
        )
        await self._session.execute(stmt)

    async def upsert_type_definition(
        self,
        *,
        kg_id: str,
        type_def: TypeDefinition,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Insert or replace a single type definition row."""
        entity_type = type_def.entity_type.value
        values = {
            "id": str(ULID()),
            "knowledge_graph_id": kg_id,
            "entity_type": entity_type,
            "label": type_def.label,
            "description": type_def.description,
            "required_properties": sorted(type_def.required_properties),
            "optional_properties": sorted(type_def.optional_properties),
            "metadata_json": metadata,
        }
        stmt = insert(KnowledgeGraphTypeDefinitionModel).values(**values)
        metadata_column = KnowledgeGraphTypeDefinitionModel.metadata_json.name
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                KnowledgeGraphTypeDefinitionModel.knowledge_graph_id,
                KnowledgeGraphTypeDefinitionModel.entity_type,
                KnowledgeGraphTypeDefinitionModel.label,
            ],
            set_={
                "description": values["description"],
                "required_properties": values["required_properties"],
                "optional_properties": values["optional_properties"],
                metadata_column: values["metadata_json"],
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def list_for_kg(self, kg_id: str) -> list[StoredKnowledgeGraphTypeDefinition]:
        """Return all canonical type definitions for a knowledge graph."""
        stmt = (
            select(KnowledgeGraphTypeDefinitionModel)
            .where(KnowledgeGraphTypeDefinitionModel.knowledge_graph_id == kg_id)
            .order_by(
                KnowledgeGraphTypeDefinitionModel.entity_type,
                KnowledgeGraphTypeDefinitionModel.label,
            )
        )
        result = await self._session.execute(stmt)
        return [self._to_stored(row) for row in result.scalars().all()]

    @staticmethod
    def to_type_definition(
        stored: StoredKnowledgeGraphTypeDefinition,
    ) -> TypeDefinition:
        """Convert a stored projection to a graph TypeDefinition."""
        return TypeDefinition(
            label=stored.label,
            entity_type=EntityType(stored.entity_type),
            description=stored.description,
            required_properties=set(stored.required_properties),
            optional_properties=set(stored.optional_properties),
        )

    @staticmethod
    def _to_stored(
        model: KnowledgeGraphTypeDefinitionModel,
    ) -> StoredKnowledgeGraphTypeDefinition:
        return StoredKnowledgeGraphTypeDefinition(
            label=model.label,
            entity_type=model.entity_type,
            description=model.description,
            required_properties=tuple(model.required_properties or []),
            optional_properties=tuple(model.optional_properties or []),
            metadata=model.metadata_json or {},
        )
