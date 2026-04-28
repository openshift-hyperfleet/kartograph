"""MCP server for the Querying bounded context."""

from typing import Any, Dict

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.server.dependencies import get_http_headers

from infrastructure.mcp_dependencies import (
    get_mcp_secure_enclave,
    validate_mcp_api_key,
    validate_mcp_bearer_token,
)
from infrastructure.settings import get_settings
from query.application.services import MCPQueryService
from query.dependencies import (
    get_git_repository,
    get_mcp_query_service,
    get_prompt_repository,
)
from query.domain.value_objects import QueryError, QueryResultRow
from query.ports.file_repository_models import RemoteFileRepositoryResponse
from shared_kernel.middleware.mcp_api_key_auth import MCPApiKeyAuthMiddleware

settings = get_settings()

mcp = FastMCP(name=settings.app_name)

_mcp_http_app = mcp.http_app(path="/mcp", stateless_http=True)

#: The raw MCP Starlette app, exposed so main.py can invoke its lifespan.
mcp_http_app_inner = _mcp_http_app

query_mcp_app = MCPApiKeyAuthMiddleware(
    app=_mcp_http_app,
    validate_api_key=validate_mcp_api_key,
    validate_bearer_token=validate_mcp_bearer_token,
)

# Eagerly validate prompts at startup (fail-fast if missing)
_prompt_repository = get_prompt_repository()


def _filter_internal_properties(data: Any) -> Any:
    """Recursively filter internal properties from query results.

    Removes properties that are internal implementation details and should
    not be exposed to agents/users:
    - all_content_lower: Lowercase concatenation used only for search indexing

    This filtering happens at the MCP layer to hide Graph bounded context
    implementation details from consumers.

    Args:
        data: Query result data (dict, list, or scalar)

    Returns:
        Data with internal properties removed
    """
    INTERNAL_PROPERTIES = {"all_content_lower"}

    if isinstance(data, dict):
        return {
            k: _filter_internal_properties(v)
            for k, v in data.items()
            if k not in INTERNAL_PROPERTIES
        }
    elif isinstance(data, list):
        return [_filter_internal_properties(item) for item in data]
    else:
        return data


def _value_matches_kg(value: Any, knowledge_graph_id: str) -> bool | None:
    """Check whether a single value is an entity matching *knowledge_graph_id*.

    Three-valued return:
    - ``True``  — value is a NodeDict/EdgeDict and its ``knowledge_graph_id``
                  property equals *knowledge_graph_id*.
    - ``False`` — value is a NodeDict/EdgeDict but its ``knowledge_graph_id``
                  is absent, empty, or different.
    - ``None``  — value is a scalar (int, str, etc.); no entity determination
                  can be made.

    For plain dicts (map results), the function recurses and returns ``True``
    if any nested entity matches, ``False`` if entities exist but none match,
    or ``None`` if no entities are found.
    """
    if not isinstance(value, dict):
        return None  # scalar — no entity to check

    props = value.get("properties")
    if isinstance(props, dict):
        # This is an entity dict (NodeDict or EdgeDict)
        kg_id = props.get("knowledge_graph_id")
        if isinstance(kg_id, str) and kg_id and kg_id == knowledge_graph_id:
            return True
        return False  # entity present, but doesn't match

    # Plain dict (map result) — recurse into values
    nested_has_entity = False
    nested_has_match = False
    for v in value.values():
        result = _value_matches_kg(v, knowledge_graph_id)
        if result is not None:
            nested_has_entity = True
            if result:
                nested_has_match = True

    if not nested_has_entity:
        return None  # map with no entity values inside
    return nested_has_match


def _filter_by_knowledge_graph(
    rows: list[QueryResultRow],
    knowledge_graph_id: str | None,
) -> list[QueryResultRow]:
    """Filter query result rows to only include those from *knowledge_graph_id*.

    If *knowledge_graph_id* is None, all rows are returned unchanged.

    Inclusion rules:
    - Node row (``{"node": NodeDict}``):
        included iff ``node.properties.knowledge_graph_id == knowledge_graph_id``
    - Edge row (``{"edge": EdgeDict}``):
        included iff ``edge.properties.knowledge_graph_id == knowledge_graph_id``
    - Map row (``{"key": NodeDict, ...}``):
        included iff at least one nested entity has the matching ``knowledge_graph_id``
    - Scalar row (``{"value": 42}``):
        always included — no entity to filter on (e.g., aggregation counts)

    Args:
        rows:               Raw result rows from the graph repository.
        knowledge_graph_id: ID to filter by, or None to skip filtering.

    Returns:
        Filtered list of rows (original objects, not copies).
    """
    if knowledge_graph_id is None:
        return rows

    filtered: list[QueryResultRow] = []
    for row in rows:
        has_any_entity = False
        has_matching_entity = False

        for value in row.values():
            match_result = _value_matches_kg(value, knowledge_graph_id)
            if match_result is not None:
                has_any_entity = True
                if match_result:
                    has_matching_entity = True

        # Pure scalar rows (no entities) always pass through
        if has_matching_entity or not has_any_entity:
            filtered.append(row)

    return filtered


