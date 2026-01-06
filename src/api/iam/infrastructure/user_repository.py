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
from iam.infrastructure.observability import (
    DefaultUserRepositoryProbe,
    UserRepositoryProbe,
)
from iam.ports.repositories import IUserRepository


class UserRepository(IUserRepository):
    """PostgreSQL-backed repository for User aggregates.

    Simple metadata-only repository. Users are provisioned from SSO,
    so this only stores minimal metadata for lookup and reference.
    """

    def __init__(
        self, session: AsyncSession, probe: UserRepositoryProbe | None = None
    ) -> None:
        """Initialize repository with database session and probe.

        Args:
            session: AsyncSession from FastAPI dependency injection
            probe: Optional domain probe for observability
        """
        self._session = session
        self._probe = probe or DefaultUserRepositoryProbe()

    async def save(self, user: User) -> None:
        """Persist a user aggregate.

        Creates a new user or updates an existing one.

        Args:
            user: The User aggregate to persist
        """
        # Check if user exists
        async with self._session.begin():
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

        self._probe.user_saved(user.id.value, user.username)

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
            self._probe.user_not_found(user_id.value)
            return None

        self._probe.user_retrieved(user_id.value)
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
            self._probe.username_not_found(username)
            return None

        self._probe.user_retrieved(model.id)
        return User(
            id=UserId(value=model.id),
            username=model.username,
        )
