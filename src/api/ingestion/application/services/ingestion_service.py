"""IngestionService: orchestrates the ingestion pipeline.

Implements the extract → package flow for the Ingestion bounded context.
The service is stateless; all context flows via method parameters.
"""

from __future__ import annotations

from pathlib import Path

from ingestion.ports.adapters import IDataSourceAdapter
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    ChangesetEntry,
    JobPackageId,
    SyncMode,
)


class IngestionService:
    """Orchestrates the ingestion pipeline for a single sync run.

    The ingestion pipeline is:
    1. Look up the adapter for the given adapter_type
    2. Call adapter.extract() to get raw items and a checkpoint
    3. Build a JobPackage ZIP using JobPackageBuilder
    4. Return the JobPackageId

    The service does NOT write to the outbox directly. The caller
    (IngestionEventHandler) is responsible for writing JobPackageProduced
    or IngestionFailed to the outbox based on success or failure.

    Args:
        adapter_registry: Mapping of adapter_type strings to IDataSourceAdapter
            implementations. The service raises ValueError for unknown types.
        work_dir: Directory where JobPackage ZIP files will be written.
    """

    def __init__(
        self,
        adapter_registry: dict[str, IDataSourceAdapter],
        work_dir: Path,
    ) -> None:
        self._adapter_registry = adapter_registry
        self._work_dir = work_dir

    async def run(
        self,
        sync_run_id: str,
        data_source_id: str,
        knowledge_graph_id: str,
        adapter_type: str,
        connection_config: dict[str, str],
        credentials_path: str | None,
    ) -> JobPackageId:
        """Run the ingestion pipeline for a data source sync.

        Args:
            sync_run_id: The ID of the sync run (for tracing/correlation)
            data_source_id: The data source being synced
            knowledge_graph_id: The knowledge graph this feeds
            adapter_type: The adapter type string (e.g. "github")
            connection_config: Key-value adapter configuration
            credentials_path: Vault path for credentials (currently unused;
                future implementations will decrypt and pass credentials)

        Returns:
            The JobPackageId of the produced ZIP archive

        Raises:
            ValueError: If the adapter_type is not registered
            Exception: Any exception from the adapter propagates upward;
                callers should catch and emit IngestionFailed.
        """
        adapter = self._adapter_registry.get(adapter_type)
        if adapter is None:
            raise ValueError(
                f"Unknown adapter type: {adapter_type!r}. "
                f"Registered adapters: {list(self._adapter_registry.keys())}"
            )

        # TODO: decrypt credentials from credentials_path when secret store
        # is injected. Currently credentials are passed as None.
        credentials: dict[str, str] | None = None

        # Extract raw items from the adapter
        raw_items, checkpoint = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
        )

        # Build the JobPackage
        builder = JobPackageBuilder(
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        for item in raw_items:
            content_ref = builder.add_content(item.content_bytes)
            entry = ChangesetEntry(
                operation=item.operation,
                id=item.id,
                type=item.type,
                path=item.path,
                content_ref=content_ref,
                content_type=item.content_type,
                metadata=item.metadata,
            )
            builder.add_changeset_entry(entry)

        builder.set_checkpoint(checkpoint)

        # Write the ZIP archive to work_dir
        self._work_dir.mkdir(parents=True, exist_ok=True)
        builder.build(self._work_dir)

        return builder._package_id
