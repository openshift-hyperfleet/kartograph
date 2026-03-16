"""MCP server for the Querying bounded context."""

import os
from typing import Any, Dict, Optional

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from infrastructure.mcp_dependencies import validate_mcp_api_key
from infrastructure.settings import get_settings
from query.application.services import MCPQueryService
from query.dependencies import (
    build_ask_sre_gitlab_url,
    get_git_repository,
    get_mcp_query_service,
    get_prompt_repository,
    resolve_ask_sre_document_path,
)
from query.domain.value_objects import QueryError
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


@mcp.tool
def query_graph(
    cypher: str,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
    service: MCPQueryService = Depends(get_mcp_query_service),  # type: ignore[arg-type]
) -> Dict[str, Any]:
    """Read-only Cypher query against the knowledge graph."""

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


# Process-lifetime cache keyed on (identifier, token).
# Only successful responses are stored — errors are never cached so transient
# GitLab failures don't permanently poison an identifier for the process lifetime.
_file_content_cache: dict[tuple[str, Optional[str]], RemoteFileRepositoryResponse] = {}


async def _fetch_file_async(
    identifier: str, gitlab_token: Optional[str]
) -> RemoteFileRepositoryResponse:
    """Fetch file content from GitLab, returning a cached result if available.

    Async so the GitLab HTTP round-trip runs on the event loop rather than
    blocking a thread pool worker. With many concurrent agents, the sync
    version exhausted the thread pool (~12 workers) causing query_graph calls
    to queue behind blocked file-fetch threads.
    """
    cache_key = (identifier, gitlab_token)
    cached = _file_content_cache.get(cache_key)
    if cached is not None:
        return cached

    relative_path = resolve_ask_sre_document_path(identifier)

    if relative_path is None:
        return RemoteFileRepositoryResponse(
            success=False,
            error=f"Could not resolve identifier '{identifier}' to a known file. "
            "Check that the entity slug or file path exists in read_file.json.",
            content=None,
            source_url=None,
            raw_url=None,
        )

    gitlab_url = build_ask_sre_gitlab_url(relative_path)
    repository = get_git_repository(url=gitlab_url, gitlab_token=gitlab_token)
    result = await repository.get_file(url=gitlab_url)

    if result.success:
        _file_content_cache[cache_key] = result

    return result


@mcp.tool
async def get_file_contents(
    identifier: str,
) -> RemoteFileRepositoryResponse:
    """Returns full file content. Pass a slug or file_path from the graph."""
    return await _fetch_file_async(
        identifier=identifier,
        gitlab_token=os.environ.get("KARTOGRAPH_GITLAB_PAT"),
    )


# @mcp.resource(
#     uri="instructions://agent",
#     name="AgentInstructions",
#     description="System instructions for AI agents using the query_graph tool with multi-term search strategies and platform-aware filtering",
#     mime_type="text/markdown",
#     annotations={"readOnlyHint": True, "idempotentHint": True},
# )
# def get_agent_instructions() -> str:
#     """Get agent instructions for querying the knowledge graph using Cypher.

#     Returns instructions optimized for agents that will use the query_graph tool,
#     writing raw Cypher queries against Apache AGE.

#     Includes:
#     - Apache AGE-specific Cypher syntax requirements
#     - Multi-term search strategies with AND logic
#     - Platform-aware filtering using view_uri paths
#     - Deprecated item discovery patterns
#     - Self-check workflow before answering
#     - Best practices for efficient graph traversal
#     - Knowledge graph overview and domain context

#     Returns:
#         Markdown-formatted agent instructions (cached from startup)
#     """
#     return _prompt_repository.get_agent_instructions()
