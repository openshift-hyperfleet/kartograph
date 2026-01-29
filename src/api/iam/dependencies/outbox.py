from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository


def get_outbox_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> OutboxRepository:
    """Get OutboxRepository instance.

    The repository accepts pre-serialized payloads, making it context-agnostic.
    Serialization is handled by the bounded context's repository.

    Args:
        session: Async database session (shared with calling repository)

    Returns:
        OutboxRepository instance
    """
    return OutboxRepository(session=session)
