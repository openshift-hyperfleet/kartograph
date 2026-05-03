"""Repository interfaces (ports) for the Querying bounded context.

These protocols define the contracts for accessing graph data
without specifying implementation details.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from query.domain.value_objects import AccessibleKnowledgeGraph, QueryResultRow
from query.ports.file_repository_models import RemoteFileRepositoryResponse


@runtime_checkable
class IQueryGraphRepository(Protocol):
    """Read-only repository interface for graph queries.

    This interface is designed for the Querying context to execute
    Cypher queries against the entire graph (unscoped access).

    Unlike IGraphReadOnlyRepository in the Graph context, this interface:
    - Does NOT scope queries to a data_source_id
    - Provides full graph visibility for MCP clients
    - Has simpler interface focused on raw query execution

    Security features are enforced by implementations:
    - Read-only operations only
    - Result limits (e.g., max 1000 rows)
    - Query timeout (e.g., 30 seconds)
    """

    def execute_cypher(
        self,
        query: str,
        timeout_seconds: int = 30,
        max_rows: int = 1000,
    ) -> list[QueryResultRow]:
        """Execute a Cypher query with safeguards.

        Args:
            query: A Cypher query string (must be read-only).
            timeout_seconds: Maximum execution time (default: 30s).
            max_rows: Maximum rows to return (default: 1000).

        Returns:
            List of result dictionaries.

        Raises:
            QueryExecutionError: If query fails or violates safeguards.
        """
        ...


class IRemoteFileRepository(Protocol):
    """Repository interface for fetching remote files.

    This interface is designed to enable fetching
    files from remote servers, such as Github, Gitlab, or others.
    """

    def get_file(self, url: str) -> RemoteFileRepositoryResponse: ...


class IAccessibleKnowledgeGraphRepository(Protocol):
    """Repository interface for listing accessible knowledge graphs.

    Fetches knowledge graph metadata for a given set of IDs within a tenant.
    Used by MCPKnowledgeGraphsService to satisfy the
    ``knowledge_graphs://accessible`` MCP resource.
    """

    async def find_by_ids_and_tenant(
        self,
        ids: list[str],
        tenant_id: str,
    ) -> list[AccessibleKnowledgeGraph]:
        """Fetch knowledge graphs by IDs, filtered to the given tenant.

        Args:
            ids: List of knowledge graph IDs to look up.
            tenant_id: Tenant ID to filter results (data isolation).

        Returns:
            Knowledge graphs matching both criteria (order not guaranteed).
        """
        ...
