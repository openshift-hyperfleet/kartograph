"""FastAPI dependencies for Extraction services."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.application import (
    ExtractionAgentSessionService,
    ExtractionChatTurnService,
    ExtractionSkillResolutionService,
)
from extraction.infrastructure.deterministic_chat_agent import DeterministicExtractionChatAgent
from extraction.infrastructure.ingestion_readiness_reader import SqlIngestionReadinessReader
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
    sticky_runtime_manager: Annotated[
        IStickySessionRuntimeManager, Depends(get_sticky_session_runtime_manager)
    ],
) -> ExtractionAgentSessionService:
    """Get ExtractionAgentSessionService instance."""
    skill_resolution_service = ExtractionSkillResolutionService(
        override_repository=ExtractionSkillOverrideRepository()
    )
    return ExtractionAgentSessionService(
        repository=ExtractionAgentSessionRepository(session=session),
        skill_resolution_service=skill_resolution_service,
        run_metrics_reader=ExtractionSessionRunMetricsReader(session=session),
        sticky_runtime_manager=sticky_runtime_manager,
    )


def get_extraction_chat_turn_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    sticky_runtime_manager: Annotated[
        IStickySessionRuntimeManager, Depends(get_sticky_session_runtime_manager)
    ],
) -> ExtractionChatTurnService:
    """Get ExtractionChatTurnService instance."""
    skill_resolution_service = ExtractionSkillResolutionService(
        override_repository=ExtractionSkillOverrideRepository()
    )
    session_service = ExtractionAgentSessionService(
        repository=ExtractionAgentSessionRepository(session=session),
        skill_resolution_service=skill_resolution_service,
        run_metrics_reader=ExtractionSessionRunMetricsReader(session=session),
        sticky_runtime_manager=sticky_runtime_manager,
    )
    return ExtractionChatTurnService(
        session_service=session_service,
        skill_resolution_service=skill_resolution_service,
        ingestion_readiness_reader=SqlIngestionReadinessReader(session=session),
        sticky_runtime_manager=sticky_runtime_manager,
        chat_agent=DeterministicExtractionChatAgent(),
    )
