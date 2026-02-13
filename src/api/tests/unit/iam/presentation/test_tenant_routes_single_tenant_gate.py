"""Unit tests for tenant route single-tenant mode gating.

Verifies that POST /tenants (create) and DELETE /tenants/{id} (delete) are
blocked with 403 when the application runs in single-tenant mode, while
GET /tenants, GET /tenants/{id}, and member management routes remain
accessible regardless of mode.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import TenantService
from iam.application.value_objects import AuthenticatedUser, CurrentUser
from iam.dependencies.multi_tenant_mode import (
    _get_single_tenant_mode,
)
from iam.dependencies.tenant import get_tenant_service
from iam.dependencies.user import get_authenticated_user, get_current_user
from iam.domain.aggregates import Tenant
from iam.domain.value_objects import TenantId, UserId
from iam.presentation import router
from infrastructure.authorization_dependencies import get_spicedb_client


@pytest.fixture
def mock_tenant_service() -> AsyncMock:
    """Mock TenantService for testing."""
    return AsyncMock(spec=TenantService)


@pytest.fixture
def mock_authz() -> AsyncMock:
    """Mock AuthorizationProvider for testing."""
    from shared_kernel.authorization.protocols import AuthorizationProvider

    return AsyncMock(spec=AuthorizationProvider)


@pytest.fixture
def mock_current_user() -> CurrentUser:
    """Mock CurrentUser for authentication."""
    return CurrentUser(
        user_id=UserId(value="test-user-123"),
        username="testuser",
        tenant_id=TenantId.generate(),
    )


@pytest.fixture
def mock_authenticated_user() -> AuthenticatedUser:
    """Mock AuthenticatedUser for tenant-bootstrap endpoints (no tenant_id)."""
    return AuthenticatedUser(
        user_id=UserId(value="test-user-123"),
        username="testuser",
    )


@pytest.fixture
def valid_tenant_id() -> TenantId:
    """A valid tenant ID for use in URL paths."""
    return TenantId.generate()


def _create_test_client(
    *,
    mock_tenant_service: AsyncMock,
    mock_authz: AsyncMock,
    mock_current_user: CurrentUser,
    mock_authenticated_user: AuthenticatedUser | None = None,
    single_tenant_mode: bool,
) -> TestClient:
    """Create a TestClient with the given single_tenant_mode override.

    Args:
        mock_tenant_service: Mock for TenantService dependency.
        mock_authz: Mock for AuthorizationProvider dependency.
        mock_current_user: Mock for tenant-scoped user dependency.
        mock_authenticated_user: Mock for tenant-bootstrap user dependency.
            If None, a default is created from mock_current_user fields.
        single_tenant_mode: Whether to simulate single-tenant mode.

    Returns:
        Configured TestClient.
    """
    app = FastAPI()

    if mock_authenticated_user is None:
        mock_authenticated_user = AuthenticatedUser(
            user_id=mock_current_user.user_id,
            username=mock_current_user.username,
        )

    app.dependency_overrides[get_tenant_service] = lambda: mock_tenant_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_authenticated_user] = lambda: mock_authenticated_user
    app.dependency_overrides[get_spicedb_client] = lambda: mock_authz
    app.dependency_overrides[_get_single_tenant_mode] = lambda: single_tenant_mode

    app.include_router(router)
    return TestClient(app)


class TestCreateTenantBlockedInSingleTenantMode:
    """POST /iam/tenants must be blocked in single-tenant mode."""

    def test_returns_403_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should return 403 Forbidden for POST /tenants in single-tenant mode."""
        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        response = client.post("/iam/tenants", json={"name": "Acme Corp"})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "single-tenant" in response.json()["detail"].lower()

    def test_service_not_called_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should never reach the service layer when blocked."""
        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        client.post("/iam/tenants", json={"name": "Acme Corp"})

        mock_tenant_service.create_tenant.assert_not_called()

    def test_allowed_in_multi_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should pass through to handler when in multi-tenant mode."""
        tenant = Tenant.create(name="Acme Corp")
        mock_tenant_service.create_tenant.return_value = tenant

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=False,
        )

        response = client.post("/iam/tenants", json={"name": "Acme Corp"})

        assert response.status_code == status.HTTP_201_CREATED
        mock_tenant_service.create_tenant.assert_called_once()


class TestDeleteTenantBlockedInSingleTenantMode:
    """DELETE /iam/tenants/{id} must be blocked in single-tenant mode."""

    def test_returns_403_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Should return 403 Forbidden for DELETE /tenants/{id} in single-tenant mode."""
        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        response = client.delete(f"/iam/tenants/{valid_tenant_id.value}")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "single-tenant" in response.json()["detail"].lower()

    def test_service_not_called_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Should never reach the service layer when blocked."""
        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        client.delete(f"/iam/tenants/{valid_tenant_id.value}")

        mock_tenant_service.delete_tenant.assert_not_called()

    def test_allowed_in_multi_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Should pass through to handler when in multi-tenant mode."""
        mock_tenant_service.delete_tenant.return_value = True

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=False,
        )

        response = client.delete(f"/iam/tenants/{valid_tenant_id.value}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_tenant_service.delete_tenant.assert_called_once()


class TestUnprotectedRoutesAccessibleInSingleTenantMode:
    """GET and member-management routes must remain accessible in single-tenant mode."""

    def test_list_tenants_allowed_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """GET /iam/tenants should work in single-tenant mode."""
        mock_tenant_service.list_tenants.return_value = []

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        response = client.get("/iam/tenants")

        assert response.status_code == status.HTTP_200_OK

    def test_get_tenant_allowed_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """GET /iam/tenants/{id} should work in single-tenant mode."""
        tenant = Tenant(id=valid_tenant_id, name="default")
        mock_tenant_service.get_tenant.return_value = tenant

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}")

        assert response.status_code == status.HTTP_200_OK

    def test_add_member_allowed_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """POST /iam/tenants/{id}/members should work in single-tenant mode."""
        mock_tenant_service.add_member.return_value = None

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        user_id = str(UserId.generate())
        response = client.post(
            f"/iam/tenants/{valid_tenant_id.value}/members",
            json={"user_id": user_id, "role": "member"},
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_remove_member_allowed_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """DELETE /iam/tenants/{id}/members/{user_id} should work in single-tenant mode."""
        mock_tenant_service.remove_member.return_value = None

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        user_id = str(UserId.generate())
        response = client.delete(
            f"/iam/tenants/{valid_tenant_id.value}/members/{user_id}"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_list_members_allowed_in_single_tenant_mode(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """GET /iam/tenants/{id}/members should work in single-tenant mode."""
        mock_tenant_service.list_members.return_value = []

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_current_user=mock_current_user,
            single_tenant_mode=True,
        )

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}/members")

        assert response.status_code == status.HTTP_200_OK
