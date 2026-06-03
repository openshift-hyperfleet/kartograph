"""Integration tests for workload graph instance mutations."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from graph.domain.value_objects import EntityType, MutationOperationType
from graph.infrastructure.tenant_graph_handler import AGEGraphProvisioner
from infrastructure.database.connection import ConnectionFactory
from infrastructure.extraction_workload.graph_mutation_writer import (
    GraphWorkloadGraphMutationWriter,
)
from infrastructure.extraction_workload.graph_reader import GraphWorkloadGraphReader
from infrastructure.extraction_workload.schema_service import GraphWorkloadSchemaService
from management.domain.value_objects import EdgeTypeDefinition, NodeTypeDefinition, OntologyConfig

pytestmark = pytest.mark.integration


async def _table_exists(async_session, table_name: str) -> bool:
    result = await async_session.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = :table_name
            """
        ),
        {"table_name": table_name},
    )
    return result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_workload_apply_mutation_jsonl_writes_instance_to_age_graph(
    async_session,
    clean_management_data: None,
    test_tenant: str,
    integration_connection_pool,
    integration_db_settings,
) -> None:
    """CREATE mutations via workload schema service persist nodes in tenant AGE graph."""
    if not await _table_exists(async_session, "knowledge_graph_type_definitions"):
        pytest.skip("knowledge_graph_type_definitions table is missing")

    await async_session.rollback()

    graph_name = f"tenant_{test_tenant}"
    factory = ConnectionFactory(integration_db_settings, pool=integration_connection_pool)
    AGEGraphProvisioner(connection_factory=factory).ensure_graph_exists(graph_name)

    knowledge_graph_id = "kg-workload-mutation-001"
    mutation_writer = GraphWorkloadGraphMutationWriter(
        pool=integration_connection_pool,
        settings=integration_db_settings,
        session=async_session,
    )
    schema_service = GraphWorkloadSchemaService(
        session=async_session,
        mutation_writer=mutation_writer,
    )
    reader = GraphWorkloadGraphReader(
        pool=integration_connection_pool,
        settings=integration_db_settings,
    )

    ontology = OntologyConfig(
        node_types=(
            NodeTypeDefinition(
                label="service",
                description="Deployable service",
                required_properties=("name", "slug"),
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
    await schema_service.replace_ontology(
        knowledge_graph_id=knowledge_graph_id,
        config=ontology,
    )

    create_line = {
        "op": MutationOperationType.CREATE.value,
        "type": EntityType.NODE.value,
        "id": "service:0123456789abcdef",
        "label": "service",
        "set_properties": {
            "name": "api-gateway",
            "slug": "api-gateway",
            "data_source_id": "schema-bootstrap",
            "source_path": "graph-management-assistant",
        },
    }
    result = await schema_service.apply_mutation_jsonl(
        tenant_id=test_tenant,
        knowledge_graph_id=knowledge_graph_id,
        jsonl=json.dumps(create_line),
    )

    assert result["applied"] is True, result.get("errors")
    assert result.get("operations_applied") == 1

    nodes = await reader.search_by_slug(
        tenant_id=test_tenant,
        knowledge_graph_id=knowledge_graph_id,
        slug="api-gateway",
        entity_type="service",
    )
    assert len(nodes) == 1
    assert nodes[0].slug == "api-gateway"
    assert nodes[0].properties.get("name") == "api-gateway"
