"""Tenant application service for IAM bounded context.

Handles tenant management operations (create, read, list, delete).
"""

from __future__ import annotations

from iam.application.observability import DefaultTenantServiceProbe, TenantServiceProbe
from iam.domain.aggregates import Tenant
from iam.domain.value_objects import TenantId, TenantRole
from iam.ports.exceptions import DuplicateTenantNameError
from iam.ports.repositories import (
    IAPIKeyRepository,
    IGroupRepository,
    ITenantRepository,
)
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import ResourceType, format_resource
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
        group_repository: IGroupRepository,
        api_key_repository: IAPIKeyRepository,
        authz: AuthorizationProvider,
        session: AsyncSession,
        probe: TenantServiceProbe | None = None,
    ):
        """Initialize TenantService with dependencies.

        Args:
            tenant_repository: Repository for tenant persistence
            group_repository: Repository for group persistence (for cascade delete)
            api_key_repository: Repository for API key persistence (for cascade delete)
            authz: Authorization provider for SpiceDB queries
            session: Database session for transaction management
            probe: Optional domain probe for observability
        """
        self._tenant_repository = tenant_repository
        self._group_repository = group_repository
        self._api_key_repository = api_key_repository
        self._authz = authz
        self._probe = probe or DefaultTenantServiceProbe()
        self._session = session

    async def create_tenant(self, name: str) -> Tenant:
        """Create a new tenant.

        Manages database transaction for the entire use case.

        Args:
            name: The name of the tenant

        Returns:
            The created Tenant aggregate

        Raises:
            DuplicateTenantNameError: If a tenant with this name already exists
        """
        async with self._session.begin():
            try:
                tenant = Tenant.create(name=name)
                await self._tenant_repository.save(tenant)

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

    async def delete_tenant(self, tenant_id: TenantId) -> bool:
        """Delete a tenant and all its child resources.

        Explicitly deletes all child aggregates (groups, API keys) before
        deleting the tenant to ensure proper domain events are emitted for
        SpiceDB cleanup. This prevents orphaned relationships in SpiceDB.

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

            # Step 1: Delete all groups belonging to this tenant
            # This ensures GroupDeleted events are emitted for SpiceDB cleanup
            groups = await self._group_repository.list_by_tenant(tenant_id)
            for group in groups:
                group.mark_for_deletion()
                await self._group_repository.delete(group)

            # Step 2: Delete all API keys belonging to this tenant
            # This ensures APIKeyDeleted events are emitted for SpiceDB cleanup
            api_keys = await self._api_key_repository.list(tenant_id=tenant_id)
            for api_key in api_keys:
                api_key.mark_for_deletion()
                await self._api_key_repository.delete(api_key)

            # Step 3: Query SpiceDB for tenant members to build snapshot
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

            # Step 4: Delete the tenant
            tenant.mark_for_deletion(members=members)
            result = await self._tenant_repository.delete(tenant)

            if result:
                self._probe.tenant_deleted(tenant_id=tenant_id.value)

            return result
