"""Integration tests for GroupRepository.

These tests require PostgreSQL and SpiceDB to be running.
They verify the complete flow of persisting and retrieving groups
with membership data coordinated across both systems.
"""

import pytest

from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupId, Role, TenantId, UserId
from iam.infrastructure.group_repository import GroupRepository
from iam.ports.exceptions import DuplicateGroupNameError

pytestmark = pytest.mark.integration


class TestGroupRoundTrip:
    """Tests for save and retrieve operations."""

    @pytest.mark.asyncio
    async def test_saves_and_retrieves_group(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should save group to PostgreSQL and retrieve it."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        tenant_id = TenantId.generate()

        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Retrieve the group
        retrieved = await group_repository.get_by_id(group.id)

        assert retrieved is not None
        assert retrieved.id.value == group.id.value
        assert retrieved.name == group.name

    @pytest.mark.asyncio
    async def test_saves_and_retrieves_group_with_members(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should save group with members to PostgreSQL and SpiceDB, then retrieve."""
        group = Group(
            id=GroupId.generate(),
            name="Engineering",
        )
        user_id = UserId.generate()
        group.add_member(user_id, Role.ADMIN)
        tenant_id = TenantId.generate()

        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Retrieve the group
        retrieved = await group_repository.get_by_id(group.id)

        assert retrieved is not None
        assert len(retrieved.members) == 1
        assert retrieved.members[0].user_id.value == user_id.value
        assert retrieved.members[0].role == Role.ADMIN


class TestGroupUpdates:
    """Tests for updating existing groups."""

    @pytest.mark.asyncio
    async def test_updates_group_name(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should update group name in PostgreSQL."""
        group = Group(id=GroupId.generate(), name="Engineering")
        tenant_id = TenantId.generate()

        # Save initial group
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Update name
        group.name = "Engineering Team"
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Verify update
        retrieved = await group_repository.get_by_id(group.id)
        assert retrieved is not None
        assert retrieved.name == "Engineering Team"

    @pytest.mark.asyncio
    async def test_adds_member_to_existing_group(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should add member and sync to SpiceDB."""
        group = Group(id=GroupId.generate(), name="Engineering")
        admin_id = UserId.generate()
        group.add_member(admin_id, Role.ADMIN)
        tenant_id = TenantId.generate()

        # Save initial group
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Add another member
        member_id = UserId.generate()
        group.add_member(member_id, Role.MEMBER)
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Verify member added
        retrieved = await group_repository.get_by_id(group.id)
        assert retrieved is not None
        assert len(retrieved.members) == 2

    @pytest.mark.asyncio
    async def test_removes_member_from_group(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should remove member and delete from SpiceDB."""
        group = Group(id=GroupId.generate(), name="Engineering")
        admin1 = UserId.generate()
        admin2 = UserId.generate()
        group.add_member(admin1, Role.ADMIN)
        group.add_member(admin2, Role.ADMIN)
        tenant_id = TenantId.generate()

        # Save initial group
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Remove one admin
        group.remove_member(admin2)
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Verify member removed
        retrieved = await group_repository.get_by_id(group.id)
        assert retrieved is not None
        assert len(retrieved.members) == 1
        assert retrieved.members[0].user_id.value == admin1.value

    @pytest.mark.asyncio
    async def test_updates_member_role(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should update member role in SpiceDB."""
        group = Group(id=GroupId.generate(), name="Engineering")
        admin_id = UserId.generate()
        member_id = UserId.generate()
        group.add_member(admin_id, Role.ADMIN)
        group.add_member(member_id, Role.MEMBER)
        tenant_id = TenantId.generate()

        # Save initial group
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Promote member to admin
        group.update_member_role(member_id, Role.ADMIN)
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Verify role updated
        retrieved = await group_repository.get_by_id(group.id)
        assert retrieved is not None
        assert len(retrieved.members) == 2
        member = next(
            m for m in retrieved.members if m.user_id.value == member_id.value
        )
        assert member.role == Role.ADMIN


class TestGroupDeletion:
    """Tests for deleting groups."""

    @pytest.mark.asyncio
    async def test_deletes_group_and_members(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should delete group from PostgreSQL and members from SpiceDB."""
        group = Group(id=GroupId.generate(), name="Engineering")
        user_id = UserId.generate()
        group.add_member(user_id, Role.ADMIN)
        tenant_id = TenantId.generate()

        # Save group
        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Verify it exists
        retrieved = await group_repository.get_by_id(group.id)
        assert retrieved is not None
        await async_session.commit()  # Commit the autobegin transaction

        # Delete group
        async with async_session.begin():
            result = await group_repository.delete(group.id, tenant_id)

        assert result is True

        # Verify it's gone
        deleted = await group_repository.get_by_id(group.id)
        assert deleted is None


class TestGroupUniqueness:
    """Tests for group name uniqueness constraints."""

    @pytest.mark.asyncio
    async def test_duplicate_name_in_same_tenant_raises_error(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should raise DuplicateGroupNameError for same name in tenant."""
        tenant_id = TenantId.generate()
        group1 = Group(id=GroupId.generate(), name="Engineering")

        # Save first group
        async with async_session.begin():
            await group_repository.save(group1, tenant_id)

        # Try to save another group with same name in same tenant
        group2 = Group(id=GroupId.generate(), name="Engineering")

        with pytest.raises(DuplicateGroupNameError):
            async with async_session.begin():
                await group_repository.save(group2, tenant_id)

    @pytest.mark.asyncio
    async def test_same_name_in_different_tenants_allowed(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should allow same group name in different tenants."""
        tenant1 = TenantId.generate()
        tenant2 = TenantId.generate()

        group1 = Group(id=GroupId.generate(), name="Engineering")
        group2 = Group(id=GroupId.generate(), name="Engineering")

        # Save to different tenants - should succeed
        async with async_session.begin():
            await group_repository.save(group1, tenant1)
            await group_repository.save(group2, tenant2)

        # Both should exist
        assert await group_repository.get_by_id(group1.id) is not None
        assert await group_repository.get_by_id(group2.id) is not None


class TestGetByName:
    """Tests for retrieving groups by name."""

    @pytest.mark.asyncio
    async def test_retrieves_group_by_name(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should retrieve group by name within tenant."""
        group = Group(id=GroupId.generate(), name="Engineering")
        tenant_id = TenantId.generate()

        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        # Retrieve by name
        retrieved = await group_repository.get_by_name("Engineering", tenant_id)

        assert retrieved is not None
        assert retrieved.id.value == group.id.value
        assert retrieved.name == "Engineering"


class TestListByTenant:
    """Tests for listing groups by tenant."""

    @pytest.mark.asyncio
    async def test_lists_only_groups_in_tenant(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should list only groups belonging to specified tenant."""
        tenant1 = TenantId.generate()
        tenant2 = TenantId.generate()

        # Create groups in different tenants
        group1 = Group(id=GroupId.generate(), name="Engineering-T1")
        group2 = Group(id=GroupId.generate(), name="Design-T1")
        group3 = Group(id=GroupId.generate(), name="Engineering-T2")

        async with async_session.begin():
            await group_repository.save(group1, tenant1)
            await group_repository.save(group2, tenant1)
            await group_repository.save(group3, tenant2)

        # List groups in tenant1
        tenant1_groups = await group_repository.list_by_tenant(tenant1)

        assert len(tenant1_groups) == 2
        group_ids = {g.id.value for g in tenant1_groups}
        assert group1.id.value in group_ids
        assert group2.id.value in group_ids
        assert group3.id.value not in group_ids

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_tenant_with_no_groups(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should return empty list when tenant has no groups."""
        empty_tenant = TenantId.generate()

        groups = await group_repository.list_by_tenant(empty_tenant)

        assert groups == []

    @pytest.mark.asyncio
    async def test_hydrates_members_for_listed_groups(
        self, group_repository: GroupRepository, async_session, clean_iam_data
    ):
        """Should hydrate members for all groups in list."""
        tenant_id = TenantId.generate()
        group = Group(id=GroupId.generate(), name="Engineering")
        user_id = UserId.generate()
        group.add_member(user_id, Role.ADMIN)

        async with async_session.begin():
            await group_repository.save(group, tenant_id)

        groups = await group_repository.list_by_tenant(tenant_id)

        assert len(groups) == 1
        assert len(groups[0].members) == 1
        assert groups[0].members[0].user_id.value == user_id.value
