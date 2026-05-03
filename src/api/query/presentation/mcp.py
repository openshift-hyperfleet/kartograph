"""MCP server for the Querying bounded context."""

from typing import Any, Dict

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.server.dependencies import get_http_headers

from infrastructure.mcp_dependencies import (
    get_accessible_knowledge_graphs_for_mcp,
    get_mcp_secure_enclave,
    validate_mcp_api_key,
    validate_mcp_bearer_token,
)
from infrastructure.settings import get_settings
from query.application.observability import (
    DefaultKnowledgeGraphResourceProbe,
    KnowledgeGraphResourceProbe,
)
from query.application.services import MCPQueryService
from query.domain.value_objects import QueryError, QueryResultRow
from query.dependencies import (
    get_git_repository,
    get_mcp_query_service,
    get_prompt_repository,
)
from query.domain.value_objects import QueryError, QueryResultRow
from query.ports.file_repository_models import RemoteFileRepositoryResponse
from shared_kernel.middleware.mcp_api_key_auth import MCPApiKeyAuthMiddleware
from shared_kernel.middleware.mcp_auth import get_mcp_auth_context

settings = get_settings()

mcp = FastMCP(name=settings.app_name)


class _MCPAppProxy:
    """ASGI proxy whose inner app can be swapped without remounting.

    FastMCP's StreamableHTTPSessionManager cannot be restarted after it
    exits (it raises RuntimeError on a second .run() call).  This proxy
    sits between the mounted route and the live FastMCP http_app so that
    the lifespan can install a fresh http_app instance on each startup
    without touching FastAPI's router.
    """

    def __init__(self) -> None:
        self._app = mcp.http_app(path="/mcp", stateless_http=True)

    def refresh(self) -> None:
        """Replace the inner app with a freshly created instance."""
        self._app = mcp.http_app(path="/mcp", stateless_http=True)

    async def __call__(self, scope, receive, send) -> None:  # type: ignore[override]
        await self._app(scope, receive, send)


#: Proxy that holds the current live FastMCP http_app.  main.py's lifespan
#: calls proxy.refresh() before entering the new app's lifespan context so
#: every startup gets a fresh StreamableHTTPSessionManager.
mcp_http_app_proxy = _MCPAppProxy()

query_mcp_app = MCPApiKeyAuthMiddleware(
    app=mcp_http_app_proxy,
    validate_api_key=validate_mcp_api_key,
    validate_bearer_token=validate_mcp_bearer_token,
)

# Eagerly validate prompts at startup (fail-fast if missing)
_prompt_repository = get_prompt_repository()

#: Domain probe for knowledge graph resource observability (module-level singleton)
_kg_resource_probe: KnowledgeGraphResourceProbe = DefaultKnowledgeGraphResourceProbe()


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

    # Enforce maximum limits (spec: max 60 s timeout, max 10 000 rows)
    timeout_seconds, max_rows = _clamp_query_params(timeout_seconds, max_rows)

    result = service.execute_cypher_query(
        query=cypher,
        timeout_seconds=timeout_seconds,
        max_rows=max_rows,
    )

    if isinstance(result, QueryError):
        return _build_error_response(result)

    # Filter to the requested KnowledgeGraph (when provided)
    rows = _filter_by_knowledge_graph(result.rows, knowledge_graph_id)

    # Apply secure enclave: redact entities the caller is not authorized to see
    secure_enclave = get_mcp_secure_enclave()
    rows = await secure_enclave.apply_redaction(rows)

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
            If the URL does not match GitHub or GitLab blob patterns, a
            ``RemoteFileRepositoryResponse(success=False, error=...)`` is returned.

    Returns:
        class RemoteFileRepositoryResponse(BaseModel):
            success: bool
            error: str | None = None  # populated when success=False
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

    try:
        repository = get_git_repository(
            url=documentationmodule_view_uri,
            github_token=github_token,
            gitlab_token=gitlab_token,
        )
        return repository.get_file(url=documentationmodule_view_uri)
    except InvalidRemoteFileURL:
        return RemoteFileRepositoryResponse(
            success=False,
            error="Invalid URL format: must be a GitHub or GitLab blob URL",
        )
    except RemoteFileFetchFailed as e:
        return RemoteFileRepositoryResponse(
            success=False,
            error=str(e) or "Failed to fetch file from remote repository",
        )


