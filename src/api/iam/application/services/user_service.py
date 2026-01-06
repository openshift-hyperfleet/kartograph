"""User application service for IAM bounded context.

Handles user provisioning from SSO with JIT (just-in-time) creation.
"""

from __future__ import annotations

from iam.domain.aggregates import User
from iam.domain.value_objects import UserId
from iam.application.observability import DefaultUserServiceProbe, UserServiceProbe
from iam.ports.repositories import IUserRepository


class UserService:
    """Application service for user management.

    Handles user provisioning from SSO with JIT (just-in-time) creation.
    """

    def __init__(
        self,
        user_repository: IUserRepository,
        probe: UserServiceProbe | None = None,
    ):
        """Initialize UserService with dependencies.

        Args:
            user_repository: Repository for user persistence
            probe: Optional domain probe for observability
        """
        self._user_repository = user_repository
        self._probe = probe or DefaultUserServiceProbe()

    async def ensure_user(self, user_id: UserId, username: str) -> User:
        """Ensure user exists in database (find-or-create pattern).

        This implements JIT provisioning for users from SSO. If the user
        doesn't exist in our database, we create them.

        Args:
            user_id: The user's ID (from SSO)
            username: The user's username (from SSO)

        Returns:
            The User aggregate (existing or newly created)

        Raises:
            Exception: If user creation fails
        """
        # Check if user already exists
        existing = await self._user_repository.get_by_id(user_id)
        if existing:
            # Sync username if changed in SSO
            if existing.username != username:
                try:
                    user = User(id=user_id, username=username)
                    await self._user_repository.save(user)
                    self._probe.user_ensured(
                        user_id=user_id.value,
                        username=username,
                        was_created=False,
                    )
                    return user
                except Exception as e:
                    self._probe.user_provision_failed(
                        user_id=user_id.value,
                        username=username,
                        error=str(e),
                    )
                    raise

            self._probe.user_ensured(
                user_id=user_id.value,
                username=username,
                was_created=False,
            )
            return existing

        # Create new user (JIT provisioning)
        try:
            user = User(id=user_id, username=username)
            await self._user_repository.save(user)

            self._probe.user_ensured(
                user_id=user_id.value,
                username=username,
                was_created=True,
            )
            return user

        except Exception as e:
            self._probe.user_provision_failed(
                user_id=user_id.value,
                username=username,
                error=str(e),
            )
            raise
