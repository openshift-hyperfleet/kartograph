"""Read-only credential retrieval port.

Defines the ICredentialReader protocol — a read-only port for retrieving
decrypted credentials by path and tenant ID. This is placed in the shared
kernel because it is consumed by the Ingestion context (to fetch DataSource
credentials at sync time) while implemented by the Management context
(which owns the full write port via ISecretStoreRepository).
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ICredentialReader(Protocol):
    """Read-only port for retrieving decrypted credentials.

    Implementations decrypt and return stored credentials for a given
    path and tenant. The Management context provides the concrete
    implementation (e.g., Fernet-encrypted PostgreSQL storage); the
    Ingestion context consumes this protocol to fetch credentials at
    sync time without depending on Management internals.

    The full write port (store/retrieve/delete) lives in
    management/ports/secret_store.py. This shared kernel protocol
    exposes only the read subset.
    """

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        """Retrieve decrypted credentials for the given path and tenant.

        Args:
            path: The credential path (e.g., "datasource/{id}/credentials").
            tenant_id: The tenant ID for scoping (defense-in-depth isolation).

        Returns:
            A dictionary of credential key-value pairs (e.g.,
            {"token": "ghp_xxx"} for GitHub, or {"username": "...",
            "password": "..."} for other adapters).

        Raises:
            ValueError: If path or tenant_id is empty or invalid.
            KeyError: If no credentials exist at the given path for the tenant.
        """
        ...
