"""HTTP routes for tenant management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.dependencies.multi_tenant_mode import require_multi_tenant_mode
from iam.dependencies.tenant import get_tenant_service
from iam.dependencies.user import get_authenticated_user, get_current_user
from iam.application.services import TenantService
from iam.application.value_objects import AuthenticatedUser, CurrentUser
from iam.domain.exceptions import CannotRemoveLastAdminError
from iam.domain.value_objects import TenantId, UserId
from iam.ports.exceptions import DuplicateTenantNameError, UnauthorizedError
from iam.presentation.tenants.models import (
    AddTenantMemberRequest,
    CreateTenantRequest,
    TenantMemberResponse,
    TenantResponse,
)

router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_tenant(
    request: CreateTenantRequest,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
    _: Annotated[None, Depends(require_multi_tenant_mode)],
) -> TenantResponse:
    """Create a new tenant.

    Uses get_authenticated_user (not get_current_user) because this is a
    bootstrap endpoint — users need to create tenants before they have
    tenant context. Only authentication is required, not tenant scoping.

    The authenticated user is automatically granted admin access to the
    newly created tenant.

    Args:
        request: Tenant creation request (name)
        authenticated_user: Authenticated user (no tenant context required).
            Automatically granted admin access to the created tenant.
        service: Tenant service for orchestration

    Returns:
        TenantResponse with created tenant details

    Raises:
        HTTPException: 409 if tenant name already exists
        HTTPException: 500 for unexpected errors
    """
    try:
        tenant = await service.create_tenant(
            name=request.name,
            creator_id=authenticated_user.user_id,
        )
        return TenantResponse.from_domain(tenant)

    except DuplicateTenantNameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tenant with this name already exists",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tenant",
        )


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    """Get tenant by ID.

    Requires VIEW permission on the tenant.

    Args:
        tenant_id: Tenant ID (ULID format)
        current_user: Current authenticated user
        service: Tenant service

    Returns:
        TenantResponse with tenant details

    Raises:
        HTTPException: 400 if tenant ID is invalid
        HTTPException: 404 if tenant not found or user lacks VIEW permission
        HTTPException: 500 for unexpected errors
    """
    try:
        tenant_id_obj = TenantId.from_string(tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tenant ID format: {e}",
        ) from e

    try:
        tenant = await service.get_tenant(
            tenant_id_obj,
            user_id=current_user.user_id,
        )
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found",
            )
        return TenantResponse.from_domain(tenant)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tenant",
        )


@router.get("")
async def list_tenants(
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> list[TenantResponse]:
    """List all tenants the user is a member of.

    Filters tenants by VIEW permission via SpiceDB.

    Uses get_authenticated_user (not get_current_user) because this is a
    bootstrap endpoint -- users need to list tenants before they have
    tenant context. Only authentication is required, not tenant scoping.

    Args:
        authenticated_user: Authenticated user (no tenant context required)
        service: Tenant service

    Returns:
        List of TenantResponse objects for tenants user can view

    Raises:
        HTTPException: 500 for unexpected errors
    """
    try:
        tenants = await service.list_tenants(
            user_id=authenticated_user.user_id,
        )
        return [TenantResponse.from_domain(t) for t in tenants]

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tenants",
        )


@router.delete(
    "/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        204: {"description": "Tenant deleted successfully"},
        400: {"description": "Invalid tenant ID format"},
        403: {"description": "Insufficient permissions to delete tenant"},
        404: {"description": "Tenant not found"},
        500: {"description": "Internal server error"},
    },
)
async def delete_tenant(
    tenant_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
    _: Annotated[None, Depends(require_multi_tenant_mode)],
) -> None:
    """Delete a tenant.

    Requires ADMINISTRATE permission on the tenant.

    Args:
        tenant_id: Tenant ID (ULID format)
        current_user: Current authenticated user
        service: Tenant service

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException: 400 if tenant ID is invalid
        HTTPException: 403 if user lacks ADMINISTRATE permission
        HTTPException: 404 if tenant not found
        HTTPException: 500 for unexpected errors
    """
    try:
        tenant_id_obj = TenantId.from_string(tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tenant ID format: {e}",
        ) from e

    try:
        deleted = await service.delete_tenant(
            tenant_id_obj,
            requesting_user_id=current_user.user_id,
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found",
            )

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete tenant",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tenant",
        )


@router.post(
    "/{tenant_id}/members",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Member successfully added to tenant",
            "model": TenantMemberResponse,
        },
        400: {
            "description": "Invalid tenant ID or user ID format",
        },
        403: {
            "description": "Insufficient permissions to manage tenant members",
        },
        404: {
            "description": "Tenant not found",
        },
        500: {
            "description": "Internal server error",
        },
    },
)
async def add_tenant_member(
    tenant_id: str,
    request: AddTenantMemberRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantMemberResponse:
    """Add a member to a tenant.

    Requires the caller to have administrate permission on the tenant.

    Args:
        tenant_id: Tenant ID (ULID format)
        request: Add member request with user_id and role
        current_user: Current authenticated user
        service: Tenant service for orchestration

    Returns:
        TenantMemberResponse with the added member details

    Raises:
        HTTPException: 400 if tenant ID or user ID is invalid
        HTTPException: 403 if caller is not tenant admin
        HTTPException: 404 if tenant not found
        HTTPException: 500 for unexpected errors
    """
    # Validate tenant ID format
    try:
        tenant_id_obj = TenantId.from_string(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )

    # Validate user ID format
    try:
        user_id_obj = UserId.from_string(request.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    try:
        await service.add_member(
            tenant_id=tenant_id_obj,
            user_id=user_id_obj,
            role=request.to_domain_role(),
            requesting_user_id=current_user.user_id,
        )
        return TenantMemberResponse(
            user_id=request.user_id,
            role=request.role.value,
        )

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add member",
        )


@router.delete(
    "/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        204: {
            "description": "Member successfully removed from tenant",
        },
        400: {
            "description": "Invalid tenant ID or user ID format",
        },
        403: {
            "description": "Insufficient permissions to manage tenant members",
        },
        404: {
            "description": "Tenant not found",
        },
        409: {
            "description": "Cannot remove the last admin from the tenant",
        },
        500: {
            "description": "Internal server error",
        },
    },
)
async def remove_tenant_member(
    tenant_id: str,
    user_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> None:
    """Remove a member from a tenant.

    Requires the caller to have administrate permission on the tenant.
    Cannot remove the last admin from a tenant.

    Args:
        tenant_id: Tenant ID (ULID format)
        user_id: User ID of the member to remove
        current_user: Current authenticated user
        service: Tenant service for orchestration

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException: 400 if tenant ID or user ID is invalid
        HTTPException: 403 if caller is not tenant admin
        HTTPException: 404 if tenant not found
        HTTPException: 409 if trying to remove the last admin
        HTTPException: 500 for unexpected errors
    """
    # Validate tenant ID format
    try:
        tenant_id_obj = TenantId.from_string(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )

    # Validate user ID format
    try:
        user_id_obj = UserId.from_string(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    try:
        await service.remove_member(
            tenant_id=tenant_id_obj,
            user_id=user_id_obj,
            requesting_user_id=current_user.user_id,
        )

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    except CannotRemoveLastAdminError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot remove the last admin from the tenant",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove member",
        )


@router.get(
    "/{tenant_id}/members",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of tenant members",
            "model": list[TenantMemberResponse],
        },
        400: {
            "description": "Invalid tenant ID format",
        },
        403: {
            "description": "Insufficient permissions to view tenant members",
        },
        404: {
            "description": "Tenant not found",
        },
        500: {
            "description": "Internal server error",
        },
    },
)
async def list_tenant_members(
    tenant_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> list[TenantMemberResponse]:
    """List all members of a tenant.

    Requires the caller to have administrate permission on the tenant.

    Args:
        tenant_id: Tenant ID (ULID format)
        current_user: Current authenticated user
        service: Tenant service for orchestration

    Returns:
        List of TenantMemberResponse objects

    Raises:
        HTTPException: 400 if tenant ID is invalid
        HTTPException: 403 if caller is not tenant admin
        HTTPException: 404 if tenant not found
        HTTPException: 500 for unexpected errors
    """
    # Validate tenant ID format
    try:
        tenant_id_obj = TenantId.from_string(tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tenant ID format",
        )

    try:
        members = await service.list_members(
            tenant_id=tenant_id_obj, requesting_user_id=current_user.user_id
        )

        if members is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tenant not found",
            )

        return [TenantMemberResponse.from_tuple(m) for m in members]

    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list members",
        )
