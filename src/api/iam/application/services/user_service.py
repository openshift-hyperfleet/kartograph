"""User application service for IAM bounded context.

Handles user provisioning from SSO with JIT (just-in-time) creation.
"""

from __future__ import annotations

from iam.domain.aggregates import User
from iam.domain.value_objects import UserId
from iam.application.observability import DefaultUserServiceProbe, UserServiceProbe
from iam.ports.repositories import IUserRepository
from sqlalchemy.ext.asyncio import AsyncSession


class UserService:
    """Application service for user management.

    Handles user provisioning from SSO with JIT (just-in-time) creation.
    """

    def __init__(
        self,
        user_repository: IUserRepository,
        session: AsyncSession,
        probe: UserServiceProbe | None = None,
    ):
        """Initialize UserService with dependencies.

        Args:
            user_repository: Repository for user persistence
            session: Database session for transaction management
            probe: Optional domain probe for observability
        """
        self._user_repository = user_repository
        self._probe = probe or DefaultUserServiceProbe()
        self._session = session

    async def ensure_user(self, user_id: UserId, username: str) -> User:
        """Ensure user exists in database (find-or-create pattern).

        This implements JIT provisioning for users from SSO. If the user
        doesn't exist in our database, we create them.

        Manages database transaction for the entire use case.

        Args:
            user_id: The user's ID (from SSO)
            username: The user's username (from SSO)

        Returns:
            The User aggregate (existing or newly created)

        Raises:
            Exception: If user creation fails
        """
        try:
            async with self._session.begin():
                # Check if user already exists
                existing = await self._user_repository.get_by_id(user_id)
                if existing:
                    # Sync username if changed in SSO
                    if existing.username != username:
                        user = User(id=user_id, username=username)
                        await self._user_repository.save(user)
                        self._probe.user_ensured(
                            user_id=user_id.value,
                            username=username,
                            was_created=False,
                            was_updated=True,
                        )
                        return user

                    self._probe.user_ensured(
                        user_id=user_id.value,
                        username=username,
                        was_created=False,
                        was_updated=False,
                    )
                    return existing

                # Create new user (JIT provisioning)
                user = User(id=user_id, username=username)
                await self._user_repository.save(user)

                self._probe.user_ensured(
                    user_id=user_id.value,
                    username=username,
                    was_created=True,
                    was_updated=False,
                )
                return user

        except Exception as e:
            self._probe.user_provision_failed(
                user_id=user_id.value,
                username=username,
                error=str(e),
            )
            raise
