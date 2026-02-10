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
from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId, UserId, WorkspaceId
from infrastructure.settings import get_iam_settings
from iam.ports.exceptions import (
    CannotDeleteRootWorkspaceError,
    DuplicateWorkspaceNameError,
    UnauthorizedError,
    WorkspaceHasChildrenError,
)
from iam.ports.repositories import IWorkspaceRepository
from shared_kernel.authorization.protocols import AuthorizationProvider


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

    async def create_workspace(
        self,
        name: str,
        parent_workspace_id: WorkspaceId,
        creator_id: UserId,
    ) -> Workspace:
        """Create a child workspace.

        Business rules:
        - Name must be unique within tenant
        - Parent workspace must exist and belong to tenant
        - Service is scoped to tenant boundary

        Args:
            name: Workspace name (1-512 characters)
            parent_workspace_id: Parent workspace ID (must exist in scoped tenant)
            creator_id: User creating the workspace (for event attribution)

        Returns:
            The created Workspace aggregate

        Raises:
            DuplicateWorkspaceNameError: If workspace name already exists in tenant
            ValueError: If parent workspace doesn't exist or belongs to different tenant
            Exception: If workspace creation fails
        """
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
    ) -> Workspace | None:
        """Get workspace by ID with tenant scoping check.

        Returns None if workspace doesn't exist or belongs to different tenant.
        Tenant scoping prevents cross-tenant access.

        TODO (Phase 3): Add user-level VIEW permission check via SpiceDB.

        Args:
            workspace_id: The workspace ID to retrieve

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

        # Probe success
        self._probe.workspace_retrieved(
            workspace_id=workspace.id.value,
            tenant_id=workspace.tenant_id.value,
            name=workspace.name,
        )

        return workspace

    async def list_workspaces(self) -> list[Workspace]:
        """List all workspaces in the scoped tenant.

        Returns all workspaces within scope_to_tenant.
        No user-level permission filtering in Phase 1 - that's added in Phase 3.

        TODO (Phase 3): Add SpiceDB permission filtering to only return
        workspaces the user has VIEW permission on.

        Returns:
            List of Workspace aggregates in the scoped tenant
        """
        workspaces = await self._workspace_repository.list_by_tenant(
            tenant_id=self._scope_to_tenant
        )

        # Probe success
        self._probe.workspaces_listed(
            tenant_id=self._scope_to_tenant.value,
            count=len(workspaces),
        )

        return workspaces

    async def delete_workspace(
        self,
        workspace_id: WorkspaceId,
    ) -> bool:
        """Delete a workspace.

        Business rules:
        - Cannot delete root workspace
        - Cannot delete workspace with children (caught via DB IntegrityError)
        - Workspace must belong to scoped tenant

        Args:
            workspace_id: The workspace ID to delete

        Returns:
            True if deleted, False if not found

        Raises:
            CannotDeleteRootWorkspaceError: If attempting to delete root workspace
            WorkspaceHasChildrenError: If workspace has children
            UnauthorizedError: If workspace belongs to different tenant
        """
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
