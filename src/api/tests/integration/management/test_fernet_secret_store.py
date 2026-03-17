"""Integration tests for FernetSecretStore.

These tests require a running PostgreSQL instance with the
encrypted_credentials table created via Alembic migration.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from management.infrastructure.repositories.fernet_secret_store import FernetSecretStore

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def encryption_key() -> str:
    """Generate a Fernet key for integration tests."""
    return Fernet.generate_key().decode()


@pytest_asyncio.fixture
async def clean_encrypted_credentials(
    async_session: AsyncSession,
) -> AsyncGenerator[None, None]:
    """Clean encrypted_credentials table before each test."""
    try:
        await async_session.execute(text("DELETE FROM encrypted_credentials"))
        await async_session.commit()
    except Exception:
        await async_session.rollback()

    yield

    try:
        await async_session.execute(text("DELETE FROM encrypted_credentials"))
        await async_session.commit()
    except Exception:
        await async_session.rollback()


@pytest.fixture
def secret_store(async_session: AsyncSession, encryption_key: str) -> FernetSecretStore:
    """Provide a FernetSecretStore for integration tests."""
    return FernetSecretStore(session=async_session, encryption_keys=[encryption_key])


class TestRoundTrip:
    """Test store-then-retrieve returns original credentials."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve(
        self,
        secret_store: FernetSecretStore,
        async_session: AsyncSession,
        test_tenant: str,
        clean_encrypted_credentials: None,
    ):
        credentials = {"token": "test-value-abc-123"}
        path = "datasource/integ-1/creds"

        async with async_session.begin():
            await secret_store.store(path, test_tenant, credentials)

        result = await secret_store.retrieve(path, test_tenant)
        assert result == credentials


class TestOverwrite:
    """Test that storing twice with same path overwrites."""

    @pytest.mark.asyncio
    async def test_overwrite_credentials(
        self,
        secret_store: FernetSecretStore,
        async_session: AsyncSession,
        test_tenant: str,
        clean_encrypted_credentials: None,
    ):
        path = "datasource/integ-2/creds"

        async with async_session.begin():
            await secret_store.store(path, test_tenant, {"token": "old_value"})

        async with async_session.begin():
            await secret_store.store(path, test_tenant, {"token": "new_value"})

        result = await secret_store.retrieve(path, test_tenant)
        assert result == {"token": "new_value"}


class TestDelete:
    """Test store-then-delete-then-retrieve raises KeyError."""

    @pytest.mark.asyncio
    async def test_delete_then_retrieve_raises_key_error(
        self,
        secret_store: FernetSecretStore,
        async_session: AsyncSession,
        test_tenant: str,
        clean_encrypted_credentials: None,
    ):
        path = "datasource/integ-3/creds"

        async with async_session.begin():
            await secret_store.store(path, test_tenant, {"token": "to_delete"})

        async with async_session.begin():
            deleted = await secret_store.delete(path, test_tenant)

        assert deleted is True

        with pytest.raises(KeyError):
            await secret_store.retrieve(path, test_tenant)


class TestTenantIsolation:
    """Test that credentials are scoped by tenant_id."""

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_read_tenant_b(
        self,
        secret_store: FernetSecretStore,
        async_session: AsyncSession,
        test_tenant: str,
        clean_encrypted_credentials: None,
    ):
        path = "datasource/integ-4/creds"

        async with async_session.begin():
            await secret_store.store(path, test_tenant, {"token": "tenant_a_only"})

        with pytest.raises(KeyError):
            await secret_store.retrieve(path, "different-tenant-id")


class TestNotFound:
    """Test that retrieve raises KeyError for nonexistent path."""

    @pytest.mark.asyncio
    async def test_nonexistent_path_raises_key_error(
        self,
        secret_store: FernetSecretStore,
        test_tenant: str,
        clean_encrypted_credentials: None,
    ):
        with pytest.raises(KeyError):
            await secret_store.retrieve("nonexistent/path", test_tenant)
