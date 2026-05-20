"""FastAPI dependencies for Extraction services."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.application import ExtractionAgentSessionService
from extraction.infrastructure.repositories import ExtractionAgentSessionRepository
from infrastructure.database.dependencies import get_write_session


def get_extraction_agent_session_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> ExtractionAgentSessionService:
    """Get ExtractionAgentSessionService instance."""
    return ExtractionAgentSessionService(
        repository=ExtractionAgentSessionRepository(session=session)
    )

