"""Unit tests for workload readiness snapshot helpers."""

from __future__ import annotations

import pytest

from infrastructure.extraction_workload.workspace_readiness import (
    build_workload_readiness_snapshot,
    sync_prepopulated_instance_counts,
)
from management.domain.value_objects import EdgeTypeDefinition, NodeTypeDefinition, OntologyConfig


class _FakeGraphReader:
    async def count_entity_instances_by_type(self, **kwargs):
        entity_type = kwargs.get("entity_type")
        return {"service": 2, "folder": 0}.get(entity_type, 0)

    async def count_relationship_instances(self, **kwargs):
        relationship_type = kwargs.get("relationship_type")
        return 1 if relationship_type == "contains" else 0


@pytest.mark.asyncio
async def test_build_workload_readiness_snapshot_reports_live_relationship_gaps() -> None:
    ontology = OntologyConfig(
        node_types=(
            NodeTypeDefinition(label="folder", prepopulated=True),
            NodeTypeDefinition(label="service", prepopulated=True, prepopulated_instance_count=0),
        ),
        edge_types=(
            EdgeTypeDefinition(
                label="contains",
                source_labels=("folder",),
                target_labels=("source_file",),
                prepopulated=True,
            ),
        ),
    )

    snapshot = await build_workload_readiness_snapshot(
        ontology=ontology,
        knowledge_graph_id="kg-1",
        tenant_id="tenant-1",
        graph_reader=_FakeGraphReader(),
    )

    assert "folder" in snapshot["prepopulated_entity_types_without_instances_live"]
    assert snapshot["prepopulated_types_ready_live"] is False
    assert snapshot["prepopulated_relationship_types"][0]["live_instance_count"] == 1
    assert snapshot["next_action"]
    assert "folder" in snapshot["next_action"]
    assert snapshot["prepopulation_tasks"]
    assert snapshot["prepopulation_tasks"][0]["kind"] == "entity"
    assert snapshot["prepopulation_tasks"][0]["scanner_path"] == "instance_generators/folder.py"
    assert snapshot["prepopulation_tasks"][0]["order"] == 1
    assert snapshot["prepopulation_tasks"][0]["run_command"] == (
        "python3 instance_generators/run_scanner.py folder --entity"
    )
    assert "|" not in snapshot["prepopulation_tasks"][0]["output_jsonl"]
    assert "required_properties" in snapshot["prepopulated_entity_types"][0]


@pytest.mark.asyncio
async def test_sync_prepopulated_instance_counts_updates_metadata() -> None:
    ontology = OntologyConfig(
        node_types=(NodeTypeDefinition(label="service", prepopulated=True, prepopulated_instance_count=0),),
        edge_types=(
            EdgeTypeDefinition(
                label="contains",
                source_labels=("folder",),
                target_labels=("source_file",),
                prepopulated=True,
                prepopulated_instance_count=0,
            ),
        ),
    )

    synced = await sync_prepopulated_instance_counts(
        ontology=ontology,
        knowledge_graph_id="kg-1",
        tenant_id="tenant-1",
        graph_reader=_FakeGraphReader(),
    )

    assert synced.node_types[0].prepopulated_instance_count == 2
    assert synced.edge_types[0].prepopulated_instance_count == 1
