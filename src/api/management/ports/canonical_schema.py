"""Port for graph-native canonical schema access in Management."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from management.domain.value_objects import OntologyConfig


@runtime_checkable
class ICanonicalSchemaRepository(Protocol):
    """Read/write canonical schema state stored as graph type definitions."""

    async def get_ontology(self, kg_id: str) -> OntologyConfig | None:
        """Return canonical schema for a knowledge graph, if any exists."""
        ...

    async def replace_ontology(self, kg_id: str, config: OntologyConfig) -> None:
        """Replace canonical schema via mutation-log DEFINE operations."""
        ...

    async def apply_mutation_log(self, kg_id: str, jsonl_content: str) -> None:
        """Apply additive schema/entity mutations from JSONL content."""
        ...
