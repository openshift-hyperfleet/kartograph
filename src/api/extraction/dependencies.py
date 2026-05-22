"""FastAPI dependencies for Extraction services."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.application import (
    ExtractionAgentSessionService,
    ExtractionSkillResolutionService,
)
from extraction.infrastructure.repositories import (
    ExtractionAgentSessionRepository,
    ExtractionSessionRunMetricsReader,
    ExtractionSkillOverrideRepository,
)
from extraction.infrastructure.workload_runtime_factory import (
    create_ephemeral_extraction_worker_launcher,
    create_sticky_session_runtime_manager,
)
from extraction.ports.runtime import (
    IEphemeralExtractionWorkerLauncher,
    IStickySessionRuntimeManager,
)
from infrastructure.database.dependencies import get_write_session


@lru_cache
def get_sticky_session_runtime_manager() -> IStickySessionRuntimeManager:
    """Return configured sticky session runtime manager."""
    return create_sticky_session_runtime_manager()


@lru_cache
def get_ephemeral_extraction_worker_launcher() -> IEphemeralExtractionWorkerLauncher:
    """Return configured ephemeral extraction worker launcher."""
    return create_ephemeral_extraction_worker_launcher()


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
        run_metrics_reader=ExtractionSessionRunMetricsReader(session=session),
    )
