"""Service port protocols for the Extraction bounded context."""

from __future__ import annotations

from typing import Protocol


class IExtractionService(Protocol):
    """Protocol for the AI-based entity extraction service.

    Implementors process a JobPackage — running the Claude Agent SDK
    to discover entities and relationships — and produce a MutationLog
    (JSONL file) describing the graph operations to apply.

    Returns the mutation_log_id for the produced log on success.
    Raises on failure, allowing the caller to emit ExtractionFailed.
    """

    async def run(
        self,
        sync_run_id: str,
        data_source_id: str,
        knowledge_graph_id: str,
        job_package_id: str,
    ) -> str:
        """Run the AI extraction pipeline for a JobPackage.

        Args:
            sync_run_id: Identifier for the current sync run
            data_source_id: Identifier for the data source being extracted
            knowledge_graph_id: Identifier for the target knowledge graph
            job_package_id: Identifier for the JobPackage to process

        Returns:
            mutation_log_id: Identifier for the produced MutationLog (JSONL)

        Raises:
            Exception: Any exception signals extraction failure; callers
                should catch and emit ExtractionFailed to the outbox.
        """
        ...
