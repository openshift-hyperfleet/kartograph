"""Integration tests for KnowledgeGraphRepository and KnowledgeGraphService.

These tests require PostgreSQL to be running.
They verify the complete flow of persisting and retrieving knowledge graphs
as well as service-level transactional atomicity.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.outbox.repository import OutboxRepository
from management.application.observability import DefaultKnowledgeGraphServiceProbe
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.domain.aggregates import DataSource, KnowledgeGraph
from management.infrastructure.repositories.data_source_repository import (
    DataSourceRepository,
)
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from management.ports.exceptions import DuplicateKnowledgeGraphNameError
from shared_kernel.datasource_types import DataSourceAdapterType

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


class TestKnowledgeGraphFKRestrict:
    """Tests for FK RESTRICT behavior preventing KG deletion with child data sources."""

    @pytest.mark.asyncio
    async def test_delete_kg_with_data_sources_raises_integrity_error(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        async_session,
        test_tenant: str,
        test_workspace: str,
        clean_management_data,
    ):
        """Should reject deletion when KG still has data sources (FK RESTRICT)."""
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError as SAIntegrityError

        from shared_kernel.datasource_types import DataSourceAdapterType

        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="KG With Children",
            description="Has data sources",
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        # Insert a data source via raw SQL to avoid circular repo dependency
        from ulid import ULID

        ds_id = str(ULID())
        await async_session.execute(
            text(
                "INSERT INTO data_sources "
                "(id, knowledge_graph_id, tenant_id, name, adapter_type, "
                "connection_config, schedule_type, created_at, updated_at) "
                "VALUES (:id, :kg_id, :tid, :name, :adapter, "
                "'{}'::jsonb, 'MANUAL', NOW(), NOW())"
            ),
            {
                "id": ds_id,
                "kg_id": kg.id.value,
                "tid": test_tenant,
                "name": "child-ds",
                "adapter": DataSourceAdapterType.GITHUB.value,
            },
        )
        await async_session.commit()

        kg.mark_for_deletion()

        with pytest.raises(SAIntegrityError):
            async with async_session.begin():
                await knowledge_graph_repository.delete(kg)


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


class TestCascadeDeleteRollback:
    """Tests that KG cascade delete is fully atomic — rolls back on failure.

    The spec requires: 'if any step fails, the entire deletion rolls back
    with no partial state'. These tests inject a failure mid-cascade and
    verify full rollback using real SQLAlchemy sessions.

    NOTE: These are integration tests; mock sessions cannot verify SQLAlchemy
    transaction rollback semantics.
    """

    @pytest.mark.asyncio
    async def test_knowledge_graph_deletion_rollback_on_failure(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        data_source_repository: DataSourceRepository,
        async_session: AsyncSession,
        test_tenant: str,
        test_workspace: str,
        clean_management_data: None,
    ) -> None:
        """When cascade delete fails mid-transaction, neither KG nor its data
        sources are deleted — full transactional rollback.

        Simulates a failure after the data source is deleted but before the
        knowledge graph itself is removed, verifying that the entire cascade
        rolls back atomically as required by the spec.
        """
        # Arrange: create a KG with one data source
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Rollback Test KG",
            description="Testing cascade delete rollback",
        )
        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Rollback Test DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo", "branch": "main"},
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        async with async_session.begin():
            await data_source_repository.save(ds)

        # Act: simulate cascade — delete the DS then raise before the KG is removed
        try:
            async with async_session.begin():
                ds.mark_for_deletion(deleted_by="user-1")
                await data_source_repository.delete(ds)
                # Inject failure before the KG deletion step
                raise Exception("Simulated failure mid-cascade")
        except Exception:
            pass  # Expected: the transaction must roll back

        # Assert: both KG and DS still exist — no partial state
        retrieved_kg = await knowledge_graph_repository.get_by_id(kg.id)
        assert retrieved_kg is not None, (
            "KnowledgeGraph must not be deleted when cascade fails mid-transaction"
        )

        retrieved_ds = await data_source_repository.get_by_id(ds.id)
        assert retrieved_ds is not None, (
            "DataSource must not be deleted when cascade fails mid-transaction"
        )


class TestKnowledgeGraphServiceCascadeAtomicity:
    """Integration tests for KnowledgeGraphService.delete() transactional atomicity.

    The spec requires: 'if any step fails, the entire deletion rolls back with
    no partial state'.  These tests exercise the FULL service path — including
    the ``async with self._session.begin()`` boundary in
    ``KnowledgeGraphService.delete()`` — with real SQLAlchemy sessions.

    This class complements ``TestCascadeDeleteRollback`` (which tests the
    repository layer directly) by verifying that the SERVICE-LEVEL transaction
    boundary also provides correct rollback semantics.
    """

    @pytest.mark.asyncio
    async def test_service_delete_rolls_back_on_kg_deletion_failure(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        data_source_repository: DataSourceRepository,
        async_session: AsyncSession,
        test_tenant: str,
        test_workspace: str,
        clean_management_data: None,
    ) -> None:
        """When KG deletion fails after DS cascade deletion, the entire service
        transaction rolls back — neither the KG nor its data sources are removed.

        Simulates a hard failure in ``KnowledgeGraphRepository.delete()`` AFTER
        all data sources have been deleted within the same
        ``async with session.begin()`` block in ``KnowledgeGraphService.delete()``.
        The SQLAlchemy context manager must roll back all writes in the block.
        """
        from tests.fakes.authorization import InMemoryAuthorizationProvider

        # --- Arrange: create KG with one data source ---
        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Service Rollback Test KG",
            description="Verifies service-level atomicity",
        )
        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Service Rollback Test DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo", "branch": "main"},
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        async with async_session.begin():
            await data_source_repository.save(ds)

        # --- Arrange: KG repo subclass that raises during delete ---
        class FailingOnDeleteKGRepo(KnowledgeGraphRepository):
            """Raises a RuntimeError when delete() is called.

            Simulates a failure that occurs AFTER all data sources have been
            deleted (within the same transaction) but BEFORE the KG row is
            removed.
            """

            async def delete(self, knowledge_graph: KnowledgeGraph) -> bool:
                raise RuntimeError(
                    "Simulated KG deletion failure to verify service rollback"
                )

        outbox = OutboxRepository(session=async_session)
        failing_kg_repo = FailingOnDeleteKGRepo(session=async_session, outbox=outbox)

        # --- Arrange: authorization (in-memory; SpiceDB not needed here) ---
        authz = InMemoryAuthorizationProvider()
        await authz.write_relationship(
            f"knowledge_graph:{kg.id.value}", "admin", "user:test-user"
        )

        svc = KnowledgeGraphService(
            session=async_session,
            knowledge_graph_repository=failing_kg_repo,
            data_source_repository=data_source_repository,
            authz=authz,
            scope_to_tenant=test_tenant,
            probe=DefaultKnowledgeGraphServiceProbe(),
        )

        # --- Act: delete must raise (the KG repo is wired to fail) ---
        with pytest.raises(RuntimeError, match="Simulated KG deletion failure"):
            await svc.delete(user_id="test-user", kg_id=kg.id.value)

        # --- Assert: transaction rolled back — both KG and DS still exist ---
        retrieved_kg = await knowledge_graph_repository.get_by_id(kg.id)
        assert retrieved_kg is not None, (
            "KnowledgeGraph must survive when service-level cascade fails; "
            "the async with session.begin() block must roll back completely."
        )

        retrieved_ds = await data_source_repository.get_by_id(ds.id)
        assert retrieved_ds is not None, (
            "DataSource must survive when service-level cascade fails; "
            "DS deletion must be rolled back together with the KG deletion."
        )

    @pytest.mark.asyncio
    async def test_service_delete_commits_fully_on_success(
        self,
        knowledge_graph_repository: KnowledgeGraphRepository,
        data_source_repository: DataSourceRepository,
        async_session: AsyncSession,
        test_tenant: str,
        test_workspace: str,
        clean_management_data: None,
    ) -> None:
        """When delete succeeds, both the KG and its data sources are removed.

        Verifies the happy path of the service-level cascade to complement the
        rollback test — the transaction must commit and leave no orphaned rows.
        """
        from tests.fakes.authorization import InMemoryAuthorizationProvider

        kg = KnowledgeGraph.create(
            tenant_id=test_tenant,
            workspace_id=test_workspace,
            name="Service Delete Commit KG",
            description="Verifies successful service-level deletion",
        )
        ds = DataSource.create(
            knowledge_graph_id=kg.id.value,
            tenant_id=test_tenant,
            name="Service Delete Commit DS",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo", "branch": "main"},
        )

        async with async_session.begin():
            await knowledge_graph_repository.save(kg)

        async with async_session.begin():
            await data_source_repository.save(ds)

        authz = InMemoryAuthorizationProvider()
        await authz.write_relationship(
            f"knowledge_graph:{kg.id.value}", "admin", "user:test-user"
        )

        svc = KnowledgeGraphService(
            session=async_session,
            knowledge_graph_repository=knowledge_graph_repository,
            data_source_repository=data_source_repository,
            authz=authz,
            scope_to_tenant=test_tenant,
            probe=DefaultKnowledgeGraphServiceProbe(),
        )

        result = await svc.delete(user_id="test-user", kg_id=kg.id.value)

        assert result is True, "service.delete() must return True on success"

        # Both KG and DS must be gone after a successful delete
        retrieved_kg = await knowledge_graph_repository.get_by_id(kg.id)
        assert retrieved_kg is None, "KnowledgeGraph must be deleted from the DB"

        retrieved_ds = await data_source_repository.get_by_id(ds.id)
        assert retrieved_ds is None, "DataSource must be deleted from the DB"
