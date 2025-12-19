"""MCP-specific cross-context dependency composition.

This is the integration/composition layer for MCP resources and tools.
It's the ONLY place allowed to wire together Graph and Query contexts.

Future service decomposition: When splitting into microservices, this is
where you'd swap GraphSchemaService for an HTTP REST client that calls
the Graph service's API endpoints. The Query context's ISchemaService port
remains unchanged.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from query.ports.schema import ISchemaService


def get_schema_service_for_mcp() -> "ISchemaService":
    """Get schema service for MCP resources.

    Composes Graph context's GraphSchemaService to satisfy Query context's
    ISchemaService port. This is the integration point between contexts.

    Returns:
        Schema service implementation (GraphSchemaService)
    """
    from graph.application.services import GraphSchemaService
    from graph.dependencies import get_type_definition_repository

    type_def_repo = get_type_definition_repository()
    return GraphSchemaService(type_definition_repository=type_def_repo)
