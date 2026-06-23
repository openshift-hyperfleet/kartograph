"""Expand workload mutation operations with bidirectional twin edge CREATE lines."""

from __future__ import annotations

from graph.domain.value_objects import MutationOperation
from management.domain.relationship_pairing import expand_twin_edge_creates
from management.domain.value_objects import OntologyConfig


def expand_twin_edge_mutation_operations(
    operations: list[MutationOperation],
    *,
    ontology: OntologyConfig,
    tenant_id: str,
) -> list[MutationOperation]:
    """Append inverse edge CREATE MutationOperations for bidirectional types."""
    dict_rows = [
        operation.model_dump(mode="json", exclude_none=True) for operation in operations
    ]
    expanded_rows = expand_twin_edge_creates(
        dict_rows,
        ontology=ontology,
        tenant_id=tenant_id,
    )
    if len(expanded_rows) == len(operations):
        return operations
    return [MutationOperation.model_validate(row) for row in expanded_rows]
