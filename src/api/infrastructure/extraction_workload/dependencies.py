"""Dependencies for extraction workload HTTP endpoints."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from extraction.infrastructure.workload_credential_issuer import (
    ScopedWorkloadCredentialIssuer,
)
from extraction.infrastructure.workload_runtime_factory import (
    get_workload_credential_issuer,
)
from extraction.ports.workload_extraction_jobs import IWorkloadExtractionJobsService
from extraction.ports.workload_graph import IWorkloadGraphReader
from extraction.ports.workload_schema import IWorkloadSchemaService
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.extraction_workload.extraction_jobs_service import (
    GraphWorkloadExtractionJobsService,
)
from extraction.application.graph_management_session_journal import (
    GraphManagementSessionJournalService,
)
from extraction.infrastructure.repositories import ExtractionAgentSessionRepository
from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from infrastructure.extraction_workload.graph_mutation_writer import (
    GraphWorkloadGraphMutationWriter,
)
from infrastructure.extraction_workload.graph_reader import GraphWorkloadGraphReader
from infrastructure.extraction_workload.schema_service import GraphWorkloadSchemaService
from infrastructure.settings import get_database_settings
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.dependencies import get_write_session


@lru_cache
def _cached_workload_credential_issuer() -> ScopedWorkloadCredentialIssuer:
    return get_workload_credential_issuer()


def get_extraction_workload_credential_issuer() -> ScopedWorkloadCredentialIssuer:
    return _cached_workload_credential_issuer()


def get_workload_graph_reader(
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
) -> IWorkloadGraphReader:
    return GraphWorkloadGraphReader(pool=pool, settings=get_database_settings())


def get_graph_management_session_journal_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> GraphManagementSessionJournalService:
    return GraphManagementSessionJournalService(
        session_repository=ExtractionAgentSessionRepository(session=session),
        extraction_job_repository=ExtractionJobRepository(session=session),
    )


def get_workload_schema_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
) -> IWorkloadSchemaService:
    return GraphWorkloadSchemaService(
        session=session,
        mutation_writer=GraphWorkloadGraphMutationWriter(
            pool=pool,
            settings=get_database_settings(),
            session=session,
        ),
        graph_reader=GraphWorkloadGraphReader(
            pool=pool, settings=get_database_settings()
        ),
    )


def get_workload_extraction_jobs_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_write_session)],
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
) -> IWorkloadExtractionJobsService:
    return GraphWorkloadExtractionJobsService(
        session=session,
        connection_pool=pool,
        session_factory=request.app.state.write_sessionmaker,
    )
