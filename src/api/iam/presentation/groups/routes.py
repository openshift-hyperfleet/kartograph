"""HTTP routes for group management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.dependencies.group import get_group_service
from iam.dependencies.user import get_current_user
from iam.application.services import GroupService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import GroupId, UserId
from iam.ports.exceptions import DuplicateGroupNameError
from iam.presentation.groups.models import (
    AddGroupMemberRequest,
    CreateGroupRequest,
    GroupMemberResponse,
    GroupResponse,
    UpdateGroupMemberRoleRequest,
    UpdateGroupRequest,
)

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
)


@router.get(
    "",
    response_model=list[GroupResponse],
    summary="List groups",
    description="List all groups in the authenticated user's tenant",
    responses={
        200: {"description": "Groups listed successfully"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def list_groups(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> list[GroupResponse]:
    """List all groups in user's tenant."""
    try:
        groups = await service.list_groups(user_id=current_user.user_id)
        return [GroupResponse.from_domain(group) for group in groups]

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list groups",
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_group(
    request: CreateGroupRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupResponse:
    """Create a new group with authenticated user as admin.

    The authenticated user (from headers/JWT) will be the creator and
    initial admin of the group. Tenant ID comes from auth context.

    Args:
        request: Group creation request (just name)
        current_user: Current authenticated user
        service: Group service, tenant scoped

    Returns:
        GroupResponse with created group details

    Raises:
        HTTPException: 409 if group name already exists in tenant
        HTTPException: 500 for unexpected errors
    """
    try:
        group = await service.create_group(
            name=request.name,
            creator_id=current_user.user_id,
        )
        return GroupResponse.from_domain(group)

    except DuplicateGroupNameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A group with this name already exists",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create group",
        )


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupResponse:
    """Get group by ID with tenant isolation.

    Requires authentication. Service verifies group belongs to authenticated
    user's tenant via SpiceDB.

    Args:
        group_id: Group ID (ULID format)
        current_user: Current authenticated user with tenant context
        service: Group service

    Returns:
        GroupResponse with group details and members

    Raises:
        HTTPException: 400 if group ID is invalid
        HTTPException: 404 if group not found or not accessible in tenant
        HTTPException: 500 for unexpected errors
    """
    try:
        group_id_obj = GroupId.from_string(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format",
        )

    try:
        group = await service.get_group(group_id=group_id_obj)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found",
            )
        return GroupResponse.from_domain(group)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve group",
        )


@router.patch(
    "/{group_id}",
    response_model=GroupResponse,
    summary="Update group",
    description="Update group metadata (currently just name). Requires MANAGE permission.",
    responses={
        200: {"description": "Group updated successfully"},
        400: {"description": "Invalid group ID or name"},
        403: {"description": "Insufficient permissions to manage group"},
        409: {"description": "Group name already exists in tenant"},
        500: {"description": "Internal server error"},
    },
)
async def update_group(
    group_id: str,
    request: UpdateGroupRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupResponse:
    """Update a group's metadata."""
    try:
        group_id_obj = GroupId.from_string(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format",
        )

    try:
        group = await service.update_group(
            group_id=group_id_obj,
            user_id=current_user.user_id,
            name=request.name,
        )

        return GroupResponse.from_domain(group)

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage group",
        )
    except DuplicateGroupNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update group",
        )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> None:
    """Delete a group.

    Args:
        group_id: Group ID (ULID format)
        current_user: Current authenticated user
        service: Group service, tenant scoped

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException: 400 if group ID is invalid
        HTTPException: 404 if group not found
        HTTPException: 500 for unexpected errors
    """
    try:
        group_id_obj = GroupId.from_string(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format",
        )

    try:
        deleted = await service.delete_group(
            group_id=group_id_obj, user_id=current_user.user_id
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group not found",
            )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete group",
        )


@router.post(
    "/{group_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=GroupMemberResponse,
    summary="Add member to group",
    description="Add a user as a member of a group with a specific role. Requires MANAGE permission.",
    responses={
        201: {"description": "Member successfully added to group"},
        400: {"description": "Invalid group ID, user ID, or validation error"},
        403: {"description": "Insufficient permissions to manage group members"},
        500: {"description": "Internal server error"},
    },
)
async def add_group_member(
    group_id: str,
    request: AddGroupMemberRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupMemberResponse:
    """Add a member to a group.

    Requires MANAGE permission on the group.
    """
    try:
        group_id_obj = GroupId.from_string(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format",
        )

    try:
        user_id_obj = UserId.from_string(request.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    try:
        await service.add_member(
            group_id=group_id_obj,
            acting_user_id=current_user.user_id,
            user_id=user_id_obj,
            role=request.to_domain_role(),
        )

        return GroupMemberResponse(
            user_id=request.user_id,
            role=request.to_domain_role(),
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage group members",
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member to group",
        )


@router.get(
    "/{group_id}/members",
    status_code=status.HTTP_200_OK,
    response_model=list[GroupMemberResponse],
    summary="List group members",
    description="List all members of a group. Requires VIEW permission.",
    responses={
        200: {"description": "List of group members"},
        400: {"description": "Invalid group ID format"},
        403: {"description": "Insufficient permissions to view group members"},
        500: {"description": "Internal server error"},
    },
)
async def list_group_members(
    group_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> list[GroupMemberResponse]:
    """List all members of a group.

    Requires VIEW permission on the group.
    """
    try:
        group_id_obj = GroupId.from_string(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format",
        )

    try:
        members = await service.list_members(
            group_id=group_id_obj,
            user_id=current_user.user_id,
        )

        return [
            GroupMemberResponse(
                user_id=grant.user_id,
                role=grant.role,
            )
            for grant in members
        ]

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view group members",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list group members",
        )


@router.patch(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=GroupMemberResponse,
    summary="Update group member role",
    description="Update a member's role in a group. Requires MANAGE permission.",
    responses={
        200: {"description": "Member role updated successfully"},
        400: {"description": "Invalid group ID, user ID, or validation error"},
        403: {"description": "Insufficient permissions to manage group members"},
        500: {"description": "Internal server error"},
    },
)
async def update_group_member_role(
    group_id: str,
    user_id: str,
    request: UpdateGroupMemberRoleRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupMemberResponse:
    """Update a group member's role.

    Requires MANAGE permission on the group.
    """
    try:
        group_id_obj = GroupId.from_string(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format",
        )

    try:
        user_id_obj = UserId.from_string(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    try:
        await service.update_member_role(
            group_id=group_id_obj,
            acting_user_id=current_user.user_id,
            user_id=user_id_obj,
            new_role=request.to_domain_role(),
        )

        return GroupMemberResponse(
            user_id=user_id,
            role=request.to_domain_role(),
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage group members",
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update member role",
        )


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from group",
    description="Remove a user from a group. Requires MANAGE permission.",
    responses={
        204: {"description": "Member successfully removed from group"},
        400: {"description": "Invalid group ID, user ID, or validation error"},
        403: {"description": "Insufficient permissions to manage group members"},
        500: {"description": "Internal server error"},
    },
)
async def remove_group_member(
    group_id: str,
    user_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> None:
    """Remove a member from a group.

    Requires MANAGE permission on the group.
    """
    try:
        group_id_obj = GroupId.from_string(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group ID format",
        )

    try:
        user_id_obj = UserId.from_string(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    try:
        await service.remove_member(
            group_id=group_id_obj,
            acting_user_id=current_user.user_id,
            user_id=user_id_obj,
        )

    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to manage group members",
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member from group",
        )
