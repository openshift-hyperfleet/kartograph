"""FastAPI dependencies for maintenance pipeline orchestration."""

from __future__ import annotations

from typing import Annotated, Any, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.infrastructure.repositories.extraction_job_repository import (
    ExtractionJobRepository,
)
from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from infrastructure.management.maintenance_pipeline_service import (
    MaintenancePipelineService,
)
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.settings import get_management_settings, get_spicedb_settings
from management.infrastructure.git_commit_reference_service import (
    GitCommitReferenceService,
)
from management.infrastructure.git_diff_summary_service import GitDiffSummaryService
from management.infrastructure.repositories import (
    DataSourceRepository,
    DataSourceSyncRunRepository,
    FernetSecretStore,
    KnowledgeGraphRepository,
)
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.spicedb.client import SpiceDBClient


def _diff_summary_service_factory(
    secret_store: FernetSecretStore,
) -> Callable[[str], GitDiffSummaryService]:
    def factory(tenant_id: str) -> GitDiffSummaryService:
        return GitDiffSummaryService(
            credential_reader=secret_store,
            tenant_id=tenant_id,
        )

    return factory


def _commit_reference_service_factory(
    secret_store: FernetSecretStore,
) -> Callable[[str], GitCommitReferenceService]:
    def factory(tenant_id: str) -> GitCommitReferenceService:
        return GitCommitReferenceService(
            credential_reader=secret_store,
            tenant_id=tenant_id,
        )

    return factory


def build_maintenance_pipeline_for_background(
    *,
    session_factory: Any,
    session: AsyncSession,
) -> MaintenancePipelineService:
    """Construct a maintenance pipeline for scheduler background tasks."""
    settings = get_management_settings()
    outbox = OutboxRepository(session=session)
    secret_store = FernetSecretStore(
        session=session,
        encryption_keys=settings.encryption_key.get_secret_value().split(","),
    )
    spicedb_settings = get_spicedb_settings()
    authz = SpiceDBClient(
        endpoint=spicedb_settings.endpoint,
        preshared_key=spicedb_settings.preshared_key.get_secret_value(),
        use_tls=spicedb_settings.use_tls,
        cert_path=spicedb_settings.cert_path,
    )
    return MaintenancePipelineService(
        session=session,
        session_factory=session_factory,
        knowledge_graph_repository=KnowledgeGraphRepository(
            session=session, outbox=outbox
        ),
        data_source_repository=DataSourceRepository(session=session, outbox=outbox),
        sync_run_repository=DataSourceSyncRunRepository(session=session),
        extraction_job_repository=ExtractionJobRepository(session=session),
        authorization=authz,
        tenant_id="",
        diff_summary_service_factory=_diff_summary_service_factory(secret_store),
        commit_reference_service_factory=_commit_reference_service_factory(
            secret_store
        ),
    )


def get_maintenance_pipeline_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> MaintenancePipelineService:
    settings = get_management_settings()
    outbox = OutboxRepository(session=session)
    secret_store = FernetSecretStore(
        session=session,
        encryption_keys=settings.encryption_key.get_secret_value().split(","),
    )
    return MaintenancePipelineService(
        session=session,
        session_factory=request.app.state.write_sessionmaker,
        knowledge_graph_repository=KnowledgeGraphRepository(
            session=session, outbox=outbox
        ),
        data_source_repository=DataSourceRepository(session=session, outbox=outbox),
        sync_run_repository=DataSourceSyncRunRepository(session=session),
        extraction_job_repository=ExtractionJobRepository(session=session),
        authorization=authz,
        tenant_id=current_user.tenant_id.value,
        diff_summary_service_factory=_diff_summary_service_factory(secret_store),
        commit_reference_service_factory=_commit_reference_service_factory(
            secret_store
        ),
    )
