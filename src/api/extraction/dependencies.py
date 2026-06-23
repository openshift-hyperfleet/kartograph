"""FastAPI dependencies for Extraction services."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.application import (
    ExtractionAgentSessionService,
    ExtractionChatTurnService,
    ExtractionSkillResolutionService,
)
from extraction.application.graph_management_session_journal import (
    GraphManagementSessionJournalService,
)
from extraction.application.sticky_session_runtime_service import (
    StickySessionRuntimeService,
)
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from extraction.infrastructure.sticky_runtime_health import StickyRuntimeHealthChecker
from extraction.infrastructure.ingestion_readiness_reader import (
    SqlIngestionReadinessReader,
)
from infrastructure.job_packages.archive_hydrator import JobPackageArchiveHydrator
from extraction.infrastructure.prepared_job_package_reader import (
    SqlPreparedJobPackageReader,
)
from extraction.infrastructure.repositories import (
    ExtractionAgentSessionRepository,
    ExtractionSessionRunMetricsReader,
    ExtractionSkillOverrideRepository,
)
from extraction.infrastructure.sticky_session_bootstrap_builder import (
    StickySessionBootstrapBuilder,
)
from extraction.infrastructure.sticky_session_workdir_materializer import (
    StickySessionWorkdirMaterializer,
)
from extraction.infrastructure.workload_runtime_factory import (
    create_ephemeral_extraction_worker_launcher,
    create_extraction_chat_agent,
    create_sticky_session_runtime_manager,
    get_workload_credential_issuer,
)
from datetime import timedelta

from extraction.infrastructure.workload_runtime_settings import (
    get_extraction_workload_runtime_settings,
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


def _build_extraction_agent_session_service(
    session: AsyncSession,
    *,
    sticky_runtime_manager: IStickySessionRuntimeManager | None = None,
) -> ExtractionAgentSessionService:
    runtime_settings = get_extraction_workload_runtime_settings()
    skill_resolution_service = ExtractionSkillResolutionService(
        override_repository=ExtractionSkillOverrideRepository()
    )
    return ExtractionAgentSessionService(
        repository=ExtractionAgentSessionRepository(session=session),
        skill_resolution_service=skill_resolution_service,
        run_metrics_reader=ExtractionSessionRunMetricsReader(session=session),
        sticky_runtime_manager=sticky_runtime_manager,
        session_journal_service=GraphManagementSessionJournalService(
            session_repository=ExtractionAgentSessionRepository(session=session),
            extraction_job_repository=ExtractionJobRepository(session=session),
        ),
        idle_session_ttl=timedelta(minutes=runtime_settings.session_ttl_minutes),
    )


def get_extraction_agent_session_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> ExtractionAgentSessionService:
    """Get ExtractionAgentSessionService for read/create session routes."""
    return _build_extraction_agent_session_service(session)


def get_extraction_agent_session_service_with_runtime(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    sticky_runtime_manager: Annotated[
        IStickySessionRuntimeManager, Depends(get_sticky_session_runtime_manager)
    ],
) -> ExtractionAgentSessionService:
    """Get ExtractionAgentSessionService for routes that reset sticky containers."""
    return _build_extraction_agent_session_service(
        session,
        sticky_runtime_manager=sticky_runtime_manager,
    )


def get_extraction_chat_turn_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    sticky_runtime_manager: Annotated[
        IStickySessionRuntimeManager, Depends(get_sticky_session_runtime_manager)
    ],
) -> ExtractionChatTurnService:
    """Get ExtractionChatTurnService instance."""
    runtime_settings = get_extraction_workload_runtime_settings()
    skill_resolution_service = ExtractionSkillResolutionService(
        override_repository=ExtractionSkillOverrideRepository()
    )
    session_service = _build_extraction_agent_session_service(
        session,
        sticky_runtime_manager=sticky_runtime_manager,
    )
    bootstrap_builder = StickySessionBootstrapBuilder(
        credential_issuer=get_workload_credential_issuer(),
        prepared_job_package_reader=SqlPreparedJobPackageReader(
            session=session,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        ),
        workdir_materializer=StickySessionWorkdirMaterializer(
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
            container_run_uid=runtime_settings.container_run_uid,
            container_run_gid=runtime_settings.container_run_gid,
        ),
        runtime_settings=runtime_settings,
        archive_hydrator=JobPackageArchiveHydrator(
            session=session,
            job_package_work_dir=Path(runtime_settings.job_package_work_dir),
        ),
    )
    runtime_service = StickySessionRuntimeService(
        session_service=session_service,
        skill_resolution_service=skill_resolution_service,
        ingestion_readiness_reader=SqlIngestionReadinessReader(
            session=session,
            job_package_work_dir_path=Path(runtime_settings.job_package_work_dir),
        ),
        sticky_runtime_manager=sticky_runtime_manager,
        bootstrap_builder=bootstrap_builder,
        health_checker=StickyRuntimeHealthChecker(),
        runtime_backend=runtime_settings.backend,
        sticky_health_timeout_seconds=runtime_settings.sticky_health_timeout_seconds,
    )
    return ExtractionChatTurnService(
        session_service=session_service,
        runtime_service=runtime_service,
        chat_agent=create_extraction_chat_agent(runtime_settings),
        credential_issuer=get_workload_credential_issuer(),
    )
