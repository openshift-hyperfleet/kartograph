"""HTTP routes for IAM bounded context.

Provides REST API for group, tenant, and API key management operations.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.dependencies.api_key import get_api_key_service
from iam.dependencies.group import get_group_service
from iam.dependencies.user import get_current_user
from iam.dependencies.tenant import get_tenant_service
from iam.application.services import GroupService, TenantService
from iam.application.services.api_key_service import APIKeyService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import APIKeyId, GroupId, TenantId, UserId
from iam.ports.exceptions import (
    APIKeyAlreadyRevokedError,
    APIKeyNotFoundError,
    DuplicateAPIKeyNameError,
    DuplicateGroupNameError,
    DuplicateTenantNameError,
)
from iam.presentation.models import (
    APIKeyCreatedResponse,
    APIKeyResponse,
    CreateAPIKeyRequest,
    CreateGroupRequest,
    CreateTenantRequest,
    GroupResponse,
    TenantResponse,
)

router = APIRouter(
    prefix="/iam",
    tags=["iam"],
    dependencies=[Depends(get_current_user)],
)

# TODO: Proper authorization is needed for all of these routes


@router.post("/groups", status_code=status.HTTP_201_CREATED)
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid group ID format: {e}",
        ) from e

    try:
        group = await service.get_group(group_id=group_id_obj)
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
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID format: {e}",
        ) from e

    try:
        deleted = await service.delete_group(
            group_id=group_id_obj, user_id=current_user.user_id
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group {group_id} not found",
            )

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete group: {e}",
        ) from e


# Tenant endpoints


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
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


@router.get("/tenants/{tenant_id}")
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


@router.get("/tenants")
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


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
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


# API Key endpoints


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[APIKeyService, Depends(get_api_key_service)],
) -> APIKeyCreatedResponse:
    """Create a new API key for the current user.

    The plaintext secret is returned ONLY in this response. Store it securely -
    it cannot be retrieved again.

    Args:
        request: API key creation request (name, optional expiration)
        current_user: Current authenticated user with tenant context
        service: API key service for orchestration

    Returns:
        APIKeyCreatedResponse with key details and plaintext secret

    Raises:
        HTTPException: 409 if API key name already exists for user
        HTTPException: 500 for unexpected errors
    """
    try:
        api_key, plaintext_secret = await service.create_api_key(
            created_by_user_id=current_user.user_id,
            name=request.name,
            expires_in_days=request.expires_in_days,
            tenant_id=current_user.tenant_id,
        )
        return APIKeyCreatedResponse(
            secret=plaintext_secret,
            **APIKeyResponse.from_domain(api_key).model_dump(),
        )

    except DuplicateAPIKeyNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {e}",
        ) from e


@router.get(
    "/api-keys",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of API keys the user can view",
            "model": list[APIKeyResponse],
        },
        400: {
            "description": "Invalid user_id (cannot be empty or whitespace)",
        },
        500: {
            "description": "Internal server error",
        },
    },
)
async def list_api_keys(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[APIKeyService, Depends(get_api_key_service)],
    user_id: str | None = None,
) -> list[APIKeyResponse]:
    """List API keys the current user can view.

    Uses SpiceDB to determine which API keys are viewable. By default, users
    see their own keys. Tenant admins can see all keys in their tenant.

    The secret is NEVER returned in this response - it is only available
    at creation time.

    Args:
        current_user: Current authenticated user with tenant context
        service: API key service for orchestration
        user_id: Optional filter to show only keys created by this user

    Returns:
        List of APIKeyResponse objects (without secrets) that the user can view
    """
    try:
        # Parse and validate user_id if provided
        filter_user_id = None
        if user_id is not None:
            try:
                filter_user_id = UserId.from_string(value=user_id)
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid user_id format: {e}",
                ) from e

        # Get keys filtered by SpiceDB permissions
        api_keys = await service.list_api_keys(
            created_by_user_id=filter_user_id,
            tenant_id=current_user.tenant_id,
            current_user=current_user,
        )
        return [APIKeyResponse.from_domain(key) for key in api_keys]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys",
        ) from e


@router.delete("/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[APIKeyService, Depends(get_api_key_service)],
) -> None:
    """Revoke an API key.

    A revoked key can no longer be used for authentication but remains
    visible in the API key list with is_revoked=true for audit purposes.

    Args:
        api_key_id: API Key ID (ULID format)
        current_user: Current authenticated user with tenant context
        service: API key service for orchestration

    Returns:
        None (204 No Content on success)

    Raises:
        HTTPException: 422 if API key ID is invalid
        HTTPException: 404 if API key not found
        HTTPException: 409 if API key is already revoked
        HTTPException: 500 for unexpected errors
    """
    try:
        api_key_id_obj = APIKeyId.from_string(api_key_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid API key ID format: {e}",
        ) from e

    try:
        await service.revoke_api_key(
            api_key_id=api_key_id_obj,
            user_id=current_user.user_id,
            tenant_id=current_user.tenant_id,
        )

    except APIKeyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except APIKeyAlreadyRevokedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {e}",
        ) from e
