from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import (
    DefaultTenantServiceProbe,
    TenantServiceProbe,
)
from iam.application.services import TenantService
from iam.dependencies.outbox import get_outbox_repository
from iam.domain.value_objects import TenantId
from iam.infrastructure.api_key_repository import APIKeyRepository
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.tenant_repository import TenantRepository
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.protocols import AuthorizationProvider


#  Module-level cache for default tenant ID (populated at startup)
_default_tenant_id: str | None = None


def set_default_tenant_id(tenant_id: TenantId) -> None:
    """Set the default tenant ID (called during app startup).

    Args:
        tenant_id: The default tenant ID to cache
    """
    global _default_tenant_id
    _default_tenant_id = tenant_id.value


def get_default_tenant_id() -> str:
    """Get the cached default tenant ID.

    Returns:
        The default tenant ID

    Raises:
        RuntimeError: If default tenant hasn't been initialized
    """
    if _default_tenant_id is None:
        raise RuntimeError(
            "Default tenant not initialized. Ensure app startup completed successfully."
        )
    return _default_tenant_id


def get_tenant_service_probe() -> TenantServiceProbe:
    """Get TenantServiceProbe instance.

    Returns:
        DefaultTenantServiceProbe instance for observability
    """
    return DefaultTenantServiceProbe()


def get_tenant_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> TenantRepository:
    """Get TenantRepository instance.

    Args:
        session: Async database session
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        TenantRepository instance with outbox pattern enabled
    """
    return TenantRepository(session=session, outbox=outbox)


def _get_group_repository_for_tenant_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> GroupRepository:
    """Get GroupRepository for TenantService (breaks circular import)."""
    # Import here to avoid circular dependency
    from iam.dependencies.group import get_group_repository

    return get_group_repository(session=session, authz=authz, outbox=outbox)


def _get_api_key_repository_for_tenant_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> APIKeyRepository:
    """Get APIKeyRepository for TenantService (breaks circular import)."""
    # Import here to avoid circular dependency
    from iam.dependencies.api_key import get_api_key_repository

    return get_api_key_repository(session=session, outbox=outbox)


def get_tenant_service(
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
    group_repo: Annotated[
        GroupRepository, Depends(_get_group_repository_for_tenant_service)
    ],
    api_key_repo: Annotated[
        APIKeyRepository, Depends(_get_api_key_repository_for_tenant_service)
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    tenant_service_probe: Annotated[
        TenantServiceProbe, Depends(get_tenant_service_probe)
    ],
) -> TenantService:
    """Get TenantService instance.

    Args:
        tenant_repo: Tenant repository (shares session via FastAPI dependency caching)
        group_repo: Group repository for cascade deletion
        api_key_repo: API key repository for cascade deletion
        authz: Authorization provider (SpiceDB client)
        session: Database session for transaction management
        tenant_service_probe: Tenant service probe for observability

    Returns:
        TenantService instance
    """
    return TenantService(
        tenant_repository=tenant_repo,
        group_repository=group_repo,
        api_key_repository=api_key_repo,
        authz=authz,
        session=session,
        probe=tenant_service_probe,
    )
