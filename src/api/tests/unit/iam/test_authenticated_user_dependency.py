"""Unit tests for get_authenticated_user dependency.

Tests the thin wrapper over _authenticate that returns an AuthenticatedUser
and performs JIT user provisioning for JWT-authenticated users.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_archon import archrule

from iam.application.observability import UserServiceProbe
from iam.application.value_objects import AuthenticatedUser
from iam.dependencies.user import _AuthResult, get_authenticated_user
from iam.domain.aggregates import User
from iam.domain.value_objects import TenantId, UserId


class TestAuthenticatedUserDependencyArchitecturalBoundaries:
    """IAM dependencies must not depend on other bounded contexts."""

    def test_iam_dependencies_do_not_import_graph(self):
        """IAM dependencies should not depend on Graph context."""
        (
            archrule("iam_deps_no_graph")
            .match("iam.dependencies*")
            .should_not_import("graph*")
            .check("iam")
        )

    def test_iam_dependencies_do_not_import_extraction(self):
        """IAM dependencies should not depend on Extraction context."""
        (
            archrule("iam_deps_no_extraction")
            .match("iam.dependencies*")
            .should_not_import("extraction*")
            .check("iam")
        )

    def test_iam_dependencies_do_not_import_management(self):
        """IAM dependencies should not depend on Management context."""
        (
            archrule("iam_deps_no_management")
            .match("iam.dependencies*")
            .should_not_import("management*")
            .check("iam")
        )

    def test_iam_dependencies_do_not_import_ingestion(self):
        """IAM dependencies should not depend on Ingestion context."""
        (
            archrule("iam_deps_no_ingestion")
            .match("iam.dependencies*")
            .should_not_import("ingestion*")
            .check("iam")
        )

    def test_iam_dependencies_do_not_import_querying(self):
        """IAM dependencies should not depend on Querying context."""
        (
            archrule("iam_deps_no_querying")
            .match("iam.dependencies*")
            .should_not_import("query*")
            .check("iam")
        )


@pytest.fixture
def jwt_auth_result() -> _AuthResult:
    """Create an _AuthResult for JWT-authenticated user."""
    return _AuthResult(
        user_id=UserId(value="external-user-123"),
        username="testuser",
        api_key_tenant_id=None,
        is_api_key=False,
    )


@pytest.fixture
def api_key_auth_result() -> _AuthResult:
    """Create an _AuthResult for API-key-authenticated user."""
    return _AuthResult(
        user_id=UserId(value="user-456"),
        username="api-key:api-key-id-123",
        api_key_tenant_id=TenantId.generate(),
        is_api_key=True,
    )


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Create a mock user repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session with begin() context manager."""
    session = AsyncMock()
    session.begin = MagicMock(return_value=AsyncMock())
    return session


@pytest.fixture
def mock_probe() -> MagicMock:
    """Create a mock user service probe."""
    return MagicMock(spec=UserServiceProbe)


class TestGetAuthenticatedUser:
    """Tests for get_authenticated_user dependency.

    This dependency wraps _authenticate and adds JIT user provisioning.
    It returns an AuthenticatedUser (without tenant_id).
    """

    @pytest.mark.asyncio
    async def test_returns_authenticated_user_from_jwt(
        self,
        jwt_auth_result: _AuthResult,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """Should return AuthenticatedUser with user_id and username."""
        result = await get_authenticated_user(
            auth_result=jwt_auth_result,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
        )

        assert isinstance(result, AuthenticatedUser)
        assert result.user_id == UserId(value="external-user-123")
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_does_not_have_tenant_id(
        self,
        jwt_auth_result: _AuthResult,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """AuthenticatedUser should NOT have a tenant_id attribute."""
        result = await get_authenticated_user(
            auth_result=jwt_auth_result,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
        )

        assert not hasattr(result, "tenant_id")

    @pytest.mark.asyncio
    async def test_returns_authenticated_user_from_api_key(
        self,
        api_key_auth_result: _AuthResult,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """Should return AuthenticatedUser when authenticated via API key."""
        result = await get_authenticated_user(
            auth_result=api_key_auth_result,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
        )

        assert isinstance(result, AuthenticatedUser)
        assert result.user_id == UserId(value="user-456")

    @pytest.mark.asyncio
    async def test_jit_provisions_user_for_jwt_auth(
        self,
        jwt_auth_result: _AuthResult,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """Should JIT provision user in database for JWT authentication."""
        mock_user_repo.get_by_id.return_value = None

        await get_authenticated_user(
            auth_result=jwt_auth_result,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
        )

        mock_user_repo.save.assert_awaited_once()
        mock_probe.user_ensured.assert_called_once_with(
            user_id="external-user-123",
            username="testuser",
            was_created=True,
            was_updated=False,
        )

    @pytest.mark.asyncio
    async def test_jit_skips_creation_for_existing_user(
        self,
        jwt_auth_result: _AuthResult,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """Should not create user if already exists with same username."""
        existing_user = User(id=UserId(value="external-user-123"), username="testuser")
        mock_user_repo.get_by_id.return_value = existing_user

        await get_authenticated_user(
            auth_result=jwt_auth_result,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
        )

        mock_user_repo.save.assert_not_awaited()
        mock_probe.user_ensured.assert_called_once_with(
            user_id="external-user-123",
            username="testuser",
            was_created=False,
            was_updated=False,
        )

    @pytest.mark.asyncio
    async def test_jit_syncs_username_when_changed_in_sso(
        self,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """Should update username when it changed in SSO."""
        auth_result = _AuthResult(
            user_id=UserId(value="user-123"),
            username="new-username",
            api_key_tenant_id=None,
            is_api_key=False,
        )
        existing_user = User(id=UserId(value="user-123"), username="old-username")
        mock_user_repo.get_by_id.return_value = existing_user

        await get_authenticated_user(
            auth_result=auth_result,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
        )

        mock_user_repo.save.assert_awaited_once()
        mock_probe.user_ensured.assert_called_once_with(
            user_id="user-123",
            username="new-username",
            was_created=False,
            was_updated=True,
        )

    @pytest.mark.asyncio
    async def test_skips_jit_for_api_key_auth(
        self,
        api_key_auth_result: _AuthResult,
        mock_user_repo: AsyncMock,
        mock_session: AsyncMock,
        mock_probe: MagicMock,
    ) -> None:
        """Should NOT JIT provision for API key authentication."""
        await get_authenticated_user(
            auth_result=api_key_auth_result,
            user_repo=mock_user_repo,
            session=mock_session,
            probe=mock_probe,
        )

        mock_user_repo.get_by_id.assert_not_awaited()
        mock_user_repo.save.assert_not_awaited()
        mock_probe.user_ensured.assert_not_called()
