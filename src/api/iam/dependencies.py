"""Dependency injection for IAM bounded context.

Composes infrastructure resources (database sessions, authorization) with
IAM-specific components (repositories, services).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.services import GroupService, UserService
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.user_repository import UserRepository
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from shared_kernel.authorization.protocols import AuthorizationProvider


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
) -> GroupRepository:
    """Get GroupRepository instance.

    Args:
        session: Async database session
        authz: Authorization provider (SpiceDB client)

    Returns:
        GroupRepository instance
    """
    return GroupRepository(session=session, authz=authz)


def get_user_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    """Get UserService instance.

    Args:
        user_repo: User repository

    Returns:
        UserService instance
    """
    return UserService(user_repository=user_repo)


def get_group_service(
    group_repo: Annotated[GroupRepository, Depends(get_group_repository)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> GroupService:
    """Get GroupService instance.

    Args:
        group_repo: Group repository
        user_service: User service for JIT user provisioning

    Returns:
        GroupService instance
    """
    return GroupService(
        group_repository=group_repo,
        user_service=user_service,
    )
