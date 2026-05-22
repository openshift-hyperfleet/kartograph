"""Integration tests for archived extraction session history and run metadata."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from extraction.application.agent_session_service import ExtractionAgentSessionService
from extraction.domain.value_objects import ExtractionSessionMode
from extraction.infrastructure.repositories import (
    ExtractionAgentSessionRepository,
    ExtractionSessionRunMetricsReader,
)
from management.application.services.data_source_service import DataSourceService
from management.application.services.knowledge_graph_service import KnowledgeGraphService
from management.domain.aggregates import KnowledgeGraph
from management.domain.entities.data_source_sync_run import MutationLogRunMetadata
from management.domain.value_objects import EdgeTypeDefinition, NodeTypeDefinition, OntologyConfig
from shared_kernel.datasource_types import DataSourceAdapterType
from tests.fakes.authorization import InMemoryAuthorizationProvider

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_archived_session_history_retains_linked_run_metadata(
    async_session,
    clean_management_data: None,
    knowledge_graph_repository,
    data_source_repository,
    data_source_sync_run_repository,
    test_tenant: str,
    test_workspace: str,
) -> None:
    """Clear chat archives sessions while history retrieval keeps run metrics."""
    table_check = await async_session.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'extraction_agent_sessions'
            """
        )
    )
    if table_check.scalar_one_or_none() is None:
        pytest.skip("extraction_agent_sessions table is missing in local integration database")
    await async_session.rollback()

    user_id = "user-integration-session-history"
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
        name="Session History KG",
        description="Archived session history retention",
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
    transitioned = await kg_service.transition_workspace_to_extraction(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
    )
    assert transitioned.session_pointers.active_extraction_operations_session_id is not None

    session_repo = ExtractionAgentSessionRepository(session=async_session)
    metrics_reader = ExtractionSessionRunMetricsReader(session=async_session)
    session_service = ExtractionAgentSessionService(
        repository=session_repo,
        run_metrics_reader=metrics_reader,
    )

    active = await session_service.get_or_create_active_session(
        user_id=user_id,
        knowledge_graph_id=knowledge_graph.id.value,
        mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
    )
    session_id = active.id

    data_source = await ds_service.create(
        user_id=user_id,
        kg_id=knowledge_graph.id.value,
        name="History Source",
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
    sync_run.status = "completed"
    sync_run.completed_at = datetime.now(UTC)
    sync_run.mutation_log_run = MutationLogRunMetadata(
        mutation_log_id="mlog-history-001",
        knowledge_graph_id=knowledge_graph.id.value,
        session_id=session_id,
        actor_id=user_id,
        started_at=sync_run.started_at,
        completed_at=sync_run.completed_at,
        token_usage_total=1024,
        cost_total_usd=0.88,
        operation_counts={"create_node": 4},
    )
    async with async_session.begin():
        await data_source_sync_run_repository.save(sync_run)

    archived_session = await session_service.clear_chat(
        user_id=user_id,
        knowledge_graph_id=knowledge_graph.id.value,
        mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
    )
    assert archived_session.id != session_id

    history = await session_service.list_session_history(
        user_id=user_id,
        knowledge_graph_id=knowledge_graph.id.value,
        mode=ExtractionSessionMode.EXTRACTION_OPERATIONS,
    )

    assert len(history) == 2
    archived_record = next(item for item in history if item.session.id == session_id)
    assert archived_record.session.archived_at is not None
    assert archived_record.session.updated_at is not None
    assert len(archived_record.run_metrics) == 1
    assert archived_record.run_metrics[0].mutation_log_id == "mlog-history-001"
    assert archived_record.run_metrics[0].token_usage_total == 1024
    assert archived_record.run_metrics[0].operation_counts == {"create_node": 4}

    still_archived = await session_repo.get_by_id(session_id)
    assert still_archived is not None
    assert still_archived.archived_at is not None

    runs = await data_source_sync_run_repository.find_by_data_source(data_source.id.value)
    assert len(runs) == 1
    assert runs[0].mutation_log_run is not None
    assert runs[0].mutation_log_run.session_id == session_id
