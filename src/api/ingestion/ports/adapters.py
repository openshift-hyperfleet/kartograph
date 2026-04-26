"""Adapter port protocols for the Ingestion bounded context.

Adapters extract raw data from external systems (GitHub, Kubernetes, etc.)
and return it in a normalized form for packaging into JobPackages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from shared_kernel.job_package.value_objects import AdapterCheckpoint, ChangeOperation


@dataclass(frozen=True)
class RawItem:
    """A single raw item returned by an adapter extract call.

    Represents one changed item from the data source. The content_bytes
    field holds the raw content that will be stored in the JobPackage's
    content/ directory.

    The Ingestion service uses these to build ChangesetEntries by:
    1. Adding content_bytes to the builder → receiving a ContentRef
    2. Constructing a ChangesetEntry with the returned ContentRef

    Attributes:
        operation: The type of change (ADD or MODIFY)
        id: Stable identifier for the item within the data source
        type: Reverse-DNS type identifier (e.g. "io.kartograph.change.file")
        path: Current path or location of the item in the data source
        content_bytes: The raw content bytes for this item
        content_type: MIME type of the raw content (e.g. "text/x-python")
        metadata: Adapter-specific metadata (e.g. previous_path for renames)
    """

    operation: ChangeOperation
    id: str
    type: str
    path: str
    content_bytes: bytes
    content_type: str
    metadata: dict[str, Any]


@runtime_checkable
class IDataSourceAdapter(Protocol):
    """Protocol for data source adapters.

    Each adapter implementation knows how to connect to a specific type
    of data source (GitHub, Kubernetes, etc.) and extract changed items
    since the last sync.

    Adapters are stateless — all connection information is passed via
    connection_config and credentials at call time.
    """

    async def extract(
        self,
        connection_config: dict[str, str],
        credentials: dict[str, str] | None = None,
    ) -> tuple[list[RawItem], AdapterCheckpoint]:
        """Extract changed items from the data source.

        Args:
            connection_config: Key-value configuration for this adapter
                (e.g. {"repo": "org/repo", "branch": "main"} for GitHub)
            credentials: Optional decrypted credentials for authentication

        Returns:
            A tuple of (raw_items, checkpoint) where:
            - raw_items: List of changed items with their raw content
            - checkpoint: Adapter state snapshot for next incremental sync

        Raises:
            Exception: Any exception signals extraction failure; the
                IngestionService will catch it and emit IngestionFailed.
        """
        ...
