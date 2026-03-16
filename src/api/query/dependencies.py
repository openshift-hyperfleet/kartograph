"""Dependency injection for Query bounded context.

Provides dependencies local to the Query context only.
Cross-context composition is handled in infrastructure.mcp_dependencies.
"""

import json
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Generator, Iterator, Optional

from query.infrastructure.git_repository import GitRepositoryFactory
from query.infrastructure.observability.remote_file_repository_probe import (
    DefaultRemoteFileRepositoryProbe,
)
from query.infrastructure.prompt_repository import PromptRepository
from query.ports.repositories import IRemoteFileRepository

from infrastructure.database.connection import ConnectionFactory
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.settings import get_database_settings, get_query_settings
from query.application.observability import (
    DefaultQueryServiceProbe,
    DefaultSchemaResourceProbe,
    QueryServiceProbe,
    SchemaResourceProbe,
)
from query.application.services import MCPQueryService
from query.infrastructure.query_repository import QueryGraphRepository

if TYPE_CHECKING:
    from graph.infrastructure.age_client import AgeGraphClient

_FILE_PATH_INDEX = Path(__file__).parent / "infrastructure" / "file_indexes" / "ask_sre_file_identifiers.json"


def get_query_service_probe() -> QueryServiceProbe:
    """Get QueryServiceProbe instance.

    Returns:
        DefaultQueryServiceProbe instance for observability
    """
    return DefaultQueryServiceProbe()


@contextmanager
def mcp_graph_client_context() -> Generator["AgeGraphClient", None, None]:
    """Context manager for MCP graph client lifecycle.

    Creates a connected graph client and ensures proper cleanup.
    Uses the shared connection pool for efficiency.

    Yields:
        Connected AgeGraphClient instance
    """
    # Runtime import to avoid static dependency on Graph infrastructure
    from graph.infrastructure.age_client import AgeGraphClient

    pool = get_age_connection_pool()
    settings = get_database_settings()
    factory = ConnectionFactory(settings, pool=pool)
    client = AgeGraphClient(settings, connection_factory=factory)
    client.connect()
    try:
        yield client
    finally:
        client.disconnect()


@contextmanager
def get_mcp_query_service() -> Iterator[MCPQueryService]:
    """Get MCPQueryService for MCP operations.

    Context manager that manually resolves all dependencies to work with
    FastMCP's docket DI system, which doesn't support nested Depends() chains.

    Handles graph client lifecycle (connect/disconnect) automatically.

    Yields:
        MCPQueryService instance with active database connection
    """
    with mcp_graph_client_context() as client:
        probe = get_query_service_probe()
        repository = QueryGraphRepository(client=client)
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
        ValueError: If URL is from an unsupported git provider

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
def _load_file_path_index() -> dict[str, str]:
    """Load the file path index from disk once and cache for process lifetime."""
    with _FILE_PATH_INDEX.open() as f:
        return json.load(f)


def resolve_ask_sre_document_path(identifier: str) -> Optional[str]:
    """Resolve an identifier (slug or file path) to its repo-relative path.

    Looks up the identifier in the file path index, which maps both full
    paths (e.g. "openshift-docs-md/foo/bar.md") and slugs
    (e.g. "bar-md") to their canonical path within the data source repo
    (e.g. "data/openshift-docs-md/foo/bar.md").

    Args:
        identifier: A slug or file_path value from the knowledge graph.

    Returns:
        The repo-relative path (e.g. "data/openshift-docs-md/foo/bar.md"),
        or None if the identifier is not found.
    """
    return _load_file_path_index().get(identifier)


def build_ask_sre_gitlab_url(relative_path: str) -> str:
    """Build a full GitLab blob URL for a repo-relative file path.

    Combines the configured base URL with the relative path from the index.

    Args:
        relative_path: Repo-relative path, e.g. "data/openshift-docs-md/foo/bar.md"

    Returns:
        Full GitLab blob URL, e.g.:
        https://gitlab.example.com/org/repo/-/blob/main/data/openshift-docs-md/foo/bar.md
    """
    base = get_query_settings().ask_sre_gitlab_blob_base_url.rstrip("/")
    return f"{base}/{relative_path}"


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
