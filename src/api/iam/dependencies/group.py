from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.dependencies.user import get_current_user_no_jit
from iam.application.value_objects import CurrentUser
from iam.dependencies.outbox import get_outbox_repository
from iam.application.services.group_service import GroupService
from iam.application.observability import (
    DefaultGroupServiceProbe,
    GroupServiceProbe,
)

from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.user_repository import UserRepository
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.protocols import AuthorizationProvider


def get_group_service_probe() -> GroupServiceProbe:
    """Get GroupServiceProbe instance.

    Returns:
        DefaultGroupServiceProbe instance for observability
    """
    return DefaultGroupServiceProbe()


def get_group_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> GroupRepository:
    """Get GroupRepository instance.

    Args:
        session: Async database session
        authz: Authorization provider (SpiceDB client)
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        GroupRepository instance with outbox pattern enabled
    """
    return GroupRepository(session=session, authz=authz, outbox=outbox)


def get_user_repository_for_group(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> UserRepository:
    """Get UserRepository instance for group member validation.

    Args:
        session: Async database session

    Returns:
        UserRepository instance
    """
    return UserRepository(session=session)


def get_group_service(
    group_repo: Annotated[GroupRepository, Depends(get_group_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    group_service_probe: Annotated[GroupServiceProbe, Depends(get_group_service_probe)],
    current_user: Annotated[CurrentUser, Depends(get_current_user_no_jit)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository_for_group)],
) -> GroupService:
    """Get GroupService instance.

    Args:
        group_repo: Group repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        authz: Authorization provider (SpiceDB client)
        group_service_probe: Group service probe for observability
        current_user: The current user, from which the tenant ID will be used to scope the user service.
        user_repo: User repository for member existence validation
    Returns:
        GroupService instance
    """
    return GroupService(
        session=session,
        group_repository=group_repo,
        authz=authz,
        scope_to_tenant=current_user.tenant_id,
        probe=group_service_probe,
        user_repository=user_repo,
    )
