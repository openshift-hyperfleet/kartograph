"""FastAPI dependency injection for workspace repository and service.

Provides workspace repository and service instances for route handlers
using FastAPI's dependency injection system.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.observability import (
    DefaultWorkspaceServiceProbe,
    WorkspaceServiceProbe,
)
from iam.application.services import WorkspaceService
from iam.application.value_objects import CurrentUser
from iam.dependencies.group import get_group_repository
from iam.dependencies.outbox import get_outbox_repository
from iam.dependencies.user import get_current_user_no_jit
from iam.infrastructure.group_repository import GroupRepository
from iam.infrastructure.user_repository import UserRepository
from iam.infrastructure.workspace_repository import WorkspaceRepository
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository
from shared_kernel.authorization.protocols import AuthorizationProvider


def get_workspace_service_probe() -> WorkspaceServiceProbe:
    """Get WorkspaceServiceProbe instance.

    Returns:
        DefaultWorkspaceServiceProbe instance for observability
    """
    return DefaultWorkspaceServiceProbe()


def get_workspace_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> WorkspaceRepository:
    """Get WorkspaceRepository instance.

    Args:
        session: Async database session
        authz: Authorization provider (SpiceDB client) for member hydration
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        WorkspaceRepository instance with outbox pattern enabled
    """
    return WorkspaceRepository(session=session, authz=authz, outbox=outbox)


def get_user_repository_for_workspace(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> UserRepository:
    """Get UserRepository instance for workspace member validation.

    Args:
        session: Async database session

    Returns:
        UserRepository instance
    """
    return UserRepository(session=session)


def get_workspace_service(
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    workspace_service_probe: Annotated[
        WorkspaceServiceProbe, Depends(get_workspace_service_probe)
    ],
    current_user: Annotated[CurrentUser, Depends(get_current_user_no_jit)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository_for_workspace)],
    group_repo: Annotated[GroupRepository, Depends(get_group_repository)],
) -> WorkspaceService:
    """Get WorkspaceService instance.

    Args:
        workspace_repo: Workspace repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        authz: Authorization provider (SpiceDB client)
        workspace_service_probe: Workspace service probe for observability
        current_user: The current user, from which the tenant ID will be used to scope the service.
        user_repo: User repository for member existence validation
        group_repo: Group repository for member existence validation

    Returns:
        WorkspaceService instance
    """
    return WorkspaceService(
        session=session,
        workspace_repository=workspace_repo,
        authz=authz,
        scope_to_tenant=current_user.tenant_id,
        probe=workspace_service_probe,
        user_repository=user_repo,
        group_repository=group_repo,
    )
