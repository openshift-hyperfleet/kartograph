"""Unit tests for WorkspaceId validation consistency in workspace routes.

Verifies that all workspace routes use WorkspaceId.from_string() for ULID
validation rather than the unchecked WorkspaceId() constructor.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import WorkspaceService
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId


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
def test_client(
    mock_workspace_service: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies.user import get_current_user
    from iam.dependencies.workspace import get_workspace_service
    from iam.presentation import router

    app = FastAPI()

    app.dependency_overrides[get_workspace_service] = lambda: mock_workspace_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    app.include_router(router)

    return TestClient(app)


class TestCreateWorkspaceIdValidation:
    """Tests that POST /workspaces validates parent_workspace_id format."""

    def test_create_workspace_returns_400_for_invalid_parent_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test POST /workspaces returns 400 when parent_workspace_id is not valid ULID."""
        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": "not-a-valid-ulid-value!!!!",
            },
        )

        # Pydantic catches this due to min_length=26/max_length=26 validation
        # but we also need from_string validation for valid-length but invalid ULID
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    def test_create_workspace_returns_400_for_ulid_length_but_invalid_chars(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test POST /workspaces returns 400 for 26-char string with invalid ULID chars."""
        # 26 chars but contains invalid characters for ULID
        invalid_ulid = "ZZZZZZZZZZZZZZZZZZZZZZZZZZ"

        response = test_client.post(
            "/iam/workspaces",
            json={
                "name": "Engineering",
                "parent_workspace_id": invalid_ulid,
            },
        )

        # Should be 400 (from_string validation) not 500 (uncaught error)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid parent workspace id" in response.json()["detail"].lower()
        # Service should NOT have been called
        mock_workspace_service.create_workspace.assert_not_called()


class TestGetWorkspaceIdValidation:
    """Tests that GET /workspaces/{workspace_id} validates ID format."""

    def test_get_workspace_returns_400_for_invalid_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test GET /workspaces/{id} returns 400 when ID is not valid ULID."""
        response = test_client.get(
            "/iam/workspaces/invalid-id",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid workspace id" in response.json()["detail"].lower()
        mock_workspace_service.get_workspace.assert_not_called()


class TestDeleteWorkspaceIdValidation:
    """Tests that DELETE /workspaces/{workspace_id} validates ID format."""

    def test_delete_workspace_returns_400_for_invalid_id(
        self,
        test_client: TestClient,
        mock_workspace_service: AsyncMock,
    ) -> None:
        """Test DELETE /workspaces/{id} returns 400 when ID is not valid ULID."""
        response = test_client.delete(
            "/iam/workspaces/invalid-id",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid workspace id" in response.json()["detail"].lower()
        mock_workspace_service.delete_workspace.assert_not_called()
