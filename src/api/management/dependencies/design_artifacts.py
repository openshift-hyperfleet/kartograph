"""Dependencies for design artifact endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.management.design_artifacts_service import DesignArtifactsService
from management.dependencies.knowledge_graph import get_knowledge_graph_service
from management.application.services.knowledge_graph_service import KnowledgeGraphService


def get_design_artifacts_service(
    kg_service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DesignArtifactsService:
    return DesignArtifactsService(
        knowledge_graph_service=kg_service,
        connection_pool=pool,
        tenant_id=current_user.tenant_id.value,
    )
