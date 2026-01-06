"""Authentication helpers for IAM presentation layer.

Provides stub authentication for tracer bullet implementation.
In production, this will validate x-rh-identity header from Red Hat SSO.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from iam.domain.value_objects import UserId


@dataclass(frozen=True)
class CurrentUser:
    """Represents the currently authenticated user.

    This is extracted from authentication headers and used throughout
    the request lifecycle.
    """

    user_id: UserId
    username: str


async def get_current_user(
    x_user_id: str = Header(..., description="User ID from SSO (stub)"),
    x_username: str = Header(..., description="Username from SSO (stub)"),
) -> CurrentUser:
    """Extract current user from headers (stub for SSO integration).

    This is a simplified authentication mechanism for the walking skeleton.
    In production, this will:
    - Validate x-rh-identity header from Red Hat SSO
    - Extract user ID and username from trusted header
    - Handle authentication errors properly

    For now, we accept user info from custom headers to enable testing
    without a full SSO integration.

    Args:
        x_user_id: User ID header (ULID format)
        x_username: Username header

    Returns:
        CurrentUser with validated user ID and username

    Raises:
        HTTPException: 400 if user ID is invalid ULID format
    """
    try:
        user_id = UserId.from_string(x_user_id)
        return CurrentUser(user_id=user_id, username=x_username)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user ID format: {e}",
        ) from e
