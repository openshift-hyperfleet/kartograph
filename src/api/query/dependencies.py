"""Dependency injection for Query bounded context.

Provides dependencies local to the Query context only.
Cross-context composition is handled in infrastructure.mcp_dependencies.
"""

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Iterator, Optional

from query.infrastructure.git_repository import GitRepositoryFactory
from query.infrastructure.observability.remote_file_repository_probe import (
    DefaultRemoteFileRepositoryProbe,
)
from query.infrastructure.prompt_repository import PromptRepository
from query.infrastructure.tenant_routing import (
    AGEGraphExistenceChecker,
    TenantAwareQueryGraphRepository,
)
from query.ports.repositories import IRemoteFileRepository

from infrastructure.database.connection import ConnectionFactory
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.settings import get_database_settings
from query.application.observability import (
    DefaultQueryServiceProbe,
    DefaultSchemaResourceProbe,
    QueryServiceProbe,
    SchemaResourceProbe,
)
from query.application.services import MCPQueryService
from query.infrastructure.query_repository import QueryGraphRepository
from shared_kernel.middleware.mcp_auth import get_mcp_auth_context

if TYPE_CHECKING:
    from graph.infrastructure.age_client import AgeGraphClient


def get_query_service_probe() -> QueryServiceProbe:
    """Get QueryServiceProbe instance.

    Returns:
        DefaultQueryServiceProbe instance for observability
    """
    return DefaultQueryServiceProbe()


@contextmanager
def mcp_graph_client_context(
    graph_name: Optional[str] = None,
) -> Generator["AgeGraphClient", None, None]:
    """Context manager for MCP graph client lifecycle.

    Creates a connected graph client and ensures proper cleanup.
    Uses the shared connection pool for efficiency.

    Args:
        graph_name: Optional graph name override. When provided (e.g.,
            ``"tenant_{tenant_id}"``), the client targets that specific
            AGE graph instead of the default from settings. Pass this
            for per-tenant graph isolation (spec: Per-Tenant Graph Routing).

    Yields:
        Connected AgeGraphClient instance
    """
    # Runtime import to avoid static dependency on Graph infrastructure
    from graph.infrastructure.age_client import AgeGraphClient

    pool = get_age_connection_pool()
    settings = get_database_settings()
    factory = ConnectionFactory(settings, pool=pool)
    client = AgeGraphClient(settings, connection_factory=factory, graph_name=graph_name)
    client.connect()
    try:
        yield client
    finally:
        client.disconnect()


@contextmanager
def get_mcp_query_service() -> Iterator[MCPQueryService]:
    """Get a tenant-aware MCPQueryService for MCP tool calls.

    Reads the authenticated tenant from the MCP auth ContextVar and
    routes all queries to that tenant's AGE graph (``tenant_{tenant_id}``).

    The tenant graph existence is checked before every query execution;
    if the graph has not been provisioned the query is rejected with a
    QueryExecutionError before any AGE round-trip (spec: Tenant graph not found).

    Context manager that manually resolves all dependencies to work with
    FastMCP's DI system, which doesn't support nested Depends() chains.
    Handles graph client lifecycle (connect/disconnect) automatically.

    Per-tenant graph routing:
        Reads the authenticated MCP caller's tenant_id from the request
        context and routes all queries to the corresponding AGE graph
        (``tenant_{tenant_id}``). This guarantees tenant isolation at the
        database level — all queries run against a graph that is dedicated to
        and owned by the authenticated tenant.

    Yields:
        MCPQueryService instance with active database connection targeting
        the authenticated tenant's AGE graph.
    """
    auth_context = get_mcp_auth_context()
    tenant_graph_name = f"tenant_{auth_context.tenant_id}"

    with mcp_graph_client_context(graph_name=tenant_graph_name) as client:
        probe = get_query_service_probe()
        inner_repository = QueryGraphRepository(client=client)
        repository = TenantAwareQueryGraphRepository(
            tenant_id=tenant_id,
            inner_repository=inner_repository,
            existence_check_fn=existence_checker,
        )
        yield MCPQueryService(repository=repository, probe=probe)


def get_schema_resource_probe() -> SchemaResourceProbe:
    """Get schema resource probe for observability.

    Returns:
        SchemaResourceProbe instance for domain event emission
    """
    return DefaultSchemaResourceProbe()


def get_git_repository(
    url: str,
    github_token: Optional[str] = None,
    gitlab_token: Optional[str] = None,
) -> IRemoteFileRepository:
    """Get git repository for URL with default observability.

    Automatically detects the git provider (GitHub, GitLab, etc.) from the URL
    and selects the appropriate token. Supports self-hosted instances.

    Args:
        url: Git blob URL (e.g., https://github.com/owner/repo/blob/main/file.txt)
        github_token: Optional GitHub access token (for GitHub URLs)
        gitlab_token: Optional GitLab access token (for GitLab URLs)

    Returns:
        Repository instance for the detected provider with appropriate token

    Raises:
        InvalidRemoteFileURL: If URL is from an unsupported git provider or has an invalid format

    Example:
        >>> # Factory auto-selects the right token based on URL
        >>> repo = get_git_repository(
        ...     "https://gitlab.com/owner/repo/-/blob/main/README.md",
        ...     github_token="ghp_...",
        ...     gitlab_token="glpat_..."
        ... )
        >>> response = repo.get_file(url)
    """
    probe = DefaultRemoteFileRepositoryProbe()
    return GitRepositoryFactory.create_from_url(
        url=url, github_token=github_token, gitlab_token=gitlab_token, probe=probe
    )


@lru_cache(maxsize=1)
def get_prompt_repository() -> PromptRepository:
    """Get prompt repository with default prompts directory (cached).

    Loads prompts from query/infrastructure/prompts directory.
    Performs startup validation to ensure required files exist.

    Cached to avoid re-creating instances and re-validating on every call.

    Returns:
        PromptRepository instance with validated prompts (singleton)

    Raises:
        FileNotFoundError: If prompts directory or required files are missing
    """
    # Path relative to this module: query/dependencies.py
    # Target: query/infrastructure/prompts/
    prompts_dir = Path(__file__).parent / "infrastructure" / "prompts"
    return PromptRepository(prompts_dir=prompts_dir)
