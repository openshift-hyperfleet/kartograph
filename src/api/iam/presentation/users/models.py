"""Pydantic models for user lookup API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from iam.domain.aggregates import User


class UserProfileResponse(BaseModel):
    """Response model for a single user profile."""

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    name: str | None = Field(None, description="Display name")
    email: str | None = Field(None, description="Email address")

    @classmethod
    def from_domain(cls, user: User) -> UserProfileResponse:
        """Convert domain User aggregate to API response.

        Args:
            user: User domain aggregate

        Returns:
            UserProfileResponse
        """
        return cls(
            id=user.id.value,
            username=user.username,
            name=user.name,
            email=user.email,
        )


class UserListResponse(BaseModel):
    """Response model for a list of user profiles."""

    users: list[UserProfileResponse] = Field(..., description="List of user profiles")
    count: int = Field(..., description="Number of users returned")
