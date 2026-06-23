"""Port for enriching extraction job target instances before agent runs."""

from __future__ import annotations

from typing import Any, Protocol

from extraction.domain.extraction_job import ExtractionTargetInstance


class IExtractionJobTargetContextEnricher(Protocol):
    """Resolve live graph ids and property gaps for assigned extraction targets."""

    async def enrich_target_instances(
        self,
        *,
        tenant_id: str,
        knowledge_graph_id: str,
        instances: tuple[ExtractionTargetInstance, ...],
    ) -> list[dict[str, Any]]:
        """Return job-context target_instances entries with graph_id and properties_missing."""
