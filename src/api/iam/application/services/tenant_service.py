"""Tenant application service for IAM bounded context.

Handles tenant management operations (create, read, list, delete).
"""

from __future__ import annotations

from iam.application.observability import DefaultTenantServiceProbe, TenantServiceProbe
from iam.domain.aggregates import Tenant, Workspace
from iam.domain.value_objects import (
    MemberType,
    TenantId,
    TenantRole,
    UserId,
    WorkspaceRole,
)
from iam.ports.exceptions import DuplicateTenantNameError, UnauthorizedError
from iam.ports.repositories import (
    IAPIKeyRepository,
    IGroupRepository,
    ITenantRepository,
    IWorkspaceRepository,
)
from infrastructure.settings import get_iam_settings
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from sqlalchemy.ext.asyncio import AsyncSession


class TenantService:
    """Application service for tenant management.

    Handles tenant CRUD operations with transaction management.
    For deletion, explicitly cascades to child aggregates (groups, API keys)
    to ensure proper domain events are emitted for SpiceDB cleanup.
    """

    def __init__(
        self,
        tenant_repository: ITenantRepository,
        workspace_repository: IWorkspaceRepository,
        group_repository: IGroupRepository,
        api_key_repository: IAPIKeyRepository,
        authz: AuthorizationProvider,
        session: AsyncSession,
        probe: TenantServiceProbe | None = None,
    ):
        """Initialize TenantService with dependencies.

        Args:
            tenant_repository: Repository for tenant persistence
            workspace_repository: Repository for workspace persistence (for root workspace creation)
            group_repository: Repository for group persistence (for cascade delete)
            api_key_repository: Repository for API key persistence (for cascade delete)
            authz: Authorization provider for SpiceDB queries
            session: Database session for transaction management
            probe: Optional domain probe for observability
        """
        self._tenant_repository = tenant_repository
        self._workspace_repository = workspace_repository
        self._group_repository = group_repository
        self._api_key_repository = api_key_repository
        self._authz = authz
        self._probe = probe or DefaultTenantServiceProbe()
        self._session = session

    async def create_tenant(self, name: str, creator_id: UserId) -> Tenant:
        """Create a new tenant with root workspace.

        Creates a tenant and automatically provisions a root workspace for it.
        Grants the creator admin access to the tenant.

        Args:
            name: The name of the tenant
            creator_id: User creating the tenant (will be granted admin access)

        Returns:
            The created Tenant aggregate

        Raises:
            DuplicateTenantNameError: If a tenant with this name already exists
        """
        async with self._session.begin():
            try:
                # Create tenant
                tenant = Tenant.create(name=name)

                # Grant creator admin access (same pattern as groups/workspaces)
                tenant.add_member(user_id=creator_id, role=TenantRole.ADMIN)

                await self._tenant_repository.save(tenant)

                # Create root workspace for tenant
                settings = get_iam_settings()
                workspace_name = settings.default_workspace_name or tenant.name

                workspace = Workspace.create_root(
                    name=workspace_name,
                    tenant_id=tenant.id,
                )

                # Grant creator admin access to root workspace
                workspace.add_member(
                    member_id=creator_id.value,
                    member_type=MemberType.USER,
                    role=WorkspaceRole.ADMIN,
                )

                await self._workspace_repository.save(workspace)

                self._probe.tenant_created(
                    tenant_id=tenant.id.value,
                    name=name,
                )
                return tenant

            except DuplicateTenantNameError:
                self._probe.duplicate_tenant_name(name=name)
                raise

    async def get_tenant(
        self,
        tenant_id: TenantId,
        user_id: UserId,
    ) -> Tenant | None:
        """Retrieve a tenant by ID with VIEW permission check.

        Returns None if tenant doesn't exist or user lacks VIEW permission.

        Args:
            tenant_id: The unique identifier of the tenant
            user_id: The user requesting access (for permission check)

        Returns:
            The Tenant aggregate, or None if not found or not accessible
        """
        tenant = await self._tenant_repository.get_by_id(tenant_id)

        if tenant is None:
            self._probe.tenant_not_found(tenant_id=tenant_id.value)
            return None

        # Check user has VIEW permission
        has_view = await self._check_tenant_permission(
            tenant_id=tenant_id,
            user_id=user_id,
            permission=Permission.VIEW,
        )

        if not has_view:
            # User lacks VIEW permission - act as if not found
            return None

        self._probe.tenant_retrieved(tenant_id=tenant_id.value)
        return tenant

    async def list_tenants(self, user_id: UserId) -> list[Tenant]:
        """List tenants the user has VIEW permission on.

        Filters tenants to only those where user has VIEW permission via
        SpiceDB lookup_resources. This ensures users only see tenants they
        are members of.

        Args:
            user_id: The user requesting the list (for permission filtering)

        Returns:
            List of Tenant aggregates user can view
        """
        # Get all tenants from database
        all_tenants = await self._tenant_repository.list_all()

        # Use SpiceDB lookup_resources to filter by VIEW permission
        subject = format_subject(ResourceType.USER, user_id.value)

        accessible_ids = await self._authz.lookup_resources(
            resource_type=ResourceType.TENANT,
            permission=Permission.VIEW,
            subject=subject,
        )

        # Convert to set for O(1) lookup
        accessible_set = set(accessible_ids)

        # Filter tenants to only accessible ones
        accessible_tenants = [t for t in all_tenants if t.id.value in accessible_set]

        self._probe.tenants_listed(count=len(accessible_tenants))
        return accessible_tenants

    async def _check_tenant_permission(
        self,
        tenant_id: TenantId,
        user_id: UserId,
        permission: Permission,
    ) -> bool:
        """Check if user has permission on tenant.

        Args:
            tenant_id: Tenant ID to check
            user_id: User ID to check
            permission: Permission to check (VIEW, ADMINISTRATE)

        Returns:
            True if user has permission, False otherwise
        """
        resource = format_resource(ResourceType.TENANT, tenant_id.value)
        subject = format_subject(ResourceType.USER, user_id.value)
        return await self._authz.check_permission(
            resource=resource,
            permission=permission.value,
            subject=subject,
        )

    async def _check_tenant_admin_permission(
        self, tenant_id: TenantId, requesting_user_id: UserId
    ) -> bool:
        """Check if user has administrate permission on tenant.

        Args:
            tenant_id: Tenant ID to check
            requesting_user_id: User ID to check

        Returns:
            True if user has administrate permission, False otherwise
        """
        return await self._check_tenant_permission(
            tenant_id=tenant_id,
            user_id=requesting_user_id,
            permission=Permission.ADMINISTRATE,
        )

    async def _get_user_tenant_role(
        self, tenant_id: TenantId, user_id: UserId
    ) -> TenantRole | None:
        """Get user's current role in tenant, or None if not a member."""
        tuples = await self._authz.read_relationships(
            resource_type=ResourceType.TENANT.value,
            resource_id=tenant_id.value,
            subject_type=ResourceType.USER.value,
            subject_id=user_id.value,
        )

        valid_roles = {role.value for role in TenantRole}
        for rel_tuple in tuples:
            if rel_tuple.relation in valid_roles:
                return TenantRole(rel_tuple.relation)

        return None

    async def add_member(
        self,
        tenant_id: TenantId,
        user_id: UserId,
        role: TenantRole,
        requesting_user_id: UserId,
    ) -> None:
        """Add a member to a tenant.

        If the user already has a different role, the old role is automatically
        removed first (role replacement pattern). This ensures users can only
        have one role per tenant.

        Args:
            tenant_id: The tenant to add the member to
            user_id: The user being added
            role: The role to assign (ADMIN or MEMBER)
            requesting_user_id: The user making this request (for authorization)

        Raises:
            UnauthorizedError: If requesting user lacks administrate permission
            ValueError: If tenant not found
        """
        # Check authorization - business rule
        has_permission = await self._check_tenant_admin_permission(
            tenant_id, requesting_user_id
        )
        if not has_permission:
            raise UnauthorizedError(
                "User does not have permission to manage tenant members"
            )

        async with self._session.begin():
            tenant = await self._tenant_repository.get_by_id(tenant_id)

            if not tenant:
                self._probe.tenant_not_found(tenant_id=tenant_id.value)
                raise ValueError("Tenant not found")

            # Check if user already has a role (query SpiceDB)
            current_role = await self._get_user_tenant_role(tenant_id, user_id)

            # Check if this is the last admin being demoted
            is_last_admin = False
            if current_role == TenantRole.ADMIN and role != TenantRole.ADMIN:
                is_last_admin = await self._tenant_repository.is_last_admin(
                    tenant_id, user_id, self._authz
                )

            # Add member (will replace role if different)
            tenant.add_member(
                user_id=user_id,
                role=role,
                added_by=requesting_user_id,
                current_role=current_role,
                is_last_admin=is_last_admin,
            )
            await self._tenant_repository.save(tenant)

            # Auto-grant/revoke root workspace access based on tenant role
            await self._sync_root_workspace_access(
                tenant_id=tenant_id,
                user_id=user_id,
                new_tenant_role=role,
                old_tenant_role=current_role,
            )

            self._probe.tenant_member_added(
                tenant_id=tenant_id.value,
                user_id=user_id.value,
                role=role.value,
                added_by=requesting_user_id.value,
            )

    async def remove_member(
        self,
        tenant_id: TenantId,
        user_id: UserId,
        requesting_user_id: UserId,
    ) -> None:
        """Remove a member from a tenant.

        Args:
            tenant_id: The tenant to remove the member from
            user_id: The user being removed
            requesting_user_id: The user making this request (for authorization)

        Raises:
            UnauthorizedError: If requesting user lacks administrate permission
            CannotRemoveLastAdminError: If user is the last admin
            ValueError: If tenant not found
        """
        # Check authorization - business rule
        has_permission = await self._check_tenant_admin_permission(
            tenant_id, requesting_user_id
        )
        if not has_permission:
            raise UnauthorizedError(
                "User does not have permission to manage tenant members"
            )

        async with self._session.begin():
            tenant = await self._tenant_repository.get_by_id(tenant_id)

            if not tenant:
                self._probe.tenant_not_found(tenant_id=tenant_id.value)
                raise ValueError("Tenant not found")

            # Check if user is the last admin
            is_last_admin = await self._tenant_repository.is_last_admin(
                tenant_id, user_id, self._authz
            )

            tenant.remove_member(
                user_id=user_id,
                removed_by=requesting_user_id,
                is_last_admin=is_last_admin,
            )
            await self._tenant_repository.save(tenant)

            # Revoke root workspace access when removing member entirely
            await self._revoke_root_workspace_access(
                tenant_id=tenant_id,
                user_id=user_id,
            )

            self._probe.tenant_member_removed(
                tenant_id=tenant_id.value,
                user_id=user_id.value,
                removed_by=requesting_user_id.value,
            )

    async def _sync_root_workspace_access(
        self,
        tenant_id: TenantId,
        user_id: UserId,
        new_tenant_role: TenantRole,
        old_tenant_role: TenantRole | None,
    ) -> None:
        """Synchronize root workspace access based on tenant role changes.

        When a user is added as tenant ADMIN, they get auto-granted ADMIN
        on the root workspace. When downgraded from ADMIN to MEMBER, their
        root workspace admin is revoked.

        Regular MEMBER additions do not grant workspace access - they
        get create_child permission via the creator_tenant relation in SpiceDB.

        Args:
            tenant_id: The tenant
            user_id: The user whose access is being synchronized
            new_tenant_role: The new tenant role being assigned
            old_tenant_role: The user's previous tenant role (None if new member)
        """
        if new_tenant_role == TenantRole.ADMIN:
            # Grant root workspace admin for new tenant admins
            root_workspace = await self._workspace_repository.get_root_workspace(
                tenant_id
            )
            if not root_workspace:
                # Root workspace doesn't exist yet - skip workspace access grant
                # This can happen if add_member is called during tenant bootstrap
                return

            # Check if user already has a workspace role
            current_ws_role: WorkspaceRole | None = None
            if root_workspace.has_member(user_id.value, MemberType.USER):
                current_ws_role = root_workspace.get_member_role(
                    user_id.value, MemberType.USER
                )

            root_workspace.add_member(
                member_id=user_id.value,
                member_type=MemberType.USER,
                role=WorkspaceRole.ADMIN,
                current_role=current_ws_role,
            )
            await self._workspace_repository.save(root_workspace)

        elif (
            new_tenant_role == TenantRole.MEMBER and old_tenant_role == TenantRole.ADMIN
        ):
            # Downgrade: revoke workspace admin when demoted from tenant admin
            root_workspace = await self._workspace_repository.get_root_workspace(
                tenant_id
            )
            if not root_workspace:
                return

            if root_workspace.has_member(user_id.value, MemberType.USER):
                root_workspace.remove_member(
                    member_id=user_id.value,
                    member_type=MemberType.USER,
                    force=True,
                )
                await self._workspace_repository.save(root_workspace)

    async def _revoke_root_workspace_access(
        self,
        tenant_id: TenantId,
        user_id: UserId,
    ) -> None:
        """Revoke root workspace access when removing a member from tenant.

        Args:
            tenant_id: The tenant the user is being removed from
            user_id: The user being removed
        """
        root_workspace = await self._workspace_repository.get_root_workspace(tenant_id)
        if not root_workspace:
            return

        if root_workspace.has_member(user_id.value, MemberType.USER):
            root_workspace.remove_member(
                member_id=user_id.value,
                member_type=MemberType.USER,
                force=True,
            )
            await self._workspace_repository.save(root_workspace)

    async def _list_tenant_members_from_authorization(
        self, tenant_id: TenantId
    ) -> list[tuple[str, str]]:
        """List all users and their roles for a given tenant.

        Uses read_relationships to return only explicit tuples (not computed
        permissions), consistent with workspace and group member listing.

        Returns: list[tuple[user_id, user_role]]
        """
        tuples = await self._authz.read_relationships(
            resource_type=ResourceType.TENANT.value,
            resource_id=tenant_id.value,
            subject_type=ResourceType.USER.value,
        )

        members: list[tuple[str, str]] = []
        for rel_tuple in tuples:
            # Map SpiceDB relations to domain roles
            if rel_tuple.relation == TenantRole.ADMIN.value:
                role = TenantRole.ADMIN
            elif rel_tuple.relation == TenantRole.MEMBER.value:
                role = TenantRole.MEMBER
            else:
                continue  # Skip non-role relations

            # Parse subject (format: "user:ID")
            subject_parts = rel_tuple.subject.split(":")
            if len(subject_parts) < 2:
                continue
            user_id = ":".join(subject_parts[1:])

            members.append((user_id, role.value))

        return members

    async def list_members(
        self, tenant_id: TenantId, requesting_user_id: UserId
    ) -> list[tuple[str, str]] | None:
        """List all members of a tenant.

        Queries SpiceDB for all users with tenant membership roles.

        Args:
            tenant_id: The tenant to list members for
            requesting_user_id: The user making this request (for authorization)

        Returns:
            List of (user_id, role) tuples, or None if tenant not found

        Raises:
            UnauthorizedError: If requesting user lacks administrate permission
        """
        # Check authorization - business rule
        has_permission = await self._check_tenant_admin_permission(
            tenant_id, requesting_user_id
        )
        if not has_permission:
            raise UnauthorizedError(
                "User does not have permission to view tenant members"
            )

        # Verify tenant exists
        tenant = await self._tenant_repository.get_by_id(tenant_id)
        if not tenant:
            self._probe.tenant_not_found(tenant_id=tenant_id.value)
            return None

        # Query SpiceDB for members by role
        members = await self._list_tenant_members_from_authorization(
            tenant_id=tenant_id
        )

        self._probe.tenant_members_listed(
            tenant_id=tenant_id.value, member_count=len(members)
        )

        return members

    async def delete_tenant(
        self,
        tenant_id: TenantId,
        requesting_user_id: UserId,
    ) -> bool:
        """Delete a tenant and all its child resources.

        Requires ADMINISTRATE permission on the tenant.

        Explicitly deletes all child aggregates (workspaces, groups, API keys)
        before deleting the tenant to ensure proper domain events are emitted
        for SpiceDB cleanup. This prevents orphaned relationships in SpiceDB.

        Cascade deletion order:
        1. Workspaces (ensures WorkspaceDeleted events for SpiceDB cleanup)
        2. Groups (ensures GroupDeleted events for SpiceDB cleanup)
        3. API keys (ensures APIKeyDeleted events for SpiceDB cleanup)
        4. Tenant itself

        Args:
            tenant_id: The unique identifier of the tenant to delete
            requesting_user_id: User requesting deletion (for authorization check)

        Returns:
            True if the tenant was deleted, False if not found

        Raises:
            UnauthorizedError: If user lacks ADMINISTRATE permission on tenant
        """
        # Check authorization - user must have administrate permission
        has_permission = await self._check_tenant_admin_permission(
            tenant_id, requesting_user_id
        )
        if not has_permission:
            raise UnauthorizedError("User does not have permission to delete tenant")

        async with self._session.begin():
            tenant = await self._tenant_repository.get_by_id(tenant_id)

            if not tenant:
                self._probe.tenant_not_found(tenant_id=tenant_id.value)
                return False

            # Step 1: Delete all workspaces belonging to this tenant
            # This ensures WorkspaceDeleted events are emitted for SpiceDB cleanup
            workspaces = await self._workspace_repository.list_by_tenant(tenant_id)

            # Step 2: Delete all groups belonging to this tenant
            # This ensures GroupDeleted events are emitted for SpiceDB cleanup
            groups = await self._group_repository.list_by_tenant(tenant_id)

            # Step 3: Delete all API keys belonging to this tenant
            # This ensures APIKeyDeleted events are emitted for SpiceDB cleanup
            api_keys = await self._api_key_repository.list(tenant_id=tenant_id)

            # Log cascade deletion scope for operational visibility
            self._probe.tenant_cascade_deletion_started(
                tenant_id=tenant_id.value,
                workspaces_count=len(workspaces),
                groups_count=len(groups),
                api_keys_count=len(api_keys),
            )

            # Delete workspaces in depth-first order (children before parents)
            # Build depth map for topological sort
            workspace_by_id = {ws.id.value: ws for ws in workspaces}
            depth_map: dict[str, int] = {}

            def compute_depth(ws_id: str) -> int:
                if ws_id in depth_map:
                    return depth_map[ws_id]
                ws = workspace_by_id.get(ws_id)
                if not ws or ws.parent_workspace_id is None:
                    depth_map[ws_id] = 0
                    return 0
                parent_id = ws.parent_workspace_id.value
                if parent_id not in workspace_by_id:
                    # Parent not in deletion set (e.g., belongs to another tenant)
                    depth_map[ws_id] = 0
                    return 0
                depth_map[ws_id] = compute_depth(parent_id) + 1
                return depth_map[ws_id]

            for ws in workspaces:
                compute_depth(ws.id.value)

            # Sort by descending depth (deepest children first)
            sorted_workspaces = sorted(
                workspaces,
                key=lambda ws: depth_map.get(ws.id.value, 0),
                reverse=True,
            )

            for workspace in sorted_workspaces:
                workspace.mark_for_deletion()
                await self._workspace_repository.delete(workspace)

            # Then delete groups
            for group in groups:
                group.mark_for_deletion()
                await self._group_repository.delete(group)

            for api_key in api_keys:
                api_key.mark_for_deletion()
                await self._api_key_repository.delete(api_key)

            # Step 4: Query SpiceDB for tenant members to build snapshot
            members = await self._list_tenant_members_from_authorization(
                tenant_id=tenant_id
            )

            # Step 5: Delete the tenant
            tenant.mark_for_deletion(members=members)
            result = await self._tenant_repository.delete(tenant)

            if result:
                self._probe.tenant_deleted(tenant_id=tenant_id.value)

            return result
