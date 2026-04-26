"""Unit tests for FernetSecretStore.

Tests the Fernet encryption/decryption logic without a database.
Database operations are mocked with unittest.mock.AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet, InvalidToken

from management.ports.secret_store import ISecretStoreRepository
from shared_kernel.credential_reader import ICredentialReader


@pytest.fixture
def fernet_key() -> str:
    """Generate a fresh Fernet key."""
    return Fernet.generate_key().decode()


@pytest.fixture
def fernet_key_2() -> str:
    """Generate a second Fernet key for rotation tests."""
    return Fernet.generate_key().decode()


@pytest.fixture
def mock_session() -> AsyncMock:
    """Provide a mocked AsyncSession."""
    session = AsyncMock()
    session.merge = AsyncMock()
    session.execute = AsyncMock()
    session.delete = AsyncMock()
    return session


def _make_store(session: AsyncMock, keys: list[str]):
    """Create a FernetSecretStore with mocked session."""
    from management.infrastructure.repositories.fernet_secret_store import (
        FernetSecretStore,
    )

    return FernetSecretStore(session=session, encryption_keys=keys)


class TestProtocolConformance:
    """Verify FernetSecretStore satisfies both port protocols."""

    def test_implements_secret_store_repository(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        assert isinstance(store, ISecretStoreRepository)

    def test_implements_credential_reader(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        assert isinstance(store, ICredentialReader)


class TestFernetRoundTrip:
    """Test encrypt-then-decrypt produces original credentials."""

    @pytest.mark.asyncio
    async def test_round_trip_single_key(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        credentials = {"token": "ghp_abc123"}

        # Store: capture the encrypted value passed to merge
        await store.store("datasource/1/creds", "tenant-1", credentials)
        merge_call = mock_session.merge.call_args
        model = merge_call[0][0]

        # Retrieve: mock the DB to return the encrypted blob
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await store.retrieve("datasource/1/creds", "tenant-1")
        assert result == credentials

    @pytest.mark.asyncio
    async def test_round_trip_multiple_credentials(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        credentials = {"username": "admin", "password": "secret", "host": "db.local"}

        await store.store("datasource/2/creds", "tenant-1", credentials)
        model = mock_session.merge.call_args[0][0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await store.retrieve("datasource/2/creds", "tenant-1")
        assert result == credentials

    @pytest.mark.asyncio
    async def test_round_trip_empty_values(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        credentials = {"token": ""}

        await store.store("datasource/3/creds", "tenant-1", credentials)
        model = mock_session.merge.call_args[0][0]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await store.retrieve("datasource/3/creds", "tenant-1")
        assert result == credentials


class TestMultiFernetRotation:
    """Test that key rotation works via MultiFernet."""

    @pytest.mark.asyncio
    async def test_decrypt_with_rotated_keys(
        self, mock_session: AsyncMock, fernet_key: str, fernet_key_2: str
    ):
        # Encrypt with key1
        store_v1 = _make_store(mock_session, [fernet_key])
        credentials = {"token": "ghp_rotate_me"}

        await store_v1.store("datasource/4/creds", "tenant-1", credentials)
        model = mock_session.merge.call_args[0][0]

        # Decrypt with [key2, key1] — key2 is primary, key1 is legacy
        store_v2 = _make_store(mock_session, [fernet_key_2, fernet_key])

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await store_v2.retrieve("datasource/4/creds", "tenant-1")
        assert result == credentials


class TestRetrieveNotFound:
    """Test that retrieve raises KeyError when not found."""

    @pytest.mark.asyncio
    async def test_raises_key_error(self, mock_session: AsyncMock, fernet_key: str):
        store = _make_store(mock_session, [fernet_key])

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(KeyError):
            await store.retrieve("nonexistent/path", "tenant-1")


class TestInvalidKey:
    """Test that invalid Fernet keys raise an error."""

    def test_invalid_key_raises_error(self, mock_session: AsyncMock):
        with pytest.raises(Exception):
            _make_store(mock_session, ["not-a-valid-fernet-key"])


class TestDelete:
    """Test delete behavior with mocked session."""

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_credentials_exist(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])

        from management.infrastructure.models.encrypted_credential import (
            EncryptedCredentialModel,
        )

        model = EncryptedCredentialModel(
            path="datasource/5/creds",
            tenant_id="tenant-1",
            encrypted_value=b"encrypted",
            key_version=0,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await store.delete("datasource/5/creds", "tenant-1")
        assert result is True
        mock_session.delete.assert_awaited_once_with(model)
        mock_session.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_credentials_not_found(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await store.delete("datasource/6/creds", "tenant-1")
        assert result is False
        mock_session.delete.assert_not_awaited()


class TestInputValidation:
    """Test input validation for path and tenant_id."""

    @pytest.mark.asyncio
    async def test_store_with_empty_path_raises_value_error(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        with pytest.raises(ValueError, match="path must not be empty"):
            await store.store("", "tenant-1", {"token": "abc"})

    @pytest.mark.asyncio
    async def test_retrieve_with_empty_tenant_id_raises_value_error(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        with pytest.raises(ValueError, match="tenant_id must not be empty"):
            await store.retrieve("datasource/1/creds", "")

    @pytest.mark.asyncio
    async def test_store_with_whitespace_path_raises_value_error(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        with pytest.raises(ValueError, match="path must not be empty"):
            await store.store("   ", "tenant-1", {"token": "abc"})

    @pytest.mark.asyncio
    async def test_retrieve_with_whitespace_tenant_id_raises_value_error(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        with pytest.raises(ValueError, match="tenant_id must not be empty"):
            await store.retrieve("datasource/1/creds", "   ")

    @pytest.mark.asyncio
    async def test_delete_with_empty_path_raises_value_error(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        with pytest.raises(ValueError, match="path must not be empty"):
            await store.delete("", "tenant-1")

    @pytest.mark.asyncio
    async def test_delete_with_empty_tenant_id_raises_value_error(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])
        with pytest.raises(ValueError, match="tenant_id must not be empty"):
            await store.delete("datasource/1/creds", "")


class TestTenantIsolation:
    """Test that credentials are scoped by (path, tenant_id) composite key.

    Scenario (spec: credentials.spec.md - Tenant Isolation):
        GIVEN credentials stored at a path for tenant A
        WHEN tenant B attempts to retrieve credentials at the same path
        THEN the retrieval fails (credentials are scoped to tenant A)
    """

    @pytest.mark.asyncio
    async def test_same_path_different_tenant_raises_key_error(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        """Same path, different tenant → KeyError (tenant isolation enforced)."""
        store = _make_store(mock_session, [fernet_key])

        # Simulate DB returning None when queried for tenant-B's credentials
        # (because the composite key includes tenant_id, tenant-B has no record)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(KeyError):
            await store.retrieve("datasource/abc/credentials", "tenant-b")

    @pytest.mark.asyncio
    async def test_retrieve_with_correct_tenant_succeeds(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        """Retrieving credentials with the correct tenant succeeds."""
        store = _make_store(mock_session, [fernet_key])
        credentials = {"token": "tenant_a_secret"}

        # Store credentials for tenant-a
        await store.store("datasource/abc/credentials", "tenant-a", credentials)
        model = mock_session.merge.call_args[0][0]

        # Simulate DB returning the model when queried with matching tenant
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await store.retrieve("datasource/abc/credentials", "tenant-a")
        assert result == credentials


class TestCorruptedCiphertext:
    """Test that corrupted ciphertext raises InvalidToken."""

    @pytest.mark.asyncio
    async def test_corrupted_encrypted_value_raises_invalid_token(
        self, mock_session: AsyncMock, fernet_key: str
    ):
        store = _make_store(mock_session, [fernet_key])

        from management.infrastructure.models.encrypted_credential import (
            EncryptedCredentialModel,
        )

        model = EncryptedCredentialModel(
            path="datasource/corrupt/creds",
            tenant_id="tenant-1",
            encrypted_value=b"this-is-not-valid-fernet-ciphertext",
            key_version=0,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        with pytest.raises(InvalidToken):
            await store.retrieve("datasource/corrupt/creds", "tenant-1")
