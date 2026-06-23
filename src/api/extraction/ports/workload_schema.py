"""Port for schema reads and writes performed by sticky session workload tokens."""

from __future__ import annotations

from typing import Any, Protocol


class IWorkloadSchemaService(Protocol):
    """Canonical schema access scoped to a workload-authenticated knowledge graph."""

    async def get_ontology(self, *, knowledge_graph_id: str) -> dict[str, Any] | None:
        """Return the canonical ontology for one knowledge graph."""

    async def replace_ontology(
        self,
        *,
        knowledge_graph_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Replace the canonical ontology via DEFINE mutation-log operations."""

    async def replace_ontology_from_authoring_payload(
        self,
        *,
        knowledge_graph_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate authoring payload and replace the canonical ontology."""

    async def validate_mutation_jsonl(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        jsonl: str,
    ) -> dict[str, Any]:
        """Dry-run validation for JSONL mutations without writing to the graph."""

    async def apply_mutation_jsonl(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        jsonl: str,
    ) -> dict[str, Any]:
        """Apply JSONL mutation lines (CREATE/UPDATE/DELETE instances, additive DEFINE)."""
