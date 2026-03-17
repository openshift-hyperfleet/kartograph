"""Integration tests for DataSourceSyncRunRepository.

These tests require PostgreSQL to be running.
They verify the complete flow of persisting and retrieving sync runs.
"""

import pytest
from datetime import datetime, UTC

from sqlalchemy import text

from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.entities import DataSourceSyncRun
from management.infrastructure.repositories.data_source_sync_run_repository import (
    DataSourceSyncRunRepository,
)
from management.infrastructure.repositories.data_source_repository import (
    DataSourceRepository,
)
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from shared_kernel.datasource_types import DataSourceAdapterType
from ulid import ULID

pytestmark = pytest.mark.integration


class TestSyncRunRoundTrip:
    """Tests for save and retrieve operations."""

    @pytest.mark.asyncio
    async def test_saves_and_retrieves_sync_run(
        self,
        data_source_sync_run_repository: DataSourceSyncRunRepository,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should save a running sync run and retrieve it with all fields."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For sync run tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="My GitHub Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo", "branch": "main"},
        )
        async with async_session.begin():
            await data_source_repository.save(ds)

        now = datetime.now(UTC)
        sync_run = DataSourceSyncRun(
            id=str(ULID()),
            data_source_id=ds.id.value,
            status="running",
            started_at=now,
            completed_at=None,
            error=None,
            created_at=now,
        )

        async with async_session.begin():
            await data_source_sync_run_repository.save(sync_run)

        retrieved = await data_source_sync_run_repository.get_by_id(sync_run.id)

        assert retrieved is not None
        assert retrieved.id == sync_run.id
        assert retrieved.data_source_id == ds.id.value
        assert retrieved.status == "running"
        assert retrieved.started_at is not None
        assert retrieved.completed_at is None
        assert retrieved.error is None
        assert retrieved.created_at is not None

    @pytest.mark.asyncio
    async def test_saves_completed_sync_run(
        self,
        data_source_sync_run_repository: DataSourceSyncRunRepository,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should roundtrip a completed sync run with completed_at set."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For sync run tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="My GitHub Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )
        async with async_session.begin():
            await data_source_repository.save(ds)

        now = datetime.now(UTC)
        sync_run = DataSourceSyncRun(
            id=str(ULID()),
            data_source_id=ds.id.value,
            status="completed",
            started_at=now,
            completed_at=now,
            error=None,
            created_at=now,
        )

        async with async_session.begin():
            await data_source_sync_run_repository.save(sync_run)

        retrieved = await data_source_sync_run_repository.get_by_id(sync_run.id)

        assert retrieved is not None
        assert retrieved.status == "completed"
        assert retrieved.completed_at is not None
        assert retrieved.error is None

    @pytest.mark.asyncio
    async def test_saves_failed_sync_run(
        self,
        data_source_sync_run_repository: DataSourceSyncRunRepository,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should roundtrip a failed sync run with error message."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For sync run tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="My GitHub Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )
        async with async_session.begin():
            await data_source_repository.save(ds)

        now = datetime.now(UTC)
        sync_run = DataSourceSyncRun(
            id=str(ULID()),
            data_source_id=ds.id.value,
            status="failed",
            started_at=now,
            completed_at=now,
            error="Connection timeout",
            created_at=now,
        )

        async with async_session.begin():
            await data_source_sync_run_repository.save(sync_run)

        retrieved = await data_source_sync_run_repository.get_by_id(sync_run.id)

        assert retrieved is not None
        assert retrieved.status == "failed"
        assert retrieved.completed_at is not None
        assert retrieved.error == "Connection timeout"