@mcp.tool
async def query_graph(
    cypher: str,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
    knowledge_graph_id: str | None = None,
    service: MCPQueryService = Depends(get_mcp_query_service),  # type: ignore[arg-type]
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
        knowledge_graph_id: Optional KnowledgeGraph ID to scope the results.
            When provided, only entities belonging to that KnowledgeGraph
            are returned. When omitted, results span all KnowledgeGraphs
            in the tenant.

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

        # Scope to a specific KnowledgeGraph
        query_graph("MATCH (p:Person) RETURN p", knowledge_graph_id="kg-01J...")
    """

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

    # Filter to the requested KnowledgeGraph (when provided)
    rows = _filter_by_knowledge_graph(result.rows, knowledge_graph_id)

    # Apply secure enclave: redact entities the caller is not authorized to see
    secure_enclave = get_mcp_secure_enclave()
    rows = await secure_enclave.apply_redaction(rows)

    # Filter internal properties before returning to agent
    filtered_rows = _filter_internal_properties(rows)

    # CypherQueryResult
    return {
        "success": True,
        "rows": filtered_rows,
        "row_count": len(filtered_rows),
        "truncated": result.truncated,
        "execution_time_ms": result.execution_time_ms,
    }


@mcp.tool
def fetch_documentation_source(
    documentationmodule_view_uri: str,
) -> RemoteFileRepositoryResponse:
    """Fetch the full source content of a DocumentationModule from its view_uri.

    Use this tool when you need to read the complete documentation content
    for a DocumentationModule. The `content_summary` and `misc` properties
    provide a concise overview, but this tool retrieves the full source file
    including all procedure steps, code blocks, and configuration details.

    Pass GitHub and/or GitLab access tokens for access to private
    repositories via the headers:

    `x-github-pat`
    `x-gitlab-pat`

    The tool automatically:
    - Transforms GitHub blob URLs to raw content URLs
    - Strips AsciiDoc metadata and comments
    - Returns only the main documentation content (starting from the title)

    Args:
        documentationmodule_view_uri: The view_uri from a DocumentationModule
            instance. Must be a GitHub blob URL like:
            https://github.com/openshift/openshift-docs/blob/main/modules/file.adoc

    Returns:
        class RemoteFileRepositoryResponse(BaseModel):
            success: bool
            error: str | None = None
            content: str | None = None
            source_url: str | None = None
            raw_url: str | None = None

    Example:
        Fetch the full AsciiDoc source for a DocumentationModule whose
        ``view_uri`` was returned by a prior ``query_graph`` call.  The
        ``content`` field of the response contains the full document text
        starting from its title line.
    """

    headers = get_http_headers()

    github_token = headers.get("x-github-pat", None)
    gitlab_token = headers.get("x-gitlab-pat", None)

    repository = get_git_repository(
        url=documentationmodule_view_uri,
        github_token=github_token,
        gitlab_token=gitlab_token,
    )

    return repository.get_file(url=documentationmodule_view_uri)


@mcp.resource(
    uri="instructions://agent",
    name="AgentInstructions",
    description="System instructions for AI agents using the query_graph tool with multi-term search strategies and platform-aware filtering",
    mime_type="text/markdown",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
def get_agent_instructions() -> str:
    """Get agent instructions for querying the knowledge graph using Cypher.

    Returns instructions optimized for agents that will use the query_graph tool,
    writing raw Cypher queries against Apache AGE.

    Includes:
    - Apache AGE-specific Cypher syntax requirements
    - Multi-term search strategies with AND logic
    - Platform-aware filtering using view_uri paths
    - Deprecated item discovery patterns
    - Self-check workflow before answering
    - Best practices for efficient graph traversal
    - Knowledge graph overview and domain context

    Returns:
        Markdown-formatted agent instructions (cached from startup)
    """
    return _prompt_repository.get_agent_instructions()
