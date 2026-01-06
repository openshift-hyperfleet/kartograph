"""Authentication helpers for IAM presentation layer.

Provides stub authentication for tracer bullet implementation.
In production, this will validate x-rh-identity header from Red Hat SSO.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from iam.domain.value_objects import TenantId, UserId
from iam.dependencies import get_user_service, UserService


@dataclass(frozen=True)
class CurrentUser:
    """Represents the currently authenticated user.

    This is extracted from authentication headers and used throughout
    the request lifecycle. In production, this comes from JWT claims.
    """

    user_id: UserId
    username: str
    tenant_id: TenantId


async def get_current_user(
    user_service: Annotated[UserService, Depends(get_user_service)],
    x_user_id: str = Header(..., description="User ID from SSO (stub)"),
    x_username: str = Header(..., description="Username from SSO (stub)"),
    x_tenant_id: str = Header(..., description="Tenant ID from SSO (stub)"),
) -> CurrentUser:
    """Extract current user from headers (stub for SSO integration).

    This is a simplified authentication mechanism for the walking skeleton.
    In production, this will:
    - Decode and validate JWT from Authorization header
    - Extract user_id, username, tenant_id from JWT claims
    - Validate JWT signature with Red Hat SSO public key
    - Handle authentication errors properly

    For now, we accept user info from custom headers to enable testing
    without a full SSO/JWT integration, and ensure the user exists in the
    application database.

    Args:
        user_service: The user service
        x_user_id: User ID header (ULID format)
        x_username: Username header
        x_tenant_id: Tenant ID header (ULID format)

    Returns:
        CurrentUser with user ID (from SSO), username, and validated tenant ID

    Raises:
        HTTPException: 400 if tenant ID is invalid ULID format
    """
    try:
        # User IDs come from external SSO - accept any string format
        user_id = UserId(value=x_user_id)

        # Ensure the user exists in the system
        await user_service.ensure_user(user_id=user_id, username=x_username)

        # Tenant IDs are internal - validate ULID format
        tenant_id = TenantId.from_string(x_tenant_id)
        return CurrentUser(user_id=user_id, username=x_username, tenant_id=tenant_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tenant ID format: {e}",
        ) from e
