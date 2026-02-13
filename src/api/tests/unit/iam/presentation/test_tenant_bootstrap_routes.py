"""Unit tests for tenant bootstrap routes (list_tenants, create_tenant).

These tests verify that the tenant bootstrap endpoints (list and create)
use get_authenticated_user instead of get_current_user, allowing them
to work without X-Tenant-ID header context.

This fixes the chicken-and-egg problem where users need to list/create
tenants before they have a tenant context.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import TenantService
from iam.application.value_objects import AuthenticatedUser
from iam.dependencies.multi_tenant_mode import _get_single_tenant_mode
from iam.dependencies.tenant import get_tenant_service
from iam.dependencies.user import get_authenticated_user
from iam.domain.aggregates import Tenant
from iam.domain.value_objects import UserId
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
def mock_authenticated_user() -> AuthenticatedUser:
    """Mock AuthenticatedUser for authentication (no tenant_id)."""
    return AuthenticatedUser(
        user_id=UserId(value="test-user-123"),
        username="testuser",
    )


def _create_test_client(
    *,
    mock_tenant_service: AsyncMock,
    mock_authz: AsyncMock,
    mock_authenticated_user: AuthenticatedUser,
    single_tenant_mode: bool = False,
) -> TestClient:
    """Create a TestClient with dependency overrides.

    Args:
        mock_tenant_service: Mock for TenantService dependency.
        mock_authz: Mock for AuthorizationProvider dependency.
        mock_authenticated_user: Mock for authenticated user dependency.
        single_tenant_mode: Whether to simulate single-tenant mode.

    Returns:
        Configured TestClient.
    """
    app = FastAPI()

    app.dependency_overrides[get_tenant_service] = lambda: mock_tenant_service
    app.dependency_overrides[get_authenticated_user] = lambda: mock_authenticated_user
    app.dependency_overrides[get_spicedb_client] = lambda: mock_authz
    app.dependency_overrides[_get_single_tenant_mode] = lambda: single_tenant_mode

    app.include_router(router)
    return TestClient(app)


class TestListTenantsWithoutTenantContext:
    """GET /iam/tenants should work without X-Tenant-ID header.

    The list_tenants endpoint uses get_authenticated_user (not get_current_user),
    so it only requires authentication, not tenant context resolution.
    """

    def test_list_tenants_succeeds_with_authenticated_user(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Should return 200 when user is authenticated but has no tenant context."""
        mock_tenant_service.list_tenants.return_value = []

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_authenticated_user=mock_authenticated_user,
        )

        response = client.get("/iam/tenants")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
        mock_tenant_service.list_tenants.assert_called_once()

    def test_list_tenants_returns_tenant_data(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Should return tenant data from the service."""
        tenant = Tenant.create(name="Acme Corp")
        mock_tenant_service.list_tenants.return_value = [tenant]

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_authenticated_user=mock_authenticated_user,
        )

        response = client.get("/iam/tenants")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Acme Corp"


class TestCreateTenantWithoutTenantContext:
    """POST /iam/tenants should work without X-Tenant-ID header.

    The create_tenant endpoint uses get_authenticated_user (not get_current_user),
    so it only requires authentication, not tenant context resolution.
    """

    def test_create_tenant_succeeds_with_authenticated_user(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Should return 201 when user is authenticated but has no tenant context."""
        tenant = Tenant.create(name="Acme Corp")
        mock_tenant_service.create_tenant.return_value = tenant

        client = _create_test_client(
            mock_tenant_service=mock_tenant_service,
            mock_authz=mock_authz,
            mock_authenticated_user=mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.post("/iam/tenants", json={"name": "Acme Corp"})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "Acme Corp"
        mock_tenant_service.create_tenant.assert_called_once_with(name="Acme Corp")
