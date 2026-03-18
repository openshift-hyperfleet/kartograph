"""Knowledge graph management routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.dependencies.knowledge_graph import get_knowledge_graph_service
from management.domain.exceptions import InvalidKnowledgeGraphNameError
from management.ports.exceptions import (
    DuplicateKnowledgeGraphNameError,
    UnauthorizedError,
)
from management.presentation.knowledge_graphs.models import (
    CreateKnowledgeGraphRequest,
    KnowledgeGraphListResponse,
    KnowledgeGraphResponse,
    UpdateKnowledgeGraphRequest,
)

router = APIRouter(tags=["Knowledge Graphs"])


@router.post(
    "/workspaces/{workspace_id}/knowledge-graphs",
    response_model=KnowledgeGraphResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a knowledge graph",
)
async def create_knowledge_graph(
    workspace_id: str,
    request: CreateKnowledgeGraphRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Create a new knowledge graph in a workspace."""
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
    except (InvalidKnowledgeGraphNameError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/workspaces/{workspace_id}/knowledge-graphs",
    response_model=KnowledgeGraphListResponse,
    summary="List knowledge graphs in a workspace",
)
async def list_knowledge_graphs(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> KnowledgeGraphListResponse:
    """List knowledge graphs in a workspace with pagination."""
    try:
        all_kgs = await service.list_for_workspace(
            user_id=current_user.user_id.value,
            workspace_id=workspace_id,
        )
        total = len(all_kgs)
        paginated = all_kgs[offset : offset + limit]
        return KnowledgeGraphListResponse(
            items=[KnowledgeGraphResponse.from_domain(kg) for kg in paginated],
            total=total,
            offset=offset,
            limit=limit,
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


@router.get(
    "/knowledge-graphs/{kg_id}",
    response_model=KnowledgeGraphResponse,
    summary="Get a knowledge graph by ID",
)
async def get_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Get a knowledge graph by ID."""
    try:
        kg = await service.get(user_id=current_user.user_id.value, kg_id=kg_id)
        if kg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge graph not found",
            )
        return KnowledgeGraphResponse.from_domain(kg)
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


@router.patch(
    "/knowledge-graphs/{kg_id}",
    response_model=KnowledgeGraphResponse,
    summary="Update a knowledge graph",
)
async def update_knowledge_graph(
    kg_id: str,
    request: UpdateKnowledgeGraphRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Update a knowledge graph's metadata."""
    try:
        kg = await service.update(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
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
    except (InvalidKnowledgeGraphNameError, ValueError) as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge graph not found",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )


@router.delete(
    "/knowledge-graphs/{kg_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a knowledge graph",
)
async def delete_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> None:
    """Delete a knowledge graph."""
    try:
        result = await service.delete(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge graph not found",
            )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete knowledge graph",
        )
