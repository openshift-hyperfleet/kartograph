"""Workspace application service for IAM bounded context.

Orchestrates workspace creation with proper validation and authorization setup.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import (
    DefaultWorkspaceServiceProbe,
    WorkspaceServiceProbe,
)
from iam.application.value_objects import WorkspaceAccessGrant
from iam.domain.aggregates import Workspace
from iam.domain.value_objects import (
    MemberType,
    TenantId,
    UserId,
    WorkspaceId,
    WorkspaceRole,
)
from infrastructure.settings import get_iam_settings
from iam.ports.exceptions import (
    CannotDeleteRootWorkspaceError,
    DuplicateWorkspaceNameError,
    UnauthorizedError,
    WorkspaceHasChildrenError,
)
from iam.ports.repositories import IWorkspaceRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)


class WorkspaceService:
    """Application service for workspace management.

    Orchestrates workspace operations with proper tenant scoping
    and business rule enforcement.
    """

    def __init__(
        self,
        session: AsyncSession,
        workspace_repository: IWorkspaceRepository,
        authz: AuthorizationProvider,
        scope_to_tenant: TenantId,
        probe: WorkspaceServiceProbe | None = None,
    ):
        """Initialize WorkspaceService with dependencies.

        Args:
            session: Database session for transaction management
            workspace_repository: Repository for workspace persistence
            authz: Authorization provider for permission checks
            scope_to_tenant: Tenant ID to which this service is scoped
            probe: Optional domain probe for observability
        """
        self._session = session
        self._workspace_repository = workspace_repository
        self._authz = authz
        self._scope_to_tenant = scope_to_tenant
        self._probe = probe or DefaultWorkspaceServiceProbe()

    async def _check_workspace_permission(
        self,
        user_id: UserId,
        workspace_id: WorkspaceId,
        permission: Permission,
    ) -> bool:
        """Check if user has permission on workspace.

        Args:
            user_id: The user to check
            workspace_id: The workspace resource
            permission: The permission to check (VIEW, EDIT, MANAGE)

        Returns:
            True if user has permission, False otherwise
        """
        resource = format_resource(ResourceType.WORKSPACE, workspace_id.value)
        subject = format_subject(ResourceType.USER, user_id.value)

        return await self._authz.check_permission(
            resource=resource,
            permission=permission.value,
            subject=subject,
        )

    async def create_workspace(
        self,
        name: str,
        parent_workspace_id: WorkspaceId,
        creator_id: UserId,
    ) -> Workspace:
        """Create a child workspace.

        Business rules:
        - User must have MANAGE permission on parent workspace
        - Name must be unique within tenant
        - Parent workspace must exist and belong to tenant
        - Service is scoped to tenant boundary

        Args:
            name: Workspace name (1-512 characters)
            parent_workspace_id: Parent workspace ID (must exist in scoped tenant)
            creator_id: User creating the workspace (for permission check and event attribution)

        Returns:
            The created Workspace aggregate

        Raises:
            PermissionError: If user lacks MANAGE permission on parent
            DuplicateWorkspaceNameError: If workspace name already exists in tenant
            ValueError: If parent workspace doesn't exist or belongs to different tenant
            Exception: If workspace creation fails
        """
        # Check user has MANAGE permission on parent (before transaction)
        has_manage = await self._check_workspace_permission(
            user_id=creator_id,
            workspace_id=parent_workspace_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {creator_id.value} lacks manage permission on parent workspace "
                f"{parent_workspace_id.value}"
            )

        try:
            async with self._session.begin():
                # Check name uniqueness within tenant
                existing = await self._workspace_repository.get_by_name(
                    tenant_id=self._scope_to_tenant,
                    name=name,
                )
                if existing:
                    raise DuplicateWorkspaceNameError(
                        f"Workspace '{name}' already exists in tenant"
                    )

                # Validate parent workspace exists
                parent = await self._workspace_repository.get_by_id(parent_workspace_id)
                if not parent:
                    raise ValueError(
                        f"Parent workspace {parent_workspace_id.value} does not exist - "
                        f"the parent workspace must exist before creating a child"
                    )

                # Validate parent belongs to the scoped tenant
                if parent.tenant_id != self._scope_to_tenant:
                    raise ValueError(
                        "Parent workspace belongs to different tenant - "
                        "cannot create child workspace across tenant boundaries"
                    )

                # Create workspace using domain factory method
                workspace = Workspace.create(
                    name=name,
                    tenant_id=self._scope_to_tenant,
                    parent_workspace_id=parent_workspace_id,
                )

                # Persist workspace
                await self._workspace_repository.save(workspace)

            # Probe success (outside transaction - it's committed)
            self._probe.workspace_created(
                workspace_id=workspace.id.value,
                tenant_id=self._scope_to_tenant.value,
                name=name,
                parent_workspace_id=parent_workspace_id.value,
                is_root=False,
                creator_id=creator_id.value,
            )

            return workspace

        except IntegrityError as e:
            # DB unique constraint violation (race condition)
            if "uq_workspaces_tenant_name" in str(e) or (
                "tenant_id" in str(e) and "name" in str(e)
            ):
                self._probe.workspace_creation_failed(
                    tenant_id=self._scope_to_tenant.value,
                    name=name,
                    error=f"Workspace name '{name}' already exists in tenant",
                )
                raise DuplicateWorkspaceNameError(
                    f"Workspace '{name}' already exists in tenant"
                ) from e
            raise  # Re-raise if different constraint
        except DuplicateWorkspaceNameError:
            self._probe.workspace_creation_failed(
                tenant_id=self._scope_to_tenant.value,
                name=name,
                error=f"Workspace '{name}' already exists in tenant",
            )
            raise
        except ValueError:
            raise
        except PermissionError:
            raise
        except Exception as e:
            self._probe.workspace_creation_failed(
                tenant_id=self._scope_to_tenant.value,
                name=name,
                error=str(e),
            )
            raise

    async def create_root_workspace(
        self,
        name: str | None = None,
    ) -> Workspace:
        """Create root workspace for the scoped tenant.

        Uses service's scope_to_tenant for the tenant ID.

        Name priority:
        1. Provided name parameter
        2. default_workspace_name from IAMSettings
        3. "Root" (hardcoded fallback)

        Called by TenantService during tenant creation. TenantService
        instantiates a WorkspaceService scoped to the new tenant and
        passes the tenant name explicitly when no settings default exists:

        ```python
        # In TenantService.create_tenant():
        workspace_service = WorkspaceService(
            session=self._session,
            workspace_repository=workspace_repo,
            authz=self._authz,
            scope_to_tenant=new_tenant.id,
        )
        await workspace_service.create_root_workspace(name=tenant.name)
        ```

        Args:
            name: Optional workspace name. If None, uses settings or "Root" fallback.

        Returns:
            The created root Workspace aggregate

        Raises:
            Exception: If workspace creation fails
        """
        # Determine workspace name with priority:
        # 1. Explicit name parameter
        # 2. Settings default_workspace_name
        # 3. "Root" fallback
        workspace_name = name
        if workspace_name is None:
            settings = get_iam_settings()
            workspace_name = settings.default_workspace_name

        if workspace_name is None:
            workspace_name = "Root"

        try:
            # Create root workspace using domain factory method
            workspace = Workspace.create_root(
                name=workspace_name,
                tenant_id=self._scope_to_tenant,
            )

            # Persist in transaction with IntegrityError handling
            try:
                async with self._session.begin():
                    await self._workspace_repository.save(workspace)
            except IntegrityError as e:
                # DB unique constraint violation (race condition)
                if "uq_workspaces_tenant_name" in str(e) or (
                    "tenant_id" in str(e) and "name" in str(e)
                ):
                    self._probe.workspace_creation_failed(
                        tenant_id=self._scope_to_tenant.value,
                        name=workspace_name,
                        error=f"Workspace name '{workspace_name}' already exists in tenant",
                    )
                    raise DuplicateWorkspaceNameError(
                        f"Workspace '{workspace_name}' already exists in tenant"
                    ) from e
                raise  # Re-raise if different constraint

            # Probe success
            self._probe.workspace_created(
                workspace_id=workspace.id.value,
                tenant_id=self._scope_to_tenant.value,
                name=workspace_name,
                parent_workspace_id=None,
                is_root=True,
                creator_id="",  # Root workspace has no creator
            )

            return workspace

        except (DuplicateWorkspaceNameError, IntegrityError):
            raise
        except Exception as e:
            self._probe.workspace_creation_failed(
                tenant_id=self._scope_to_tenant.value,
                name=workspace_name,
                error=str(e),
            )
            raise

    async def get_workspace(
        self,
        workspace_id: WorkspaceId,
        user_id: UserId,
    ) -> Workspace | None:
        """Get workspace by ID with tenant scoping and VIEW permission check.

        Returns None if workspace doesn't exist, belongs to different tenant,
        or user lacks VIEW permission.

        Args:
            workspace_id: The workspace ID to retrieve
            user_id: The user requesting access (for permission check)

        Returns:
            The Workspace aggregate, or None if not found or not accessible
        """
        # Fetch workspace from repository
        workspace = await self._workspace_repository.get_by_id(workspace_id)
        if workspace is None:
            self._probe.workspace_not_found(workspace_id=workspace_id.value)
            return None

        # Verify workspace belongs to scoped tenant
        if workspace.tenant_id != self._scope_to_tenant:
            # Don't leak existence of workspaces in other tenants
            return None

        # Check user has VIEW permission
        has_view = await self._check_workspace_permission(
            user_id=user_id,
            workspace_id=workspace_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            # User lacks VIEW permission - act as if not found
            self._probe.workspace_access_denied(
                workspace_id=workspace_id.value,
                user_id=user_id.value,
                permission="view",
            )
            return None

        # Probe success
        self._probe.workspace_retrieved(
            workspace_id=workspace.id.value,
            tenant_id=workspace.tenant_id.value,
            name=workspace.name,
        )

        return workspace

    async def list_workspaces(
        self,
        user_id: UserId,
    ) -> list[Workspace]:
        """List workspaces the user has VIEW permission on.

        Filters workspaces in scoped tenant to only those where user has
        VIEW permission via SpiceDB lookup_resources.

        Args:
            user_id: The user requesting the list (for permission filtering)

        Returns:
            List of Workspace aggregates user can view
        """
        # Get all workspaces in tenant from database
        all_workspaces = await self._workspace_repository.list_by_tenant(
            tenant_id=self._scope_to_tenant
        )

        # Use SpiceDB lookup_resources to filter by VIEW permission
        subject = format_subject(ResourceType.USER, user_id.value)

        accessible_ids = await self._authz.lookup_resources(
            resource_type=ResourceType.WORKSPACE,
            permission=Permission.VIEW,
            subject=subject,
        )

        # Convert to set for O(1) lookup
        accessible_set = set(accessible_ids)

        # Filter workspaces to only accessible ones
        accessible_workspaces = [
            w for w in all_workspaces if w.id.value in accessible_set
        ]

        # Probe success
        self._probe.workspaces_listed(
            tenant_id=self._scope_to_tenant.value,
            count=len(accessible_workspaces),
            user_id=user_id.value,
        )

        return accessible_workspaces

    async def delete_workspace(
        self,
        workspace_id: WorkspaceId,
        user_id: UserId,
    ) -> bool:
        """Delete a workspace.

        Business rules:
        - User must have MANAGE permission on workspace
        - Cannot delete root workspace
        - Cannot delete workspace with children
        - Workspace must belong to scoped tenant

        Args:
            workspace_id: The workspace ID to delete
            user_id: The user attempting deletion (for permission check)

        Returns:
            True if deleted, False if not found

        Raises:
            PermissionError: If user lacks MANAGE permission
            CannotDeleteRootWorkspaceError: If attempting to delete root workspace
            WorkspaceHasChildrenError: If workspace has children
            UnauthorizedError: If workspace belongs to different tenant
        """
        # Check user has MANAGE permission (before transaction)
        has_manage = await self._check_workspace_permission(
            user_id=user_id,
            workspace_id=workspace_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {user_id.value} lacks manage permission on workspace "
                f"{workspace_id.value}"
            )

        async with self._session.begin():
            # Load workspace from repository
            workspace = await self._workspace_repository.get_by_id(workspace_id)
            if workspace is None:
                return False

            # Check tenant ownership
            if workspace.tenant_id != self._scope_to_tenant:
                raise UnauthorizedError(
                    f"Workspace {workspace_id.value} belongs to different tenant"
                )

            # Check if root workspace
            if workspace.is_root:
                self._probe.workspace_deletion_failed(
                    workspace_id=workspace_id.value,
                    error="Root workspace cannot be deleted",
                )
                raise CannotDeleteRootWorkspaceError("Root workspace cannot be deleted")

            # Mark for deletion (records WorkspaceDeleted event with snapshot)
            workspace.mark_for_deletion()

            # Attempt to delete; catch IntegrityError from DB RESTRICT constraint
            try:
                result = await self._workspace_repository.delete(workspace)
            except IntegrityError as e:
                if "parent_workspace_id" in str(e):
                    self._probe.workspace_deletion_failed(
                        workspace_id=workspace_id.value,
                        error="Cannot delete workspace with children",
                    )
                    raise WorkspaceHasChildrenError(
                        "Cannot delete workspace with children"
                    ) from e
                raise

            if result:
                self._probe.workspace_deleted(
                    workspace_id=workspace_id.value,
                    tenant_id=workspace.tenant_id.value,
                )

            return result

    async def add_member(
        self,
        workspace_id: WorkspaceId,
        acting_user_id: UserId,
        member_id: str,
        member_type: MemberType,
        role: WorkspaceRole,
    ) -> Workspace:
        """Add a member to a workspace.

        Args:
            workspace_id: The workspace to add member to
            acting_user_id: User performing the action (must have MANAGE permission)
            member_id: ID of user or group to add
            member_type: Whether adding a USER or GROUP
            role: The role to assign (ADMIN, EDITOR, MEMBER)

        Returns:
            Updated Workspace aggregate

        Raises:
            PermissionError: If acting user lacks MANAGE permission
            ValueError: If member already exists or workspace not found
            UnauthorizedError: If workspace belongs to different tenant
        """
        # Check acting user has MANAGE permission
        has_manage = await self._check_workspace_permission(
            user_id=acting_user_id,
            workspace_id=workspace_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {acting_user_id.value} lacks manage permission on workspace "
                f"{workspace_id.value}"
            )

        async with self._session.begin():
            # Load workspace
            workspace = await self._workspace_repository.get_by_id(workspace_id)
            if workspace is None:
                raise ValueError(f"Workspace {workspace_id.value} not found")

            # Verify tenant ownership
            if workspace.tenant_id != self._scope_to_tenant:
                raise UnauthorizedError("Workspace belongs to different tenant")

            # Add member (aggregate handles validation and events)
            workspace.add_member(member_id, member_type, role)

            # Save (persists events to outbox)
            await self._workspace_repository.save(workspace)

        # Emit probe
        self._probe.workspace_member_added(
            workspace_id=workspace_id.value,
            member_id=member_id,
            member_type=member_type.value,
            role=role.value,
            acting_user_id=acting_user_id.value,
        )

        return workspace

    async def remove_member(
        self,
        workspace_id: WorkspaceId,
        acting_user_id: UserId,
        member_id: str,
        member_type: MemberType,
    ) -> Workspace:
        """Remove a member from a workspace.

        Args:
            workspace_id: The workspace to remove member from
            acting_user_id: User performing the action (must have MANAGE permission)
            member_id: ID of user or group to remove
            member_type: Whether removing a USER or GROUP

        Returns:
            Updated Workspace aggregate

        Raises:
            PermissionError: If acting user lacks MANAGE permission
            ValueError: If member doesn't exist or workspace not found
            UnauthorizedError: If workspace belongs to different tenant
        """
        # Check acting user has MANAGE permission
        has_manage = await self._check_workspace_permission(
            user_id=acting_user_id,
            workspace_id=workspace_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {acting_user_id.value} lacks manage permission on workspace "
                f"{workspace_id.value}"
            )

        async with self._session.begin():
            # Load workspace
            workspace = await self._workspace_repository.get_by_id(workspace_id)
            if workspace is None:
                raise ValueError(f"Workspace {workspace_id.value} not found")

            # Verify tenant ownership
            if workspace.tenant_id != self._scope_to_tenant:
                raise UnauthorizedError("Workspace belongs to different tenant")

            # Remove member (aggregate handles validation and events)
            workspace.remove_member(member_id, member_type)

            # Save (persists events to outbox)
            await self._workspace_repository.save(workspace)

        # Emit probe
        self._probe.workspace_member_removed(
            workspace_id=workspace_id.value,
            member_id=member_id,
            member_type=member_type.value,
            acting_user_id=acting_user_id.value,
        )

        return workspace

    async def update_workspace(
        self,
        workspace_id: WorkspaceId,
        user_id: UserId,
        name: str,
    ) -> Workspace:
        """Update workspace metadata.

        Args:
            workspace_id: The workspace to update
            user_id: User performing the action (must have MANAGE permission)
            name: New workspace name

        Returns:
            Updated Workspace aggregate

        Raises:
            PermissionError: If user lacks MANAGE permission
            ValueError: If workspace not found or name invalid
            DuplicateWorkspaceNameError: If name already exists in tenant
            UnauthorizedError: If workspace belongs to different tenant
        """
        # Check user has MANAGE permission
        has_manage = await self._check_workspace_permission(
            user_id=user_id,
            workspace_id=workspace_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {user_id.value} lacks manage permission on workspace "
                f"{workspace_id.value}"
            )

        async with self._session.begin():
            # Load workspace
            workspace = await self._workspace_repository.get_by_id(workspace_id)
            if workspace is None:
                raise ValueError(f"Workspace {workspace_id.value} not found")

            # Verify tenant ownership
            if workspace.tenant_id != self._scope_to_tenant:
                raise UnauthorizedError("Workspace belongs to different tenant")

            # Check name uniqueness (if name is changing)
            if name != workspace.name:
                existing = await self._workspace_repository.get_by_name(
                    tenant_id=self._scope_to_tenant,
                    name=name,
                )
                if existing:
                    raise DuplicateWorkspaceNameError(
                        f"Workspace '{name}' already exists in tenant"
                    )

            # Update workspace
            workspace.rename(name)

            # Save
            await self._workspace_repository.save(workspace)

        return workspace

    async def update_member_role(
        self,
        workspace_id: WorkspaceId,
        acting_user_id: UserId,
        member_id: str,
        member_type: MemberType,
        new_role: WorkspaceRole,
    ) -> Workspace:
        """Update a member's role in a workspace.

        Args:
            workspace_id: The workspace
            acting_user_id: User performing the action (must have MANAGE permission)
            member_id: ID of user or group to update
            member_type: Whether updating a USER or GROUP
            new_role: The new role to assign

        Returns:
            Updated Workspace aggregate

        Raises:
            PermissionError: If acting user lacks MANAGE permission
            ValueError: If member doesn't exist, role unchanged, or workspace not found
            UnauthorizedError: If workspace belongs to different tenant
        """
        # Check acting user has MANAGE permission
        has_manage = await self._check_workspace_permission(
            user_id=acting_user_id,
            workspace_id=workspace_id,
            permission=Permission.MANAGE,
        )

        if not has_manage:
            raise PermissionError(
                f"User {acting_user_id.value} lacks manage permission on workspace "
                f"{workspace_id.value}"
            )

        async with self._session.begin():
            # Load workspace
            workspace = await self._workspace_repository.get_by_id(workspace_id)
            if workspace is None:
                raise ValueError(f"Workspace {workspace_id.value} not found")

            # Verify tenant ownership
            if workspace.tenant_id != self._scope_to_tenant:
                raise UnauthorizedError("Workspace belongs to different tenant")

            # Update member role (aggregate handles validation and events)
            workspace.update_member_role(member_id, member_type, new_role)

            # Save (persists events to outbox)
            await self._workspace_repository.save(workspace)

        # Emit probe
        self._probe.workspace_member_role_changed(
            workspace_id=workspace_id.value,
            member_id=member_id,
            member_type=member_type.value,
            new_role=new_role.value,
            acting_user_id=acting_user_id.value,
        )

        return workspace

    async def list_members(
        self,
        workspace_id: WorkspaceId,
        user_id: UserId,
    ) -> list[WorkspaceAccessGrant]:
        """List members of a workspace.

        Returns list of WorkspaceAccessGrant objects from SpiceDB.
        User must have VIEW permission on workspace.

        Args:
            workspace_id: The workspace to list members for
            user_id: User requesting the list (must have VIEW permission)

        Returns:
            List of WorkspaceAccessGrant objects

        Raises:
            PermissionError: If user lacks VIEW permission
        """
        # Check user has VIEW permission
        has_view = await self._check_workspace_permission(
            user_id=user_id,
            workspace_id=workspace_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            raise PermissionError(
                f"User {user_id.value} lacks view permission on workspace "
                f"{workspace_id.value}"
            )

        # Query SpiceDB for all members across all three roles
        resource = format_resource(ResourceType.WORKSPACE, workspace_id.value)
        members: list[WorkspaceAccessGrant] = []

        for role in WorkspaceRole:
            # Query users
            user_subjects = await self._authz.lookup_subjects(
                resource=resource,
                relation=role.value,
                subject_type=ResourceType.USER,
            )

            for subject_relation in user_subjects:
                members.append(
                    WorkspaceAccessGrant(
                        member_id=subject_relation.subject_id,
                        member_type=MemberType.USER,
                        role=role,
                    )
                )

            # Query groups
            group_subjects = await self._authz.lookup_subjects(
                resource=resource,
                relation=role.value,
                subject_type=ResourceType.GROUP,
            )

            for subject_relation in group_subjects:
                members.append(
                    WorkspaceAccessGrant(
                        member_id=subject_relation.subject_id,
                        member_type=MemberType.GROUP,
                        role=role,
                    )
                )

        return members
