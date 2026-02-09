"""Workspace application service for IAM bounded context.

Orchestrates workspace creation with proper validation and authorization setup.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import (
    DefaultWorkspaceServiceProbe,
    WorkspaceServiceProbe,
)
from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId, UserId, WorkspaceId
from infrastructure.settings import get_iam_settings
from iam.ports.exceptions import (
    DuplicateWorkspaceNameError,
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

            # Persist in transaction
            async with self._session.begin():
                await self._workspace_repository.save(workspace)

            # Probe success
            self._probe.workspace_created(
                workspace_id=workspace.id.value,
                tenant_id=self._scope_to_tenant.value,
                name=name,
                parent_workspace_id=parent_workspace_id.value,
                is_root=False,
                creator_id=creator_id.value,
            )

            return workspace

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

            # Persist in transaction
            async with self._session.begin():
                await self._workspace_repository.save(workspace)

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

        except Exception as e:
            self._probe.workspace_creation_failed(
                tenant_id=self._scope_to_tenant.value,
                name=workspace_name,
                error=str(e),
            )
            raise
