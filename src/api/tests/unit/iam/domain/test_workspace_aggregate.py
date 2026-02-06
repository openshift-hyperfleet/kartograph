"""Unit tests for Workspace aggregate (TDD - tests first).

Following TDD: Write tests that describe the desired behavior,
then implement the Workspace aggregate to make these tests pass.
"""

import pytest
from datetime import datetime, UTC

from iam.domain.aggregates import Workspace
from iam.domain.events import WorkspaceCreated, WorkspaceDeleted
from iam.domain.value_objects import TenantId, WorkspaceId


class TestWorkspaceCreation:
    """Tests for Workspace aggregate creation."""

    def test_creates_with_required_fields(self):
        """Test that Workspace can be created with required fields."""
        workspace_id = WorkspaceId.generate()
        tenant_id = TenantId.generate()
        now = datetime.now(UTC)

        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Engineering",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        assert workspace.id == workspace_id
        assert workspace.tenant_id == tenant_id
        assert workspace.name == "Engineering"
        assert workspace.parent_workspace_id is None
        assert workspace.is_root is False
        assert workspace.created_at == now
        assert workspace.updated_at == now

    def test_requires_id(self):
        """Test that Workspace requires an id."""
        now = datetime.now(UTC)
        with pytest.raises(TypeError):
            Workspace(
                tenant_id=TenantId.generate(),
                name="Engineering",
                parent_workspace_id=None,
                is_root=False,
                created_at=now,
                updated_at=now,
            )

    def test_requires_tenant_id(self):
        """Test that Workspace requires a tenant_id."""
        now = datetime.now(UTC)
        with pytest.raises(TypeError):
            Workspace(
                id=WorkspaceId.generate(),
                name="Engineering",
                parent_workspace_id=None,
                is_root=False,
                created_at=now,
                updated_at=now,
            )

    def test_requires_name(self):
        """Test that Workspace requires a name."""
        now = datetime.now(UTC)
        with pytest.raises(TypeError):
            Workspace(
                id=WorkspaceId.generate(),
                tenant_id=TenantId.generate(),
                parent_workspace_id=None,
                is_root=False,
                created_at=now,
                updated_at=now,
            )


class TestWorkspaceFactory:
    """Tests for Workspace.create() factory method."""

    def test_factory_creates_workspace_with_generated_id(self):
        """Factory should generate an ID for the workspace."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        assert workspace.id is not None
        assert workspace.tenant_id == tenant_id
        assert workspace.name == "Engineering"
        assert workspace.parent_workspace_id == parent_id
        assert workspace.is_root is False

    def test_factory_sets_timestamps(self):
        """Factory should set created_at and updated_at to now."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        before = datetime.now(UTC)
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )
        after = datetime.now(UTC)

        assert before <= workspace.created_at <= after
        assert before <= workspace.updated_at <= after
        assert workspace.created_at.tzinfo == UTC
        assert workspace.updated_at.tzinfo == UTC

    def test_factory_records_workspace_created_event(self):
        """Factory should record a WorkspaceCreated event."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceCreated)
        assert events[0].workspace_id == workspace.id.value
        assert events[0].tenant_id == tenant_id.value
        assert events[0].name == "Engineering"
        assert events[0].parent_workspace_id == parent_id.value
        assert events[0].is_root is False

    def test_factory_creates_workspace_with_parent(self):
        """Factory should create workspace with parent when specified."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        workspace = Workspace.create(
            name="Team A",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        assert workspace.parent_workspace_id == parent_id
        assert workspace.is_root is False

        events = workspace.collect_events()
        assert events[0].parent_workspace_id == parent_id.value


class TestRootWorkspaceFactory:
    """Tests for Workspace.create_root() factory method."""

    def test_create_root_creates_root_workspace(self):
        """create_root should create a root workspace."""
        tenant_id = TenantId.generate()

        workspace = Workspace.create_root(
            name="Root Workspace",
            tenant_id=tenant_id,
        )

        assert workspace.is_root is True
        assert workspace.parent_workspace_id is None
        assert workspace.name == "Root Workspace"
        assert workspace.tenant_id == tenant_id

    def test_create_root_records_event_with_is_root_true(self):
        """create_root should record event with is_root=True."""
        tenant_id = TenantId.generate()

        workspace = Workspace.create_root(
            name="Root",
            tenant_id=tenant_id,
        )
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceCreated)
        assert events[0].is_root is True


