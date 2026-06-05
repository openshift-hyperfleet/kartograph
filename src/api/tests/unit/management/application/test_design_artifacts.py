"""Unit tests for design artifact builders."""

from __future__ import annotations

from management.application.design_artifacts import build_design_artifacts
from management.domain.value_objects import EdgeTypeDefinition, NodeTypeDefinition, OntologyConfig


def test_build_design_artifacts_merges_ontology_with_graph_instances() -> None:
    ontology = OntologyConfig(
        node_types=(
            NodeTypeDefinition(
                label="service",
                description="Deployable service",
                required_properties=("name", "slug"),
                prepopulated=True,
            ),
        ),
        edge_types=(
            EdgeTypeDefinition(
                label="depends_on",
                source_labels=("service",),
                target_labels=("service",),
            ),
        ),
    )
    graph_data = {
        "nodes": [
            {
                "id": "age-1",
                "type": "service",
                "slug": "api-gateway",
                "knowledge_graph_id": "kg-1",
                "name": "api-gateway",
                "data_source_id": "bootstrap",
                "source_path": "assistant",
            }
        ],
        "edges": [
            {
                "id": "edge-1",
                "type": "depends_on",
                "source": "age-1",
                "target": "age-1",
                "knowledge_graph_id": "kg-1",
                "data_source_id": "bootstrap",
                "source_path": "assistant",
            }
        ],
    }

    payload = build_design_artifacts(
        knowledge_graph_id="kg-1",
        ontology=ontology,
        graph_data=graph_data,
        limit=500,
    )

    assert payload["found"] is True
    assert payload["entities"]["service"]["instance_count"] == 1
    assert payload["entities"]["service"]["instances"][0]["slug"] == "api-gateway"
    assert payload["relationships"][0]["instance_count"] == 1
    assert payload["relationships"][0]["instances"][0]["source_slug"] == "api-gateway"


def test_build_design_artifacts_reports_true_instance_count_when_payload_truncated() -> None:
    graph_data = {
        "nodes": [
            {
                "id": f"age-{index}",
                "type": "service",
                "slug": f"service-{index:04d}",
                "knowledge_graph_id": "kg-1",
            }
            for index in range(600)
        ],
        "edges": [],
    }

    payload = build_design_artifacts(
        knowledge_graph_id="kg-1",
        ontology=OntologyConfig(
            node_types=(
                NodeTypeDefinition(label="service", description="Service", prepopulated=True),
            ),
        ),
        graph_data=graph_data,
        limit=500,
    )

    service = payload["entities"]["service"]
    assert service["instance_count"] == 600
    assert service["instances_returned"] == 500
    assert service["instances_truncated"] is True
    assert len(service["instances"]) == 500
    assert payload["limits"]["entity_instances_truncated"] is True


def test_build_design_artifacts_filters_other_knowledge_graphs() -> None:
    payload = build_design_artifacts(
        knowledge_graph_id="kg-1",
        ontology=None,
        graph_data={
            "nodes": [
                {"id": "1", "type": "service", "slug": "a", "knowledge_graph_id": "kg-2"},
                {"id": "2", "type": "service", "slug": "b", "knowledge_graph_id": "kg-1"},
            ],
            "edges": [],
        },
        limit=500,
    )

    assert payload["counts"]["entity_instances"] == 1
    assert payload["entities"]["service"]["instance_count"] == 1
