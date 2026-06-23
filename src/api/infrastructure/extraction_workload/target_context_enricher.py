"""Graph-backed enrichment for extraction job target instances in job-context.json."""

from __future__ import annotations

from typing import Any

from extraction.application.extraction_job_target_context import (
    enrich_target_instances_for_context,
)
from extraction.domain.extraction_job import ExtractionTargetInstance
from extraction.ports.extraction_job_target_context import (
    IExtractionJobTargetContextEnricher,
)
from extraction.ports.workload_graph import IWorkloadGraphReader, WorkloadGraphNode
from extraction.ports.workload_schema import IWorkloadSchemaService


def _node_type_dicts_from_ontology(ontology: Any | None) -> list[dict[str, Any]]:
    if ontology is None:
        return []
    node_types = getattr(ontology, "node_types", None) or ()
    return [
        {
            "label": str(getattr(node, "label", "") or "").strip(),
            "required_properties": list(
                getattr(node, "required_properties", None) or ()
            ),
            "optional_properties": list(
                getattr(node, "optional_properties", None) or ()
            ),
        }
        for node in node_types
    ]


class GraphExtractionJobTargetContextEnricher(IExtractionJobTargetContextEnricher):
    """Uses workload graph and schema services to pre-seed agent job context."""

    def __init__(
        self,
        *,
        graph_reader: IWorkloadGraphReader,
        schema_service: IWorkloadSchemaService,
    ) -> None:
        self._graph_reader = graph_reader
        self._schema_service = schema_service

    async def enrich_target_instances(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        instances: tuple[ExtractionTargetInstance, ...],
    ) -> list[dict[str, Any]]:
        if not instances:
            return []

        ontology = await self._schema_service.get_ontology(
            knowledge_graph_id=knowledge_graph_id
        )
        graph_nodes_by_slug: dict[str, WorkloadGraphNode] = {}
        for instance in instances:
            matches = await self._graph_reader.search_by_slug(
                tenant_id=tenant_id,
                knowledge_graph_id=knowledge_graph_id,
                slug=instance.slug,
                entity_type=instance.entity_type,
            )
            if matches:
                graph_nodes_by_slug[instance.slug] = matches[0]

        return enrich_target_instances_for_context(
            instances,
            graph_nodes_by_slug=graph_nodes_by_slug,
            node_types=_node_type_dicts_from_ontology(ontology),
        )
