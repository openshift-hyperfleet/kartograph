"""Integration test for workspace transition and mutation-log run visibility."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from management.application.services.data_source_service import DataSourceService
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.domain.aggregates import KnowledgeGraph
from management.domain.entities.data_source_sync_run import MutationLogRunMetadata
from management.domain.value_objects import (
    EdgeTypeDefinition,
    NodeTypeDefinition,
    OntologyConfig,
)
from management.presentation.data_sources.models import SyncRunResponse
from shared_kernel.datasource_types import DataSourceAdapterType
from tests.fakes.authorization import InMemoryAuthorizationProvider

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_workspace_transition_then_extraction_run_metadata_visibility(
    async_session,
    clean_management_data: None,
    knowledge_graph_repository,
    data_source_repository,
    data_source_sync_run_repository,
    test_tenant: str,
    test_workspace: str,
) -> None:
    """End-to-end flow: validate/transition workspace and project mutation-run metadata."""
    required_columns = (
        "maintenance_schedule",
        "maintenance_run_history",
    )
    for column_name in required_columns:
        column_check = await async_session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'knowledge_graphs'
                  AND column_name = :column_name
                """
            ),
            {"column_name": column_name},
        )
        if column_check.scalar_one_or_none() is None:
            pytest.skip(
                f"knowledge_graphs.{column_name} is missing in local integration database"
            )
    # The column introspection query starts an implicit transaction on the session.
    # Reset it before entering explicit transaction scopes below.
    await async_session.rollback()

    user_id = "user-integration-001"
    authz = InMemoryAuthorizationProvider()

    kg_service = KnowledgeGraphService(
        session=async_session,
        knowledge_graph_repository=knowledge_graph_repository,
        data_source_repository=data_source_repository,
        sync_run_repository=data_source_sync_run_repository,
        secret_store=None,
        authz=authz,
        scope_to_tenant=test_tenant,
    )
    ds_service = DataSourceService(
        session=async_session,
        data_source_repository=data_source_repository,
        knowledge_graph_repository=knowledge_graph_repository,
        sync_run_repository=data_source_sync_run_repository,
        secret_store=None,
        authz=authz,
        scope_to_tenant=test_tenant,
    )

    knowledge_graph = KnowledgeGraph.create(
        tenant_id=test_tenant,
        workspace_id=test_workspace,
        name="Integration Flow KG",
        description="Workspace transition + extraction run visibility",
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
    knowledge_graph.set_ontology(ontology_config)
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

    status_before = await kg_service.get_workspace_status(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
    )
    assert status_before is not None
    assert status_before.workspace_mode.value == "schema_bootstrap"
    assert status_before.transition_eligible is True

    validated = await kg_service.validate_workspace(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
    )
    assert validated.transition_eligible is True
    assert validated.readiness.blocking_reasons == ()

    transitioned = await kg_service.transition_workspace_to_extraction(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
    )
    assert transitioned.workspace_mode.value == "extraction_operations"
    assert (
        transitioned.session_pointers.active_extraction_operations_session_id
        is not None
    )

    data_source = await ds_service.create(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
        name="Integration Source",
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"repo_url": "https://github.com/example/repo"},
    )
    await authz.write_relationship(
        f"data_source:{data_source.id.value}",
        "manage",
        f"user:{user_id}",
    )

    sync_run = await ds_service.trigger_sync(
        user_id=user_id,
        ds_id=data_source.id.value,
    )
    assert sync_run.status == "pending"

    sync_run.status = "completed"
    sync_run.completed_at = datetime.now(UTC)
    sync_run.mutation_log_run = MutationLogRunMetadata(
        mutation_log_id="mlog-int-001",
        knowledge_graph_id=knowledge_graph.id.value,
        session_id=transitioned.session_pointers.active_extraction_operations_session_id,
        actor_id=user_id,
        started_at=sync_run.started_at,
        completed_at=sync_run.completed_at,
        token_usage_total=2048,
        cost_total_usd=1.37,
        operation_counts={"create_node": 12, "create_edge": 8},
    )
    async with async_session.begin():
        await data_source_sync_run_repository.save(sync_run)

    runs = await data_source_sync_run_repository.find_by_data_source(
        data_source.id.value
    )
    assert len(runs) == 1
    projected = SyncRunResponse.from_domain(runs[0])

    assert projected.mutation_log_id == "mlog-int-001"
    assert (
        projected.session_id
        == transitioned.session_pointers.active_extraction_operations_session_id
    )
    assert projected.token_usage_total == 2048
    assert projected.cost_total_usd == pytest.approx(1.37)
    assert projected.operation_counts == {"create_node": 12, "create_edge": 8}