class TestSyncRunUpdate:
    """Tests for updating sync runs."""

    @pytest.mark.asyncio
    async def test_updates_sync_run_status(
        self,
        data_source_sync_run_repository: DataSourceSyncRunRepository,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should persist status update from running to completed."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For sync run tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="My GitHub Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )
        async with async_session.begin():
            await data_source_repository.save(ds)

        now = datetime.now(UTC)
        sync_run = DataSourceSyncRun(
            id=str(ULID()),
            data_source_id=ds.id.value,
            status="running",
            started_at=now,
            completed_at=None,
            error=None,
            created_at=now,
        )

        async with async_session.begin():
            await data_source_sync_run_repository.save(sync_run)

        # Update status to completed
        completed_at = datetime.now(UTC)
        sync_run.status = "completed"
        sync_run.completed_at = completed_at

        async with async_session.begin():
            await data_source_sync_run_repository.save(sync_run)

        retrieved = await data_source_sync_run_repository.get_by_id(sync_run.id)

        assert retrieved is not None
        assert retrieved.status == "completed"
        assert retrieved.completed_at is not None


class TestFindByDataSource:
    """Tests for querying sync runs by data source."""

    @pytest.mark.asyncio
    async def test_finds_sync_runs_by_data_source(
        self,
        data_source_sync_run_repository: DataSourceSyncRunRepository,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should return only sync runs belonging to the specified data source."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For sync run tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds1 = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Data Source One",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo-1"},
        )
        ds2 = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Data Source Two",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo-2"},
        )
        async with async_session.begin():
            await data_source_repository.save(ds1)
            await data_source_repository.save(ds2)

        now = datetime.now(UTC)

        # Create 3 sync runs for ds1
        for i in range(3):
            sync_run = DataSourceSyncRun(
                id=str(ULID()),
                data_source_id=ds1.id.value,
                status="completed",
                started_at=now,
                completed_at=now,
                error=None,
                created_at=now,
            )
            async with async_session.begin():
                await data_source_sync_run_repository.save(sync_run)

        # Create 1 sync run for ds2
        sync_run_ds2 = DataSourceSyncRun(
            id=str(ULID()),
            data_source_id=ds2.id.value,
            status="running",
            started_at=now,
            completed_at=None,
            error=None,
            created_at=now,
        )
        async with async_session.begin():
            await data_source_sync_run_repository.save(sync_run_ds2)

        results = await data_source_sync_run_repository.find_by_data_source(
            ds1.id.value
        )

        assert len(results) == 3
        for result in results:
            assert result.data_source_id == ds1.id.value

    @pytest.mark.asyncio
    async def test_returns_empty_for_data_source_with_no_runs(
        self,
        data_source_sync_run_repository: DataSourceSyncRunRepository,
        clean_management_data,
    ):
        """Should return an empty list when data source has no sync runs."""
        results = await data_source_sync_run_repository.find_by_data_source(
            "nonexistent"
        )

        assert results == []


class TestCascadeDelete:
    """Tests for FK CASCADE behavior when data source is deleted."""

    @pytest.mark.asyncio
    async def test_sync_runs_deleted_when_data_source_deleted(
        self,
        data_source_sync_run_repository: DataSourceSyncRunRepository,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should cascade-delete sync runs when the parent data source is deleted."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For cascade tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Cascade Test DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )
        async with async_session.begin():
            await data_source_repository.save(ds)

        now = datetime.now(UTC)
        sync_run_ids = []
        for _ in range(2):
            sync_run = DataSourceSyncRun(
                id=str(ULID()),
                data_source_id=ds.id.value,
                status="completed",
                started_at=now,
                completed_at=now,
                error=None,
                created_at=now,
            )
            async with async_session.begin():
                await data_source_sync_run_repository.save(sync_run)
            sync_run_ids.append(sync_run.id)

        # Verify sync runs exist before deletion
        result = await async_session.execute(
            text(
                "SELECT COUNT(*) FROM data_source_sync_runs "
                "WHERE data_source_id = :ds_id"
            ),
            {"ds_id": ds.id.value},
        )
        assert result.scalar() == 2

        # Delete the data source via raw SQL to trigger CASCADE
        await async_session.execute(
            text("DELETE FROM data_sources WHERE id = :ds_id"),
            {"ds_id": ds.id.value},
        )
        await async_session.commit()

        # Verify sync runs are gone via raw SQL
        result = await async_session.execute(
            text(
                "SELECT COUNT(*) FROM data_source_sync_runs "
                "WHERE data_source_id = :ds_id"
            ),
            {"ds_id": ds.id.value},
        )
        assert result.scalar() == 0
