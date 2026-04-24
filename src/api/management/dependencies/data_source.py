"""FastAPI dependency injection for DataSourceService.

Provides DataSourceService instances for route handlers
using FastAPI's dependency injection system.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.settings import get_management_settings
from management.application.observability import DefaultDataSourceServiceProbe
from management.application.services.data_source_service import DataSourceService
from management.infrastructure.repositories import (
    DataSourceRepository,
    DataSourceSyncRunRepository,
    FernetSecretStore,
    KnowledgeGraphRepository,
)
from shared_kernel.authorization.protocols import AuthorizationProvider


def get_sync_run_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> DataSourceSyncRunRepository:
    """Get DataSourceSyncRunRepository instance.

    Provides direct repository access for listing sync runs on a data source.
    Authorization is enforced by the route handler before calling this repository.

    Args:
        session: Async database session

    Returns:
        DataSourceSyncRunRepository instance
    """
    return DataSourceSyncRunRepository(session=session)


def get_data_source_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DataSourceService:
    """Get DataSourceService instance.

    Args:
        session: Async database session for transaction management
        authz: Authorization provider (SpiceDB client)
        current_user: The current user, from which tenant ID is extracted

    Returns:
        DataSourceService instance scoped to the current tenant
    """
    settings = get_management_settings()
    outbox = OutboxRepository(session=session)
    ds_repo = DataSourceRepository(session=session, outbox=outbox)
    kg_repo = KnowledgeGraphRepository(session=session, outbox=outbox)
    encryption_keys = settings.encryption_key.get_secret_value().split(",")
    secret_store = FernetSecretStore(
        session=session,
        encryption_keys=encryption_keys,
    )
    sync_run_repo = DataSourceSyncRunRepository(session=session)
    return DataSourceService(
        session=session,
        data_source_repository=ds_repo,
        knowledge_graph_repository=kg_repo,
        secret_store=secret_store,
        sync_run_repository=sync_run_repo,
        authz=authz,
        scope_to_tenant=current_user.tenant_id.value,
        probe=DefaultDataSourceServiceProbe(),
    )
