"""Integration tests for canonical graph-native schema storage."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from graph.domain.value_objects import EntityType, MutationOperationType
from infrastructure.canonical_schema.graph_canonical_schema_repository import (
    GraphCanonicalSchemaRepository,
)
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
)
from tests.fakes.authorization import InMemoryAuthorizationProvider

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
async def test_bootstrap_schema_persisted_in_canonical_store_and_readiness(
    async_session,
    clean_management_data: None,
    knowledge_graph_repository,
    test_tenant: str,
    test_workspace: str,
) -> None:
    """Bootstrap ontology flows through mutation-log DEFINE path into canonical store."""
    if not await _table_exists(async_session, "knowledge_graph_type_definitions"):
        pytest.skip("knowledge_graph_type_definitions table is missing")

    await async_session.rollback()

    user_id = "user-canonical-schema-001"
    authz = InMemoryAuthorizationProvider()
    canonical_repo = GraphCanonicalSchemaRepository(async_session)
    kg_service = KnowledgeGraphService(
        session=async_session,
        knowledge_graph_repository=knowledge_graph_repository,
        authz=authz,
        scope_to_tenant=test_tenant,
        canonical_schema_repository=canonical_repo,
    )

    knowledge_graph = KnowledgeGraph.create(
        tenant_id=test_tenant,
        workspace_id=test_workspace,
        name="Canonical Schema KG",
        description="Bootstrap canonical schema",
        created_by=user_id,
    )
    ontology_config = OntologyConfig(
        node_types=(
            NodeTypeDefinition(label="Repository"),
            NodeTypeDefinition(
                label="SeedNode",
                prepopulated=True,
                prepopulated_instance_count=1,
            ),
        ),
        edge_types=(
            EdgeTypeDefinition(
                label="CONTAINS",
                source_labels=("Repository",),
                target_labels=("SeedNode",),
            ),
        ),
    )

    async with async_session.begin():
        await knowledge_graph_repository.save(knowledge_graph)

    await authz.write_relationship(
        f"knowledge_graph:{knowledge_graph.id.value}",
        "admin",
        f"user:{user_id}",
    )

    await kg_service.save_ontology(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
        config=ontology_config,
    )

    canonical = await canonical_repo.get_ontology(knowledge_graph.id.value)
    assert canonical is not None
    assert {node.label for node in canonical.node_types} == {"Repository", "SeedNode"}

    row_count = await async_session.execute(
        text(
            """
            SELECT COUNT(*) AS count
            FROM knowledge_graph_type_definitions
            WHERE knowledge_graph_id = :kg_id
            """
        ),
        {"kg_id": knowledge_graph.id.value},
    )
    assert row_count.scalar_one() == 3

    status = await kg_service.get_workspace_status(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
    )
    assert status is not None
    assert status.transition_eligible is True


@pytest.mark.asyncio
async def test_additive_schema_evolution_in_extraction_mode(
    async_session,
    clean_management_data: None,
    knowledge_graph_repository,
    test_tenant: str,
    test_workspace: str,
) -> None:
    """Extraction mode accepts additive DEFINE mutations via mutation log."""
    if not await _table_exists(async_session, "knowledge_graph_type_definitions"):
        pytest.skip("knowledge_graph_type_definitions table is missing")

    await async_session.rollback()

    user_id = "user-canonical-schema-002"
    authz = InMemoryAuthorizationProvider()
    canonical_repo = GraphCanonicalSchemaRepository(async_session)
    kg_service = KnowledgeGraphService(
        session=async_session,
        knowledge_graph_repository=knowledge_graph_repository,
        authz=authz,
        scope_to_tenant=test_tenant,
        canonical_schema_repository=canonical_repo,
    )

    knowledge_graph = KnowledgeGraph.create(
        tenant_id=test_tenant,
        workspace_id=test_workspace,
        name="Schema Evolution KG",
        description="Additive schema evolution",
        created_by=user_id,
    )
    bootstrap_config = OntologyConfig(
        node_types=(NodeTypeDefinition(label="Repository"),),
        edge_types=(
            EdgeTypeDefinition(
                label="CONTAINS",
                source_labels=("Repository",),
                target_labels=("Repository",),
            ),
        ),
    )

    async with async_session.begin():
        await knowledge_graph_repository.save(knowledge_graph)

    await authz.write_relationship(
        f"knowledge_graph:{knowledge_graph.id.value}",
        "admin",
        f"user:{user_id}",
    )
    await kg_service.save_ontology(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
        config=bootstrap_config,
    )
    await kg_service.transition_workspace_to_extraction(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
    )

    additive_define = {
        "op": MutationOperationType.DEFINE.value,
        "type": EntityType.NODE.value,
        "label": "Service",
        "description": "A deployable service",
        "required_properties": ["slug", "name"],
        "optional_properties": [],
    }
    await canonical_repo.apply_mutation_log(
        knowledge_graph.id.value,
        json.dumps(additive_define),
    )
    await async_session.commit()

    canonical = await canonical_repo.get_ontology(knowledge_graph.id.value)
    assert canonical is not None
    assert {node.label for node in canonical.node_types} == {"Repository", "Service"}

    status = await kg_service.get_workspace_status(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
    )
    assert status is not None
    assert status.workspace_mode.value == "extraction_operations"
