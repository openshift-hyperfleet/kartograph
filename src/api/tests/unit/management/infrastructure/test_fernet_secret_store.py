"""Unit tests for FernetSecretStore.

Tests the Fernet encryption/decryption logic without a database.
Database operations are mocked with unittest.mock.AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

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
    from management.infrastructure.fernet_secret_store import FernetSecretStore

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
