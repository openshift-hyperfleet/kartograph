"""Integration tests for KnowledgeGraphRepository.

These tests require PostgreSQL to be running.
They verify the complete flow of persisting and retrieving knowledge graphs.
"""

import pytest
from sqlalchemy import text

from management.domain.aggregates import KnowledgeGraph
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from management.ports.exceptions import DuplicateKnowledgeGraphNameError

pytestmark = pytest.mark.integration


class TestKnowledgeGraphRoundTrip:
    """Tests for save and retrieve operations."""

    @pytest.mark.asyncio
    async def test_saves_and_retrieves_knowledge_graph(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should save knowledge graph to PostgreSQL and retrieve it."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="My Knowledge Graph",
            description="A test knowledge graph",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        retrieved = await knowledge_graph_repository.get_by_id(kg.id)

        assert retrieved is not None
        assert retrieved.id.value == kg.id.value
        assert retrieved.tenant_id == test_tenant
        assert retrieved.workspace_id == test_workspace
        assert retrieved.name == "My Knowledge Graph"
        assert retrieved.description == "A test knowledge graph"

    @pytest.mark.asyncio
    async def test_saves_and_retrieves_with_description(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should roundtrip description correctly, including empty string."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Empty Description KG",
            description="",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        retrieved = await knowledge_graph_repository.get_by_id(kg.id)

        assert retrieved is not None
        assert retrieved.description == ""


class TestKnowledgeGraphUpdate:
    """Tests for updating knowledge graphs."""

    @pytest.mark.asyncio
    async def test_updates_knowledge_graph(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should persist updated name and description."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Original Name",
            description="Original description",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        # Update in a new transaction
        kg.update(name="Updated Name", description="Updated description")

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        retrieved = await knowledge_graph_repository.get_by_id(kg.id)

        assert retrieved is not None
        assert retrieved.name == "Updated Name"
        assert retrieved.description == "Updated description"

    @pytest.mark.asyncio
    async def test_update_records_outbox_event(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should record a KnowledgeGraphUpdated event in the outbox."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Before Update",
            description="Before",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        # Clear outbox of the create event so we can isolate the update event
        await async_session.execute(text("DELETE FROM outbox"))
        await async_session.commit()

        kg.update(name="After Update", description="After")

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        result = await async_session.execute(
            text(
                "SELECT aggregate_type, event_type, aggregate_id "
                "FROM outbox WHERE aggregate_type = 'knowledge_graph'"
            )
        )
        rows = result.fetchall()

        assert len(rows) == 1
        assert rows[0].aggregate_type == "knowledge_graph"
        assert rows[0].event_type == "KnowledgeGraphUpdated"
        assert rows[0].aggregate_id == kg.id.value


class TestKnowledgeGraphDeletion:
    """Tests for deleting knowledge graphs."""

    @pytest.mark.asyncio
    async def test_deletes_knowledge_graph(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should delete knowledge graph from PostgreSQL."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="To Be Deleted",
            description="Will be removed",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        # Mark for deletion and delete in a new transaction
        async with async_session.begin():
            retrieved = await knowledge_graph_repository.get_by_id(kg.id)
            assert retrieved is not None

            retrieved.mark_for_deletion()
            result = await knowledge_graph_repository.delete(retrieved)

        assert result is True

        # Verify it's gone
        deleted = await knowledge_graph_repository.get_by_id(kg.id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should return False when deleting a knowledge graph that was never saved."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Never Saved",
            description="This KG is not in the database",
        )
        kg.mark_for_deletion()

        async with async_session.begin():
            result = await knowledge_graph_repository.delete(kg)

        assert result is False


class TestKnowledgeGraphUniqueness:
    """Tests for knowledge graph name uniqueness constraints."""

    @pytest.mark.asyncio
    async def test_duplicate_name_in_same_tenant_raises_error(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should raise DuplicateKnowledgeGraphNameError for duplicate name in tenant."""
        kg1 = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Duplicate Name",
            description="First",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg1)

        kg2 = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Duplicate Name",
            description="Second",
        )

        with pytest.raises(DuplicateKnowledgeGraphNameError):
            async with async_session.begin():
                await knowledge_graph_repository.save(kg2)


class TestFindByTenant:
    """Tests for querying knowledge graphs by tenant."""

    @pytest.mark.asyncio
    async def test_finds_knowledge_graphs_by_tenant(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should return only knowledge graphs belonging to the specified tenant."""
        # Create 2 KGs in the test tenant
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

        # Create a second tenant and workspace via raw SQL for isolation
        from ulid import ULID

        other_tenant_id = str(ULID())
        other_workspace_id = str(ULID())
        await async_session.execute(
            text(
                "INSERT INTO tenants (id, name, created_at, updated_at) "
                "VALUES (:id, :name, NOW(), NOW())"
            ),
            {"id": other_tenant_id, "name": f"other-tenant-{other_tenant_id}"},
        )
        await async_session.execute(
            text(
                "INSERT INTO workspaces (id, tenant_id, name, is_root, created_at, updated_at) "
                "VALUES (:id, :tenant_id, :name, :is_root, NOW(), NOW())"
            ),
            {
                "id": other_workspace_id,
                "tenant_id": other_tenant_id,
                "name": f"other-workspace-{other_workspace_id}",
                "is_root": True,
            },
        )
        await async_session.commit()

        # Create 1 KG in the other tenant
        kg_other = KnowledgeGraph.create(
            tenant_id=other_tenant_id,
            workspace_id=other_workspace_id,
            name="Other Tenant KG",
            description="Should not appear",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg_other)

        # Query for the test tenant
        results = await knowledge_graph_repository.find_by_tenant(test_tenant)

        assert len(results) == 2
        result_ids = {r.id.value for r in results}
        assert kg1.id.value in result_ids
        assert kg2.id.value in result_ids

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_tenant_with_no_graphs(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        clean_management_data,
    ):
        """Should return an empty list when tenant has no knowledge graphs."""
        results = await knowledge_graph_repository.find_by_tenant("nonexistent-tenant")

        assert results == []


class TestOutboxConsistency:
    """Tests verifying outbox events are recorded with aggregate operations."""

    @pytest.mark.asyncio
    async def test_save_records_outbox_event(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should record a KnowledgeGraphCreated event in the outbox table."""
        # Clear any pre-existing outbox entries
        await async_session.execute(text("DELETE FROM outbox"))
        await async_session.commit()

        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Outbox Test KG",
            description="Testing outbox integration",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        result = await async_session.execute(
            text(
                "SELECT aggregate_type, event_type, aggregate_id "
                "FROM outbox WHERE aggregate_type = 'knowledge_graph'"
            )
        )
        rows = result.fetchall()

        assert len(rows) == 1
        assert rows[0].aggregate_type == "knowledge_graph"
        assert rows[0].event_type == "KnowledgeGraphCreated"
        assert rows[0].aggregate_id == kg.id.value

    @pytest.mark.asyncio
    async def test_delete_records_outbox_event(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should record a KnowledgeGraphDeleted event in the outbox table."""
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Delete Outbox KG",
            description="Testing delete outbox event",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        # Clear outbox of the create event so we can isolate the delete event
        await async_session.execute(text("DELETE FROM outbox"))
        await async_session.commit()

        async with async_session.begin():
            retrieved = await knowledge_graph_repository.get_by_id(kg.id)
            assert retrieved is not None

            retrieved.mark_for_deletion()
            await knowledge_graph_repository.delete(retrieved)

        result = await async_session.execute(
            text(
                "SELECT aggregate_type, event_type, aggregate_id "
                "FROM outbox WHERE aggregate_type = 'knowledge_graph'"
            )
        )
        rows = result.fetchall()

        assert len(rows) == 1
        assert rows[0].aggregate_type == "knowledge_graph"
        assert rows[0].event_type == "KnowledgeGraphDeleted"
        assert rows[0].aggregate_id == kg.id.value
