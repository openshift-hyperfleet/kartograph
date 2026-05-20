"""FastAPI dependencies for Extraction services."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.application import (
    ExtractionAgentSessionService,
    ExtractionSkillResolutionService,
)
from extraction.infrastructure.repositories import (
    ExtractionAgentSessionRepository,
    ExtractionSkillOverrideRepository,
)
from infrastructure.database.dependencies import get_write_session


def get_extraction_agent_session_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> ExtractionAgentSessionService:
    """Get ExtractionAgentSessionService instance."""
    skill_resolution_service = ExtractionSkillResolutionService(
        override_repository=ExtractionSkillOverrideRepository()
    )
    return ExtractionAgentSessionService(
        repository=ExtractionAgentSessionRepository(session=session),
        skill_resolution_service=skill_resolution_service,
    )

