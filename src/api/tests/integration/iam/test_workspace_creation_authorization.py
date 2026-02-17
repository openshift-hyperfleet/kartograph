"""Integration tests for workspace creation authorization model.

Tests the create_child permission model that allows any tenant member to
create workspaces under root while restricting child workspace creation
to workspace admins/editors.

Requirements:
    - PostgreSQL with migrations applied
    - SpiceDB running and accessible
"""

import pytest
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import Workspace
from iam.domain.value_objects import (
    TenantId,
    UserId,
)
from iam.infrastructure.workspace_repository import WorkspaceRepository
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)

pytestmark = pytest.mark.integration


class TestRootWorkspaceCreatorTenantRelation:
    """Tests for creator_tenant relation on root workspaces."""

    @pytest.mark.asyncio
    async def test_root_workspace_has_creator_tenant_relation(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant: TenantId,
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """Root workspace creation should write workspace#creator_tenant@tenant relation.

        This relation enables the create_child permission for all tenant members.
        """
        outbox_repo = OutboxRepository(async_session)
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Create root workspace
        workspace = Workspace.create_root(
            name="Test Root",
            tenant_id=test_tenant,
        )

        async with async_session.begin():
            await workspace_repo.save(workspace)

        # Process outbox to sync relationships to SpiceDB
        await process_outbox()

        # Verify creator_tenant relation exists in SpiceDB
        tuples = await spicedb_client.read_relationships(
            resource_type=ResourceType.WORKSPACE.value,
            resource_id=workspace.id.value,
        )

        creator_tenant_tuples = [t for t in tuples if t.relation == "creator_tenant"]
        assert len(creator_tenant_tuples) == 1
        assert creator_tenant_tuples[0].subject == f"tenant:{test_tenant.value}"

    @pytest.mark.asyncio
    async def test_child_workspace_has_no_creator_tenant_relation(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant: TenantId,
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """Child workspace creation should NOT write workspace#creator_tenant@tenant.

        Only root workspaces get the creator_tenant relation, ensuring
        child workspace creation is restricted to admins/editors.
        """
        outbox_repo = OutboxRepository(async_session)
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # First create root workspace
        root = Workspace.create_root(
            name="Root for Child Test",
            tenant_id=test_tenant,
        )
        async with async_session.begin():
            await workspace_repo.save(root)
        await process_outbox()

        # Create child workspace
        child = Workspace.create(
            name="Child Workspace",
            tenant_id=test_tenant,
            parent_workspace_id=root.id,
        )
        async with async_session.begin():
            await workspace_repo.save(child)
        await process_outbox()

        # Verify NO creator_tenant relation on child workspace
        tuples = await spicedb_client.read_relationships(
            resource_type=ResourceType.WORKSPACE.value,
            resource_id=child.id.value,
        )

        creator_tenant_tuples = [t for t in tuples if t.relation == "creator_tenant"]
        assert len(creator_tenant_tuples) == 0


class TestCreateChildPermission:
    """Tests for the create_child permission model."""

    @pytest.mark.asyncio
    async def test_tenant_member_can_create_workspace_under_root(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant: TenantId,
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """Any tenant member should have create_child permission on root workspace.

        The create_child permission includes creator_tenant->view, which resolves
        to all tenant members (since tenant view = admin + member).
        """
        outbox_repo = OutboxRepository(async_session)
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Create root workspace
        root = Workspace.create_root(
            name="Root for Permission Test",
            tenant_id=test_tenant,
        )
        async with async_session.begin():
            await workspace_repo.save(root)
        await process_outbox()

        # Create a regular tenant member (not workspace admin)
        member_id = UserId.generate()
        member_subject = format_subject(ResourceType.USER, member_id.value)

        # Write tenant membership to SpiceDB
        tenant_resource = format_resource(ResourceType.TENANT, test_tenant.value)
        await spicedb_client.write_relationship(
            resource=tenant_resource,
            relation="member",
            subject=member_subject,
        )

        # Check that tenant member has create_child on root workspace
        root_resource = format_resource(ResourceType.WORKSPACE, root.id.value)
        has_create_child = await spicedb_client.check_permission(
            resource=root_resource,
            permission=Permission.CREATE_CHILD.value,
            subject=member_subject,
        )
        assert has_create_child is True

    @pytest.mark.asyncio
    async def test_tenant_member_cannot_create_under_child_workspace(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant: TenantId,
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """A tenant member (not workspace admin/editor) should NOT have
        create_child permission on a child workspace.

        Child workspaces don't have creator_tenant set, so only their
        admins/editors can create sub-children.
        """
        outbox_repo = OutboxRepository(async_session)
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Create workspace hierarchy
        root = Workspace.create_root(
            name="Root for Child Perm Test",
            tenant_id=test_tenant,
        )
        async with async_session.begin():
            await workspace_repo.save(root)
        await process_outbox()

        child = Workspace.create(
            name="Child for Perm Test",
            tenant_id=test_tenant,
            parent_workspace_id=root.id,
        )
        async with async_session.begin():
            await workspace_repo.save(child)
        await process_outbox()

        # Create a regular tenant member
        member_id = UserId.generate()
        member_subject = format_subject(ResourceType.USER, member_id.value)

        tenant_resource = format_resource(ResourceType.TENANT, test_tenant.value)
        await spicedb_client.write_relationship(
            resource=tenant_resource,
            relation="member",
            subject=member_subject,
        )

        # Check that tenant member does NOT have create_child on child workspace
        child_resource = format_resource(ResourceType.WORKSPACE, child.id.value)
        has_create_child = await spicedb_client.check_permission(
            resource=child_resource,
            permission=Permission.CREATE_CHILD.value,
            subject=member_subject,
        )
        assert has_create_child is False

    @pytest.mark.asyncio
    async def test_workspace_admin_can_create_under_their_workspace(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant: TenantId,
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """A workspace admin should have create_child permission on their workspace.

        Even on child workspaces (without creator_tenant), admins and editors
        can create sub-children via the admin + editor terms in create_child.
        """
        outbox_repo = OutboxRepository(async_session)
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Create workspace hierarchy
        root = Workspace.create_root(
            name="Root for Admin Perm Test",
            tenant_id=test_tenant,
        )
        async with async_session.begin():
            await workspace_repo.save(root)
        await process_outbox()

        child = Workspace.create(
            name="Child for Admin Perm Test",
            tenant_id=test_tenant,
            parent_workspace_id=root.id,
        )
        async with async_session.begin():
            await workspace_repo.save(child)
        await process_outbox()

        # Grant a user admin on the child workspace
        admin_id = UserId.generate()
        admin_subject = format_subject(ResourceType.USER, admin_id.value)

        child_resource = format_resource(ResourceType.WORKSPACE, child.id.value)
        await spicedb_client.write_relationship(
            resource=child_resource,
            relation="admin",
            subject=admin_subject,
        )

        # Check that workspace admin has create_child
        has_create_child = await spicedb_client.check_permission(
            resource=child_resource,
            permission=Permission.CREATE_CHILD.value,
            subject=admin_subject,
        )
        assert has_create_child is True

    @pytest.mark.asyncio
    async def test_workspace_editor_can_create_under_their_workspace(
        self,
        async_session: AsyncSession,
        spicedb_client: AuthorizationProvider,
        test_tenant: TenantId,
        process_outbox: Callable[[], Coroutine[Any, Any, None]],
    ):
        """A workspace editor should have create_child permission on their workspace."""
        outbox_repo = OutboxRepository(async_session)
        workspace_repo = WorkspaceRepository(
            session=async_session,
            authz=spicedb_client,
            outbox=outbox_repo,
        )

        # Create workspace hierarchy
        root = Workspace.create_root(
            name="Root for Editor Perm Test",
            tenant_id=test_tenant,
        )
        async with async_session.begin():
            await workspace_repo.save(root)
        await process_outbox()

        child = Workspace.create(
            name="Child for Editor Perm Test",
            tenant_id=test_tenant,
            parent_workspace_id=root.id,
        )
        async with async_session.begin():
            await workspace_repo.save(child)
        await process_outbox()

        # Grant a user editor on the child workspace
        editor_id = UserId.generate()
        editor_subject = format_subject(ResourceType.USER, editor_id.value)

        child_resource = format_resource(ResourceType.WORKSPACE, child.id.value)
        await spicedb_client.write_relationship(
            resource=child_resource,
            relation="editor",
            subject=editor_subject,
        )

        # Check that workspace editor has create_child
        has_create_child = await spicedb_client.check_permission(
            resource=child_resource,
            permission=Permission.CREATE_CHILD.value,
            subject=editor_subject,
        )
        assert has_create_child is True
