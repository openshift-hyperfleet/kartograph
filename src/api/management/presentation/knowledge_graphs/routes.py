"""HTTP routes for Knowledge Graph management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.dependencies.knowledge_graph import get_knowledge_graph_service
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    UnauthorizedError,
)
from management.presentation.knowledge_graphs.models import (
    CreateKnowledgeGraphRequest,
    KnowledgeGraphListResponse,
    KnowledgeGraphResponse,
)

router = APIRouter(tags=["knowledge-graphs"])


@router.get(
    "/knowledge-graphs",
    status_code=status.HTTP_200_OK,
)
async def list_knowledge_graphs(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphListResponse:
    """List all knowledge graphs visible to the current user in their tenant.

    Returns knowledge graphs filtered by VIEW permission via SpiceDB.

    Args:
        current_user: Current authenticated user with tenant context
        service: Knowledge graph service for orchestration

    Returns:
        KnowledgeGraphListResponse with all viewable KGs

    Raises:
        HTTPException: 500 for unexpected errors
    """
    try:
        kgs = await service.list_all(user_id=current_user.user_id.value)
        return KnowledgeGraphListResponse(
            knowledge_graphs=[KnowledgeGraphResponse.from_domain(kg) for kg in kgs]
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list knowledge graphs",
        )


@router.get(
    "/knowledge-graphs/{kg_id}",
    status_code=status.HTTP_200_OK,
)
async def get_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Get a specific knowledge graph by ID.

    Returns the knowledge graph details for the given ID. Returns 404 if
    not found or if the user lacks VIEW permission (to prevent existence leakage).

    Args:
        kg_id: Knowledge Graph ID (ULID format)
        current_user: Current authenticated user with tenant context
        service: Knowledge graph service for orchestration

    Returns:
        KnowledgeGraphResponse with KG details

    Raises:
        HTTPException: 404 if KG not found or user lacks VIEW permission
        HTTPException: 500 for unexpected errors
    """
    try:
        kg = await service.get(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )

        if kg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge graph not found",
            )

        return KnowledgeGraphResponse.from_domain(kg)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge graph",
        )


@router.post(
    "/workspaces/{workspace_id}/knowledge-graphs",
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_graph(
    workspace_id: str,
    request: CreateKnowledgeGraphRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Create a new knowledge graph in a workspace.

    The current user must have EDIT permission on the target workspace.

    Args:
        workspace_id: The workspace to create the KG in
        request: Knowledge graph creation request (name, optional description)
        current_user: Current authenticated user with tenant context
        service: Knowledge graph service for orchestration

    Returns:
        KnowledgeGraphResponse with created KG details

    Raises:
        HTTPException: 403 if user lacks EDIT permission on the workspace
        HTTPException: 409 if a KG with this name already exists in the tenant
        HTTPException: 500 for unexpected errors
    """
    try:
        kg = await service.create(
            user_id=current_user.user_id.value,
            workspace_id=workspace_id,
            name=request.name,
            description=request.description,
        )
        return KnowledgeGraphResponse.from_domain(kg)

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except DuplicateKnowledgeGraphNameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A knowledge graph with this name already exists",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create knowledge graph",
        )
