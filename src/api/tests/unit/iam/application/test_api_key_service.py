"""Unit tests for APIKeyService.

Following TDD - write tests first to define desired behavior.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, create_autospec
import uuid

import pytest

from iam.application.services.api_key_service import APIKeyService
from iam.domain.aggregates import APIKey
from iam.domain.value_objects import APIKeyId, TenantId, UserId
from iam.ports.exceptions import (
    APIKeyAlreadyRevokedError,
    APIKeyNotFoundError,
    DuplicateAPIKeyNameError,
)
from iam.ports.repositories import IAPIKeyRepository


@pytest.fixture
def mock_session():
    """Create mock async session with transaction support."""
    session = AsyncMock()
    # Mock transaction context manager properly
    mock_transaction = MagicMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=None)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)
    session.begin = MagicMock(return_value=mock_transaction)
    return session


@pytest.fixture
def mock_api_key_repository():
    """Create mock API key repository."""
    return create_autospec(IAPIKeyRepository, instance=True)


@pytest.fixture
def mock_probe():
    """Create mock API key service probe."""
    from iam.application.observability.api_key_service_probe import APIKeyServiceProbe

    return create_autospec(APIKeyServiceProbe, instance=True)


@pytest.fixture
async def unique_api_key_name() -> str:
    return f"test-unit-api-key-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def api_key_service(mock_session, mock_api_key_repository, mock_probe):
    """Create APIKeyService with mock dependencies."""
    from iam.application.services.api_key_service import APIKeyService

    return APIKeyService(
        session=mock_session,
        api_key_repository=mock_api_key_repository,
        probe=mock_probe,
    )


class TestAPIKeyServiceInit:
    """Tests for APIKeyService initialization."""

    def test_stores_session(self, mock_session, mock_api_key_repository):
        """Service should store session reference."""
        from iam.application.services.api_key_service import APIKeyService

        service = APIKeyService(
            session=mock_session,
            api_key_repository=mock_api_key_repository,
        )
        assert service._session is mock_session

    def test_stores_repository(self, mock_session, mock_api_key_repository):
        """Service should store repository reference."""
        from iam.application.services.api_key_service import APIKeyService

        service = APIKeyService(
            session=mock_session,
            api_key_repository=mock_api_key_repository,
        )
        assert service._api_key_repository is mock_api_key_repository

    def test_uses_default_probe_when_not_provided(
        self, mock_session, mock_api_key_repository
    ):
        """Service should create default probe when not provided."""
        from iam.application.services.api_key_service import APIKeyService

        service = APIKeyService(
            session=mock_session,
            api_key_repository=mock_api_key_repository,
        )
        assert service._probe is not None


class TestAPIKeyServiceCreate:
    """Tests for create_api_key method."""

    @pytest.mark.asyncio
    async def test_creates_api_key_with_hashed_secret(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should create API key with hashed secret stored."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_api_key_repository.save = AsyncMock()

        api_key, plaintext_secret = await api_key_service.create_api_key(
            created_by_user_id=created_by_user_id,
            expires_in_days=1,
            tenant_id=tenant_id,
            name="My CI Key",
        )

        # Verify API key was created
        assert isinstance(api_key, APIKey)
        assert api_key.name == "My CI Key"
        assert api_key.created_by_user_id == created_by_user_id
        assert api_key.tenant_id == tenant_id
        # key_hash should be set and different from plaintext
        assert api_key.key_hash is not None
        assert api_key.key_hash != plaintext_secret

    @pytest.mark.asyncio
    async def test_returns_plaintext_secret_only_at_creation(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should return plaintext secret at creation time."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_api_key_repository.save = AsyncMock()

        api_key, plaintext_secret = await api_key_service.create_api_key(
            created_by_user_id=created_by_user_id,
            expires_in_days=1,
            tenant_id=tenant_id,
            name="My CI Key",
        )

        # Plaintext secret should be returned
        assert plaintext_secret is not None
        assert isinstance(plaintext_secret, str)
        assert len(plaintext_secret) > 20  # Should have substantial length

    @pytest.mark.asyncio
    async def test_secret_has_karto_prefix(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Generated secret should have karto_ prefix."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_api_key_repository.save = AsyncMock()

        api_key, plaintext_secret = await api_key_service.create_api_key(
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            expires_in_days=1,
            name="My CI Key",
        )

        assert plaintext_secret.startswith("karto_")

    @pytest.mark.asyncio
    async def test_records_probe_event_on_success(
        self, api_key_service: APIKeyService, mock_api_key_repository, mock_probe
    ):
        """Should record api_key_created probe event on success."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_api_key_repository.save = AsyncMock()

        api_key, _ = await api_key_service.create_api_key(
            created_by_user_id=created_by_user_id,
            expires_in_days=1,
            tenant_id=tenant_id,
            name="My CI Key",
        )

        mock_probe.api_key_created.assert_called_once()
        call_args = mock_probe.api_key_created.call_args[1]
        assert call_args["api_key_id"] == api_key.id.value
        # Probe uses user_id for logging purposes
        assert call_args["user_id"] == created_by_user_id.value
        assert call_args["name"] == "My CI Key"

    @pytest.mark.asyncio
    async def test_raises_on_duplicate_name(
        self, api_key_service: APIKeyService, mock_api_key_repository, mock_probe
    ):
        """Should raise DuplicateAPIKeyNameError when name exists."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_api_key_repository.save = AsyncMock(
            side_effect=DuplicateAPIKeyNameError("Key name already exists")
        )

        with pytest.raises(DuplicateAPIKeyNameError):
            await api_key_service.create_api_key(
                created_by_user_id=created_by_user_id,
                expires_in_days=1,
                tenant_id=tenant_id,
                name="Duplicate Name",
            )

        mock_probe.api_key_creation_failed.assert_called_once()
        call_args = mock_probe.api_key_creation_failed.call_args[1]
        # Probe uses user_id for logging purposes
        assert call_args["user_id"] == created_by_user_id.value
        assert "already exists" in call_args["error"]

    @pytest.mark.asyncio
    async def test_creates_with_expiration(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should create API key with expiration date when expires_in_days provided."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_api_key_repository.save = AsyncMock()

        api_key, _ = await api_key_service.create_api_key(
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name="Expiring Key",
            expires_in_days=30,
        )

        assert api_key.expires_at is not None
        # Should be roughly 30 days from now
        expected = datetime.now(UTC) + timedelta(days=30)
        # Allow 1 minute tolerance for test execution time
        assert abs((api_key.expires_at - expected).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_stores_prefix_from_secret(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should store prefix (first 12 chars) from secret."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_api_key_repository.save = AsyncMock()

        api_key, plaintext_secret = await api_key_service.create_api_key(
            created_by_user_id=created_by_user_id,
            expires_in_days=1,
            tenant_id=tenant_id,
            name="My Key",
        )

        assert api_key.prefix == plaintext_secret[:12]


class TestAPIKeyServiceRevoke:
    """Tests for revoke_api_key method."""

    @pytest.mark.asyncio
    async def test_revokes_existing_key(
        self, api_key_service: APIKeyService, mock_api_key_repository, mock_probe
    ):
        """Should revoke an existing API key."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        api_key_id = APIKeyId.generate()

        mock_key = APIKey(
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name="My Key",
            key_hash="hash",
            prefix="karto_abc12",
            created_at=datetime.now(UTC),
        )
        mock_api_key_repository.get_by_id = AsyncMock(return_value=mock_key)
        mock_api_key_repository.save = AsyncMock()

        # The service uses user_id (the caller performing the revoke)
        await api_key_service.revoke_api_key(
            api_key_id=api_key_id,
            user_id=created_by_user_id,
            tenant_id=tenant_id,
        )

        # Verify key was revoked and saved
        mock_api_key_repository.save.assert_called_once()
        saved_key = mock_api_key_repository.save.call_args[0][0]
        assert saved_key.is_revoked is True

        # Probe uses user_id for logging purposes
        mock_probe.api_key_revoked.assert_called_once_with(
            api_key_id=api_key_id.value,
            user_id=created_by_user_id.value,
        )

    @pytest.mark.asyncio
    async def test_raises_when_key_not_found(
        self, api_key_service: APIKeyService, mock_api_key_repository, mock_probe
    ):
        """Should raise APIKeyNotFoundError when key doesn't exist."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        api_key_id = APIKeyId.generate()

        mock_api_key_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(APIKeyNotFoundError):
            # The service uses user_id (the caller performing the revoke)
            await api_key_service.revoke_api_key(
                api_key_id=api_key_id,
                user_id=created_by_user_id,
                tenant_id=tenant_id,
            )

        mock_probe.api_key_revocation_failed.assert_called_once()
        call_args = mock_probe.api_key_revocation_failed.call_args[1]
        assert call_args["api_key_id"] == api_key_id.value
        assert "not found" in call_args["error"].lower()

    @pytest.mark.asyncio
    async def test_raises_when_already_revoked(
        self, api_key_service: APIKeyService, mock_api_key_repository, mock_probe
    ):
        """Should raise APIKeyAlreadyRevokedError when key is already revoked."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        api_key_id = APIKeyId.generate()

        mock_key = APIKey(
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=tenant_id,
            name="My Key",
            key_hash="hash",
            prefix="karto_abc12",
            created_at=datetime.now(UTC),
            is_revoked=True,  # Already revoked
        )
        mock_api_key_repository.get_by_id = AsyncMock(return_value=mock_key)

        with pytest.raises(APIKeyAlreadyRevokedError):
            # The service uses user_id (the caller performing the revoke)
            await api_key_service.revoke_api_key(
                api_key_id=api_key_id,
                user_id=created_by_user_id,
                tenant_id=tenant_id,
            )

        mock_probe.api_key_revocation_failed.assert_called_once()
        call_args = mock_probe.api_key_revocation_failed.call_args[1]
        assert call_args["api_key_id"] == api_key_id.value
        assert "already revoked" in call_args["error"].lower()


