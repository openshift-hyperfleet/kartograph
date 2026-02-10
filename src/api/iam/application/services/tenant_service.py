"""Tenant application service for IAM bounded context.

Handles tenant management operations (create, read, list, delete).
"""

from __future__ import annotations

from iam.application.observability import DefaultTenantServiceProbe, TenantServiceProbe
from iam.domain.aggregates import Tenant, Workspace
from iam.domain.value_objects import TenantId, TenantRole, UserId
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

    async def create_tenant(self, name: str) -> Tenant:
        """Create a new tenant with root workspace.

        Creates a tenant and automatically provisions a root workspace for it.
        Uses default_workspace_name from settings, falling back to tenant name.

        Args:
            name: The name of the tenant

        Returns:
            The created Tenant aggregate

        Raises:
            DuplicateTenantNameError: If a tenant with this name already exists
        """
        async with self._session.begin():
            try:
                # Create tenant
                tenant = Tenant.create(name=name)
                await self._tenant_repository.save(tenant)

                # Create root workspace for tenant
                settings = get_iam_settings()
                workspace_name = settings.default_workspace_name or tenant.name

                workspace = Workspace.create_root(
                    name=workspace_name,
                    tenant_id=tenant.id,
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

    async def get_tenant(self, tenant_id: TenantId) -> Tenant | None:
        """Retrieve a tenant by ID.

        Args:
            tenant_id: The unique identifier of the tenant

        Returns:
            The Tenant aggregate, or None if not found
        """
        tenant = await self._tenant_repository.get_by_id(tenant_id)

        if tenant:
            self._probe.tenant_retrieved(tenant_id=tenant_id.value)
        else:
            self._probe.tenant_not_found(tenant_id=tenant_id.value)

        return tenant

    async def list_tenants(self) -> list[Tenant]:
        """List all tenants in the system.

        Returns:
            List of all Tenant aggregates
        """
        tenants = await self._tenant_repository.list_all()

        self._probe.tenants_listed(count=len(tenants))
        return tenants

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
        resource = format_resource(ResourceType.TENANT, tenant_id.value)
        subject = format_subject(ResourceType.USER, requesting_user_id.value)
        return await self._authz.check_permission(
            resource=resource,
            permission=Permission.ADMINISTRATE,
            subject=subject,
        )

    async def add_member(
        self,
        tenant_id: TenantId,
        user_id: UserId,
        role: TenantRole,
        requesting_user_id: UserId,
    ) -> None:
        """Add a member to a tenant.

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

            tenant.add_member(user_id=user_id, role=role, added_by=requesting_user_id)
            await self._tenant_repository.save(tenant)

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

            self._probe.tenant_member_removed(
                tenant_id=tenant_id.value,
                user_id=user_id.value,
                removed_by=requesting_user_id.value,
            )

    async def _list_tenant_members_from_authorization(
        self, tenant_id: TenantId
    ) -> list[tuple[str, str]]:
        """List all users and their roles for a given tenant.

        Returns: list[tuple[user_id, user_role]]
        """
        members = [
            (subject.subject_id, role.value)
            for role in TenantRole
            for subject in await self._authz.lookup_subjects(
                resource=format_resource(
                    resource_type=ResourceType.TENANT,
                    resource_id=tenant_id.value,
                ),
                relation=role.value,
                subject_type=ResourceType.USER,
            )
        ]

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

    async def delete_tenant(self, tenant_id: TenantId) -> bool:
        """Delete a tenant and all its child resources.

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

        Returns:
            True if the tenant was deleted, False if not found
        """
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
