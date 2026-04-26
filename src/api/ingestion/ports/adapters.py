"""Adapter port for the Ingestion bounded context.

Defines IDatasourceAdapter — the common extraction interface that all data
source adapters implement — and ExtractionResult, the value object returned
by every extraction run.

Domain isolation rule: this module must NOT import dlt, httpx, or any
adapter framework. It is pure Python with no infrastructure dependencies.
Only shared_kernel types are permitted as external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangesetEntry,
    SyncMode,
)


@dataclass(frozen=True)
class ExtractionResult:
    """Value object returned by every IDatasourceAdapter.extract() call.

    Holds all output produced by a single extraction run:
    - The list of changeset entries (what changed and how).
    - The raw content blobs keyed by SHA-256 hex digest (for deduplication).
    - The updated checkpoint to be persisted for the next incremental run.

    Attributes:
        changeset_entries: Ordered list of changes discovered during extraction.
            For a full refresh, all entries have ChangeOperation.ADD. For an
            incremental run, entries reflect only changes since the checkpoint.
        content_blobs: Content-addressed map of hex_digest → raw bytes.
            Keys match the hex_digest on each entry's content_ref.  Multiple
            entries can reference the same blob (deduplication).
        new_checkpoint: Opaque adapter-specific state capturing the extraction
            position (e.g., the current commit SHA for GitHub). Must be
            persisted by the caller so the next incremental run starts here.
    """

    changeset_entries: list[ChangesetEntry]
    content_blobs: dict[str, bytes]
    new_checkpoint: AdapterCheckpoint


@runtime_checkable
class IDatasourceAdapter(Protocol):
    """Common extraction interface for all data source adapters.

    Every adapter (GitHub, Kubernetes, Jira, …) implements this protocol.
    The protocol is structurally typed: no inheritance is required; any class
    with a matching ``extract`` signature satisfies it.

    Domain isolation: this protocol lives in the Ingestion domain/ports layer
    and contains no references to dlt, httpx, or any adapter framework.
    Concrete implementations in ingestion.infrastructure.adapters may import
    those libraries freely.

    Spec scenarios:
    - Extract contract: extract() accepts connection_config, credentials, and
      checkpoint state; returns raw extracted data and updated checkpoint.
    - Domain isolation: no dlt or framework imports in this module.
    """

    async def extract(
        self,
        connection_config: dict[str, str],
        credentials: dict[str, str],
        checkpoint: AdapterCheckpoint | None,
        sync_mode: SyncMode,
    ) -> ExtractionResult:
        """Extract raw content from the data source.

        Args:
            connection_config: Source-specific connection parameters (e.g.,
                ``{"owner": "myorg", "repo": "myrepo", "branch": "main"}``
                for GitHub).
            credentials: Decrypted credentials obtained via ICredentialReader
                (e.g., ``{"token": "ghp_xxx"}`` for GitHub).  Callers are
                responsible for retrieving and decrypting credentials before
                calling this method.
            checkpoint: Opaque state from the previous successful extraction,
                used for incremental runs.  ``None`` triggers a full refresh
                (all content extracted from scratch).
            sync_mode: ``SyncMode.INCREMENTAL`` uses the checkpoint to extract
                only changes; ``SyncMode.FULL_REFRESH`` ignores the checkpoint
                and extracts everything.

        Returns:
            ExtractionResult containing changeset entries, content blobs, and
            the updated checkpoint to store for the next incremental run.
        """
        ...
