"""Unit tests for GET /iam/groups route.

Tests the presentation layer for listing all groups in a tenant.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services import GroupService
from iam.application.value_objects import CurrentUser
from iam.domain.aggregates import Group
from iam.domain.value_objects import GroupRole, TenantId, UserId


@pytest.fixture
def mock_group_service() -> AsyncMock:
    """Mock GroupService for testing."""
    return AsyncMock(spec=GroupService)


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
    mock_group_service: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies.group import get_group_service
    from iam.dependencies.user import get_current_user
    from iam.presentation import router

    app = FastAPI()

    app.dependency_overrides[get_group_service] = lambda: mock_group_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user

    app.include_router(router)

    return TestClient(app)


class TestListGroups:
    """Tests for GET /iam/groups endpoint."""

    def test_list_groups_returns_200_with_groups(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
        mock_current_user: CurrentUser,
    ) -> None:
        """Test GET /groups returns 200 with list of groups."""
        group1 = Group.create(
            name="Engineering",
            tenant_id=mock_current_user.tenant_id,
        )
        group1.add_member(UserId(value="alice-id"), GroupRole.ADMIN)

        group2 = Group.create(
            name="Marketing",
            tenant_id=mock_current_user.tenant_id,
        )
        group2.add_member(UserId(value="bob-id"), GroupRole.ADMIN)

        mock_group_service.list_groups.return_value = [group1, group2]

        response = test_client.get("/iam/groups")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result) == 2
        assert result[0]["name"] == "Engineering"
        assert result[1]["name"] == "Marketing"

    def test_list_groups_returns_empty_list(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test GET /groups returns 200 with empty list when no groups exist."""
        mock_group_service.list_groups.return_value = []

        response = test_client.get("/iam/groups")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_groups_returns_500_on_unexpected_error(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test GET /groups returns 500 on unexpected exceptions."""
        mock_group_service.list_groups.side_effect = Exception("DB connection failed")

        response = test_client.get("/iam/groups")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to list groups" in response.json()["detail"].lower()

    def test_list_groups_calls_service(
        self,
        test_client: TestClient,
        mock_group_service: AsyncMock,
    ) -> None:
        """Test that service list_groups is called."""
        mock_group_service.list_groups.return_value = []

        test_client.get("/iam/groups")

        mock_group_service.list_groups.assert_called_once()
