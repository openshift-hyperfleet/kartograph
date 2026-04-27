"""FastAPI dependency injection for KnowledgeGraphService.

Provides KnowledgeGraphService instances for route handlers
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
from management.application.observability import DefaultKnowledgeGraphServiceProbe
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.infrastructure.repositories import (
    DataSourceRepository,
    FernetSecretStore,
    KnowledgeGraphRepository,
)
from shared_kernel.authorization.protocols import AuthorizationProvider


def get_knowledge_graph_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> KnowledgeGraphService:
    """Get KnowledgeGraphService instance.

    Args:
        session: Async database session for transaction management
        authz: Authorization provider (SpiceDB client)
        current_user: The current user, from which tenant ID is extracted

    Returns:
        KnowledgeGraphService instance scoped to the current tenant
    """
    settings = get_management_settings()
    outbox = OutboxRepository(session=session)
    kg_repo = KnowledgeGraphRepository(session=session, outbox=outbox)
    ds_repo = DataSourceRepository(session=session, outbox=outbox)
    encryption_keys = settings.encryption_key.get_secret_value().split(",")
    secret_store = FernetSecretStore(
        session=session,
        encryption_keys=encryption_keys,
    )
    return KnowledgeGraphService(
        session=session,
        knowledge_graph_repository=kg_repo,
        data_source_repository=ds_repo,
        secret_store=secret_store,
        authz=authz,
        scope_to_tenant=current_user.tenant_id.value,
        probe=DefaultKnowledgeGraphServiceProbe(),
    )
