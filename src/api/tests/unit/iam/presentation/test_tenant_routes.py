"""Unit tests for core tenant CRUD routes.

Verifies HTTP responses for:
- POST /iam/tenants (create tenant)
- GET /iam/tenants/{id} (get tenant by ID)
- GET /iam/tenants (list tenants)
- DELETE /iam/tenants/{id} (delete tenant)

Spec: specs/iam/tenants.spec.md
Requirements:
- Tenant Creation
- Tenant Retrieval
- Tenant Listing
- Tenant Deletion
- Tenant Name Validation
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import TenantService
from iam.application.value_objects import AuthenticatedUser, CurrentUser
from iam.dependencies.multi_tenant_mode import _get_single_tenant_mode
from iam.dependencies.tenant import get_tenant_service
from iam.dependencies.user import get_authenticated_user, get_current_user
from iam.domain.aggregates import Tenant
from iam.domain.value_objects import TenantId, UserId
from iam.ports.exceptions import DuplicateTenantNameError, UnauthorizedError
from iam.presentation import router
from infrastructure.authorization_dependencies import get_spicedb_client


@pytest.fixture
def mock_tenant_service() -> AsyncMock:
    """Mock TenantService for testing."""
    return AsyncMock(spec=TenantService)


@pytest.fixture
def mock_authz() -> AsyncMock:
    """Mock AuthorizationProvider."""
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


@pytest.fixture
def mock_authenticated_user() -> AuthenticatedUser:
    """Mock authenticated user (no tenant context)."""
    return AuthenticatedUser(
        user_id=UserId(value="admin-user-123"),
        username="adminuser",
    )


def _make_client(
    mock_tenant_service: AsyncMock,
    mock_authz: AsyncMock,
    mock_current_user: CurrentUser,
    mock_authenticated_user: AuthenticatedUser,
    *,
    single_tenant_mode: bool = False,
) -> TestClient:
    """Build a test client with overridden dependencies."""
    app = FastAPI()

    app.dependency_overrides[get_tenant_service] = lambda: mock_tenant_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_authenticated_user] = lambda: mock_authenticated_user
    app.dependency_overrides[get_spicedb_client] = lambda: mock_authz
    app.dependency_overrides[_get_single_tenant_mode] = lambda: single_tenant_mode
    app.include_router(router)
    return TestClient(app)


class TestCreateTenantRoute:
    """Tests for POST /iam/tenants.

    Spec: Requirement 'Tenant Creation'
    """

    def test_returns_201_with_id_and_name_on_successful_creation(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Successful tenant creation returns 201 with id and name.

        Spec: Scenario 'Successful creation'
        - WHEN the user creates a tenant with name "Acme Corp"
        - THEN a tenant is created with a generated ULID identifier
        """
        tenant = Tenant.create(name="Acme Corp")
        mock_tenant_service.create_tenant.return_value = tenant

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.post("/iam/tenants", json={"name": "Acme Corp"})

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Acme Corp"
        assert "id" in data
        assert data["id"] == tenant.id.value

    def test_returns_409_for_duplicate_tenant_name(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Duplicate tenant name returns 409 Conflict.

        Spec: Scenario 'Duplicate name'
        - GIVEN a tenant named "Acme Corp" already exists
        - WHEN a user attempts to create another tenant named "Acme Corp"
        - THEN the request is rejected with a conflict error
        """
        mock_tenant_service.create_tenant.side_effect = DuplicateTenantNameError(
            "Acme Corp"
        )

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.post("/iam/tenants", json={"name": "Acme Corp"})

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_calls_service_with_creator_user_id(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Service is called with the authenticated user as creator.

        Spec: Scenario 'Successful creation'
        - AND the creating user is granted the admin role on the tenant
        """
        tenant = Tenant.create(name="Acme Corp")
        mock_tenant_service.create_tenant.return_value = tenant

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        client.post("/iam/tenants", json={"name": "Acme Corp"})

        mock_tenant_service.create_tenant.assert_called_once_with(
            name="Acme Corp",
            creator_id=mock_authenticated_user.user_id,
        )


class TestTenantNameValidation:
    """Tests for Tenant Name Validation via route request model.

    Spec: Requirement 'Tenant Name Validation'
    """

    def test_returns_422_for_empty_name(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Empty name is rejected with 422 Unprocessable Entity.

        Spec: Scenario 'Empty name'
        - GIVEN an empty string as tenant name
        - WHEN used to create a tenant
        - THEN the request is rejected with a validation error
        """
        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.post("/iam/tenants", json={"name": ""})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        # Service should not be called with invalid input
        mock_tenant_service.create_tenant.assert_not_called()

    def test_returns_422_for_name_exceeding_255_characters(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Name exceeding 255 characters is rejected with 422.

        Spec: Scenario 'Name too long'
        - GIVEN a name exceeding 255 characters
        - WHEN used to create a tenant
        - THEN the request is rejected with a validation error
        """
        too_long_name = "A" * 256

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.post("/iam/tenants", json={"name": too_long_name})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_tenant_service.create_tenant.assert_not_called()

    def test_accepts_name_with_exactly_255_characters(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Name with exactly 255 characters is accepted.

        Spec: Scenario 'Valid name'
        - GIVEN a name between 1 and 255 characters
        - WHEN used to create a tenant
        - THEN the name is accepted
        """
        max_length_name = "A" * 255
        tenant = Tenant.create(name=max_length_name)
        mock_tenant_service.create_tenant.return_value = tenant

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.post("/iam/tenants", json={"name": max_length_name})

        assert response.status_code == status.HTTP_201_CREATED
        mock_tenant_service.create_tenant.assert_called_once()

    def test_accepts_name_with_single_character(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Single-character name is accepted (minimum valid length).

        Spec: Scenario 'Valid name'
        - GIVEN a name between 1 and 255 characters
        """
        tenant = Tenant.create(name="A")
        mock_tenant_service.create_tenant.return_value = tenant

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.post("/iam/tenants", json={"name": "A"})

        assert response.status_code == status.HTTP_201_CREATED


class TestGetTenantRoute:
    """Tests for GET /iam/tenants/{id}.

    Spec: Requirement 'Tenant Retrieval'
    """

    def test_returns_200_with_id_and_name_for_authorized_user(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Authorized retrieval returns 200 with id and name.

        Spec: Scenario 'Authorized retrieval'
        - GIVEN a tenant exists and the requesting user has view permission
        - WHEN the user requests the tenant by ID
        - THEN the tenant's id and name are returned
        """
        tenant = Tenant(id=valid_tenant_id, name="Acme Corp")
        mock_tenant_service.get_tenant.return_value = tenant

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
        )

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == valid_tenant_id.value
        assert data["name"] == "Acme Corp"

    def test_returns_404_when_tenant_not_found(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Tenant not found returns 404.

        Spec: Scenario 'Unauthorized or non-existent'
        - GIVEN a tenant the user cannot view (or does not exist)
        - WHEN the user requests the tenant by ID
        - THEN a not-found response is returned
        """
        mock_tenant_service.get_tenant.return_value = None

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
        )

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_404_when_user_lacks_view_permission(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Unauthorized access returns 404 (no info leakage).

        Spec: Scenario 'Unauthorized or non-existent'
        - AND no distinction is made between "unauthorized" and "missing"
        """
        # Service returns None when user lacks VIEW permission
        mock_tenant_service.get_tenant.return_value = None

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
        )

        response = client.get(f"/iam/tenants/{valid_tenant_id.value}")

        # Both "not found" and "unauthorized" must return 404 (no info leakage)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_400_for_invalid_tenant_id_format(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Invalid tenant ID format returns 400."""
        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
        )

        response = client.get("/iam/tenants/not-a-valid-id")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestListTenantsRoute:
    """Tests for GET /iam/tenants.

    Spec: Requirement 'Tenant Listing'
    """

    def test_returns_only_tenants_user_can_view(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Only tenants user has VIEW permission on are returned.

        Spec: Scenario 'User belongs to multiple tenants'
        - GIVEN a user has view permission on tenants A and B but not C
        - WHEN the user lists tenants
        - THEN tenants A and B are returned
        """
        tenant_a = Tenant(id=TenantId.generate(), name="Tenant A")
        tenant_b = Tenant(id=TenantId.generate(), name="Tenant B")
        mock_tenant_service.list_tenants.return_value = [tenant_a, tenant_b]

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
        )

        response = client.get("/iam/tenants")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        names = {t["name"] for t in data}
        assert "Tenant A" in names
        assert "Tenant B" in names

    def test_returns_empty_list_when_user_has_no_tenants(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
    ) -> None:
        """Empty list returned when user belongs to no tenants.

        Spec: Scenario 'User belongs to no tenants'
        - GIVEN a user has no tenant memberships
        - WHEN the user lists tenants
        - THEN an empty list is returned
        """
        mock_tenant_service.list_tenants.return_value = []

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
        )

        response = client.get("/iam/tenants")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestDeleteTenantRoute:
    """Tests for DELETE /iam/tenants/{id}.

    Spec: Requirement 'Tenant Deletion'
    """

    def test_returns_204_on_successful_deletion(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Successful deletion returns 204 No Content.

        Spec: Scenario 'Successful deletion'
        - GIVEN an authenticated user with administrate permission
        - WHEN the user deletes the tenant
        """
        mock_tenant_service.delete_tenant.return_value = True

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.delete(f"/iam/tenants/{valid_tenant_id.value}")

        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_returns_403_when_user_lacks_administrate_permission(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Non-admin attempting to delete returns 403.

        Spec: Scenario 'Unauthorized deletion'
        - GIVEN a user without administrate permission on a tenant
        - WHEN the user attempts to delete the tenant
        - THEN the request is rejected with a forbidden error
        """
        mock_tenant_service.delete_tenant.side_effect = UnauthorizedError(
            "Insufficient permissions"
        )

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.delete(f"/iam/tenants/{valid_tenant_id.value}")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_404_when_tenant_not_found(
        self,
        mock_tenant_service: AsyncMock,
        mock_authz: AsyncMock,
        mock_current_user: CurrentUser,
        mock_authenticated_user: AuthenticatedUser,
        valid_tenant_id: TenantId,
    ) -> None:
        """Non-existent tenant deletion returns 404."""
        mock_tenant_service.delete_tenant.return_value = False

        client = _make_client(
            mock_tenant_service,
            mock_authz,
            mock_current_user,
            mock_authenticated_user,
            single_tenant_mode=False,
        )

        response = client.delete(f"/iam/tenants/{valid_tenant_id.value}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
