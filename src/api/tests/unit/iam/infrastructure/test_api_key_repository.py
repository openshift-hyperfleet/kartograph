"""Unit tests for APIKeyRepository.

Following TDD principles - tests verify repository behavior with mocked dependencies.
"""

import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from iam.domain.aggregates import APIKey
from iam.domain.value_objects import APIKeyId, TenantId, UserId
from iam.infrastructure.api_key_repository import APIKeyRepository
from iam.infrastructure.models import APIKeyModel
from iam.ports.exceptions import DuplicateAPIKeyNameError
from iam.ports.repositories import IAPIKeyRepository


@pytest.fixture
def mock_session():
    """Create mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_probe():
    """Create mock repository probe."""
    probe = MagicMock()
    return probe


@pytest.fixture
def mock_outbox():
    """Create mock outbox repository."""
    outbox = MagicMock()
    outbox.append = AsyncMock()
    return outbox


@pytest.fixture
def mock_serializer():
    """Create mock event serializer."""
    serializer = MagicMock()
    serializer.serialize.return_value = {"test": "payload"}
    return serializer


@pytest.fixture
def repository(mock_session, mock_probe, mock_outbox, mock_serializer):
    """Create repository with mock dependencies."""
    return APIKeyRepository(
        session=mock_session,
        outbox=mock_outbox,
        probe=mock_probe,
        serializer=mock_serializer,
    )


@pytest.fixture
def sample_api_key():
    """Create a sample APIKey aggregate for testing."""
    created_by_user_id = UserId.generate()
    tenant_id = TenantId.generate()
    return APIKey.create(
        created_by_user_id=created_by_user_id,
        tenant_id=tenant_id,
        name="Test API Key",
        key_hash="hashed_secret_value",
        prefix="karto_ab",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )


class TestProtocolCompliance:
    """Tests for protocol compliance."""

    def test_implements_protocol(self, repository):
        """Repository should implement IAPIKeyRepository protocol."""
        assert isinstance(repository, IAPIKeyRepository)


class TestAPIKeyRepositorySave:
    """Tests for save method."""

    @pytest.mark.asyncio
    async def test_saves_new_api_key(self, repository, mock_session, sample_api_key):
        """Should add new API key model to session."""
        # Mock session to return None (api_key doesn't exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Mock scalars for duplicate name check
        mock_scalars_result = MagicMock()
        mock_scalars_result.scalars.return_value.first.return_value = None
        mock_session.execute.side_effect = [mock_scalars_result, mock_result]

        await repository.save(sample_api_key)

        # Should add new model
        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        assert isinstance(added_model, APIKeyModel)
        assert added_model.id == sample_api_key.id.value
        assert added_model.name == sample_api_key.name
        assert added_model.key_hash == sample_api_key.key_hash
        assert added_model.prefix == sample_api_key.prefix

    @pytest.mark.asyncio
    async def test_updates_existing_api_key(
        self, repository, mock_session, sample_api_key
    ):
        """Should update existing API key model."""
        # Create existing model
        existing_model = APIKeyModel(
            id=sample_api_key.id.value,
            created_by_user_id=sample_api_key.created_by_user_id.value,
            tenant_id=sample_api_key.tenant_id.value,
            name="Old Name",
            key_hash=sample_api_key.key_hash,
            prefix=sample_api_key.prefix,
            expires_at=sample_api_key.expires_at,
            last_used_at=None,
            is_revoked=False,
        )

        # Mock scalars for duplicate name check (no conflict - same key)
        mock_name_check_result = MagicMock()
        mock_name_check_result.scalars.return_value.first.return_value = existing_model

        # Mock get by id returns existing
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = existing_model

        mock_session.execute.side_effect = [mock_name_check_result, mock_get_result]

        await repository.save(sample_api_key)

        # Should not add, should update
        mock_session.add.assert_not_called()
        assert existing_model.name == sample_api_key.name

    @pytest.mark.asyncio
    async def test_publishes_events_to_outbox(
        self, repository, mock_session, mock_outbox, sample_api_key
    ):
        """Should append collected events to outbox."""
        # Mock session
        mock_name_check_result = MagicMock()
        mock_name_check_result.scalars.return_value.first.return_value = None

        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = None
        mock_session.execute.side_effect = [mock_name_check_result, mock_get_result]

        await repository.save(sample_api_key)

        # Should have appended APIKeyCreated event to outbox
        mock_outbox.append.assert_called()
        calls = mock_outbox.append.call_args_list
        event_types = [call.kwargs.get("event_type") for call in calls]
        assert "APIKeyCreated" in event_types

    @pytest.mark.asyncio
    async def test_raises_on_duplicate_name(
        self, repository, mock_session, sample_api_key
    ):
        """Should raise DuplicateAPIKeyNameError when name exists for user in tenant."""
        # Create a different API key with the same name
        different_id = APIKeyId.generate()
        existing_model = APIKeyModel(
            id=different_id.value,
            created_by_user_id=sample_api_key.created_by_user_id.value,
            tenant_id=sample_api_key.tenant_id.value,
            name=sample_api_key.name,
            key_hash="different_hash",
            prefix="karto_cd",
            expires_at=None,
            last_used_at=None,
            is_revoked=False,
        )

        # Mock name check returns existing key with different ID
        mock_name_check_result = MagicMock()
        mock_name_check_result.scalars.return_value.first.return_value = existing_model
        mock_session.execute.return_value = mock_name_check_result

        with pytest.raises(DuplicateAPIKeyNameError):
            await repository.save(sample_api_key)


class TestAPIKeyRepositoryGet:
    """Tests for get methods."""

    @pytest.mark.asyncio
    async def test_gets_by_id(self, repository, mock_session, mock_probe):
        """Should return API key when found by ID."""
        api_key_id = APIKeyId.generate()
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        model = APIKeyModel(
            id=api_key_id.value,
            created_by_user_id=created_by_user_id.value,
            tenant_id=tenant_id.value,
            name="Test Key",
            key_hash="hash123",
            prefix="karto_ab",
            expires_at=None,
            last_used_at=None,
            is_revoked=False,
        )
        # Set timestamps that TimestampMixin would provide
        model.created_at = datetime.now(UTC)
        model.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(api_key_id, created_by_user_id, tenant_id)

        assert result is not None
        assert result.id.value == api_key_id.value
        assert result.name == "Test Key"
        mock_probe.api_key_retrieved.assert_called_once_with(api_key_id.value)

    @pytest.mark.asyncio
    async def test_gets_by_key_hash(self, repository, mock_session, mock_probe):
        """Should return API key when found by key hash."""
        api_key_id = APIKeyId.generate()
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        key_hash = "unique_hash_value"

        model = APIKeyModel(
            id=api_key_id.value,
            created_by_user_id=created_by_user_id.value,
            tenant_id=tenant_id.value,
            name="Test Key",
            key_hash=key_hash,
            prefix="karto_ab",
            expires_at=None,
            last_used_at=None,
            is_revoked=False,
        )
        model.created_at = datetime.now(UTC)
        model.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_key_hash(key_hash)

        assert result is not None
        assert result.key_hash == key_hash
        mock_probe.api_key_retrieved.assert_called_once_with(api_key_id.value)

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_id(
        self, repository, mock_session, mock_probe
    ):
        """Should return None when API key doesn't exist."""
        api_key_id = APIKeyId.generate()
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(api_key_id, created_by_user_id, tenant_id)

        assert result is None
        mock_probe.api_key_not_found.assert_called_once_with(api_key_id.value)

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_hash(
        self, repository, mock_session, mock_probe
    ):
        """Should return None when API key hash doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_key_hash("nonexistent_hash")

        assert result is None
        mock_probe.api_key_not_found_by_hash.assert_called_once()


class TestAPIKeyRepositoryList:
    """Tests for list method."""

    @pytest.mark.asyncio
    async def test_lists_by_user_and_tenant(self, repository, mock_session, mock_probe):
        """Should list all API keys for a user in a tenant."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        model1 = APIKeyModel(
            id=APIKeyId.generate().value,
            created_by_user_id=created_by_user_id.value,
            tenant_id=tenant_id.value,
            name="Key 1",
            key_hash="hash1",
            prefix="karto_ab",
            expires_at=None,
            last_used_at=None,
            is_revoked=False,
        )
        model1.created_at = datetime.now(UTC)
        model1.updated_at = datetime.now(UTC)

        model2 = APIKeyModel(
            id=APIKeyId.generate().value,
            created_by_user_id=created_by_user_id.value,
            tenant_id=tenant_id.value,
            name="Key 2",
            key_hash="hash2",
            prefix="karto_cd",
            expires_at=None,
            last_used_at=None,
            is_revoked=False,
        )
        model2.created_at = datetime.now(UTC)
        model2.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [model1, model2]
        mock_session.execute.return_value = mock_result

        result = await repository.list_by_user(created_by_user_id, tenant_id)

        assert len(result) == 2
        assert result[0].name == "Key 1"
        assert result[1].name == "Key 2"
        mock_probe.api_key_list_retrieved.assert_called_once_with(
            created_by_user_id.value, 2
        )

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_keys(
        self, repository, mock_session, mock_probe
    ):
        """Should return empty list when user has no API keys."""
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await repository.list_by_user(created_by_user_id, tenant_id)

        assert result == []
        mock_probe.api_key_list_retrieved.assert_called_once_with(
            created_by_user_id.value, 0
        )


class TestAPIKeyRepositoryDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_deletes_existing_api_key(
        self, repository, mock_session, mock_probe, mock_outbox
    ):
        """Should delete API key from PostgreSQL."""
        api_key_id = APIKeyId.generate()
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        api_key = APIKey(
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name="Test Key",
            key_hash="hash123",
            prefix="karto_ab",
            created_at=datetime.now(UTC),
            expires_at=None,
            last_used_at=None,
            is_revoked=False,
        )
        # Revoke to record the event
        api_key.revoke()

        model = APIKeyModel(
            id=api_key_id.value,
            created_by_user_id=created_by_user_id.value,
            tenant_id=tenant_id.value,
            name="Test Key",
            key_hash="hash123",
            prefix="karto_ab",
            expires_at=None,
            last_used_at=None,
            is_revoked=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.delete(api_key)

        assert result is True
        mock_session.delete.assert_called_once_with(model)
        mock_probe.api_key_deleted.assert_called_once_with(api_key_id.value)

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent(
        self, repository, mock_session, mock_probe
    ):
        """Should return False when API key doesn't exist."""
        api_key_id = APIKeyId.generate()
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        api_key = APIKey(
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name="Test Key",
            key_hash="hash123",
            prefix="karto_ab",
            created_at=datetime.now(UTC),
            expires_at=None,
            last_used_at=None,
            is_revoked=False,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.delete(api_key)

        assert result is False
        mock_probe.api_key_not_found.assert_called_once_with(api_key_id.value)

    @pytest.mark.asyncio
    async def test_appends_revoked_event_to_outbox(
        self, repository, mock_session, mock_probe, mock_outbox
    ):
        """Should append APIKeyRevoked event to outbox when deleting."""
        api_key_id = APIKeyId.generate()
        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()

        api_key = APIKey(
            id=api_key_id,
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name="Test Key",
            key_hash="hash123",
            prefix="karto_ab",
            created_at=datetime.now(UTC),
            expires_at=None,
            last_used_at=None,
            is_revoked=False,
        )
        # Revoke to record the event
        api_key.revoke()

        model = APIKeyModel(
            id=api_key_id.value,
            created_by_user_id=created_by_user_id.value,
            tenant_id=tenant_id.value,
            name="Test Key",
            key_hash="hash123",
            prefix="karto_ab",
            expires_at=None,
            last_used_at=None,
            is_revoked=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        await repository.delete(api_key)

        # Should have appended APIKeyRevoked event
        calls = mock_outbox.append.call_args_list
        event_types = [call.kwargs.get("event_type") for call in calls]
        assert "APIKeyRevoked" in event_types


class TestSerializerInjection:
    """Tests for serializer dependency injection."""

    @pytest.mark.asyncio
    async def test_uses_injected_serializer(
        self, mock_session, mock_outbox, mock_probe, mock_serializer
    ):
        """Should use injected serializer instead of creating default."""
        repository = APIKeyRepository(
            session=mock_session,
            outbox=mock_outbox,
            probe=mock_probe,
            serializer=mock_serializer,
        )

        created_by_user_id = UserId.generate()
        tenant_id = TenantId.generate()
        api_key = APIKey.create(
            created_by_user_id=created_by_user_id,
            tenant_id=tenant_id,
            name="Test Key",
            key_hash="hash123",
            prefix="karto_ab",
        )

        # Mock session
        mock_name_check_result = MagicMock()
        mock_name_check_result.scalars.return_value.first.return_value = None

        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = None
        mock_session.execute.side_effect = [mock_name_check_result, mock_get_result]

        await repository.save(api_key)

        # Injected serializer should have been called
        mock_serializer.serialize.assert_called()

    def test_uses_default_serializer_when_not_injected(
        self, mock_session, mock_outbox, mock_probe
    ):
        """Should create default serializer when not injected."""
        from iam.infrastructure.outbox import IAMEventSerializer

        repository = APIKeyRepository(
            session=mock_session,
            outbox=mock_outbox,
            probe=mock_probe,
        )

        assert isinstance(repository._serializer, IAMEventSerializer)
