"""Tenant bootstrap service for IAM bounded context.

TEMPORARY SERVICE: This service is used during the walking skeleton phase
to ensure the default tenant and its root workspace exist at application startup.

This service provides a minimal-dependency alternative to TenantService for
bootstrap operations, avoiding the need for authorization providers and other
dependencies that may not be available or appropriate during startup.

This service will be removed when proper multi-tenancy is implemented.
"""

from __future__ import annotations

from iam.domain.aggregates import Tenant, Workspace
from iam.ports.exceptions import DuplicateTenantNameError
from iam.ports.repositories import ITenantRepository, IWorkspaceRepository
from infrastructure.observability.startup_probe import (
    DefaultStartupProbe,
    StartupProbe,
)
from sqlalchemy.ext.asyncio import AsyncSession


class TenantBootstrapService:
    """Bootstrap service for default tenant provisioning.

    Handles the creation of the default tenant and its root workspace
    during application startup. This is a simplified service with minimal
    dependencies, designed specifically for bootstrap operations.

    Unlike TenantService, this service:
    - Does not require authorization providers
    - Does not require group/API key repositories
    - Uses StartupProbe instead of TenantServiceProbe
    - Is intended only for single-tenant walking skeleton phase
    """

    def __init__(
        self,
        tenant_repository: ITenantRepository,
        workspace_repository: IWorkspaceRepository,
        session: AsyncSession,
        probe: StartupProbe | None = None,
    ):
        """Initialize TenantBootstrapService with dependencies.

        Args:
            tenant_repository: Repository for tenant persistence
            workspace_repository: Repository for workspace persistence
            session: Database session for transaction management
            probe: Optional startup probe for observability
        """
        self._tenant_repository = tenant_repository
        self._workspace_repository = workspace_repository
        self._session = session
        self._probe = probe or DefaultStartupProbe()

    async def ensure_default_tenant_with_workspace(
        self,
        tenant_name: str,
        workspace_name: str,
    ) -> Tenant:
        """Ensure the default tenant and its root workspace exist.

        This method is idempotent and handles race conditions during
        concurrent startup of multiple application instances.

        Args:
            tenant_name: Name for the default tenant
            workspace_name: Name for the root workspace

        Returns:
            The default Tenant (either newly created or existing)

        Raises:
            RuntimeError: If tenant cannot be created or retrieved after
                race condition handling
        """
        async with self._session.begin():
            # Step 1: Check if tenant exists
            tenant = await self._tenant_repository.get_by_name(tenant_name)

            if tenant:
                # Tenant already exists
                self._probe.default_tenant_already_exists(
                    tenant_id=tenant.id.value,
                    name=tenant.name,
                )
            else:
                # Tenant doesn't exist, try to create it
                tenant = await self._create_tenant_with_race_handling(tenant_name)

            if not tenant:
                # This should never happen after race condition handling
                raise RuntimeError("Failed to create or retrieve default tenant")

            # Step 2: Check if root workspace exists
            await self._ensure_root_workspace(tenant, workspace_name)

            return tenant

    async def _create_tenant_with_race_handling(
        self,
        tenant_name: str,
    ) -> Tenant | None:
        """Create tenant with handling for race conditions.

        Args:
            tenant_name: Name for the tenant

        Returns:
            The created or concurrently-created Tenant, or None if unrecoverable
        """
        try:
            tenant = Tenant.create(name=tenant_name)
            await self._tenant_repository.save(tenant)

            self._probe.default_tenant_bootstrapped(
                tenant_id=tenant.id.value,
                name=tenant.name,
            )
            return tenant

        except DuplicateTenantNameError:
            # Another instance created it concurrently, re-query
            concurrent_tenant = await self._tenant_repository.get_by_name(tenant_name)
            if concurrent_tenant:
                self._probe.default_tenant_already_exists(
                    tenant_id=concurrent_tenant.id.value,
                    name=concurrent_tenant.name,
                )
            return concurrent_tenant

    async def _ensure_root_workspace(
        self,
        tenant: Tenant,
        workspace_name: str,
    ) -> None:
        """Ensure the root workspace exists for the tenant.

        Args:
            tenant: The tenant to create the workspace for
            workspace_name: Name for the root workspace
        """
        # Check if root workspace already exists
        existing_workspace = await self._workspace_repository.get_root_workspace(
            tenant.id
        )

        if existing_workspace:
            self._probe.default_workspace_already_exists(
                workspace_id=existing_workspace.id.value,
                tenant_id=tenant.id.value,
                name=existing_workspace.name,
            )
            return

        # Create root workspace
        workspace = Workspace.create_root(
            name=workspace_name,
            tenant_id=tenant.id,
        )
        await self._workspace_repository.save(workspace)

        self._probe.default_workspace_bootstrapped(
            workspace_id=workspace.id.value,
            tenant_id=tenant.id.value,
            name=workspace.name,
        )
