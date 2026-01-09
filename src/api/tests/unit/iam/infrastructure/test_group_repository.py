"""Unit tests for GroupRepository.

Following TDD principles - tests verify repository behavior with mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, create_autospec

from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, Role, TenantId, UserId
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.models import GroupModel
from iam.ports.exceptions import DuplicateGroupNameError
from iam.ports.repositories import IGroupRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import SubjectRelation


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_authz():
    """Create mock authorization provider."""
    authz = create_autospec(AuthorizationProvider, instance=True)
    # Make all methods async
    authz.write_relationship = AsyncMock()
    authz.write_relationships = AsyncMock()
    authz.delete_relationship = AsyncMock()
    authz.delete_relationships = AsyncMock()
    authz.lookup_subjects = AsyncMock(return_value=[])
    authz.lookup_resources = AsyncMock(return_value=[])
    authz.check_permission = AsyncMock(return_value=False)
    return authz


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
def repository(mock_session, mock_authz, mock_probe, mock_outbox):
    """Create repository with mock dependencies."""
    return GroupRepository(
        session=mock_session,
        authz=mock_authz,
        outbox=mock_outbox,
        probe=mock_probe,
    )


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_implements_protocol(self, repository):
        """Repository should implement IGroupRepository protocol."""
        assert isinstance(repository, IGroupRepository)


class TestSave:
    """Tests for save method."""

    @pytest.mark.asyncio
    async def test_saves_new_group_to_postgresql(
        self, repository, mock_session, mock_authz
    ):
        """Should add new group model to session."""
        tenant_id = TenantId.generate()
        group = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Engineering",
        )

        # Mock get_by_name to return None (no existing group)
        repository.get_by_name = AsyncMock(return_value=None)

        # Mock session to return None (group doesn't exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(group)

        # Should add new model
        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        assert isinstance(added_model, GroupModel)
        assert added_model.id == group.id.value
        assert added_model.name == group.name

    @pytest.mark.asyncio
    async def test_updates_existing_group(self, repository, mock_session, mock_authz):
        """Should update existing group model."""
        group_id = GroupId.generate()
        tenant_id = TenantId.generate()
        group = Group(
            id=group_id,
            tenant_id=tenant_id,
            name="Engineering Updated",
        )

        # Mock get_by_name to return None (no name conflict)
        repository.get_by_name = AsyncMock(return_value=None)

        # Mock existing group
        existing_model = GroupModel(
            id=group_id.value, tenant_id=tenant_id.value, name="Engineering"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute.return_value = mock_result

        await repository.save(group)

        # Should not add, should update
        mock_session.add.assert_not_called()
        assert existing_model.name == "Engineering Updated"

    @pytest.mark.asyncio
    async def test_appends_events_to_outbox(
        self, repository, mock_session, mock_authz, mock_outbox
    ):
        """Should append collected events to outbox."""
        tenant_id = TenantId.generate()
        # Use factory to generate events
        group = Group.create(name="Engineering", tenant_id=tenant_id)
        group.add_member(UserId.generate(), Role.ADMIN)

        # Mock get_by_name to return None
        repository.get_by_name = AsyncMock(return_value=None)

        # Mock session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(group)

        # Should have appended events to outbox (GroupCreated + MemberAdded)
        assert mock_outbox.append.call_count >= 2

    @pytest.mark.asyncio
    async def test_raises_duplicate_group_name_error(
        self, repository, mock_session, mock_authz
    ):
        """Should raise DuplicateGroupNameError when name exists in tenant."""
        group_id = GroupId.generate()
        different_id = GroupId.generate()
        tenant_id = TenantId.generate()
        group = Group(id=group_id, tenant_id=tenant_id, name="Engineering")

        # Mock get_by_name to return existing group with different ID
        existing_group = Group(id=different_id, tenant_id=tenant_id, name="Engineering")
        repository.get_by_name = AsyncMock(return_value=existing_group)

        with pytest.raises(DuplicateGroupNameError):
            await repository.save(group)


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, repository, mock_session):
        """Should return None when group doesn't exist."""
        group_id = GroupId.generate()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(group_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_group_with_members_hydrated(
        self, repository, mock_session, mock_authz
    ):
        """Should return group with members loaded from SpiceDB."""
        group_id = GroupId.generate()
        tenant_id = TenantId.generate()
        user_id = UserId.generate()

        # Mock PostgreSQL group
        model = GroupModel(
            id=group_id.value, tenant_id=tenant_id.value, name="Engineering"
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        # Mock SpiceDB members - return members only for ADMIN role, empty for others
        async def mock_lookup(resource, relation, subject_type):
            if relation == Role.ADMIN.value:
                return [
                    SubjectRelation(subject_id=user_id.value, relation=Role.ADMIN.value)
                ]
            return []

        mock_authz.lookup_subjects.side_effect = mock_lookup

        result = await repository.get_by_id(group_id)

        assert result is not None
        assert result.id.value == group_id.value
        assert result.tenant_id.value == tenant_id.value
        assert result.name == "Engineering"
        assert len(result.members) == 1
        assert result.members[0].user_id.value == user_id.value
        assert result.members[0].role == Role.ADMIN


class TestGetByName:
    """Tests for get_by_name method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self, repository, mock_session, mock_authz
    ):
        """Should return None when group name doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name("Nonexistent", TenantId.generate())

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_group_by_name(self, repository, mock_session, mock_authz):
        """Should return group when found by name."""
        group_id = GroupId.generate()
        tenant_id = TenantId.generate()
        model = GroupModel(
            id=group_id.value, tenant_id=tenant_id.value, name="Engineering"
        )

        # Mock PostgreSQL query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_name("Engineering", tenant_id)

        assert result is not None
        assert result.name == "Engineering"


class TestDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_not_found(self, repository, mock_session):
        """Should return False when group doesn't exist."""
        tenant_id = TenantId.generate()
        group = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Engineering",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.delete(group)

        assert result is False

    @pytest.mark.asyncio
    async def test_deletes_group_from_postgresql(
        self, repository, mock_session, mock_authz
    ):
        """Should delete group from PostgreSQL."""
        tenant_id = TenantId.generate()
        group = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Engineering",
        )
        # Mark for deletion to record event
        group.mark_for_deletion()

        model = GroupModel(
            id=group.id.value, tenant_id=tenant_id.value, name="Engineering"
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.delete(group)

        assert result is True
        mock_session.delete.assert_called_once_with(model)

    @pytest.mark.asyncio
    async def test_appends_group_deleted_to_outbox(
        self, repository, mock_session, mock_authz, mock_outbox
    ):
        """Should append GroupDeleted event to outbox."""
        tenant_id = TenantId.generate()
        group = Group(
            id=GroupId.generate(),
            tenant_id=tenant_id,
            name="Engineering",
        )
        admin_id = UserId.generate()
        group.add_member(admin_id, Role.ADMIN)
        group.collect_events()  # Clear the add event
        group.mark_for_deletion()

        model = GroupModel(
            id=group.id.value, tenant_id=tenant_id.value, name="Engineering"
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        await repository.delete(group)

        # Should have appended GroupDeleted event (check event_type kwarg)
        calls = mock_outbox.append.call_args_list
        event_types = [call.kwargs.get("event_type") for call in calls]
        assert "GroupDeleted" in event_types


class TestSerializerInjection:
    """Tests for serializer dependency injection."""

    @pytest.mark.asyncio
    async def test_uses_injected_serializer(
        self, mock_session, mock_authz, mock_outbox, mock_probe, mock_serializer
    ):
        """Should use injected serializer instead of creating default."""
        repository = GroupRepository(
            session=mock_session,
            authz=mock_authz,
            outbox=mock_outbox,
            probe=mock_probe,
            serializer=mock_serializer,
        )

        tenant_id = TenantId.generate()
        group = Group.create(name="Test Group", tenant_id=tenant_id)

        # Mock get_by_name to return None
        repository.get_by_name = AsyncMock(return_value=None)

        # Mock session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(group)

        # Injected serializer should have been called
        mock_serializer.serialize.assert_called()

    def test_uses_default_serializer_when_not_injected(
        self, mock_session, mock_authz, mock_outbox, mock_probe
    ):
        """Should create default serializer when not injected."""
        from iam.infrastructure.outbox import IAMEventSerializer

        repository = GroupRepository(
            session=mock_session,
            authz=mock_authz,
            outbox=mock_outbox,
            probe=mock_probe,
        )

        assert isinstance(repository._serializer, IAMEventSerializer)
