"""Service port protocols for the Ingestion bounded context."""

from __future__ import annotations

from typing import Protocol

from shared_kernel.job_package.value_objects import JobPackageId


class IIngestionService(Protocol):
    """Protocol for the ingestion pipeline service.

    Implementors run an adapter extract → package build pipeline and
    return the resulting JobPackageId on success.
    """

    async def run(
        self,
        sync_run_id: str,
        data_source_id: str,
        knowledge_graph_id: str,
        adapter_type: str,
        connection_config: dict[str, str],
        credentials_path: str | None,
    ) -> JobPackageId:
        """Run the ingestion pipeline.

        Args:
            sync_run_id: Identifier for the current sync run
            data_source_id: Identifier for the data source being synced
            knowledge_graph_id: Identifier for the target knowledge graph
            adapter_type: Which adapter to use (e.g. "github")
            connection_config: Adapter-specific connection configuration
            credentials_path: Optional Vault path for credentials

        Returns:
            JobPackageId for the produced archive

        Raises:
            ValueError: If the adapter_type is unknown
            Exception: Any exception from the adapter signals failure
        """
        ...
