"""Secret store port for encrypted credential management.

Defines the ISecretStoreRepository protocol for storing, retrieving,
and deleting encrypted credentials within the Management bounded context.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ISecretStoreRepository(Protocol):
    """Port for encrypted credential storage.

    Implementations encrypt credentials at rest and scope them by
    path and tenant_id for defense-in-depth isolation.

    The retrieve method signature matches ICredentialReader.retrieve
    from shared_kernel/credential_reader.py so that a single
    implementation can satisfy both protocols.
    """

    async def store(
        self, path: str, tenant_id: str, credentials: dict[str, str]
    ) -> None:
        """Encrypt and persist credentials.

        Args:
            path: The credential path (e.g., "datasource/{id}/credentials").
            tenant_id: The tenant ID for scoping.
            credentials: Key-value pairs to encrypt and store.
        """
        ...

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        """Decrypt and return stored credentials.

        Args:
            path: The credential path.
            tenant_id: The tenant ID for scoping.

        Returns:
            A dictionary of credential key-value pairs.

        Raises:
            KeyError: If no credentials exist at the given path for the tenant.
        """
        ...

    async def delete(self, path: str, tenant_id: str) -> bool:
        """Remove stored credentials.

        Args:
            path: The credential path.
            tenant_id: The tenant ID for scoping.

        Returns:
            True if credentials were deleted, False if not found.
        """
        ...
