"""Fernet-encrypted secret store implementation.

Uses cryptography.fernet.MultiFernet to encrypt credentials at rest
in PostgreSQL, supporting key rotation via multiple Fernet keys.
"""

from __future__ import annotations

import json

from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from management.infrastructure.models.encrypted_credential import (
    EncryptedCredentialModel,
)
from management.infrastructure.observability.secret_store_probe import (
    DefaultSecretStoreProbe,
    SecretStoreProbe,
)


def _validate_inputs(path: str, tenant_id: str) -> None:
    """Validate that path and tenant_id are non-empty."""
    if not path or not path.strip():
        raise ValueError("path must not be empty or whitespace-only")
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id must not be empty or whitespace-only")


class FernetSecretStore:
    """Fernet-encrypted credential storage backed by PostgreSQL.

    Implements both ISecretStoreRepository (management port) and
    ICredentialReader (shared kernel) for a single implementation
    that satisfies both read-write and read-only consumers.

    Uses MultiFernet to support key rotation: the first key in the
    list is used for encryption, and all keys are tried for decryption.
    """

    def __init__(
        self,
        session: AsyncSession,
        encryption_keys: list[str],
        probe: SecretStoreProbe | None = None,
    ) -> None:
        self._session = session
        self._multi_fernet = MultiFernet([Fernet(key) for key in encryption_keys])
        self._probe: SecretStoreProbe = probe or DefaultSecretStoreProbe()

    async def store(
        self, path: str, tenant_id: str, credentials: dict[str, str]
    ) -> None:
        """Encrypt and persist credentials via upsert."""
        _validate_inputs(path, tenant_id)

        plaintext = json.dumps(credentials).encode("utf-8")
        encrypted = self._multi_fernet.encrypt(plaintext)

        model = EncryptedCredentialModel(
            path=path,
            tenant_id=tenant_id,
            encrypted_value=encrypted,
            key_version=0,
        )
        await self._session.merge(model)
        await self._session.flush()
        self._probe.credential_stored(path, tenant_id)

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        """Decrypt and return stored credentials.

        Raises:
            KeyError: If no credentials exist at the given path for the tenant.
        """
        _validate_inputs(path, tenant_id)

        stmt = select(EncryptedCredentialModel).where(
            EncryptedCredentialModel.path == path,
            EncryptedCredentialModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            self._probe.credential_not_found(path, tenant_id)
            raise KeyError("Credentials not found")

        decrypted = self._multi_fernet.decrypt(model.encrypted_value)
        self._probe.credential_retrieved(path, tenant_id)
        return json.loads(decrypted.decode("utf-8"))

    async def delete(self, path: str, tenant_id: str) -> bool:
        """Remove stored credentials. Returns True if deleted."""
        _validate_inputs(path, tenant_id)

        stmt = select(EncryptedCredentialModel).where(
            EncryptedCredentialModel.path == path,
            EncryptedCredentialModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        await self._session.delete(model)
        await self._session.flush()
        self._probe.credential_deleted(path, tenant_id)
        return True
