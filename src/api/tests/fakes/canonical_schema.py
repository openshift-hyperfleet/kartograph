"""In-memory fake for ICanonicalSchemaRepository."""

from __future__ import annotations

from management.domain.value_objects import OntologyConfig


class InMemoryCanonicalSchemaRepository:
    """Stores canonical schema per knowledge graph for unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, OntologyConfig] = {}
        self.replaced: list[tuple[str, OntologyConfig]] = []
        self.applied_logs: list[tuple[str, str]] = []

    async def get_ontology(self, kg_id: str) -> OntologyConfig | None:
        return self._store.get(kg_id)

    async def replace_ontology(self, kg_id: str, config: OntologyConfig) -> None:
        self.replaced.append((kg_id, config))
        self._store[kg_id] = config

    async def apply_mutation_log(self, kg_id: str, jsonl_content: str) -> None:
        self.applied_logs.append((kg_id, jsonl_content))

    def seed(self, kg_id: str, config: OntologyConfig) -> None:
        """Preload canonical schema for a knowledge graph."""
        self._store[kg_id] = config
