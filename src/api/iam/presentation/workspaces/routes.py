"""Workspace management routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.application.services import WorkspaceService
from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from iam.dependencies.workspace import get_workspace_service
from iam.domain.value_objects import WorkspaceId
from iam.ports.exceptions import DuplicateWorkspaceNameError
from iam.presentation.workspaces.models import (
    CreateWorkspaceRequest,
    WorkspaceListResponse,
    WorkspaceResponse,
)

router = APIRouter(
    prefix="/workspaces",
    tags=["workspaces"],
)


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a child workspace",
    description="""
Create a new child workspace within your tenant.

The parent workspace must exist and belong to your tenant. Workspace names
must be unique within the tenant.
""",
    response_description="The created workspace with generated ID and timestamps",
    responses={
        201: {"description": "Workspace created successfully"},
        400: {"description": "Invalid parent workspace or validation error"},
        401: {"description": "Authentication required"},
        409: {"description": "Workspace name already exists in tenant"},
        500: {"description": "Internal server error"},
    },
)
async def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Create a new child workspace."""
    try:
        parent_id = WorkspaceId(request.parent_workspace_id)

        workspace = await service.create_workspace(
            name=request.name,
            parent_workspace_id=parent_id,
            creator_id=current_user.user_id,
        )

        return WorkspaceResponse.from_domain(workspace)

    except DuplicateWorkspaceNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace",
        )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get workspace by ID",
    description="""
Retrieve a workspace by its ID within the authenticated user's tenant.

Returns 404 if the workspace does not exist or belongs to a different tenant
(to avoid leaking existence of workspaces across tenant boundaries).
""",
    response_description="The workspace details including name, hierarchy, and timestamps",
    responses={
        200: {"description": "Workspace found and returned"},
        401: {"description": "Authentication required"},
        404: {"description": "Workspace not found or belongs to different tenant"},
        500: {"description": "Internal server error"},
    },
)
async def get_workspace(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Get workspace by ID."""
    try:
        workspace_id_obj = WorkspaceId(workspace_id)

        workspace = await service.get_workspace(workspace_id_obj)

        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace {workspace_id} not found",
            )

        return WorkspaceResponse.from_domain(workspace)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workspace",
        )


@router.get(
    "",
    response_model=WorkspaceListResponse,
    summary="List workspaces",
    description="""
List all workspaces within the authenticated user's tenant.

Returns all workspaces the user has access to, including the root workspace
and any child workspaces. Results are scoped to the user's tenant.
""",
    response_description="List of workspaces with total count",
    responses={
        200: {"description": "Workspaces listed successfully"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def list_workspaces(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceListResponse:
    """List all workspaces in user's tenant.

    Returns all workspaces the user has access to within their tenant.
    In Phase 1, this returns all workspaces without user-level permission filtering.

    Returns:
        200 OK with list of workspaces and count
    """
    try:
        workspaces = await service.list_workspaces()

        workspace_responses = [
            WorkspaceResponse.from_domain(workspace) for workspace in workspaces
        ]

        return WorkspaceListResponse(
            workspaces=workspace_responses,
            count=len(workspace_responses),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workspaces",
        )


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a workspace",
    description="""
Delete a workspace from the authenticated user's tenant.

The root workspace cannot be deleted. Workspaces with child workspaces
cannot be deleted until all children are removed first.
""",
    response_description="No content returned on successful deletion",
    responses={
        204: {"description": "Workspace deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Workspace belongs to different tenant"},
        404: {"description": "Workspace not found"},
        409: {"description": "Cannot delete root workspace or workspace with children"},
        500: {"description": "Internal server error"},
    },
)
async def delete_workspace(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Delete a workspace."""
    # TODO: Implement in next task
    raise NotImplementedError()
