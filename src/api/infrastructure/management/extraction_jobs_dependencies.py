"""Dependencies for extraction job endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.database.dependencies import get_write_session
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.management.extraction_jobs_service import ExtractionJobsService
from infrastructure.outbox.repository import OutboxRepository
from management.application.services.knowledge_graph_service import KnowledgeGraphService
from management.dependencies.knowledge_graph import get_knowledge_graph_service
from management.infrastructure.repositories.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)


def get_write_sessionmaker(request: Request):
    return request.app.state.write_sessionmaker


def get_extraction_jobs_service(
    request: Request,
    kg_service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
    session: Annotated[AsyncSession, Depends(get_write_session)],
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ExtractionJobsService:
    outbox = OutboxRepository(session=session)
    kg_repo = KnowledgeGraphRepository(session=session, outbox=outbox)
    job_repo = ExtractionJobRepository(session=session)
    return ExtractionJobsService(
        knowledge_graph_service=kg_service,
        knowledge_graph_repository=kg_repo,
        extraction_job_repository=job_repo,
        connection_pool=pool,
        tenant_id=current_user.tenant_id.value,
        session=session,
        session_factory=get_write_sessionmaker(request),
    )
