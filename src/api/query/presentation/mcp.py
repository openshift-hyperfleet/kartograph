"""MCP server for the Querying bounded context."""

import re
from pathlib import Path
from typing import Any, Dict

import httpx
from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from infrastructure.settings import get_settings
from query.application.services import MCPQueryService
from query.dependencies import get_mcp_query_service
from query.domain.value_objects import QueryError

settings = get_settings()

mcp = FastMCP(name=settings.app_name, stateless_http=True)

query_mcp_app = mcp.http_app(path="/mcp")

# Load agent instructions from file
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_AGENT_INSTRUCTIONS_PATH = _PROMPTS_DIR / "agent_instructions.md"

# Regex pattern for GitHub blob URLs
_GITHUB_BLOB_PATTERN = re.compile(
    r"^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$"
)


def _transform_github_blob_to_raw_url(blob_url: str) -> str:
    """Transform a GitHub blob URL to a raw.githubusercontent.com URL.

    Args:
        blob_url: A GitHub blob URL like:
            https://github.com/owner/repo/blob/branch/path/to/file.adoc

    Returns:
        The corresponding raw URL like:
            https://raw.githubusercontent.com/owner/repo/branch/path/to/file.adoc

    Raises:
        ValueError: If the URL is not a valid GitHub blob URL.
    """
    match = _GITHUB_BLOB_PATTERN.match(blob_url)
    if not match:
        raise ValueError(
            f"Invalid URL format. Expected a GitHub blob URL like "
            f"'https://github.com/owner/repo/blob/branch/path/file.adoc', "
            f"got: {blob_url}"
        )

    owner, repo, branch, path = match.groups()
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"


def _extract_asciidoc_content(raw_content: str) -> str:
    """Extract the main content from an AsciiDoc file.

    Strips metadata, comments, and attributes that appear before the first
    level-1 heading (= Title). Returns content from the title onwards.

    Args:
        raw_content: The raw AsciiDoc file content.

    Returns:
        The content starting from the first level-1 heading title,
        or the original content if no heading is found.
    """
    if not raw_content:
        return raw_content

    # Find the first occurrence of "\n= " (level-1 heading after newline)
    # or "= " at the very start of the file
    newline_heading_pos = raw_content.find("\n= ")
    start_heading_match = raw_content.startswith("= ")

    if start_heading_match:
        # Heading is at the very start, skip the "= " marker
        return raw_content[2:]
    elif newline_heading_pos != -1:
        # Found heading after newline, skip "\n= " to start at title text
        return raw_content[newline_heading_pos + 3 :]
    else:
        # No level-1 heading found, return as-is
        return raw_content


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


def _fetch_documentation_source_impl(
    documentationmodule_view_uri: str,
) -> Dict[str, Any]:
    """Core implementation for fetching documentation source content.

    This is the testable implementation extracted from the MCP tool.

    Args:
        documentationmodule_view_uri: The view_uri from a DocumentationModule.

    Returns:
        A dictionary with success status and content or error.
    """
    # Transform the GitHub blob URL to raw content URL
    try:
        raw_url = _transform_github_blob_to_raw_url(documentationmodule_view_uri)
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }

    # Fetch the raw content
    try:
        response = httpx.get(raw_url, timeout=30.0, follow_redirects=True)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch content: {e}",
        }

    # Check for HTTP errors
    if response.status_code != 200:
        return {
            "success": False,
            "error": f"HTTP {response.status_code}: Failed to fetch content from {raw_url}",
        }

    # Extract the main content (strip metadata/comments before title)
    raw_content = response.text
    content = _extract_asciidoc_content(raw_content)

    return {
        "success": True,
        "content": content,
        "source_url": documentationmodule_view_uri,
        "raw_url": raw_url,
    }


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
) -> Dict[str, Any]:
    """Fetch the full source content of a DocumentationModule from its view_uri.

    Use this tool when you need to read the complete documentation content
    for a DocumentationModule. The `content_summary` and `misc` properties
    provide a concise overview, but this tool retrieves the full source file
    including all procedure steps, code blocks, and configuration details.

    The tool automatically:
    - Transforms GitHub blob URLs to raw content URLs
    - Strips AsciiDoc metadata and comments
    - Returns only the main documentation content (starting from the title)

    Args:
        documentationmodule_view_uri: The view_uri from a DocumentationModule
            instance. Must be a GitHub blob URL like:
            https://github.com/openshift/openshift-docs/blob/main/modules/file.adoc

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the fetch succeeded
        - content: The extracted documentation content (on success)
        - source_url: The original view_uri (on success)
        - raw_url: The raw.githubusercontent.com URL used (on success)
        - error: Error message (on failure)

    Examples:
        # Get full content for a DocumentationModule
        details = query_graph("MATCH (d:DocumentationModule {slug: 'abi-c3-resources-services'}) RETURN properties(d)")
        view_uri = details["rows"][0]["view_uri"]
        source = fetch_documentation_source(view_uri)
        print(source["content"])  # Full AsciiDoc content starting from title
    """
    return _fetch_documentation_source_impl(documentationmodule_view_uri)


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