class TestAPIKeyServiceValidate:
    """Tests for validate_and_get_key method."""

    @pytest.mark.asyncio
    async def test_validates_correct_secret(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should return key when secret is valid."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        api_key_id = APIKeyId.generate()

        # Use real hashing for this test
        from iam.application.security import hash_api_key_secret

        secret = "karto_test_secret_12345"  # gitleaks:allow
        key_hash = hash_api_key_secret(secret)

        mock_key = APIKey(
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=tenant_id,
            name="My Key",
            key_hash=key_hash,
            prefix="karto_test_s",
            created_at=datetime.now(UTC),
        )
        mock_api_key_repository.get_verified_key = AsyncMock(return_value=mock_key)
        mock_api_key_repository.save = AsyncMock()

        result = await api_key_service.validate_and_get_key(secret)

        assert result is not None
        assert result.id == api_key_id

    @pytest.mark.asyncio
    async def test_updates_last_used_at(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should update last_used_at when key is validated."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        api_key_id = APIKeyId.generate()

        from iam.application.security import hash_api_key_secret

        secret = "karto_test_secret_12345"  # gitleaks:allow
        key_hash = hash_api_key_secret(secret)

        mock_key = APIKey(
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=tenant_id,
            name="My Key",
            key_hash=key_hash,
            prefix="karto_test_s",
            created_at=datetime.now(UTC),
            last_used_at=None,
        )
        mock_api_key_repository.get_verified_key = AsyncMock(return_value=mock_key)
        mock_api_key_repository.save = AsyncMock()

        result = await api_key_service.validate_and_get_key(secret)

        assert result is not None
        # Save should have been called to update last_used_at
        mock_api_key_repository.save.assert_called_once()
        saved_key = mock_api_key_repository.save.call_args[0][0]
        assert saved_key.last_used_at is not None

    @pytest.mark.asyncio
    async def test_returns_none_for_revoked_key(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should return None when key is revoked."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        api_key_id = APIKeyId.generate()

        from iam.application.security import hash_api_key_secret

        secret = "karto_test_secret_12345"  # gitleaks:allow
        key_hash = hash_api_key_secret(secret)

        mock_key = APIKey(
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            expires_at=(datetime.now(UTC) + timedelta(days=1)),
            tenant_id=tenant_id,
            name="My Key",
            key_hash=key_hash,
            prefix="karto_test_s",
            created_at=datetime.now(UTC),
            is_revoked=True,
        )
        mock_api_key_repository.get_verified_key = AsyncMock(return_value=mock_key)

        result = await api_key_service.validate_and_get_key(secret)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_expired_key(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should return None when key is expired."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        api_key_id = APIKeyId.generate()

        from iam.application.security import hash_api_key_secret

        secret = "karto_test_secret_12345"  # gitleaks:allow
        key_hash = hash_api_key_secret(secret)

        mock_key = APIKey(
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name="My Key",
            key_hash=key_hash,
            prefix="karto_test_s",
            created_at=datetime.now(UTC) - timedelta(days=60),
            expires_at=datetime.now(UTC) - timedelta(days=30),  # Expired 30 days ago
        )
        mock_api_key_repository.get_verified_key = AsyncMock(return_value=mock_key)

        result = await api_key_service.validate_and_get_key(secret)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_key(
        self, api_key_service: APIKeyService, mock_api_key_repository
    ):
        """Should return None when no key matches prefix."""
        mock_api_key_repository.get_verified_key = AsyncMock(return_value=None)

        result = await api_key_service.validate_and_get_key("karto_nonexistent_key")

        assert result is None
