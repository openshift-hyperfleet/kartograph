"""Unit tests for Workspace HTTP routes.

Tests the presentation layer for workspace endpoints following
the patterns established in iam/presentation/test_api_key_routes.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import WorkspaceService
from iam.application.value_objects import CurrentUser
from iam.domain.aggregates import Workspace
from iam.domain.value_objects import TenantId, UserId, WorkspaceId
from iam.ports.exceptions import DuplicateWorkspaceNameError


@pytest.fixture
def mock_workspace_service() -> AsyncMock:
    """Mock WorkspaceService for testing."""
    return AsyncMock(spec=WorkspaceService)


@pytest.fixture
def mock_current_user() -> CurrentUser:
    """Mock CurrentUser for authentication."""
    return CurrentUser(
        user_id=UserId(value="test-user-123"),
        username="testuser",
        tenant_id=TenantId.generate(),
    )


@pytest.fixture
def root_workspace(mock_current_user: CurrentUser) -> Workspace:
    """Create a root workspace for use as parent in tests."""
    now = datetime.now(UTC)
    return Workspace(
        id=WorkspaceId.generate(),
        tenant_id=mock_current_user.tenant_id,
        name="Root",
        parent_workspace_id=None,
        is_root=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def child_workspace(
    mock_current_user: CurrentUser, root_workspace: Workspace
) -> Workspace:
    """Create a child workspace for testing."""
    now = datetime.now(UTC)
    return Workspace(
        id=WorkspaceId.generate(),
        tenant_id=mock_current_user.tenant_id,
        name="Engineering",
        parent_workspace_id=root_workspace.id,
        is_root=False,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def test_client(
    mock_workspace_service: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies.user import get_current_user
    from iam.dependencies.workspace import get_workspace_service
    from iam.presentation import router

    app = FastAPI()

    # Override dependencies with mocks
    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    app.include_router(router)

    return TestClient(app)


@pytest.fixture
def unauthenticated_test_client(
    mock_workspace_service: AsyncMock,
) -> TestClient:
    """Create TestClient that simulates unauthenticated requests.

    Overrides get_current_user to raise 401, simulating what the real
    auth dependency does when no credentials are provided.
    """
    from fastapi import HTTPException

    from iam.dependencies.user import get_current_user
    from iam.dependencies.workspace import get_workspace_service
    from iam.presentation import router

    async def raise_unauthorized() -> CurrentUser:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer, API-Key"},
        )

    app = FastAPI()

    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_current_user] = raise_unauthorized

    app.include_router(router)

    return TestClient(app, raise_server_exceptions=False)


class TestCreateWorkspace:
    """Tests for POST /iam/workspaces endpoint."""

    def test_create_workspace_returns_201(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        root_workspace: Workspace,
        child_workspace: Workspace,
    ) -> None:
        """Test POST /workspaces returns 201 with workspace details."""
        mock_workspace_service.create_workspace.return_value = child_workspace

        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": root_workspace.id.value,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["id"] == child_workspace.id.value
        assert result["tenant_id"] == child_workspace.tenant_id.value
        assert result["name"] == "Engineering"
        assert result["parent_workspace_id"] == root_workspace.id.value
        assert result["is_root"] is False
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_workspace_returns_409_for_duplicate_name(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        root_workspace: Workspace,
    ) -> None:
        """Test POST /workspaces returns 409 when name already exists."""
        mock_workspace_service.create_workspace.side_effect = (
            DuplicateWorkspaceNameError(
                "Workspace 'Engineering' already exists in tenant"
            )
        )

        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": root_workspace.id.value,
            },
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    def test_create_workspace_returns_400_for_invalid_parent(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test POST /workspaces returns 400 when parent doesn't exist."""
        fake_parent_id = WorkspaceId.generate().value
        mock_workspace_service.create_workspace.side_effect = ValueError(
            f"Parent workspace {fake_parent_id} does not exist"
        )

        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": fake_parent_id,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "does not exist" in response.json()["detail"]

    def test_create_workspace_returns_422_for_invalid_name(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        root_workspace: Workspace,
    ) -> None:
        """Test POST /workspaces returns 422 for validation errors."""
        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "",
                "parent_workspace_id": root_workspace.id.value,
            },
        )

        # Pydantic validation catches empty name (min_length=1)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_workspace_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Test POST /workspaces returns 401 without authentication."""
        fake_parent_id = WorkspaceId.generate().value

        response = unauthenticated_test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": fake_parent_id,
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetWorkspace:
    """Tests for GET /iam/workspaces/{id} endpoint."""

    def test_get_workspace_returns_200(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
        child_workspace: Workspace,
    ) -> None:
        """Test GET /workspaces/{id} returns 200 with workspace details."""
        mock_workspace_service.get_workspace.return_value = child_workspace

        response = test_client.get(
            f"/iam/workspaces/{child_workspace.id.value}",
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["id"] == child_workspace.id.value
        assert result["tenant_id"] == child_workspace.tenant_id.value
        assert result["name"] == child_workspace.name
        assert child_workspace.parent_workspace_id is not None
        assert (
            result["parent_workspace_id"] == child_workspace.parent_workspace_id.value
        )
        assert result["is_root"] is False
        assert "created_at" in result
        assert "updated_at" in result

    def test_get_workspace_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test GET /workspaces/{id} returns 404 when workspace doesn't exist."""
        mock_workspace_service.get_workspace.return_value = None
        random_id = WorkspaceId.generate().value

        response = test_client.get(
            f"/iam/workspaces/{random_id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_workspace_returns_404_for_different_tenant(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test GET /workspaces/{id} returns 404 for workspace in different tenant.

        The service returns None for cross-tenant workspaces (don't leak existence),
        so the route should return 404 just like a missing workspace.
        """
        mock_workspace_service.get_workspace.return_value = None
        cross_tenant_workspace_id = WorkspaceId.generate().value

        response = test_client.get(
            f"/iam/workspaces/{cross_tenant_workspace_id}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    def test_get_workspace_returns_401_when_not_authenticated(
        self,
        unauthenticated_test_client: TestClient,
    ) -> None:
        """Test GET /workspaces/{id} returns 401 without authentication."""
        random_id = WorkspaceId.generate().value

        response = unauthenticated_test_client.get(
            f"/iam/workspaces/{random_id}",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
