"""GitHub repository adapter for the Ingestion bounded context.

Extracts file content from GitHub repositories via the GitHub REST API,
producing raw content and changeset entries for packaging into a JobPackage.

Supports:
- Full refresh: downloads a repository tarball (one archive fetch).
- Incremental sync: uses the GitHub Compare API to find only files that
  changed since the previous checkpoint commit SHA.

API endpoints used:
- GET /repos/{owner}/{repo}/branches/{branch}  — resolve branch to commit SHA
- GET /repos/{owner}/{repo}/tarball/{ref}  — full refresh archive download
- GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1  — branch file counts
- GET /repos/{owner}/{repo}/compare/{base}...{head}  — changed files
- GET /repos/{owner}/{repo}/git/blobs/{sha}  — incremental blob content (base64)

dlt integration note: this adapter class provides the extraction contract
(IDatasourceAdapter). The Ingestion service (a future task) wraps this adapter
in a dlt pipeline configured with a PostgreSQL destination for state persistence
and a filesystem destination for JobPackager-readable output files. The adapter
itself uses httpx directly to keep it independently testable.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import mimetypes
import tarfile
from typing import Any

import httpx

from ingestion.ports.adapters import ExtractionResult
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    ChangesetEntry,
    ContentRef,
    SyncMode,
)

# GitHub REST API base URL
_GITHUB_API_BASE = "https://api.github.com"
_USER_AGENT = "Kartograph-GitHub-Ingestion/1.0"

# Version of the checkpoint schema this adapter understands.
# Bump on backwards-incompatible checkpoint changes; callers should
# fall back to a full refresh when the schema version does not match.
_CHECKPOINT_SCHEMA_VERSION = "1.0.0"

# Key used to store the commit SHA within the checkpoint data dict.
_COMMIT_SHA_KEY = "commit_sha"

# Reverse-DNS type identifier for file-type changeset entries.
_ENTRY_TYPE_FILE = "io.kartograph.change.file"

# GitHub file statuses that map to ChangeOperation.ADD
_ADD_STATUSES = frozenset({"added"})

# GitHub file statuses that map to ChangeOperation.MODIFY
_MODIFY_STATUSES = frozenset({"modified", "renamed", "changed", "copied"})

# GitHub file statuses to ignore (deletions handled downstream via staleness)
_IGNORED_STATUSES = frozenset({"removed", "unchanged"})


class GitHubAdapter:
    """GitHub repository adapter implementing IDatasourceAdapter.

    Extracts file content from a GitHub repository. Configured via
    connection_config (owner, repo, branch) and credentials (token).

    Args:
        http_client: Optional pre-configured httpx.AsyncClient.  When omitted,
            a default client is created per extract() call.  Inject a client
            with a custom transport for testing.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        *,
        blob_fetch_max_concurrency: int = 16,
    ) -> None:
        if blob_fetch_max_concurrency <= 0:
            raise ValueError("blob_fetch_max_concurrency must be positive")
        self._http_client = http_client
        self._blob_fetch_max_concurrency = blob_fetch_max_concurrency

    @staticmethod
    def _parse_connection_config(
        config: dict[str, str],
    ) -> tuple[str, str, str]:
        """Parse connection_config into (owner, repo, branch).

        Accepts either a ``repo_url`` key (parsed from a GitHub URL) or
        explicit ``owner``/``repo``/``branch`` keys.
        """
        if "repo_url" in config:
            url = config["repo_url"].rstrip("/")
            # Strip trailing .git
            if url.endswith(".git"):
                url = url[:-4]
            # Handle https://github.com/owner/repo[/tree/branch/...]
            parts = url.split("/")
            try:
                gh_idx = next(
                    i
                    for i, p in enumerate(parts)
                    if p in ("github.com", "www.github.com")
                )
            except StopIteration:
                raise ValueError(f"Cannot parse GitHub URL: {config['repo_url']}")
            if len(parts) < gh_idx + 3:
                raise ValueError(
                    f"GitHub URL must include owner and repo: {config['repo_url']}"
                )
            owner = parts[gh_idx + 1]
            repo = parts[gh_idx + 2]
            branch = config.get("branch", "main")
            # Extract branch from /tree/branch-name if present
            if len(parts) > gh_idx + 4 and parts[gh_idx + 3] == "tree":
                branch = parts[gh_idx + 4]
            return owner, repo, branch

        if "owner" in config and "repo" in config:
            return config["owner"], config["repo"], config.get("branch", "main")

        raise ValueError(
            "connection_config must include either 'repo_url' or 'owner'+'repo' keys"
        )

    @staticmethod
    def _github_headers(token: str) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": _USER_AGENT,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def extract(
        self,
        connection_config: dict[str, str],
        credentials: dict[str, str],
        checkpoint: AdapterCheckpoint | None,
        sync_mode: SyncMode,
    ) -> ExtractionResult:
        """Extract raw content from a GitHub repository.

        For a full refresh (sync_mode=FULL_REFRESH or checkpoint=None), fetches
        the entire repository tree and returns all blob files as ADD entries.

        For an incremental run (sync_mode=INCREMENTAL with a checkpoint), uses
        the GitHub Compare API to find only files added/modified/renamed since
        the checkpoint commit SHA, and fetches only their content.

        Args:
            connection_config: Repository parameters. Accepts either:
                - ``repo_url``: Full GitHub URL (e.g. ``https://github.com/owner/repo``)
                - Or explicit keys: ``owner``, ``repo``, ``branch`` (default: "main")
            credentials: Decrypted GitHub credentials. Expected keys:
                - ``token`` or ``access_token``: A GitHub PAT or App token.
            checkpoint: Previous checkpoint containing ``commit_sha``, or None.
            sync_mode: Controls whether to run a full refresh or incremental.

        Returns:
            ExtractionResult with changeset entries, content blobs, and the
            updated checkpoint (new HEAD commit SHA).

        Raises:
            ValueError: If the repo URL cannot be parsed or required keys are missing.
        """
        owner, repo, branch = self._parse_connection_config(connection_config)
        token = credentials.get("token") or credentials.get("access_token", "")

        use_full_refresh = (
            sync_mode == SyncMode.FULL_REFRESH
            or checkpoint is None
            or _COMMIT_SHA_KEY not in checkpoint.data
        )

        client = self._http_client or httpx.AsyncClient(follow_redirects=True)
        headers = self._github_headers(token)

        try:
            head_sha = await self._get_branch_head_sha(
                client, headers, owner, repo, branch
            )

            if use_full_refresh:
                (
                    changeset_entries,
                    content_blobs,
                    branch_file_count,
                ) = await self._extract_full_refresh_via_tarball(
                    client,
                    headers,
                    owner,
                    repo,
                    branch,
                    head_sha,
                )
            else:
                assert checkpoint is not None
                base_sha = checkpoint.data[_COMMIT_SHA_KEY]
                files_to_fetch = await self._get_changed_files(
                    client, headers, owner, repo, base_sha, head_sha
                )
                branch_file_count = await self._count_tree_blobs(
                    client, headers, owner, repo, head_sha
                )
                changeset_entries, content_blobs = await self._fetch_file_contents(
                    client, headers, owner, repo, files_to_fetch
                )

        finally:
            # Only close the client if we created it ourselves
            if self._http_client is None:
                await client.aclose()

        new_checkpoint = AdapterCheckpoint(
            schema_version=_CHECKPOINT_SCHEMA_VERSION,
            data={_COMMIT_SHA_KEY: head_sha},
        )

        return ExtractionResult(
            changeset_entries=changeset_entries,
            content_blobs=content_blobs,
            new_checkpoint=new_checkpoint,
            branch_file_count=branch_file_count,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_branch_head_sha(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        owner: str,
        repo: str,
        branch: str,
    ) -> str:
        """Resolve a branch name to its current HEAD commit SHA.

        Args:
            client: httpx async client.
            headers: GitHub API request headers.
            owner: Repository owner.
            repo: Repository name.
            branch: Branch name.

        Returns:
            The full commit SHA string.

        Raises:
            httpx.HTTPStatusError: If the GitHub API returns a non-2xx status.
        """
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/branches/{branch}"
        data = await self._get_json_with_auth_fallback(client, url, headers=headers)
        return str(data["commit"]["sha"])

    async def _get_all_tree_blobs(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        owner: str,
        repo: str,
        tree_sha: str,
    ) -> list[dict[str, Any]]:
        """Fetch all blob entries from the repository tree for a full refresh.

        Non-blob entries (e.g., directories) are excluded.

        Args:
            client: httpx async client.
            headers: GitHub API request headers.
            owner: Repository owner.
            repo: Repository name.
            tree_sha: Commit or tree SHA to fetch the tree for.

        Returns:
            List of dicts with ``path``, ``sha``, and ``operation`` keys, where
            operation is always ``ChangeOperation.ADD``.
        """
        url = (
            f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1"
        )
        tree_data = await self._get_json_with_auth_fallback(
            client, url, headers=headers
        )

        result: list[dict[str, Any]] = []
        for item in tree_data.get("tree", []):
            if item.get("type") != "blob":
                continue
            result.append(
                {
                    "path": item["path"],
                    "sha": item["sha"],
                    "operation": ChangeOperation.ADD,
                    "previous_path": None,
                }
            )
        return result

    async def _count_tree_blobs(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        owner: str,
        repo: str,
        tree_sha: str,
    ) -> int:
        """Count blob entries in the repository tree at a commit."""
        url = (
            f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1"
        )
        tree_data = await self._get_json_with_auth_fallback(
            client, url, headers=headers
        )
        return sum(
            1 for item in tree_data.get("tree", []) if item.get("type") == "blob"
        )

    async def _get_changed_files(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        owner: str,
        repo: str,
        base_sha: str,
        head_sha: str,
    ) -> list[dict[str, Any]]:
        """Fetch files changed between two commits using the Compare API.

        Only ADD and MODIFY statuses are returned. REMOVE is excluded because
        staleness detection is handled downstream by comparing ``last_synced_at``
        timestamps.

        Args:
            client: httpx async client.
            headers: GitHub API request headers.
            owner: Repository owner.
            repo: Repository name.
            base_sha: The previous checkpoint commit SHA.
            head_sha: The current HEAD commit SHA.

        Returns:
            List of dicts with ``path``, ``sha``, ``operation``, and
            ``previous_path`` keys.
        """
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}"
        compare_data = await self._get_json_with_auth_fallback(
            client, url, headers=headers
        )

        result: list[dict[str, Any]] = []
        for file_info in compare_data.get("files", []):
            status: str = file_info.get("status", "")
            filename: str = file_info["filename"]
            blob_sha: str = file_info["sha"]
            previous_filename: str | None = file_info.get("previous_filename")

            if status in _ADD_STATUSES:
                operation = ChangeOperation.ADD
            elif status in _MODIFY_STATUSES:
                operation = ChangeOperation.MODIFY
            else:
                # Skip removed, unchanged, and any unknown statuses
                continue

            result.append(
                {
                    "path": filename,
                    "sha": blob_sha,
                    "operation": operation,
                    "previous_path": previous_filename,
                }
            )
        return result

    async def _extract_full_refresh_via_tarball(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        owner: str,
        repo: str,
        branch: str,
        head_sha: str,
    ) -> tuple[list[ChangesetEntry], dict[str, bytes], int]:
        """Download repository tarball and build ADD changeset entries."""
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/tarball/{branch}"
        archive_bytes = await self._get_bytes_with_auth_fallback(
            client,
            url,
            headers=headers,
        )
        try:
            branch_file_count = await self._count_tree_blobs(
                client, headers, owner, repo, head_sha
            )
        except httpx.HTTPStatusError:
            # Tarball extraction already succeeded; tree count is metadata only.
            branch_file_count = 0
        return self._changeset_from_tarball(
            archive_bytes, branch_file_count=branch_file_count
        )

    @staticmethod
    def _changeset_from_tarball(
        archive_bytes: bytes,
        *,
        branch_file_count: int,
    ) -> tuple[list[ChangesetEntry], dict[str, bytes], int]:
        changeset_entries: list[ChangesetEntry] = []
        content_blobs: dict[str, bytes] = {}
        file_count = 0

        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            members = [member for member in archive.getmembers() if member.isfile()]
            if not members:
                return [], {}, branch_file_count

            root_prefix = members[0].name.split("/", 1)[0] + "/"
            for member in members:
                if not member.name.startswith(root_prefix):
                    continue
                relative_path = member.name[len(root_prefix) :]
                if not relative_path or relative_path.endswith("/"):
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                raw_bytes = extracted.read()
                file_count += 1
                content_ref = ContentRef.from_bytes(raw_bytes)
                content_type, _ = mimetypes.guess_type(relative_path)
                if content_type is None:
                    content_type = "application/octet-stream"
                changeset_entries.append(
                    ChangesetEntry(
                        operation=ChangeOperation.ADD,
                        id=content_ref.hex_digest,
                        type=_ENTRY_TYPE_FILE,
                        path=relative_path,
                        content_ref=content_ref,
                        content_type=content_type,
                        metadata={},
                    )
                )
                content_blobs[content_ref.hex_digest] = raw_bytes

        return changeset_entries, content_blobs, branch_file_count or file_count

    @staticmethod
    def _unauthenticated_headers(headers: dict[str, str]) -> dict[str, str]:
        return {
            key: value
            for key, value in headers.items()
            if key.lower() != "authorization"
        }

    async def _get_with_auth_fallback(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict[str, str],
    ) -> httpx.Response:
        response = await client.get(url, headers=headers)
        if response.status_code == 403 and headers.get("Authorization"):
            response = await client.get(
                url,
                headers=self._unauthenticated_headers(headers),
            )
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                self._github_error_detail(response),
                request=response.request,
                response=response,
            )
        return response

    async def _get_json_with_auth_fallback(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        response = await self._get_with_auth_fallback(client, url, headers=headers)
        return response.json()

    async def _get_bytes_with_auth_fallback(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        headers: dict[str, str],
    ) -> bytes:
        response = await self._get_with_auth_fallback(client, url, headers=headers)
        return response.content

    @staticmethod
    def _github_error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return response.text.strip() or f"HTTP {response.status_code}"
        message = str(payload.get("message") or "").strip()
        documentation = str(payload.get("documentation_url") or "").strip()
        if message and documentation:
            return f"{message} ({documentation})"
        return message or f"HTTP {response.status_code}"

    async def _fetch_file_contents(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        owner: str,
        repo: str,
        files: list[dict[str, Any]],
    ) -> tuple[list[ChangesetEntry], dict[str, bytes]]:
        """Fetch raw content for each file and build changeset entries.

        Fetches the blob for each file in ``files`` and returns a pair of
        (changeset_entries, content_blobs) suitable for ExtractionResult.

        Content is deduplicated by SHA-256 digest; if two files have identical
        content, only one blob is stored.

        Args:
            client: httpx async client.
            headers: GitHub API request headers.
            owner: Repository owner.
            repo: Repository name.
            files: List of file dicts (from _get_all_tree_blobs or
                _get_changed_files).

        Returns:
            Tuple of (list of ChangesetEntry, content_blobs dict).
        """
        semaphore = asyncio.Semaphore(self._blob_fetch_max_concurrency)
        loaded: dict[int, tuple[ChangesetEntry, bytes]] = {}

        async def _load_file(index: int, file_info: dict[str, Any]) -> None:
            path: str = file_info["path"]
            blob_sha: str = file_info["sha"]
            operation: ChangeOperation = file_info["operation"]
            previous_path: str | None = file_info.get("previous_path")

            async with semaphore:
                raw_bytes = await self._fetch_blob(
                    client, headers, owner, repo, blob_sha
                )

            content_ref = ContentRef.from_bytes(raw_bytes)
            content_type, _ = mimetypes.guess_type(path)
            if content_type is None:
                content_type = "application/octet-stream"

            metadata: dict[str, Any] = {}
            if previous_path:
                metadata["previous_path"] = previous_path

            loaded[index] = (
                ChangesetEntry(
                    operation=operation,
                    id=blob_sha,
                    type=_ENTRY_TYPE_FILE,
                    path=path,
                    content_ref=content_ref,
                    content_type=content_type,
                    metadata=metadata,
                ),
                raw_bytes,
            )

        await asyncio.gather(
            *(_load_file(index, file_info) for index, file_info in enumerate(files))
        )

        changeset_entries: list[ChangesetEntry] = []
        content_blobs: dict[str, bytes] = {}
        for index in range(len(files)):
            entry, raw_bytes = loaded[index]
            changeset_entries.append(entry)
            content_blobs[entry.content_ref.hex_digest] = raw_bytes

        return changeset_entries, content_blobs

    async def _fetch_blob(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        owner: str,
        repo: str,
        blob_sha: str,
    ) -> bytes:
        """Fetch and decode a single blob from the GitHub Blobs API.

        GitHub returns blob content as base64-encoded strings. This method
        fetches the blob and decodes it to raw bytes.

        Args:
            client: httpx async client.
            headers: GitHub API request headers.
            owner: Repository owner.
            repo: Repository name.
            blob_sha: The blob SHA to fetch.

        Returns:
            Raw bytes of the file content.

        Raises:
            httpx.HTTPStatusError: If the GitHub API returns a non-2xx status.
            ValueError: If the blob encoding is not ``base64``.
        """
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/git/blobs/{blob_sha}"
        blob_data = await self._get_json_with_auth_fallback(
            client, url, headers=headers
        )

        encoding: str = blob_data.get("encoding", "base64")
        if encoding != "base64":
            raise ValueError(
                f"Unsupported blob encoding {encoding!r} for blob {blob_sha!r}. "
                "Only 'base64' is supported."
            )

        # GitHub may include newlines in the base64 content; strip before decoding
        raw_b64: str = blob_data["content"].replace("\n", "")
        return base64.b64decode(raw_b64)
