"""Dependency injection for IAM bounded context.

Composes infrastructure resources (database sessions, authorization) with
IAM-specific components (repositories, services).
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import (
    DefaultGroupServiceProbe,
    DefaultUserServiceProbe,
    GroupServiceProbe,
    UserServiceProbe,
)
from iam.application.services import GroupService, UserService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.user_repository import UserRepository
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.protocols import AuthorizationProvider


def get_user_service_probe() -> UserServiceProbe:
    """Get UserServiceProbe instance.

    Returns:
        DefaultUserServiceProbe instance for observability
    """
    return DefaultUserServiceProbe()


def get_group_service_probe() -> GroupServiceProbe:
    """Get GroupServiceProbe instance.

    Returns:
        DefaultGroupServiceProbe instance for observability
    """
    return DefaultGroupServiceProbe()


def get_outbox_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> OutboxRepository:
    """Get OutboxRepository instance.

    Args:
        session: Async database session (shared with calling repository)

    Returns:
        OutboxRepository instance
    """
    return OutboxRepository(session=session)


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> UserRepository:
    """Get UserRepository instance.

    Args:
        session: Async database session

    Returns:
        UserRepository instance
    """
    return UserRepository(session=session)


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


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    probe: Annotated[UserServiceProbe, Depends(get_user_service_probe)],
) -> UserService:
    """Get UserService instance.

    Args:
        user_repo: User repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        probe: User service probe for observability

    Returns:
        UserService instance
    """
    return UserService(user_repository=user_repo, probe=probe, session=session)


def get_group_service(
    group_repo: Annotated[GroupRepository, Depends(get_group_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    group_service_probe: Annotated[GroupServiceProbe, Depends(get_group_service_probe)],
) -> GroupService:
    """Get GroupService instance.

    Args:
        group_repo: Group repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        authz: Authorization provider (SpiceDB client)
        group_service_probe: Group service probe for observability

    Returns:
        GroupService instance
    """
    return GroupService(
        session=session,
        group_repository=group_repo,
        authz=authz,
        probe=group_service_probe,
    )


async def get_current_user(
    user_service: Annotated[UserService, Depends(get_user_service)],
    x_user_id: str = Header(..., description="User ID from SSO (stub)"),
    x_username: str = Header(..., description="Username from SSO (stub)"),
    x_tenant_id: str = Header(..., description="Tenant ID from SSO (stub)"),
) -> CurrentUser:
    """Extract current user from headers (stub for SSO integration).

    This is a simplified authentication mechanism for the walking skeleton.
    In production, this will:
    - Decode and validate JWT from Authorization header
    - Extract user_id, username, tenant_id from JWT claims
    - Validate JWT signature with Red Hat SSO public key
    - Handle authentication errors properly

    For now, we accept user info from custom headers to enable testing
    without a full SSO/JWT integration, and ensure the user exists in the
    application database.

    Args:
        user_service: The user service (manages its own transaction)
        x_user_id: User ID header (any format from SSO)
        x_username: Username header
        x_tenant_id: Tenant ID header (ULID format)

    Returns:
        CurrentUser with user ID (from SSO), username, and validated tenant ID

    Raises:
        HTTPException: 400 if tenant ID is invalid ULID format
    """
    # Validate tenant ID first (before user provisioning to avoid orphaned users)
    try:
        tenant_id = TenantId.from_string(x_tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tenant ID format: {e}",
        ) from e

    # User IDs come from external SSO - accept any string format
    user_id = UserId(value=x_user_id)

    # Ensure the user exists in the system (service manages transaction)
    await user_service.ensure_user(user_id=user_id, username=x_username)

    return CurrentUser(user_id=user_id, username=x_username, tenant_id=tenant_id)
