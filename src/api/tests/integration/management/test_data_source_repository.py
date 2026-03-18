"""Integration tests for DataSourceRepository.

These tests require PostgreSQL to be running.
They verify the complete flow of persisting and retrieving data sources,
including FK relationships with knowledge graphs.
"""

import pytest
from sqlalchemy import text

from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.value_objects import ScheduleType
from management.infrastructure.repositories.data_source_repository import (
    DataSourceRepository,
)
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from management.ports.exceptions import DuplicateDataSourceNameError
from shared_kernel.datasource_types import DataSourceAdapterType

pytestmark = pytest.mark.integration


class TestDataSourceRoundTrip:
    """Tests for save and retrieve operations."""

    @pytest.mark.asyncio
    async def test_saves_and_retrieves_data_source(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should save data source to PostgreSQL and retrieve it with all fields."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For DS tests",
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

        retrieved = await data_source_repository.get_by_id(ds.id)

        assert retrieved is not None
        assert retrieved.id.value == ds.id.value
        assert retrieved.knowledge_graph_id == kg.id.value
        assert retrieved.tenant_id == test_tenant
        assert retrieved.name == "My GitHub Source"
        assert retrieved.adapter_type == DataSourceAdapterType.GITHUB
        assert retrieved.connection_config == {"repo": "org/repo", "branch": "main"}
        assert retrieved.credentials_path is None
        assert retrieved.schedule.schedule_type == ScheduleType.MANUAL
        assert retrieved.schedule.value is None
        assert retrieved.last_sync_at is None

    @pytest.mark.asyncio
    async def test_saves_with_credentials_path(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should roundtrip credentials_path correctly."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For DS tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="GitHub With Creds",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
            credentials_path="vault://secrets/github",
        )

        async with async_session.begin():
            await data_source_repository.save(ds)

        retrieved = await data_source_repository.get_by_id(ds.id)

        assert retrieved is not None
        assert retrieved.credentials_path == "vault://secrets/github"


class TestDataSourceUpdate:
    """Tests for updating data sources."""

    @pytest.mark.asyncio
    async def test_updates_connection_config(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should persist updated name, connection_config, and credentials_path."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For DS tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Original Name",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/old-repo"},
        )

        async with async_session.begin():
            await data_source_repository.save(ds)

        # Update in a new transaction
        ds.update_connection(
            name="Updated Name",
            connection_config={"repo": "org/new-repo", "branch": "develop"},
            credentials_path="vault://secrets/updated",
        )

        async with async_session.begin():
            await data_source_repository.save(ds)

        retrieved = await data_source_repository.get_by_id(ds.id)

        assert retrieved is not None
        assert retrieved.name == "Updated Name"
        assert retrieved.connection_config == {
            "repo": "org/new-repo",
            "branch": "develop",
        }
        assert retrieved.credentials_path == "vault://secrets/updated"


class TestDataSourceDeletion:
    """Tests for deleting data sources."""

    @pytest.mark.asyncio
    async def test_deletes_data_source(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should delete data source from PostgreSQL."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For DS tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="To Be Deleted",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )

        async with async_session.begin():
            await data_source_repository.save(ds)

        ds.mark_for_deletion()

        async with async_session.begin():
            result = await data_source_repository.delete(ds)

        assert result is True

        # Verify it's gone
        deleted = await data_source_repository.get_by_id(ds.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should return False when deleting a data source that was never saved."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For DS tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Never Saved",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )
        ds.mark_for_deletion()

        async with async_session.begin():
            result = await data_source_repository.delete(ds)

        assert result is False


class TestFindByKnowledgeGraph:
    """Tests for querying data sources by knowledge graph."""

    @pytest.mark.asyncio
    async def test_finds_data_sources_by_knowledge_graph(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should return only data sources belonging to the specified KG."""
        kg1 = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="KG One",
            description="First KG",
        )
        kg2 = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="KG Two",
            description="Second KG",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg1)
            await knowledge_graph_repository.save(kg2)

        ds1 = DataSource.create(
            knowledge_graph_id=kg1.id.value,
            tenant_id=test_tenant,
            name="DS One on KG1",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo-1"},
        )
        ds2 = DataSource.create(
            knowledge_graph_id=kg1.id.value,
            tenant_id=test_tenant,
            name="DS Two on KG1",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo-2"},
        )
        ds3 = DataSource.create(
            knowledge_graph_id=kg2.id.value,
            tenant_id=test_tenant,
            name="DS on KG2",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo-3"},
        )

        async with async_session.begin():
            await data_source_repository.save(ds1)
            await data_source_repository.save(ds2)
            await data_source_repository.save(ds3)

        results, total = await data_source_repository.find_by_knowledge_graph(
            kg1.id.value
        )

        assert total == 2
        assert len(results) == 2
        result_ids = {r.id.value for r in results}
        assert ds1.id.value in result_ids
        assert ds2.id.value in result_ids

    @pytest.mark.asyncio
    async def test_returns_empty_for_kg_with_no_sources(
        self,
        data_source_repository: DataSourceRepository,
        clean_management_data,
    ):
        """Should return an empty list when KG has no data sources."""
        results, total = await data_source_repository.find_by_knowledge_graph(
            "nonexistent"
        )

        assert results == []
        assert total == 0


class TestDataSourceUniqueness:
    """Tests for data source name uniqueness constraints."""

    @pytest.mark.asyncio
    async def test_duplicate_name_in_same_kg_raises_error(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should raise DuplicateDataSourceNameError for duplicate name in KG."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For uniqueness tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds1 = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Duplicate Name",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo-1"},
        )

        async with async_session.begin():
            await data_source_repository.save(ds1)

        ds2 = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Duplicate Name",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo-2"},
        )

        with pytest.raises(DuplicateDataSourceNameError):
            async with async_session.begin():
                await data_source_repository.save(ds2)


class TestDataSourceOutboxConsistency:
    """Tests verifying outbox events are recorded with data source operations."""

    @pytest.mark.asyncio
    async def test_save_records_outbox_event(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should record a DataSourceCreated event in the outbox table."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For DS tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        # Clear outbox of the KG create event
        await async_session.execute(text("DELETE FROM outbox"))
        await async_session.commit()

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Outbox Test DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )

        async with async_session.begin():
            await data_source_repository.save(ds)

        result = await async_session.execute(
            text(
                "SELECT aggregate_type, event_type, aggregate_id "
                "FROM outbox WHERE aggregate_type = 'data_source'"
            )
        )
        rows = result.fetchall()

        assert len(rows) == 1
        assert rows[0].aggregate_type == "data_source"
        assert rows[0].event_type == "DataSourceCreated"
        assert rows[0].aggregate_id == ds.id.value

    @pytest.mark.asyncio
    async def test_delete_records_outbox_event(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should record a DataSourceDeleted event in the outbox table."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For DS tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Delete Outbox DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )

        async with async_session.begin():
            await data_source_repository.save(ds)

        # Clear outbox of the create events so we isolate the delete event
        await async_session.execute(text("DELETE FROM outbox"))
        await async_session.commit()

        ds.mark_for_deletion()

        async with async_session.begin():
            await data_source_repository.delete(ds)

        result = await async_session.execute(
            text(
                "SELECT aggregate_type, event_type, aggregate_id "
                "FROM outbox WHERE aggregate_type = 'data_source'"
            )
        )
        rows = result.fetchall()

        assert len(rows) == 1
        assert rows[0].aggregate_type == "data_source"
        assert rows[0].event_type == "DataSourceDeleted"
        assert rows[0].aggregate_id == ds.id.value


class TestDataSourceSyncTracking:
    """Tests for sync completion tracking."""

    @pytest.mark.asyncio
    async def test_record_sync_completed_persists(
        self,
        data_source_repository: DataSourceRepository,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should persist last_sync_at after record_sync_completed."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Test KG",
            description="For DS tests",
        )
        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Sync Tracking DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
        )

        async with async_session.begin():
            await data_source_repository.save(ds)

        # Verify initial state has no sync timestamp
        async with async_session.begin():
            initial = await data_source_repository.get_by_id(ds.id)
            assert initial is not None
            assert initial.last_sync_at is None

        # Record sync and persist
        ds.record_sync_completed()

        async with async_session.begin():
            await data_source_repository.save(ds)

        async with async_session.begin():
            retrieved = await data_source_repository.get_by_id(ds.id)

        assert retrieved is not None
        assert retrieved.last_sync_at is not None
