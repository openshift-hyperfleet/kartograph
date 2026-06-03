"""Port for schema reads and writes performed by sticky session workload tokens."""

from __future__ import annotations

from typing import Protocol

from management.domain.value_objects import OntologyConfig


class IWorkloadSchemaService(Protocol):
    """Canonical schema access scoped to a workload-authenticated knowledge graph."""

    async def get_ontology(self, *, knowledge_graph_id: str) -> OntologyConfig | None:
        """Return the canonical ontology for one knowledge graph."""

    async def replace_ontology(
        self,
        *,
        knowledge_graph_id: str,
        config: OntologyConfig,
    ) -> OntologyConfig:
        """Replace the canonical ontology via DEFINE mutation-log operations."""

    async def apply_mutation_jsonl(
        self,
        *,
        knowledge_graph_id: str,
        jsonl: str,
    ) -> dict[str, object]:
        """Apply JSONL mutation lines (CREATE/UPDATE/DELETE instances, additive DEFINE)."""
