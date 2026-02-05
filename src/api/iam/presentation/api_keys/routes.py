"""HTTP routes for API key management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.dependencies.api_key import get_api_key_service
from iam.dependencies.user import get_current_user
from iam.application.services.api_key_service import APIKeyService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import APIKeyId, UserId
from iam.ports.exceptions import (
    APIKeyAlreadyRevokedError,
    APIKeyNotFoundError,
    DuplicateAPIKeyNameError,
)
from iam.presentation.api_keys.models import (
    APIKeyCreatedResponse,
    APIKeyResponse,
    CreateAPIKeyRequest,
)

router = APIRouter(
    prefix="/api-keys",
    tags=["api-keys"],
)


@router.post("", status_code=status.HTTP_201_CREATED)
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

    except DuplicateAPIKeyNameError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An API key with this name already exists",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key",
        )


@router.get(
    "",
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
            # Reject empty or whitespace-only values
            if not user_id.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid user_id format: cannot be blank",
                )
            try:
                filter_user_id = UserId.from_string(value=user_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid user_id format",
                )

        # Get keys filtered by SpiceDB permissions
        api_keys = await service.list_api_keys(
            created_by_user_id=filter_user_id,
            tenant_id=current_user.tenant_id,
            current_user=current_user,
        )
        return [APIKeyResponse.from_domain(key) for key in api_keys]

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys",
        )


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
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
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid API key ID format",
        )

    try:
        await service.revoke_api_key(
            api_key_id=api_key_id_obj,
            user_id=current_user.user_id,
            tenant_id=current_user.tenant_id,
        )

    except APIKeyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    except APIKeyAlreadyRevokedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="API key is already revoked",
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key",
        )
