"""Unit tests for API Key HTTP routes.

Tests the presentation layer for API key CRUD endpoints following
the patterns established in graph/presentation/test_routes.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from iam.application.services.api_key_service import APIKeyService
from iam.application.value_objects import CurrentUser
from iam.domain.aggregates import APIKey
from iam.domain.value_objects import APIKeyId, TenantId, UserId
from iam.ports.exceptions import (
    APIKeyAlreadyRevokedError,
    APIKeyNotFoundError,
    DuplicateAPIKeyNameError,
)


@pytest.fixture
def mock_api_key_service() -> AsyncMock:
    """Mock APIKeyService for testing."""
    return AsyncMock(spec=APIKeyService)


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
def sample_api_key(mock_current_user: CurrentUser) -> APIKey:
    """Create a sample APIKey aggregate for testing."""
    return APIKey(
        id=APIKeyId.generate(),
        created_by_user_id=mock_current_user.user_id,
        tenant_id=mock_current_user.tenant_id,
        name="my-api-key",
        key_hash="$2b$12$hashedvalue",
        prefix="karto_abc123",
        created_at=datetime.now(UTC),
        expires_at=(datetime.now(UTC) + timedelta(days=1)),
        last_used_at=None,
        is_revoked=False,
    )


@pytest.fixture
def test_client(
    mock_api_key_service: AsyncMock,
    mock_authz: AsyncMock,
    mock_current_user: CurrentUser,
) -> TestClient:
    """Create TestClient with mocked dependencies."""
    from iam.dependencies import get_current_user, get_api_key_service
    from iam.presentation.routes import router
    from infrastructure.authorization_dependencies import get_spicedb_client

    app = FastAPI()

    # Override dependencies with mocks
    app.dependency_overrides[get_api_key_service] = lambda: mock_api_key_service
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_spicedb_client] = lambda: mock_authz

    app.include_router(router)

    return TestClient(app)


class TestCreateAPIKeyRoute:
    """Tests for POST /iam/api-keys endpoint."""

    def test_creates_api_key_returns_201(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
        sample_api_key: APIKey,
    ) -> None:
        """Should create API key and return 201 with secret."""
        plaintext_secret = (
            "karto_abc123def456ghi789jkl012mno345pqr678"  # gitleaks:allow
        )
        mock_api_key_service.create_api_key.return_value = (
            sample_api_key,
            plaintext_secret,
        )

        response = test_client.post(
            "/iam/api-keys",
            json={"name": "my-api-key"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["id"] == sample_api_key.id.value
        assert result["name"] == "my-api-key"
        assert result["prefix"] == sample_api_key.prefix
        assert result["is_revoked"] is False

    def test_returns_secret_in_response(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
        sample_api_key: APIKey,
    ) -> None:
        """Should return the plaintext secret only at creation time."""
        plaintext_secret = (
            "karto_abc123def456ghi789jkl012mno345pqr678"  # gitleaks:allow
        )
        mock_api_key_service.create_api_key.return_value = (
            sample_api_key,
            plaintext_secret,
        )

        response = test_client.post(
            "/iam/api-keys",
            json={"name": "my-api-key"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        result = response.json()
        assert result["secret"] == plaintext_secret

    def test_requires_name_field(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
    ) -> None:
        """Should return 422 when name field is missing."""
        response = test_client.post(
            "/iam/api-keys",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_validates_name_min_length(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
    ) -> None:
        """Should return 422 when name is empty string."""
        response = test_client.post(
            "/iam/api-keys",
            json={"name": ""},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_returns_409_on_duplicate_name(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
    ) -> None:
        """Should return 409 when API key name already exists for user."""
        mock_api_key_service.create_api_key.side_effect = DuplicateAPIKeyNameError(
            "API key 'my-api-key' already exists for user"
        )

        response = test_client.post(
            "/iam/api-keys",
            json={"name": "my-api-key"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    def test_accepts_optional_expires_in_days(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
        sample_api_key: APIKey,
        mock_current_user: CurrentUser,
    ) -> None:
        """Should accept optional expires_in_days parameter."""
        plaintext_secret = (
            "karto_abc123def456ghi789jkl012mno345pqr678"  # gitleaks:allow
        )
        mock_api_key_service.create_api_key.return_value = (
            sample_api_key,
            plaintext_secret,
        )

        response = test_client.post(
            "/iam/api-keys",
            json={"name": "my-api-key", "expires_in_days": 30},
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify the service was called with the expires_in_days parameter
        mock_api_key_service.create_api_key.assert_called_once_with(
            created_by_user_id=mock_current_user.user_id,
            tenant_id=mock_current_user.tenant_id,
            name="my-api-key",
            expires_in_days=30,
        )

    def test_validates_expires_in_days_minimum(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
    ) -> None:
        """Should return 422 when expires_in_days is less than 1."""
        response = test_client.post(
            "/iam/api-keys",
            json={"name": "my-api-key", "expires_in_days": 0},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_validates_expires_in_days_maximum(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
    ) -> None:
        """Should return 422 when expires_in_days exceeds 3650 (10 years)."""
        response = test_client.post(
            "/iam/api-keys",
            json={"name": "my-api-key", "expires_in_days": 3651},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestListAPIKeysRoute:
    """Tests for GET /iam/api-keys endpoint."""

    def test_lists_api_keys_for_user(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
        mock_authz: AsyncMock,
        sample_api_key: APIKey,
    ) -> None:
        """Should list all API keys for the current user."""
        # Mock SpiceDB lookup_resources to return the sample key's ID
        mock_authz.lookup_resources.return_value = [sample_api_key.id.value]
        mock_api_key_service.list_api_keys.return_value = [sample_api_key]

        response = test_client.get("/iam/api-keys")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert len(result) == 1
        assert result[0]["id"] == sample_api_key.id.value
        assert result[0]["name"] == sample_api_key.name

    def test_returns_empty_list_when_no_keys(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
        mock_authz: AsyncMock,
    ) -> None:
        """Should return empty list when user has no API keys."""
        # Mock SpiceDB returning no viewable keys
        mock_authz.lookup_resources.return_value = []
        mock_api_key_service.list_api_keys.return_value = []

        response = test_client.get("/iam/api-keys")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result == []

    def test_never_returns_secret_or_hash(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
        mock_authz: AsyncMock,
        sample_api_key: APIKey,
    ) -> None:
        """Should never include secret or hash in list response."""
        # Mock SpiceDB lookup_resources to return the sample key's ID
        mock_authz.lookup_resources.return_value = [sample_api_key.id.value]
        mock_api_key_service.list_api_keys.return_value = [sample_api_key]

        response = test_client.get("/iam/api-keys")

        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert "secret" not in result[0]
        assert "key_hash" not in result[0]
        assert "hash" not in result[0]


class TestRevokeAPIKeyRoute:
    """Tests for DELETE /iam/api-keys/{api_key_id} endpoint."""

    def test_revokes_api_key_returns_204(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
        sample_api_key: APIKey,
    ) -> None:
        """Should revoke API key and return 204 No Content."""
        mock_api_key_service.revoke_api_key.return_value = None

        response = test_client.delete(f"/iam/api-keys/{sample_api_key.id.value}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

    def test_returns_404_when_not_found(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
    ) -> None:
        """Should return 404 when API key does not exist."""
        api_key_id = APIKeyId.generate()
        mock_api_key_service.revoke_api_key.side_effect = APIKeyNotFoundError(
            f"API key {api_key_id.value} not found"
        )

        response = test_client.delete(f"/iam/api-keys/{api_key_id.value}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]

    def test_returns_409_when_already_revoked(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
        sample_api_key: APIKey,
    ) -> None:
        """Should return 409 when API key is already revoked."""
        mock_api_key_service.revoke_api_key.side_effect = APIKeyAlreadyRevokedError(
            f"API key {sample_api_key.id.value} is already revoked"
        )

        response = test_client.delete(f"/iam/api-keys/{sample_api_key.id.value}")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already revoked" in response.json()["detail"]

    def test_returns_422_for_invalid_ulid(
        self,
        test_client: TestClient,
        mock_api_key_service: AsyncMock,
    ) -> None:
        """Should return 422 when API key ID is not a valid ULID."""
        response = test_client.delete("/iam/api-keys/not-a-valid-ulid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "Invalid" in response.json()["detail"]
