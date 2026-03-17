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


class FernetSecretStore:
    """Fernet-encrypted credential storage backed by PostgreSQL.

    Implements both ISecretStoreRepository (management port) and
    ICredentialReader (shared kernel) for a single implementation
    that satisfies both read-write and read-only consumers.

    Uses MultiFernet to support key rotation: the first key in the
    list is used for encryption, and all keys are tried for decryption.
    """

    def __init__(self, session: AsyncSession, encryption_keys: list[str]) -> None:
        self._session = session
        self._multi_fernet = MultiFernet([Fernet(key) for key in encryption_keys])

    async def store(
        self, path: str, tenant_id: str, credentials: dict[str, str]
    ) -> None:
        """Encrypt and persist credentials via upsert."""
        plaintext = json.dumps(credentials).encode("utf-8")
        encrypted = self._multi_fernet.encrypt(plaintext)

        model = EncryptedCredentialModel(
            path=path,
            tenant_id=tenant_id,
            encrypted_value=encrypted,
            key_version=0,
        )
        await self._session.merge(model)

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        """Decrypt and return stored credentials.

        Raises:
            KeyError: If no credentials exist at the given path for the tenant.
        """
        stmt = select(EncryptedCredentialModel).where(
            EncryptedCredentialModel.path == path,
            EncryptedCredentialModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise KeyError(
                f"No credentials found at path={path!r} for tenant={tenant_id!r}"
            )

        decrypted = self._multi_fernet.decrypt(model.encrypted_value)
        return json.loads(decrypted.decode("utf-8"))

    async def delete(self, path: str, tenant_id: str) -> bool:
        """Remove stored credentials. Returns True if deleted."""
        stmt = select(EncryptedCredentialModel).where(
            EncryptedCredentialModel.path == path,
            EncryptedCredentialModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        await self._session.delete(model)
        return True
