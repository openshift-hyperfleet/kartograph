"""Unit tests for workload graph mutation writer."""

from __future__ import annotations

import pytest

from graph.domain.value_objects import (
    EntityType,
    MutationOperation,
    MutationOperationType,
)
from infrastructure.extraction_workload.graph_mutation_writer import (
    GraphWorkloadGraphMutationWriter,
)
from management.ports.exceptions import CanonicalSchemaMutationError


def test_split_operations_separates_define_and_instance_ops() -> None:
    operations = [
        MutationOperation(
            op=MutationOperationType.DEFINE,
            type=EntityType.NODE,
            label="service",
            description="Service",
            required_properties=["name"],
        ),
        MutationOperation(
            op=MutationOperationType.CREATE,
            type=EntityType.NODE,
            id="service:0123456789abcdef",
            label="service",
            set_properties={
                "name": "api",
                "slug": "api",
                "data_source_id": "bootstrap",
                "source_path": "assistant",
            },
        ),
    ]

    define_ops, instance_ops = GraphWorkloadGraphMutationWriter.split_operations(
        operations
    )

    assert len(define_ops) == 1
    assert define_ops[0].op == MutationOperationType.DEFINE
    assert len(instance_ops) == 1
    assert instance_ops[0].op == MutationOperationType.CREATE


def test_parse_jsonl_rejects_invalid_json() -> None:
    with pytest.raises(CanonicalSchemaMutationError, match="JSON parse error"):
        GraphWorkloadGraphMutationWriter.parse_jsonl("{not-json")