class TestBusinessRules:
    """Tests for Workspace business rules."""

    def test_name_must_be_between_1_and_512_characters(self):
        """Workspace name must be 1-512 characters."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()

        # Empty name should fail
        with pytest.raises(ValueError, match="1.*512"):
            Workspace.create(
                name="", tenant_id=tenant_id, parent_workspace_id=parent_id
            )

        # 513 character name should fail
        with pytest.raises(ValueError, match="1.*512"):
            Workspace.create(
                name="a" * 513, tenant_id=tenant_id, parent_workspace_id=parent_id
            )

        # Valid names should work
        workspace_short = Workspace.create(
            name="a", tenant_id=tenant_id, parent_workspace_id=parent_id
        )
        assert workspace_short.name == "a"

        workspace_max = Workspace.create(
            name="a" * 512, tenant_id=tenant_id, parent_workspace_id=parent_id
        )
        assert len(workspace_max.name) == 512

    def test_cannot_have_is_root_true_with_parent_workspace_id(self):
        """Cannot have both is_root=True and parent_workspace_id set."""
        workspace_id = WorkspaceId.generate()
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        now = datetime.now(UTC)

        with pytest.raises(ValueError, match="root.*parent"):
            Workspace(
                id=workspace_id,
                tenant_id=tenant_id,
                name="Invalid",
                parent_workspace_id=parent_id,
                is_root=True,
                created_at=now,
                updated_at=now,
            )

    def test_root_workspace_must_have_no_parent(self):
        """Root workspace must have parent_workspace_id=None."""
        workspace_id = WorkspaceId.generate()
        tenant_id = TenantId.generate()
        now = datetime.now(UTC)

        # This should be valid
        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Root",
            parent_workspace_id=None,
            is_root=True,
            created_at=now,
            updated_at=now,
        )

        assert workspace.is_root is True
        assert workspace.parent_workspace_id is None

    def test_non_root_workspace_can_have_parent(self):
        """Non-root workspace can have a parent."""
        workspace_id = WorkspaceId.generate()
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        now = datetime.now(UTC)

        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Child",
            parent_workspace_id=parent_id,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        assert workspace.is_root is False
        assert workspace.parent_workspace_id == parent_id


class TestMarkForDeletion:
    """Tests for Workspace.mark_for_deletion() method."""

    def test_records_workspace_deleted_event(self):
        """mark_for_deletion records a WorkspaceDeleted event."""
        tenant_id = TenantId.generate()
        workspace_id = WorkspaceId.generate()
        now = datetime.now(UTC)

        workspace = Workspace(
            id=workspace_id,
            tenant_id=tenant_id,
            name="Engineering",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        assert len(events) == 1
        assert isinstance(events[0], WorkspaceDeleted)
        assert events[0].workspace_id == workspace_id.value
        assert events[0].tenant_id == tenant_id.value

    def test_workspace_deleted_event_has_utc_timestamp(self):
        """WorkspaceDeleted event should have UTC timestamp."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )
        workspace.collect_events()  # Clear creation event

        workspace.mark_for_deletion()
        events = workspace.collect_events()

        assert events[0].occurred_at.tzinfo == UTC


class TestEventCollection:
    """Tests for Workspace event collection mechanism."""

    def test_collect_events_returns_empty_list_initially(self):
        """A directly constructed workspace has no pending events."""
        now = datetime.now(UTC)
        workspace = Workspace(
            id=WorkspaceId.generate(),
            tenant_id=TenantId.generate(),
            name="Engineering",
            parent_workspace_id=None,
            is_root=False,
            created_at=now,
            updated_at=now,
        )

        events = workspace.collect_events()

        assert events == []

    def test_collect_events_clears_pending_events(self):
        """collect_events clears the pending events list."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        events1 = workspace.collect_events()
        events2 = workspace.collect_events()

        assert len(events1) == 1
        assert len(events2) == 0

    def test_multiple_operations_record_multiple_events(self):
        """Multiple operations record multiple events."""
        tenant_id = TenantId.generate()
        parent_id = WorkspaceId.generate()
        workspace = Workspace.create(
            name="Engineering",
            tenant_id=tenant_id,
            parent_workspace_id=parent_id,
        )

        # Don't collect yet - add deletion
        workspace.mark_for_deletion()

        events = workspace.collect_events()

        assert len(events) == 2
        assert isinstance(events[0], WorkspaceCreated)
        assert isinstance(events[1], WorkspaceDeleted)
