"""MCP server for the Querying bounded context."""

from typing import Any, Dict

from fastmcp import FastMCP

from infrastructure.settings import get_settings
from query.application.services import MCPQueryService
from query.domain.value_objects import QueryError

settings = get_settings()

mcp = FastMCP(name=settings.app_name)

query_mcp_app = mcp.http_app(path="/mcp")

# Service will be injected via set_query_service()
_query_service: MCPQueryService | None = None


def set_query_service(service: MCPQueryService) -> None:
    """Set the query service for MCP tools.

    Called by main.py during application startup to inject dependencies.
    """
    global _query_service
    _query_service = service


def get_query_service() -> MCPQueryService:
    """Get the query service instance.

    Raises:
        RuntimeError: If service not initialized.
    """
    if _query_service is None:
        raise RuntimeError(
            "MCPQueryService not initialized. Call set_query_service() first."
        )
    return _query_service


@mcp.tool
def query_graph(
    cypher: str,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
) -> Dict[str, Any]:
    """Execute a Cypher query against the knowledge graph.

    This tool allows you to query the Kartograph knowledge graph using
    Cypher query language. Only read-only queries are permitted.

    IMPORTANT: Apache AGE requires queries to return a single column.
    To return multiple values, wrap them in a map:
      - Single value: RETURN n
      - Multiple values: RETURN {person: p, friend: f}

    Args:
        cypher: The Cypher query to execute. Must be read-only (no CREATE,
            DELETE, SET, REMOVE, or MERGE). Must return a single column
            (use map syntax for multiple values).
        timeout_seconds: Maximum query execution time in seconds.
            Default is 30 seconds. Maximum is 60 seconds.
        max_rows: Maximum number of rows to return. Default is 1000.
            Maximum is 10000.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the query succeeded
        - rows: List of result rows (on success)
        - row_count: Number of rows returned (on success)
        - truncated: Whether results were truncated (on success)
        - execution_time_ms: Query execution time in milliseconds (on success)
        - error_type: Type of error (on failure)
        - message: Error message (on failure)

    Examples:
        # Get all Person nodes
        query_graph("MATCH (p:Person) RETURN p LIMIT 10")

        # Get specific properties
        query_graph("MATCH (p:Person) RETURN p.name, p.email")

        # Get relationships using map syntax (REQUIRED for multiple items)
        query_graph('''
            MATCH (a:Person)-[r:KNOWS]->(b:Person)
            RETURN {source: a, relationship: r, target: b}
            LIMIT 20
        ''')

        # Aggregations
        query_graph("MATCH (p:Person) RETURN count(p)")
    """
    service = get_query_service()

    # Enforce maximum limits
    timeout_seconds = min(timeout_seconds, 60)
    max_rows = min(max_rows, 10000)

    result = service.execute_cypher_query(
        query=cypher,
        timeout_seconds=timeout_seconds,
        max_rows=max_rows,
    )

    if isinstance(result, QueryError):
        return {
            "success": False,
            "error_type": result.error_type,
            "message": result.message,
        }

    # CypherQueryResult
    return {
        "success": True,
        "rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "execution_time_ms": result.execution_time_ms,
    }
