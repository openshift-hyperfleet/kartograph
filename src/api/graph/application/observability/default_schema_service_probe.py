"""Default implementation of schema service probe.

Provides a structlog-based implementation of the SchemaServiceProbe protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from graph.application.observability.schema_service_probe import SchemaServiceProbe

if TYPE_CHECKING:
    from shared_kernel.observability_context import ObservationContext


class DefaultSchemaServiceProbe(SchemaServiceProbe):
    """Default implementation of SchemaServiceProbe using structlog."""

    def __init__(
        self,
        logger: structlog.stdlib.BoundLogger | None = None,
        context: ObservationContext | None = None,
    ):
        self._logger = logger or structlog.get_logger()
        self._context = context

    def _get_context_kwargs(self) -> dict[str, Any]:
        if self._context is None:
            return {}
        return self._context.as_dict()

    def with_context(self, context: ObservationContext) -> DefaultSchemaServiceProbe:
        return DefaultSchemaServiceProbe(logger=self._logger, context=context)

    def ontology_retrieved(
        self,
        count: int,
    ) -> None:
        self._logger.info(
            "graph_ontology_retrieved",
            type_definition_count=count,
            **self._get_context_kwargs(),
        )
