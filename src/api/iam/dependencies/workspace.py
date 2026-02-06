"""FastAPI dependency injection for workspace repository.

Provides workspace repository instances for route handlers
using FastAPI's dependency injection system.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.dependencies.outbox import get_outbox_repository
from iam.infrastructure.workspace_repository import WorkspaceRepository
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository


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
