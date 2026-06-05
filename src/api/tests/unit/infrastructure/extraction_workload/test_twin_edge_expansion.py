"""Unit tests for bidirectional twin edge expansion in mutation preflight."""

from __future__ import annotations

import pytest

from graph.domain.value_objects import EntityType, MutationOperation, MutationOperationType
from infrastructure.extraction_workload.mutation_preflight import prepare_mutation_operations
from management.domain.relationship_pairing import expand_ontology_bidirectional_pairs
from management.domain.value_objects import EdgeTypeDefinition, OntologyConfig


@pytest.mark.asyncio
async def test_prepare_mutation_operations_expands_twin_edge_creates() -> None:
    ontology = expand_ontology_bidirectional_pairs(
        OntologyConfig(
            edge_types=(
                EdgeTypeDefinition(
                    label="contains",
                    source_labels=("repository",),
                    target_labels=("test",),
                    bidirectional=True,
                ),
            )
        )
    )
    jsonl = (
        '{"op":"CREATE","type":"edge","id":"contains:0123456789abcdef",'
        '"label":"contains","start_id":"repository:aaaaaaaaaaaaaaaa",'
        '"end_id":"test:bbbbbbbbbbbbbbbb","set_properties":{'
        '"data_source_id":"ds","source_path":"bootstrap","knowledge_graph_id":"kg"}}'
    )

    operations, errors = await prepare_mutation_operations(
        jsonl_content=jsonl,
        tenant_id="tenant-1",
        ontology=ontology,
    )

    assert errors == []
    assert operations is not None
    assert len(operations) == 2
    assert operations[1].label == "contained_in"
    assert operations[1].start_id == "test:bbbbbbbbbbbbbbbb"
    assert operations[1].end_id == "repository:aaaaaaaaaaaaaaaa"
