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


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Create a new child workspace.

    Creates a workspace within the user's tenant. The parent workspace must
    exist and belong to the same tenant.

    Args:
        request: Workspace creation request with name and parent ID
        current_user: Current authenticated user
        service: Workspace service, tenant scoped

    Returns:
        201 Created with workspace details

    Raises:
        HTTPException: 400 Bad Request if invalid parent workspace
        HTTPException: 409 Conflict if workspace name already exists in tenant
        HTTPException: 500 Internal Server Error for unexpected errors
    """
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


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Get workspace by ID.

    Retrieves a workspace within the user's tenant.

    Args:
        workspace_id: Workspace ID (ULID format)
        current_user: Current authenticated user with tenant context
        service: Workspace service

    Returns:
        200 OK with workspace details

    Raises:
        HTTPException: 400 Bad Request if workspace ID is invalid
        HTTPException: 404 Not Found if workspace doesn't exist or belongs to different tenant
        HTTPException: 500 Internal Server Error for unexpected errors
    """
    # TODO: Implement in next task
    raise NotImplementedError()


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceListResponse:
    """List all workspaces in user's tenant.

    Returns all workspaces the user has access to within their tenant.

    Args:
        current_user: Current authenticated user with tenant context
        service: Workspace service, tenant scoped

    Returns:
        200 OK with list of workspaces and count
    """
    # TODO: Implement in next task
    raise NotImplementedError()


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Delete a workspace.

    Deletes a workspace from the user's tenant. Cannot delete root workspace
    or workspace with children.

    Args:
        workspace_id: Workspace ID (ULID format)
        current_user: Current authenticated user
        service: Workspace service, tenant scoped

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 403 Forbidden if workspace belongs to different tenant
        HTTPException: 404 Not Found if workspace doesn't exist
        HTTPException: 409 Conflict if cannot delete root workspace or workspace with children
        HTTPException: 500 Internal Server Error for unexpected errors
    """
    # TODO: Implement in next task
    raise NotImplementedError()
