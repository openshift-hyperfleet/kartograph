"""HTTP routes for IAM bounded context.

Provides REST API for group management operations.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from iam.application.services import GroupService
from iam.dependencies import get_group_service
from iam.domain.value_objects import GroupId, TenantId
from iam.ports.exceptions import DuplicateGroupNameError
from iam.presentation.auth import CurrentUser, get_current_user
from iam.presentation.models import CreateGroupRequest, GroupResponse

router = APIRouter(prefix="/iam", tags=["iam"])


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_group(
    request: CreateGroupRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupResponse:
    """Create a new group with authenticated user as admin.

    The authenticated user (from headers) will be the creator and
    initial admin of the group.

    Args:
        request: Group creation request
        current_user: Current authenticated user from headers
        service: Group service for orchestration

    Returns:
        GroupResponse with created group details

    Raises:
        HTTPException: 409 if group name already exists in tenant
        HTTPException: 400 if tenant ID is invalid
        HTTPException: 500 for unexpected errors
    """
    try:
        tenant_id = TenantId.from_string(request.tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tenant ID format: {e}",
        ) from e

    try:
        group = await service.create_group(
            name=request.name,
            creator_id=current_user.user_id,
            creator_username=current_user.username,
            tenant_id=tenant_id,
        )
        return GroupResponse.from_domain(group)

    except DuplicateGroupNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create group: {e}",
        ) from e


@router.get("/groups/{group_id}")
async def get_group(
    group_id: str,
    service: Annotated[GroupService, Depends(get_group_service)],
) -> GroupResponse:
    """Get group by ID.

    Args:
        group_id: Group ID (ULID format)
        service: Group service

    Returns:
        GroupResponse with group details and members

    Raises:
        HTTPException: 400 if group ID is invalid
        HTTPException: 404 if group not found
        HTTPException: 500 for unexpected errors
    """
    try:
        group_id_obj = GroupId.from_string(group_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid group ID format: {e}",
        ) from e

    try:
        group = await service.get_group(group_id_obj)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group {group_id} not found",
            )
        return GroupResponse.from_domain(group)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get group: {e}",
        ) from e


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    service: Annotated[GroupService, Depends(get_group_service)],
    tenant_id: str = Query(..., description="Tenant ID (ULID format)"),
) -> None:
    """Delete a group.

    Args:
        group_id: Group ID (ULID format)
        tenant_id: Tenant ID (ULID format) - required for cleanup
        service: Group service

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException: 400 if group ID or tenant ID is invalid
        HTTPException: 404 if group not found
        HTTPException: 500 for unexpected errors
    """
    try:
        group_id_obj = GroupId.from_string(group_id)
        tenant_id_obj = TenantId.from_string(tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID format: {e}",
        ) from e

    try:
        deleted = await service.delete_group(group_id_obj, tenant_id_obj)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group {group_id} not found",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete group: {e}",
        ) from e
