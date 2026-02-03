"""MCP server for the Querying bounded context."""

from pathlib import Path
from typing import Any, Dict

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from query.ports.file_repository_models import RemoteFileRepositoryResponse
from infrastructure.settings import get_settings
from query.application.services import MCPQueryService
from query.dependencies import get_git_repository, get_mcp_query_service
from query.domain.value_objects import QueryError
from fastmcp.server.dependencies import get_http_headers

settings = get_settings()

mcp = FastMCP(name=settings.app_name, stateless_http=True)

query_mcp_app = mcp.http_app(path="/mcp")

# Load agent instructions from file
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_AGENT_INSTRUCTIONS_PATH = _PROMPTS_DIR / "agent_instructions.md"


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


@mcp.tool
def query_graph(
    cypher: str,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
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

    # Filter internal properties before returning to agent
    filtered_rows = _filter_internal_properties(result.rows)

    # CypherQueryResult
    return {
        "success": True,
        "rows": filtered_rows,
        "row_count": result.row_count,
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

    Examples:
        # Get full content for a DocumentationModule
        details = query_graph("MATCH (d:DocumentationModule {slug: 'abi-c3-resources-services'}) RETURN properties(d)")
        view_uri = details["rows"][0]["view_uri"]
        source = fetch_documentation_source(view_uri)
        print(source["content"])  # Full AsciiDoc content starting from title
    """

    headers = get_http_headers()

    print("HEADERS", headers)

    github_token = headers.get("x-github-pat", "")
    gitlab_token = headers.get("x-gitlab-pat", "")

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
        Markdown-formatted agent instructions
    """
    try:
        with open(_AGENT_INSTRUCTIONS_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return (
            "# Agent Instructions Not Found\n\n"
            "The agent instructions file could not be loaded. "
            "Please ensure the instructions file exists at the expected location."
        )