@mcp.resource(
    # NOTE: The spec uses 'knowledge_graphs://accessible' but URL schemes cannot
    # contain underscores (RFC 3986). We use 'knowledge-graphs://accessible'
    # (hyphen) which is the equivalent valid URI that FastMCP's pydantic
    # AnyUrl validator accepts. MCP clients discover this URI via resources/list.
    uri="knowledge-graphs://accessible",
    name="AccessibleKnowledgeGraphs",
    description="All knowledge graphs the authenticated caller has view permission on within their tenant",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False},
)
async def get_accessible_knowledge_graphs() -> list[dict]:
    """Get all knowledge graphs accessible to the authenticated caller.

    Queries the management context for all knowledge graphs in the caller's
    tenant, filtered to only those the caller has VIEW permission on via
    SpiceDB authorization.

    Returns:
        List of knowledge graph summaries. Each entry contains:
        - id: The knowledge graph's unique identifier
        - name: The human-readable name
        - description: A description of the knowledge graph's content

        Returns an empty list when the caller has no accessible knowledge graphs.

    Examples:
        Read the resource to discover available knowledge graphs before querying:
        - Resource URI: ``knowledge-graphs://accessible``
        - Response: ``[{"id": "kg-01J...", "name": "My Graph", "description": "..."}]``

        Use the returned ``id`` values with the ``query_graph`` tool's
        ``knowledge_graph_id`` parameter to scope queries to a specific graph.
    """
    auth_context = get_mcp_auth_context()

    _kg_resource_probe.knowledge_graphs_resource_accessed(
        user_id=auth_context.user_id,
        tenant_id=auth_context.tenant_id,
    )

    kgs = await get_accessible_knowledge_graphs_for_mcp()

    result = [
        {
            "id": kg.id,
            "name": kg.name,
            "description": kg.description,
        }
        for kg in kgs
    ]

    _kg_resource_probe.knowledge_graphs_resource_returned(
        user_id=auth_context.user_id,
        tenant_id=auth_context.tenant_id,
        count=len(result),
    )

    return result


@mcp.resource(
    # NOTE: The spec uses 'knowledge_graphs://accessible' but URL schemes cannot
    # contain underscores (RFC 3986). We use 'knowledge-graphs://accessible'
    # (hyphen) which is the equivalent valid URI that FastMCP's pydantic
    # AnyUrl validator accepts. MCP clients discover this URI via resources/list.
    uri="knowledge-graphs://accessible",
    name="AccessibleKnowledgeGraphs",
    description="All knowledge graphs the authenticated caller has view permission on within their tenant",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False},
)
async def get_accessible_knowledge_graphs() -> list[dict]:
    """Get all knowledge graphs accessible to the authenticated caller.

    Queries the management context for all knowledge graphs in the caller's
    tenant, filtered to only those the caller has VIEW permission on via
    SpiceDB authorization.

    Returns:
        List of knowledge graph summaries. Each entry contains:
        - id: The knowledge graph's unique identifier
        - name: The human-readable name
        - description: A description of the knowledge graph's content

        Returns an empty list when the caller has no accessible knowledge graphs.

    Examples:
        Read the resource to discover available knowledge graphs before querying:
        - Resource URI: ``knowledge-graphs://accessible``
        - Response: ``[{"id": "kg-01J...", "name": "My Graph", "description": "..."}]``

        Use the returned ``id`` values with the ``query_graph`` tool's
        ``knowledge_graph_id`` parameter to scope queries to a specific graph.
    """
    auth_context = get_mcp_auth_context()

    _kg_resource_probe.knowledge_graphs_resource_accessed(
        user_id=auth_context.user_id,
        tenant_id=auth_context.tenant_id,
    )

    kgs = await get_accessible_knowledge_graphs_for_mcp()

    result = [
        {
            "id": kg.id,
            "name": kg.name,
            "description": kg.description,
        }
        for kg in kgs
    ]

    _kg_resource_probe.knowledge_graphs_resource_returned(
        user_id=auth_context.user_id,
        tenant_id=auth_context.tenant_id,
        count=len(result),
    )

    return result


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
