"""IngestionService: orchestrates the ingestion pipeline.

Implements the extract → package flow for the Ingestion bounded context.
The service is stateless; all context flows via method parameters.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ingestion.application.value_objects import IngestionRunResult
from ingestion.ports.adapters import IDatasourceAdapter

if TYPE_CHECKING:
    from shared_kernel.credential_reader import ICredentialReader
from shared_kernel.job_package.builder import JobPackageBuilder
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    SyncMode,
)


class IngestionService:
    """Orchestrates the ingestion pipeline for a single sync run.

    The ingestion pipeline is:
    1. Look up the adapter for the given adapter_type
    2. Call adapter.extract() to get an ExtractionResult
    3. Build a JobPackage ZIP using JobPackageBuilder
    4. Return the JobPackageId

    The service does NOT write to the outbox directly. The caller
    (IngestionEventHandler) is responsible for writing JobPackageProduced
    or IngestionFailed to the outbox based on success or failure.

    Args:
        adapter_registry: Mapping of adapter_type strings to IDatasourceAdapter
            implementations. The service raises ValueError for unknown types.
        work_dir: Directory where JobPackage ZIP files will be written.
    """

    def __init__(
        self,
        adapter_registry: dict[str, IDatasourceAdapter],
        work_dir: Path,
        credential_reader: "ICredentialReader | None" = None,
    ) -> None:
        self._adapter_registry = adapter_registry
        self._work_dir = work_dir
        self._credential_reader = credential_reader

    async def run(
        self,
        sync_run_id: str,
        data_source_id: str,
        knowledge_graph_id: str,
        adapter_type: str,
        connection_config: dict[str, str],
        credentials_path: str | None,
        tenant_id: str | None = None,
        credentials: dict[str, str] | None = None,
        baseline_commit: str | None = None,
    ) -> IngestionRunResult:
        """Run the ingestion pipeline for a data source sync.

        Args:
            sync_run_id: The ID of the sync run (for tracing/correlation)
            data_source_id: The data source being synced
            knowledge_graph_id: The knowledge graph this feeds
            adapter_type: The adapter type string (e.g. "github")
            connection_config: Key-value adapter configuration
            credentials_path: Path for encrypted credentials
            tenant_id: Tenant ID for credential decryption scoping
            credentials: Optional decrypted credentials prepared by caller
            baseline_commit: Optional baseline commit SHA used to seed
                incremental extraction checkpoint state

        Returns:
            IngestionRunResult with the produced JobPackage metadata

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

        # Credentials are usually provided by the session-aware event wrapper.
        resolved_credentials: dict[str, str] = dict(credentials or {})
        if not resolved_credentials and credentials_path:
            if not tenant_id:
                raise ValueError("tenant_id is required when credentials_path is provided")
            if self._credential_reader is None:
                raise RuntimeError("credential_reader is not configured")
            resolved_credentials = await self._credential_reader.retrieve(
                credentials_path, tenant_id
            )

        checkpoint = None
        if baseline_commit:
            checkpoint = AdapterCheckpoint(
                schema_version="1.0.0",
                data={"commit_sha": baseline_commit},
            )
            
        # Extract raw items from the adapter using the new ExtractionResult API
        result = await adapter.extract(
            connection_config=connection_config,
            credentials=resolved_credentials,
            checkpoint=checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        # Build the JobPackage
        builder = JobPackageBuilder(
            data_source_id=data_source_id,
            knowledge_graph_id=knowledge_graph_id,
            sync_mode=SyncMode.INCREMENTAL,
        )

        # Register content blobs (deduplication is handled by the builder)
        for hex_digest, content_bytes in result.content_blobs.items():
            builder.add_content(content_bytes)

        # Add the pre-built changeset entries
        for entry in result.changeset_entries:
            builder.add_changeset_entry(entry)

        builder.set_checkpoint(result.new_checkpoint)

        # Write the ZIP archive to work_dir
        self._work_dir.mkdir(parents=True, exist_ok=True)
        builder.build(self._work_dir)

        prepared_commit_sha = None
        if result.new_checkpoint is not None:
            prepared_commit_sha = result.new_checkpoint.data.get("commit_sha")

        return IngestionRunResult(
            job_package_id=builder._package_id,
            entry_count=len(result.changeset_entries),
            prepared_commit_sha=(
                str(prepared_commit_sha) if prepared_commit_sha is not None else None
            ),
        )
