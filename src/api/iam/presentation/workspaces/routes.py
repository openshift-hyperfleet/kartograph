"""Workspace management routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.application.services import WorkspaceService
from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from iam.dependencies.workspace import get_workspace_service
from iam.domain.value_objects import MemberType, WorkspaceId
from iam.ports.exceptions import (
    CannotDeleteRootWorkspaceError,
    DuplicateWorkspaceNameError,
    UnauthorizedError,
    WorkspaceHasChildrenError,
)
from iam.presentation.workspaces.models import (
    AddWorkspaceMemberRequest,
    CreateWorkspaceRequest,
    MemberTypeEnum,
    UpdateWorkspaceMemberRoleRequest,
    UpdateWorkspaceRequest,
    WorkspaceListResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceRoleEnum,
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
        parent_id = WorkspaceId.from_string(request.parent_workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid parent workspace ID format",
        )

    try:
        workspace = await service.create_workspace(
            name=request.name,
            parent_workspace_id=parent_id,
            creator_id=current_user.user_id,
        )

        return WorkspaceResponse.from_domain(workspace)

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create workspace under this parent",
        )
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
        workspace_id_obj = WorkspaceId.from_string(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    try:
        workspace = await service.get_workspace(
            workspace_id_obj, user_id=current_user.user_id
        )

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

    Returns workspaces the user has VIEW permission on within their tenant.
    Filtered via SpiceDB lookup_resources for authorization enforcement.

    Returns:
        200 OK with list of workspaces and count
    """
    try:
        workspaces = await service.list_workspaces(user_id=current_user.user_id)

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
    """Delete a workspace.

    Deletes a workspace from the user's tenant. Cannot delete root workspace
    or workspace with children.

    Returns:
        204 No Content on success

    Raises:
        403 Forbidden: Workspace belongs to different tenant
        404 Not Found: Workspace doesn't exist
        409 Conflict: Cannot delete root workspace or workspace with children
    """
    try:
        workspace_id_obj = WorkspaceId.from_string(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    try:
        result = await service.delete_workspace(
            workspace_id_obj, user_id=current_user.user_id
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace {workspace_id} not found",
            )

        return None

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete workspace",
        )
    except CannotDeleteRootWorkspaceError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except WorkspaceHasChildrenError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except UnauthorizedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workspace",
        )


