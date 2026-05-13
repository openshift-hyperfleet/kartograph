"""Unit tests for user lookup routes.

Verifies correct HTTP responses for:
- GET /iam/users?ids=id1,id2 (batch ID resolution)
- GET /iam/users?search=alice (text search)

Spec: specs/iam/users.spec.md
Requirements:
- Batch resolve by IDs
- Search by text
- ids and search are mutually exclusive
- Empty request: 422
- More than 100 IDs: 422
- Auth required (401)
- Tenant scoping via SpiceDB
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user, get_user_repository
from iam.domain.aggregates import User
from iam.domain.value_objects import TenantId, UserId
from iam.presentation import router
from infrastructure.authorization_dependencies import get_spicedb_client
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import SubjectRelation


@pytest.fixture
def valid_tenant_id() -> TenantId:
    """A valid tenant ID."""
    return TenantId.generate()


@pytest.fixture
def mock_current_user(valid_tenant_id: TenantId) -> CurrentUser:
    """Mock current user with tenant context."""
    return CurrentUser(
        user_id=UserId(value="caller-user-id"),
        username="caller",
        tenant_id=valid_tenant_id,
    )


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Mock UserRepository for testing."""
    from iam.infrastructure.user_repository import UserRepository

    return AsyncMock(spec=UserRepository)


@pytest.fixture
def mock_authz() -> AsyncMock:
    """Mock AuthorizationProvider for testing."""
    return AsyncMock(spec=AuthorizationProvider)


def _make_client(
    mock_current_user: CurrentUser,
    mock_user_repo: AsyncMock,
    mock_authz: AsyncMock,
) -> TestClient:
    """Build a test client with overridden dependencies."""
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repo
    app.dependency_overrides[get_spicedb_client] = lambda: mock_authz
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def client(
    mock_current_user: CurrentUser,
    mock_user_repo: AsyncMock,
    mock_authz: AsyncMock,
) -> TestClient:
    """TestClient with all dependencies overridden."""
    return _make_client(mock_current_user, mock_user_repo, mock_authz)


class TestBatchResolve:
    """Tests for GET /iam/users?ids=..."""

    def test_returns_matching_users(
        self,
        client: TestClient,
        mock_user_repo: AsyncMock,
        mock_authz: AsyncMock,
    ) -> None:
        """GET /iam/users?ids=id1,id2 returns matching users."""
        mock_authz.lookup_subjects.return_value = [
            SubjectRelation(subject_id="id1", relation="member"),
            SubjectRelation(subject_id="id2", relation="member"),
        ]
        mock_user_repo.get_by_ids.return_value = [
            User(
                id=UserId(value="id1"),
                username="alice",
                name="Alice",
                email="alice@example.com",
            ),
            User(
                id=UserId(value="id2"),
                username="bob",
                name="Bob",
                email=None,
            ),
        ]

        response = client.get("/iam/users?ids=id1,id2")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["users"]) == 2
        assert data["users"][0]["username"] == "alice"
        assert data["users"][0]["email"] == "alice@example.com"
        assert data["users"][1]["username"] == "bob"
        assert data["users"][1]["email"] is None
        assert data["count"] == 2

    def test_filters_by_tenant_membership(
        self,
        client: TestClient,
        mock_user_repo: AsyncMock,
        mock_authz: AsyncMock,
    ) -> None:
        """Only users who are members of the caller's tenant are returned."""
        # id2 is not a tenant member
        mock_authz.lookup_subjects.return_value = [
            SubjectRelation(subject_id="id1", relation="member"),
        ]
        mock_user_repo.get_by_ids.return_value = [
            User(id=UserId(value="id1"), username="alice"),
        ]

        response = client.get("/iam/users?ids=id1,id2")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["users"]) == 1
        assert data["users"][0]["username"] == "alice"

    def test_omits_unknown_ids(
        self,
        client: TestClient,
        mock_user_repo: AsyncMock,
        mock_authz: AsyncMock,
    ) -> None:
        """IDs that don't match any user are silently omitted."""
        mock_authz.lookup_subjects.return_value = [
            SubjectRelation(subject_id="id1", relation="member"),
            SubjectRelation(subject_id="unknown", relation="member"),
        ]
        mock_user_repo.get_by_ids.return_value = [
            User(id=UserId(value="id1"), username="alice"),
        ]

        response = client.get("/iam/users?ids=id1,unknown")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["users"]) == 1

    def test_returns_empty_when_no_ids_in_tenant(
        self,
        client: TestClient,
        mock_user_repo: AsyncMock,
        mock_authz: AsyncMock,
    ) -> None:
        """Returns empty list when none of the requested IDs are tenant members."""
        mock_authz.lookup_subjects.return_value = []

        response = client.get("/iam/users?ids=id1,id2")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["users"]) == 0
        assert data["count"] == 0
        # Should not call the repo if no IDs match tenant
        mock_user_repo.get_by_ids.assert_not_called()


class TestSearch:
    """Tests for GET /iam/users?search=..."""

    def test_returns_matching_users(
        self,
        client: TestClient,
        mock_user_repo: AsyncMock,
        mock_authz: AsyncMock,
    ) -> None:
        """GET /iam/users?search=ali returns matching tenant members."""
        mock_authz.lookup_subjects.return_value = [
            SubjectRelation(subject_id="id1", relation="member"),
        ]
        mock_user_repo.search.return_value = [
            User(
                id=UserId(value="id1"),
                username="alice",
                name="Alice Smith",
                email="alice@example.com",
            ),
        ]

        response = client.get("/iam/users?search=ali")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["users"]) == 1
        assert data["users"][0]["username"] == "alice"

    def test_filters_search_results_by_tenant(
        self,
        client: TestClient,
        mock_user_repo: AsyncMock,
        mock_authz: AsyncMock,
    ) -> None:
        """Search results are filtered to only include tenant members."""
        mock_authz.lookup_subjects.return_value = [
            SubjectRelation(subject_id="id1", relation="member"),
        ]
        # Repo returns users from all tenants
        mock_user_repo.search.return_value = [
            User(id=UserId(value="id1"), username="alice"),
            User(id=UserId(value="id2"), username="alice2"),  # not in tenant
        ]

        response = client.get("/iam/users?search=alice")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["users"]) == 1
        assert data["users"][0]["id"] == "id1"


class TestValidation:
    """Tests for request validation."""

    def test_empty_request_returns_422(self, client: TestClient) -> None:
        """Request with neither ids nor search returns 422."""
        response = client.get("/iam/users")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_too_many_ids_returns_422(self, client: TestClient) -> None:
        """More than 100 IDs returns 422."""
        ids = ",".join([f"id{i}" for i in range(101)])

        response = client.get(f"/iam/users?ids={ids}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_mutually_exclusive_params_returns_422(self, client: TestClient) -> None:
        """Both ids and search returns 422."""
        response = client.get("/iam/users?ids=id1&search=alice")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestAuthentication:
    """Tests for authentication enforcement."""

    def test_unauthenticated_returns_401(self) -> None:
        """When auth fails, returns 401."""

        async def raise_unauthorized() -> CurrentUser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer, API-Key"},
            )

        app = FastAPI()
        app.dependency_overrides[get_current_user] = raise_unauthorized
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/iam/users?ids=id1")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
