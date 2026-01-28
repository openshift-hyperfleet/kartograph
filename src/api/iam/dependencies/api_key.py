from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user_no_jit
from iam.dependencies.outbox import get_outbox_repository
from iam.application.observability.api_key_service_probe import (
    APIKeyServiceProbe,
    DefaultAPIKeyServiceProbe,
)
from iam.application.services.api_key_service import APIKeyService
from iam.infrastructure.api_key_repository import APIKeyRepository
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository


def get_api_key_service_probe() -> APIKeyServiceProbe:
    """Get APIKeyServiceProbe instance.

    Returns:
        DefaultAPIKeyServiceProbe instance for observability
    """
    return DefaultAPIKeyServiceProbe()


def get_api_key_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> APIKeyRepository:
    """Get APIKeyRepository instance.

    Args:
        session: Async database session
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        APIKeyRepository instance with outbox pattern enabled
    """
    return APIKeyRepository(session=session, outbox=outbox)


def get_api_key_service(
    api_key_repo: Annotated[APIKeyRepository, Depends(get_api_key_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    probe: Annotated[APIKeyServiceProbe, Depends(get_api_key_service_probe)],
    current_user: Annotated[CurrentUser, Depends(get_current_user_no_jit)],
) -> APIKeyService:
    """Get APIKeyService instance.

    Args:
        api_key_repo: API key repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        probe: API key service probe for observability

    Returns:
        APIKeyService instance
    """
    return APIKeyService(
        session=session,
        api_key_repository=api_key_repo,
        probe=probe,
        scope_to_tenant=current_user.tenant_id,
    )
