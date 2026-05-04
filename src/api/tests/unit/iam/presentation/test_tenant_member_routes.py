"""Unit tests for tenant member management routes.

Verifies correct HTTP responses for:
- POST /iam/tenants/{id}/members (add member)
- DELETE /iam/tenants/{id}/members/{user_id} (remove member)
- GET /iam/tenants/{id}/members (list members)

Spec: specs/iam/tenants.spec.md
Requirements:
- Add Tenant Member
- Remove Tenant Member
- List Tenant Members
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import TenantService
from iam.application.value_objects import CurrentUser
from iam.dependencies.tenant import get_tenant_service
from iam.dependencies.user import get_authenticated_user, get_current_user
from iam.domain.exceptions import CannotRemoveLastAdminError
from iam.domain.value_objects import TenantId, UserId
from iam.ports.exceptions import UnauthorizedError
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
def valid_tenant_id() -> TenantId:
    """A valid tenant ID."""
    return TenantId.generate()


@pytest.fixture
def mock_current_user(valid_tenant_id: TenantId) -> CurrentUser:
    """Mock current user with tenant context."""
    return CurrentUser(
        user_id=UserId(value="admin-user-123"),
        username="adminuser",
        tenant_id=valid_tenant_id,
    )


def _make_client(
    mock_tenant_service: AsyncMock,
    mock_authz: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Build a test client with overridden dependencies."""
    from iam.application.value_objects import AuthenticatedUser

    app = FastAPI()
    mock_authenticated_user = AuthenticatedUser(
        user_id=mock_current_user.user_id,
        username=mock_current_user.username,
    )

    app.dependency_overrides[get_tenant_service] = lambda: mock_tenant_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_authenticated_user] = lambda: mock_authenticated_user
    app.dependency_overrides[get_spicedb_client] = lambda: mock_authz
    app.include_router(router)
    return TestClient(app)


class TestAddTenantMemberRoute:
    """Tests for POST /iam/tenants/{id}/members."""

    def test_returns_201_on_successful_add(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Successful member addition returns 201 Created."""
        mock_tenant_service.add_member = AsyncMock(return_value=None)
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.post(
            f"/iam/tenants/{valid_tenant_id.value}/members",
            json={"user_id": "new-user-456", "role": "member"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["user_id"] == "new-user-456"
        assert data["role"] == "member"

    def test_returns_403_when_unauthorized(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 403 when requesting user lacks administrate permission."""
        mock_tenant_service.add_member = AsyncMock(
            side_effect=UnauthorizedError("Insufficient permissions")
        )
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.post(
            f"/iam/tenants/{valid_tenant_id.value}/members",
            json={"user_id": "new-user-456", "role": "member"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_409_when_demoting_last_admin(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Demoting the last admin returns 409 Conflict.

        Spec: Scenario 'Demote last admin'
        - GIVEN a tenant with exactly one admin
        - WHEN that admin's role is changed to `member`
        - THEN the request is rejected with a conflict error
        """
        mock_tenant_service.add_member = AsyncMock(
            side_effect=CannotRemoveLastAdminError()
        )
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.post(
            f"/iam/tenants/{valid_tenant_id.value}/members",
            json={"user_id": "last-admin-id", "role": "member"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        detail = response.json().get("detail", "")
        assert "admin" in detail.lower()

    def test_returns_404_when_tenant_not_found(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 404 when the tenant does not exist."""
        mock_tenant_service.add_member = AsyncMock(
            side_effect=ValueError("Tenant not found")
        )
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.post(
            f"/iam/tenants/{valid_tenant_id.value}/members",
            json={"user_id": "new-user-456", "role": "member"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_400_for_invalid_tenant_id(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Returns 400 for an invalid tenant ID format."""
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.post(
            "/iam/tenants/not-a-valid-ulid/members",
            json={"user_id": "some-user", "role": "member"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_422_for_invalid_role(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 422 for an invalid role value (not admin or member)."""
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.post(
            f"/iam/tenants/{valid_tenant_id.value}/members",
            json={"user_id": "some-user", "role": "superadmin"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRemoveTenantMemberRoute:
    """Tests for DELETE /iam/tenants/{id}/members/{user_id}."""

    def test_returns_204_on_successful_removal(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Successful member removal returns 204 No Content."""
        mock_tenant_service.remove_member = AsyncMock(return_value=None)
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.delete(
            f"/iam/tenants/{valid_tenant_id.value}/members/user-to-remove"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_returns_403_when_unauthorized(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 403 when requesting user lacks administrate permission."""
        mock_tenant_service.remove_member = AsyncMock(
            side_effect=UnauthorizedError("Insufficient permissions")
        )
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.delete(
            f"/iam/tenants/{valid_tenant_id.value}/members/some-user"
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_409_when_removing_last_admin(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Removing the last admin returns 409 Conflict.

        Spec: Scenario 'Remove last admin'
        - GIVEN a tenant with exactly one admin
        - WHEN an attempt is made to remove that admin
        - THEN the request is rejected with a conflict error
        """
        mock_tenant_service.remove_member = AsyncMock(
            side_effect=CannotRemoveLastAdminError()
        )
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.delete(
            f"/iam/tenants/{valid_tenant_id.value}/members/last-admin-id"
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_returns_404_when_tenant_not_found(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 404 when the tenant does not exist."""
        mock_tenant_service.remove_member = AsyncMock(
            side_effect=ValueError("Tenant not found")
        )
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.delete(
            f"/iam/tenants/{valid_tenant_id.value}/members/some-user"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestListTenantMembersRoute:
    """Tests for GET /iam/tenants/{id}/members."""

    def test_returns_200_with_member_list(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 200 with members when user is admin.

        Spec: Scenario 'Authorized listing'
        """
        mock_tenant_service.list_members = AsyncMock(
            return_value=[
                ("user-admin-1", "admin"),
                ("user-member-1", "member"),
            ]
        )
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}/members")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert {"user_id": "user-admin-1", "role": "admin"} in data
        assert {"user_id": "user-member-1", "role": "member"} in data

    def test_returns_403_when_not_admin(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 403 when requesting user is not a tenant admin.

        Spec: Scenario 'Unauthorized listing'
        """
        mock_tenant_service.list_members = AsyncMock(
            side_effect=UnauthorizedError("Insufficient permissions")
        )
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}/members")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_404_when_tenant_not_found(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 404 when tenant does not exist."""
        mock_tenant_service.list_members = AsyncMock(return_value=None)
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}/members")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_empty_list_for_tenant_with_no_members(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Returns 200 with empty list when tenant has no members."""
        mock_tenant_service.list_members = AsyncMock(return_value=[])
        client = _make_client(mock_tenant_service, mock_authz, mock_current_user)

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}/members")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
