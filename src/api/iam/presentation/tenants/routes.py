"""HTTP routes for tenant management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.dependencies.tenant import get_tenant_service
from iam.dependencies.user import get_current_user
from iam.application.services import TenantService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId
from iam.ports.exceptions import DuplicateTenantNameError
from iam.presentation.tenants.models import CreateTenantRequest, TenantResponse

router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: CreateTenantRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    """Create a new tenant.

    For the walking skeleton, this uses header-based auth.
    In production, this should be restricted to system administrators.

    Args:
        request: Tenant creation request (name)
        current_user: Current authenticated user (admin check would go here)
        service: Tenant service for orchestration

    Returns:
        TenantResponse with created tenant details

    Raises:
        HTTPException: 409 if tenant name already exists
        HTTPException: 500 for unexpected errors
    """
    try:
        tenant = await service.create_tenant(name=request.name)
        return TenantResponse.from_domain(tenant)

    except DuplicateTenantNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create tenant: {e}",
        ) from e


@router.get("/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> TenantResponse:
    """Get tenant by ID.

    Requires authentication. For the walking skeleton, this is open to
    authenticated users. In production, this should enforce proper access control.

    Args:
        tenant_id: Tenant ID (ULID format)
        current_user: Current authenticated user
        service: Tenant service

    Returns:
        TenantResponse with tenant details

    Raises:
        HTTPException: 400 if tenant ID is invalid
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
        tenant = await service.get_tenant(tenant_id_obj)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found",
            )
        return TenantResponse.from_domain(tenant)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tenant: {e}",
        ) from e


@router.get("")
async def list_tenants(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> list[TenantResponse]:
    """List all tenants.

    Requires authentication. For the walking skeleton, this is open to
    authenticated users. In production, this should be restricted to admins.

    Args:
        current_user: Current authenticated user
        service: Tenant service

    Returns:
        List of TenantResponse objects

    Raises:
        HTTPException: 500 for unexpected errors
    """
    try:
        tenants = await service.list_tenants()
        return [TenantResponse.from_domain(t) for t in tenants]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tenants: {e}",
        ) from e


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[TenantService, Depends(get_tenant_service)],
) -> None:
    """Delete a tenant.

    TODO: In production, this should be restricted to system administrators.

    Args:
        tenant_id: Tenant ID (ULID format)
        current_user: Current authenticated user
        service: Tenant service

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException: 400 if tenant ID is invalid
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
        deleted = await service.delete_tenant(tenant_id_obj)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {tenant_id} not found",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tenant: {e}",
        ) from e
