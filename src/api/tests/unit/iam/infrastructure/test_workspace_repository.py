"""Unit tests for WorkspaceRepository.

Following TDD principles - tests verify repository behavior with mocked dependencies.
Tests cover all IWorkspaceRepository protocol methods including outbox event emission,
constraint enforcement, and edge cases.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId, WorkspaceId
from iam.infrastructure.models import WorkspaceModel
from iam.infrastructure.workspace_repository import WorkspaceRepository
from iam.ports.repositories import IWorkspaceRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_probe():
    """Create mock repository probe."""
    probe = MagicMock()
    return probe


@pytest.fixture
def mock_outbox():
    """Create mock outbox repository."""
    outbox = MagicMock()
    outbox.append = AsyncMock()
    return outbox


@pytest.fixture
def mock_serializer():
    """Create mock event serializer."""
    serializer = MagicMock()
    serializer.serialize.return_value = {"test": "payload"}
    return serializer


@pytest.fixture
def repository(mock_session, mock_probe, mock_outbox):
    """Create repository with mock dependencies."""
    return WorkspaceRepository(
        session=mock_session,
        outbox=mock_outbox,
        probe=mock_probe,
    )


@pytest.fixture
def tenant_id():
    """Create a test tenant ID."""
    return TenantId.generate()


@pytest.fixture
def now():
    """Create a fixed timestamp for testing."""
    return datetime.now(UTC)


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_implements_protocol(self, repository):
        """Repository should implement IWorkspaceRepository protocol."""
        assert isinstance(repository, IWorkspaceRepository)


class TestSave:
    """Tests for save method."""

    @pytest.mark.asyncio
    async def test_save_workspace_creates_in_database(
        self, repository, mock_session, tenant_id
    ):
        """Should add new workspace model to session when workspace doesn't exist."""
        workspace = Workspace.create_root(
            name="Root Workspace",
            tenant_id=tenant_id,
        )

        # Mock session to return None (workspace doesn't exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(workspace)

        # Should add new model
        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        assert isinstance(added_model, WorkspaceModel)
        assert added_model.id == workspace.id.value
        assert added_model.tenant_id == tenant_id.value
        assert added_model.name == "Root Workspace"
        assert added_model.is_root is True
        assert added_model.parent_workspace_id is None

    @pytest.mark.asyncio
    async def test_save_workspace_updates_existing(
        self, repository, mock_session, tenant_id, now
    ):
        """Should update existing workspace model when workspace exists."""
        workspace_id = WorkspaceId.generate()
        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Updated Name",
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )

        # Mock existing workspace
        existing_model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="Old Name",
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute.return_value = mock_result

        await repository.save(workspace)

        # Should not add, should update
        mock_session.add.assert_not_called()
        assert existing_model.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_save_workspace_emits_events_to_outbox(
        self, repository, mock_session, mock_outbox, tenant_id
    ):
        """Should append collected events to outbox when saving."""
        # Use factory to generate events
        workspace = Workspace.create_root(
            name="Root Workspace",
            tenant_id=tenant_id,
        )

        # Mock session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(workspace)

        # Should have appended WorkspaceCreated event to outbox
        assert mock_outbox.append.call_count == 1
        call_kwargs = mock_outbox.append.call_args.kwargs
        assert call_kwargs["event_type"] == "WorkspaceCreated"
        assert call_kwargs["aggregate_type"] == "workspace"
        assert call_kwargs["aggregate_id"] == workspace.id.value

    @pytest.mark.asyncio
    async def test_save_child_workspace_with_parent(
        self, repository, mock_session, tenant_id
    ):
        """Should save child workspace with parent reference."""
        parent_id = WorkspaceId.generate()
        workspace = Workspace.create(
            name="Child Workspace",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        # Mock session to return None (workspace doesn't exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(workspace)

        # Should add new model with parent reference
        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        assert added_model.parent_workspace_id == parent_id.value
        assert added_model.is_root is False


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_workspace(
        self, repository, mock_session, tenant_id, now
    ):
        """Should return workspace when found by ID."""
        workspace_id = WorkspaceId.generate()
        model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="Test Workspace",
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(workspace_id)

        assert result is not None
        assert result.id.value == workspace_id.value
        assert result.tenant_id.value == tenant_id.value
        assert result.name == "Test Workspace"
        assert result.is_root is True
        assert result.parent_workspace_id is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(
        self, repository, mock_session
    ):
        """Should return None when workspace doesn't exist."""
        workspace_id = WorkspaceId.generate()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(workspace_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_workspace_with_parent(
        self, repository, mock_session, tenant_id, now
    ):
        """Should return workspace with parent_workspace_id reconstituted."""
        workspace_id = WorkspaceId.generate()
        parent_id = WorkspaceId.generate()
        model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="Child Workspace",
            parent_workspace_id=parent_id.value,
            is_root=False,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(workspace_id)

        assert result is not None
        assert result.parent_workspace_id is not None
        assert result.parent_workspace_id.value == parent_id.value
        assert result.is_root is False


class TestGetByName:
    """Tests for get_by_name method."""

    @pytest.mark.asyncio
    async def test_get_by_name_returns_workspace(
        self, repository, mock_session, tenant_id, now
    ):
        """Should return workspace when found by name in tenant."""
        workspace_id = WorkspaceId.generate()
        model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="Engineering",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name(tenant_id, "Engineering")

        assert result is not None
        assert result.name == "Engineering"

    @pytest.mark.asyncio
    async def test_get_by_name_returns_none_when_not_found(
        self, repository, mock_session, tenant_id
    ):
        """Should return None when workspace name doesn't exist in tenant."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name(tenant_id, "Nonexistent")

        assert result is None


class TestGetRootWorkspace:
    """Tests for get_root_workspace method."""

    @pytest.mark.asyncio
    async def test_get_root_workspace_returns_root(
        self, repository, mock_session, tenant_id, now
    ):
        """Should return root workspace for tenant."""
        workspace_id = WorkspaceId.generate()
        model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="Root",
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_root_workspace(tenant_id)

        assert result is not None
        assert result.is_root is True
        assert result.parent_workspace_id is None

    @pytest.mark.asyncio
    async def test_get_root_workspace_returns_none_when_not_found(
        self, repository, mock_session, tenant_id
    ):
        """Should return None when no root workspace exists for tenant."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_root_workspace(tenant_id)

        assert result is None


class TestListByTenant:
    """Tests for list_by_tenant method."""

    @pytest.mark.asyncio
    async def test_list_by_tenant_returns_all_workspaces(
        self, repository, mock_session, tenant_id, now
    ):
        """Should return all workspaces in a tenant."""
        models = [
            WorkspaceModel(
                id=WorkspaceId.generate().value,
                tenant_id=tenant_id.value,
                name="Root",
                parent_workspace_id=None,
                is_root=True,
                created_at=now,
                updated_at=now,
            ),
            WorkspaceModel(
                id=WorkspaceId.generate().value,
                tenant_id=tenant_id.value,
                name="Engineering",
                parent_workspace_id=None,
                is_root=False,
                created_at=now,
                updated_at=now,
            ),
            WorkspaceModel(
                id=WorkspaceId.generate().value,
                tenant_id=tenant_id.value,
                name="Marketing",
                parent_workspace_id=None,
                is_root=False,
                created_at=now,
                updated_at=now,
            ),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = models
        mock_session.execute.return_value = mock_result

        result = await repository.list_by_tenant(tenant_id)

        assert len(result) == 3
        names = {w.name for w in result}
        assert "Root" in names
        assert "Engineering" in names
        assert "Marketing" in names

    @pytest.mark.asyncio
    async def test_list_by_tenant_returns_empty_when_none(
        self, repository, mock_session, tenant_id
    ):
        """Should return empty list when tenant has no workspaces."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repository.list_by_tenant(tenant_id)

        assert result == []


class TestDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_delete_workspace_removes_from_database(
        self, repository, mock_session, tenant_id, now
    ):
        """Should delete workspace from PostgreSQL."""
        workspace_id = WorkspaceId.generate()
        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="To Delete",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )
        # Mark for deletion to record event
        workspace.mark_for_deletion()

        model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="To Delete",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.delete(workspace)

        assert result is True
        mock_session.delete.assert_called_once_with(model)

    @pytest.mark.asyncio
    async def test_delete_workspace_emits_events_to_outbox(
        self, repository, mock_session, mock_outbox, tenant_id, now
    ):
        """Should append WorkspaceDeleted event to outbox."""
        workspace_id = WorkspaceId.generate()
        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="To Delete",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )
        # Mark for deletion to record event
        workspace.mark_for_deletion()

        model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="To Delete",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        await repository.delete(workspace)

        # Should have appended WorkspaceDeleted event
        calls = mock_outbox.append.call_args_list
        event_types = [call.kwargs.get("event_type") for call in calls]
        assert "WorkspaceDeleted" in event_types

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self, repository, mock_session, tenant_id, now
    ):
        """Should return False when workspace doesn't exist in database."""
        workspace = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=tenant_id,
            name="Ghost",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.delete(workspace)

        assert result is False


class TestWorkspaceNameNotUniqueAcrossTenants:
    """Tests for workspace name uniqueness behavior across tenants."""

    @pytest.mark.asyncio
    async def test_workspace_name_not_unique_across_tenants(
        self, repository, mock_session, now
    ):
        """Same workspace name should be allowed in different tenants.

        Workspace names are unique within a tenant (application-level),
        not globally. This test verifies two workspaces with the same name
        can exist in different tenants.
        """
        tenant_a = TenantId.generate()
        tenant_b = TenantId.generate()

        workspace_a = Workspace.create_root(name="Root", tenant_id=tenant_a)
        workspace_b = Workspace.create_root(name="Root", tenant_id=tenant_b)

        # Mock session for first save
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Both saves should succeed (no uniqueness violation)
        await repository.save(workspace_a)
        await repository.save(workspace_b)

        # Both adds should have been called
        assert mock_session.add.call_count == 2


class TestParentWorkspaceReference:
    """Tests for parent workspace self-referential relationship."""

    @pytest.mark.asyncio
    async def test_parent_workspace_reference_works(
        self, repository, mock_session, tenant_id, now
    ):
        """Should correctly save and retrieve child workspaces with parent references."""
        parent_id = WorkspaceId.generate()
        child = Workspace.create(
            name="Child",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        # Mock session to return None (workspace doesn't exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(child)

        # Verify parent_workspace_id was persisted
        added_model = mock_session.add.call_args[0][0]
        assert added_model.parent_workspace_id == parent_id.value


class TestRootWorkspaceConstraint:
    """Tests for root workspace uniqueness constraint."""

    @pytest.mark.asyncio
    async def test_root_workspace_constraint_enforced(
        self, repository, mock_session, tenant_id, now
    ):
        """Should verify only one root workspace per tenant.

        The partial unique index ensures at most one root workspace per tenant.
        This unit test verifies that the model correctly sets is_root=True.
        The actual database constraint enforcement is tested in integration tests.
        """
        root = Workspace.create_root(
            name="Root",
            tenant_id=tenant_id,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(root)

        added_model = mock_session.add.call_args[0][0]
        assert added_model.is_root is True

        # A non-root workspace should have is_root=False
        parent_id = WorkspaceId.generate()
        child = Workspace.create(
            name="Child",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        await repository.save(child)

        child_model = mock_session.add.call_args[0][0]
        assert child_model.is_root is False


class TestSerializerInjection:
    """Tests for serializer dependency injection."""

    @pytest.mark.asyncio
    async def test_uses_injected_serializer(
        self, mock_session, mock_outbox, mock_probe, mock_serializer
    ):
        """Should use injected serializer instead of creating default."""
        repository = WorkspaceRepository(
            session=mock_session,
            outbox=mock_outbox,
            probe=mock_probe,
            serializer=mock_serializer,
        )

        tenant_id = TenantId.generate()
        workspace = Workspace.create_root(
            name="Test Workspace",
            tenant_id=tenant_id,
        )

        # Mock session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(workspace)

        # Injected serializer should have been called
        mock_serializer.serialize.assert_called()

    def test_uses_default_serializer_when_not_injected(
        self, mock_session, mock_outbox, mock_probe
    ):
        """Should create default serializer when not injected."""
        from iam.infrastructure.outbox import IAMEventSerializer

        repository = WorkspaceRepository(
            session=mock_session,
            outbox=mock_outbox,
            probe=mock_probe,
        )

        assert isinstance(repository._serializer, IAMEventSerializer)


class TestObservabilityProbe:
    """Tests for domain probe usage."""

    @pytest.mark.asyncio
    async def test_probe_called_on_save(
        self, repository, mock_session, mock_probe, tenant_id
    ):
        """Should call probe.workspace_saved on successful save."""
        workspace = Workspace.create_root(
            name="Root",
            tenant_id=tenant_id,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(workspace)

        mock_probe.workspace_saved.assert_called_once_with(
            workspace.id.value, tenant_id.value
        )

    @pytest.mark.asyncio
    async def test_probe_called_on_not_found(
        self, repository, mock_session, mock_probe
    ):
        """Should call probe.workspace_not_found when get_by_id finds nothing."""
        workspace_id = WorkspaceId.generate()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.get_by_id(workspace_id)

        mock_probe.workspace_not_found.assert_called_once_with(workspace_id.value)

    @pytest.mark.asyncio
    async def test_probe_called_on_retrieved(
        self, repository, mock_session, mock_probe, tenant_id, now
    ):
        """Should call probe.workspace_retrieved on successful get_by_id."""
        workspace_id = WorkspaceId.generate()
        model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="Test",
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        await repository.get_by_id(workspace_id)

        mock_probe.workspace_retrieved.assert_called_once_with(workspace_id.value)

    @pytest.mark.asyncio
    async def test_probe_called_on_delete(
        self, repository, mock_session, mock_probe, tenant_id, now
    ):
        """Should call probe.workspace_deleted on successful deletion."""
        workspace_id = WorkspaceId.generate()
        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="To Delete",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )
        workspace.mark_for_deletion()

        model = WorkspaceModel(
            id=workspace_id.value,
            tenant_id=tenant_id.value,
            name="To Delete",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        await repository.delete(workspace)

        mock_probe.workspace_deleted.assert_called_once_with(workspace_id.value)

    @pytest.mark.asyncio
    async def test_probe_called_on_list(
        self, repository, mock_session, mock_probe, tenant_id
    ):
        """Should call probe.workspaces_listed on list_by_tenant."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await repository.list_by_tenant(tenant_id)

        mock_probe.workspaces_listed.assert_called_once_with(tenant_id.value, 0)
