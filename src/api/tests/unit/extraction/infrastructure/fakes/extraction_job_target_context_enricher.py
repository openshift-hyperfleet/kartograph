"""Fake target context enricher for extraction job materializer tests."""

from __future__ import annotations

from typing import Any

from extraction.application.extraction_job_target_context import (
    enrich_target_instances_for_context,
)
from extraction.domain.extraction_job import ExtractionTargetInstance
from extraction.ports.extraction_job_target_context import (
    IExtractionJobTargetContextEnricher,
)
from extraction.ports.workload_graph import WorkloadGraphNode


class FakeExtractionJobTargetContextEnricher(IExtractionJobTargetContextEnricher):
    """Returns deterministic graph context for one adapter slug used in unit tests."""

    async def enrich_target_instances(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        instances: tuple[ExtractionTargetInstance, ...],
    ) -> list[dict[str, Any]]:
        graph_nodes_by_slug = {
            "hyperfleet_e2e_cl_stuck": WorkloadGraphNode(
                id="adapter:abc123def4567890",
                entity_type="Adapter",
                slug="hyperfleet_e2e_cl_stuck",
                properties={
                    "slug": "hyperfleet_e2e_cl_stuck",
                    "name": "cl-stuck",
                    "config_file_path": "testdata/adapter-configs/cl-stuck/adapter-config.yaml",
                },
            )
        }
        return enrich_target_instances_for_context(
            instances,
            graph_nodes_by_slug=graph_nodes_by_slug,
            node_types=[
                {
                    "label": "Adapter",
                    "required_properties": ["name", "slug"],
                    "optional_properties": [
                        "transport",
                        "resource_types",
                        "config_file_path",
                    ],
                }
            ],
        )
