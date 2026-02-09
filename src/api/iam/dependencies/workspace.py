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
from iam.dependencies.outbox import get_outbox_repository
from iam.dependencies.user import get_current_user_no_jit
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
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> WorkspaceRepository:
    """Get WorkspaceRepository instance.

    Args:
        session: Async database session
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        WorkspaceRepository instance with outbox pattern enabled
    """
    return WorkspaceRepository(session=session, outbox=outbox)


def get_workspace_service(
    workspace_repo: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    workspace_service_probe: Annotated[
        WorkspaceServiceProbe, Depends(get_workspace_service_probe)
    ],
    current_user: Annotated[CurrentUser, Depends(get_current_user_no_jit)],
) -> WorkspaceService:
    """Get WorkspaceService instance.

    Args:
        workspace_repo: Workspace repository (shares session via FastAPI dependency caching)
        session: Database session for transaction management
        authz: Authorization provider (SpiceDB client)
        workspace_service_probe: Workspace service probe for observability
        current_user: The current user, from which the tenant ID will be used to scope the service.

    Returns:
        WorkspaceService instance
    """
    return WorkspaceService(
        session=session,
        workspace_repository=workspace_repo,
        authz=authz,
        scope_to_tenant=current_user.tenant_id,
        probe=workspace_service_probe,
    )
