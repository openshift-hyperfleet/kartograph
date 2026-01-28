from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.dependencies.outbox import get_outbox_repository
from iam.domain.value_objects import TenantId
from iam.application.observability import (
    DefaultTenantServiceProbe,
    TenantServiceProbe,
)

from iam.application.services import TenantService
from iam.infrastructure.tenant_repository import TenantRepository
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository


#  Module-level cache for default tenant ID (populated at startup)
_default_tenant_id: TenantId | None = None


def set_default_tenant_id(tenant_id: TenantId) -> None:
    """Set the default tenant ID (called during app startup).

    Args:
        tenant_id: The default tenant ID to cache
    """
    global _default_tenant_id
    _default_tenant_id = tenant_id


def get_default_tenant_id() -> TenantId:
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


def get_tenant_service(
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    tenant_service_probe: Annotated[
        TenantServiceProbe, Depends(get_tenant_service_probe)
    ],
) -> TenantService:
    """Get TenantService instance.

    Args:
        tenant_repo: Tenant repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        tenant_service_probe: Tenant service probe for observability

    Returns:
        TenantService instance
    """
    return TenantService(
        tenant_repository=tenant_repo,
        session=session,
        probe=tenant_service_probe,
    )