@router.post(
    "/{workspace_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=WorkspaceMemberResponse,
    summary="Add member to workspace",
    description="""
Add a user or group as a member of a workspace with a specific role.

Requires MANAGE permission on the workspace.
""",
    response_description="The added member details",
    responses={
        201: {"description": "Member successfully added to workspace"},
        400: {"description": "Invalid workspace ID, member ID, or validation error"},
        403: {"description": "Insufficient permissions to manage workspace members"},
        404: {"description": "Workspace not found"},
        500: {"description": "Internal server error"},
    },
)
async def add_workspace_member(
    workspace_id: str,
    request: AddWorkspaceMemberRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceMemberResponse:
    """Add a member (user or group) to a workspace.

    Requires MANAGE permission on the workspace.
    """
    # Validate workspace ID format
    try:
        workspace_id_obj = WorkspaceId.from_string(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    try:
        await service.add_member(
            workspace_id=workspace_id_obj,
            acting_user_id=current_user.user_id,
            member_id=request.member_id,
            member_type=request.to_domain_member_type(),
            role=request.to_domain_role(),
        )

        return WorkspaceMemberResponse(
            member_id=request.member_id,
            member_type=request.member_type,
            role=request.role,
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage workspace members",
        )
    except (ValueError, TypeError) as e:
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
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace belongs to different tenant",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member to workspace",
        )


@router.get(
    "/{workspace_id}/members",
    status_code=status.HTTP_200_OK,
    response_model=list[WorkspaceMemberResponse],
    summary="List workspace members",
    description="""
List all members (users and groups) with access to a workspace.

Requires VIEW permission on the workspace.
""",
    response_description="List of workspace members with their roles",
    responses={
        200: {"description": "List of workspace members"},
        400: {"description": "Invalid workspace ID format"},
        403: {"description": "Insufficient permissions to view workspace members"},
        500: {"description": "Internal server error"},
    },
)
async def list_workspace_members(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> list[WorkspaceMemberResponse]:
    """List all members of a workspace.

    Requires VIEW permission on the workspace.
    """
    # Validate workspace ID format
    try:
        workspace_id_obj = WorkspaceId.from_string(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    try:
        members = await service.list_members(
            workspace_id=workspace_id_obj,
            user_id=current_user.user_id,
        )

        return [WorkspaceMemberResponse.from_grant(grant) for grant in members]

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view workspace members",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workspace members",
        )


@router.delete(
    "/{workspace_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from workspace",
    description="""
Revoke a user's or group's access to a workspace.

Requires MANAGE permission on the workspace.

Note: The member_type query parameter is required to distinguish between
user and group members with the same ID.
""",
    response_description="No content returned on successful removal",
    responses={
        204: {"description": "Member successfully removed from workspace"},
        400: {"description": "Invalid workspace ID, member ID, or member_type"},
        403: {"description": "Insufficient permissions to manage workspace members"},
        404: {"description": "Workspace not found or member not found"},
        500: {"description": "Internal server error"},
    },
)
async def remove_workspace_member(
    workspace_id: str,
    member_id: str,
    member_type: MemberTypeEnum,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> None:
    """Remove a member from a workspace.

    Requires MANAGE permission on the workspace.
    """
    # Validate workspace ID format
    try:
        workspace_id_obj = WorkspaceId.from_string(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    try:
        domain_member_type = MemberType(member_type.value)

        await service.remove_member(
            workspace_id=workspace_id_obj,
            acting_user_id=current_user.user_id,
            member_id=member_id,
            member_type=domain_member_type,
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage workspace members",
        )
    except (ValueError, TypeError, RuntimeError) as e:
        # Distinguish workspace not found (404) from member not found (400)
        error_msg = str(e)
        if "Workspace" in error_msg and "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace belongs to different tenant",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member from workspace",
        )


@router.patch(
    "/{workspace_id}/members/{member_id}",
    status_code=status.HTTP_200_OK,
    response_model=WorkspaceMemberResponse,
    summary="Update workspace member role",
    description="""
Update a member's role in a workspace.

Requires MANAGE permission on the workspace.

Note: The member_type query parameter is required to distinguish between
user and group members with the same ID.
""",
    response_description="Updated member details",
    responses={
        200: {"description": "Member role updated successfully"},
        400: {"description": "Invalid workspace ID, member ID, or role unchanged"},
        403: {"description": "Insufficient permissions to manage workspace members"},
        404: {"description": "Workspace not found or member not found"},
        422: {"description": "Validation error in request body"},
        500: {"description": "Internal server error"},
    },
)
async def update_workspace_member_role(
    workspace_id: str,
    member_id: str,
    member_type: MemberTypeEnum,
    request: UpdateWorkspaceMemberRoleRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceMemberResponse:
    """Update a workspace member's role.

    Requires MANAGE permission on the workspace.
    """
    # Validate workspace ID format
    try:
        workspace_id_obj = WorkspaceId.from_string(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    try:
        domain_member_type = MemberType(member_type.value)

        await service.update_member_role(
            workspace_id=workspace_id_obj,
            acting_user_id=current_user.user_id,
            member_id=member_id,
            member_type=domain_member_type,
            new_role=request.to_domain_role(),
        )

        return WorkspaceMemberResponse(
            member_id=member_id,
            member_type=MemberTypeEnum(member_type.value),
            role=WorkspaceRoleEnum(request.role.value),
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage workspace members",
        )
    except (ValueError, TypeError, RuntimeError) as e:
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
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace belongs to different tenant",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update member role",
        )


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace",
    description="""
Update workspace metadata (currently just name).

Requires MANAGE permission on the workspace.
""",
    response_description="Updated workspace details",
    responses={
        200: {"description": "Workspace updated successfully"},
        400: {"description": "Invalid workspace ID or name"},
        403: {"description": "Insufficient permissions to manage workspace"},
        404: {"description": "Workspace not found"},
        409: {"description": "Workspace name already exists in tenant"},
        500: {"description": "Internal server error"},
    },
)
async def update_workspace(
    workspace_id: str,
    request: UpdateWorkspaceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WorkspaceService, Depends(get_workspace_service)],
) -> WorkspaceResponse:
    """Update a workspace's metadata."""
    try:
        workspace_id_obj = WorkspaceId.from_string(workspace_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format",
        )

    try:
        workspace = await service.update_workspace(
            workspace_id=workspace_id_obj,
            user_id=current_user.user_id,
            name=request.name,
        )

        return WorkspaceResponse.from_domain(workspace)

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage workspace",
        )
    except DuplicateWorkspaceNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except (ValueError, TypeError) as e:
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
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace belongs to different tenant",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workspace",
        )
