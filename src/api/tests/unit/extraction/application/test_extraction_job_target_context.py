"""Unit tests for extraction job target instance context enrichment."""

from __future__ import annotations

from extraction.application.extraction_job_target_context import (
    enrich_target_instances_for_context,
    missing_properties_for_instance,
)
from extraction.domain.extraction_job import ExtractionTargetInstance
from extraction.ports.workload_graph import WorkloadGraphNode


def test_missing_properties_for_instance_detects_empty_optional_fields() -> None:
    node_types = [
        {
            "label": "Adapter",
            "required_properties": ["name", "slug"],
            "optional_properties": ["transport", "resource_types", "description"],
        }
    ]
    missing = missing_properties_for_instance(
        entity_type="Adapter",
        node_properties={
            "slug": "cl_m_wrong_nest",
            "name": "cl-m-wrong-nest",
            "description": "Test adapter",
            "repository": "hyperfleet-e2e",
        },
        node_types=node_types,
    )

    assert missing == ("resource_types", "transport")


def test_enrich_target_instances_for_context_adds_graph_id_and_gaps() -> None:
    instances = (
        ExtractionTargetInstance(
            slug="cl_m_wrong_nest",
            entity_type="Adapter",
            properties={"config_path": "testdata/adapter-configs/cl-m-wrong-nest"},
        ),
    )
    graph_nodes = {
        "cl_m_wrong_nest": WorkloadGraphNode(
            id="adapter:96533bc42820e9c5",
            entity_type="Adapter",
            slug="cl_m_wrong_nest",
            properties={
                "slug": "cl_m_wrong_nest",
                "name": "cl-m-wrong-nest",
                "config_path": "testdata/adapter-configs/cl-m-wrong-nest",
            },
        )
    }
    enriched = enrich_target_instances_for_context(
        instances,
        graph_nodes_by_slug=graph_nodes,
        node_types=[
            {
                "label": "Adapter",
                "required_properties": ["name", "slug"],
                "optional_properties": ["transport", "resource_types"],
            }
        ],
    )

    assert enriched[0]["graph_id"] == "adapter:96533bc42820e9c5"
    assert enriched[0]["properties_missing"] == ["resource_types", "transport"]
