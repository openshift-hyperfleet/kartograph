"""Knowledge Graph management routes.

Implements the REST API for the Knowledge Graph resource in the Management
bounded context. Follows the API conventions spec:
- Scoped creation/listing: POST/GET /management/workspaces/{ws_id}/knowledge-graphs
- Flat retrieval, update, delete: GET/PATCH/DELETE /management/knowledge-graphs/{id}
"""

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
    UpdateKnowledgeGraphRequest,
)

router = APIRouter(tags=["knowledge-graphs"])


@router.post(
    "/workspaces/{workspace_id}/knowledge-graphs",
    response_model=KnowledgeGraphResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a knowledge graph",
    description="""
Create a new knowledge graph within a workspace.

Requires `edit` permission on the workspace. Knowledge graph names must be
unique within the tenant.
""",
    response_description="The created knowledge graph with generated ID and timestamps",
    responses={
        201: {"description": "Knowledge graph created successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the workspace"},
        409: {"description": "Knowledge graph name already exists in tenant"},
        422: {"description": "Validation error — name empty or exceeds 100 characters"},
        500: {"description": "Internal server error"},
    },
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
    except DuplicateKnowledgeGraphNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create knowledge graph",
        )


@router.get(
    "/knowledge-graphs/{kg_id}",
    response_model=KnowledgeGraphResponse,
    summary="Get knowledge graph by ID",
    description="""
Retrieve a knowledge graph by its ID.

Returns 404 if the knowledge graph does not exist or if the caller lacks `view`
access — no distinction is made to avoid leaking resource existence.
""",
    response_description="Knowledge graph details including name, workspace, and timestamps",
    responses={
        200: {"description": "Knowledge graph found and returned"},
        401: {"description": "Authentication required"},
        404: {"description": "Knowledge graph not found or caller lacks view access"},
        500: {"description": "Internal server error"},
    },
)
async def get_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphResponse:
    """Get a knowledge graph by ID."""
    try:
        kg = await service.get(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )

        if kg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge graph {kg_id} not found",
            )

        return KnowledgeGraphResponse.from_domain(kg)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve knowledge graph",
        )


@router.get(
    "/workspaces/{workspace_id}/knowledge-graphs",
    response_model=KnowledgeGraphListResponse,
    summary="List knowledge graphs in a workspace",
    description="""
List all knowledge graphs within a workspace that the caller can view.

Requires `view` permission on the workspace. Results are filtered by
authorization — only knowledge graphs the caller can access are returned.
""",
    response_description="List of knowledge graphs with total count",
    responses={
        200: {"description": "Knowledge graphs listed successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the workspace"},
        500: {"description": "Internal server error"},
    },
)
async def list_knowledge_graphs(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> KnowledgeGraphListResponse:
    """List knowledge graphs in a workspace."""
    try:
        kgs = await service.list_for_workspace(
            user_id=current_user.user_id.value,
            workspace_id=workspace_id,
        )

        kg_responses = [KnowledgeGraphResponse.from_domain(kg) for kg in kgs]
        return KnowledgeGraphListResponse(
            knowledge_graphs=kg_responses,
            count=len(kg_responses),
        )

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list knowledge graphs",
        )


@router.patch(
    "/knowledge-graphs/{kg_id}",
    response_model=KnowledgeGraphResponse,
    summary="Update knowledge graph metadata",
    description="""
Update the name and/or description of a knowledge graph.

Requires `edit` permission on the knowledge graph. The new name must be
unique within the tenant.
""",
    response_description="Updated knowledge graph details",
    responses={
        200: {"description": "Knowledge graph updated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the knowledge graph"},
        404: {"description": "Knowledge graph not found"},
        409: {"description": "Knowledge graph name already exists in tenant"},
        422: {"description": "Validation error — name empty or exceeds 100 characters"},
        500: {"description": "Internal server error"},
    },
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
    except DuplicateKnowledgeGraphNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update knowledge graph",
        )


@router.delete(
    "/knowledge-graphs/{kg_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a knowledge graph",
    description="""
Delete a knowledge graph and cascade-delete all of its data sources.

Requires `manage` permission on the knowledge graph. The deletion is atomic:
all data sources are removed along with the knowledge graph and all
authorization relationships in a single transaction.
""",
    response_description="No content returned on successful deletion",
    responses={
        204: {"description": "Knowledge graph deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions on the knowledge graph"},
        404: {"description": "Knowledge graph not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_knowledge_graph_service)],
) -> None:
    """Delete a knowledge graph and cascade-delete its data sources."""
    try:
        deleted = await service.delete(
            user_id=current_user.user_id.value,
            kg_id=kg_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge graph {kg_id} not found",
            )

        return None

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
