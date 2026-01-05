"""PostgreSQL implementation of IUserRepository.

Simple repository for user metadata storage. Users are provisioned from SSO
and this repository only handles metadata persistence.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iam.domain.aggregates import User
from iam.domain.value_objects import UserId
from iam.infrastructure.models import UserModel
from iam.ports.repositories import IUserRepository


class UserRepository(IUserRepository):
    """PostgreSQL-backed repository for User aggregates.

    Simple metadata-only repository. Users are provisioned from SSO,
    so this only stores minimal metadata for lookup and reference.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: AsyncSession from FastAPI dependency injection
        """
        self._session = session

    async def save(self, user: User) -> None:
        """Persist a user aggregate.

        Creates a new user or updates an existing one.

        Args:
            user: The User aggregate to persist
        """
        # Check if user exists
        stmt = select(UserModel).where(UserModel.id == user.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            # Update existing user
            model.username = user.username
        else:
            # Create new user
            model = UserModel(
                id=user.id.value,
                username=user.username,
            )
            self._session.add(model)

    async def get_by_id(self, user_id: UserId) -> User | None:
        """Retrieve a user by their ID.

        Args:
            user_id: The unique identifier of the user

        Returns:
            The User aggregate, or None if not found
        """
        stmt = select(UserModel).where(UserModel.id == user_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return User(
            id=UserId(value=model.id),
            username=model.username,
        )

    async def get_by_username(self, username: str) -> User | None:
        """Retrieve a user by their username.

        Args:
            username: The username to search for

        Returns:
            The User aggregate, or None if not found
        """
        stmt = select(UserModel).where(UserModel.username == username)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return User(
            id=UserId(value=model.id),
            username=model.username,
        )
