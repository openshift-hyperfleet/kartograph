"""HTTP routes for group management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.dependencies.group import get_group_service
from iam.dependencies.user import get_current_user
from iam.application.services import GroupService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import GroupId
from iam.ports.exceptions import DuplicateGroupNameError
from iam.presentation.groups.models import CreateGroupRequest, GroupResponse

router = APIRouter(
    prefix="/groups",
    tags=["groups"],
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

    TODO: Add presentation-layer FastAPI dependency for tenant-level access checks
    (e.g., Depends(require_tenant_access)). Service will still handle operation-specific
    authorization (e.g., can this user delete THIS specific group).

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
