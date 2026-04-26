"""GitHub repository adapter for the Ingestion bounded context.

Extracts file content from GitHub repositories via the GitHub REST API,
producing raw content and changeset entries for packaging into a JobPackage.

Supports:
- Full refresh: fetches all blobs from the repository tree.
- Incremental sync: uses the GitHub Compare API to find only files that
  changed since the previous checkpoint commit SHA.

API endpoints used:
- GET /repos/{owner}/{repo}/branches/{branch}  — resolve branch to commit SHA
- GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1  — full tree (blobs)
- GET /repos/{owner}/{repo}/compare/{base}...{head}  — changed files
- GET /repos/{owner}/{repo}/git/blobs/{sha}  — raw file content (base64)

dlt integration note: this adapter class provides the extraction contract
(IDatasourceAdapter). The Ingestion service (a future task) wraps this adapter
in a dlt pipeline configured with a PostgreSQL destination for state persistence
and a filesystem destination for JobPackager-readable output files. The adapter
itself uses httpx directly to keep it independently testable.
"""

from __future__ import annotations

import base64
import mimetypes
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

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client

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
            connection_config: Repository parameters. Expected keys:
                - ``owner``: GitHub organisation or user name.
                - ``repo``: Repository name.
                - ``branch``: Branch to extract (default: "main").
            credentials: Decrypted GitHub credentials. Expected keys:
                - ``token``: A GitHub personal access token (PAT) or App token.
            checkpoint: Previous checkpoint containing ``commit_sha``, or None.
            sync_mode: Controls whether to run a full refresh or incremental.

        Returns:
            ExtractionResult with changeset entries, content blobs, and the
            updated checkpoint (new HEAD commit SHA).
        """
        owner = connection_config["owner"]
        repo = connection_config["repo"]
        branch = connection_config.get("branch", "main")
        token = credentials["token"]

        use_full_refresh = (
            sync_mode == SyncMode.FULL_REFRESH
            or checkpoint is None
            or _COMMIT_SHA_KEY not in checkpoint.data
        )

        client = self._http_client or httpx.AsyncClient()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            # Step 1: Resolve branch to current HEAD commit SHA
            head_sha = await self._get_branch_head_sha(
                client, headers, owner, repo, branch
            )

            # Step 2: Determine which files to fetch
            if use_full_refresh:
                files_to_fetch = await self._get_all_tree_blobs(
                    client, headers, owner, repo, head_sha
                )
            else:
                assert checkpoint is not None  # narrowed above
                base_sha = checkpoint.data[_COMMIT_SHA_KEY]
                files_to_fetch = await self._get_changed_files(
                    client, headers, owner, repo, base_sha, head_sha
                )

            # Step 3: Fetch content for each file
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
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
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
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        tree_data: dict[str, Any] = response.json()

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
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        compare_data: dict[str, Any] = response.json()

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
        changeset_entries: list[ChangesetEntry] = []
        content_blobs: dict[str, bytes] = {}

        for file_info in files:
            path: str = file_info["path"]
            blob_sha: str = file_info["sha"]
            operation: ChangeOperation = file_info["operation"]
            previous_path: str | None = file_info.get("previous_path")

            # Fetch raw content from blob
            raw_bytes = await self._fetch_blob(client, headers, owner, repo, blob_sha)

            # Content-address the blob by its SHA-256 digest
            content_ref = ContentRef.from_bytes(raw_bytes)
            content_blobs[content_ref.hex_digest] = raw_bytes

            # Detect content MIME type; default to octet-stream for unknown
            content_type, _ = mimetypes.guess_type(path)
            if content_type is None:
                content_type = "application/octet-stream"

            # Build adapter-specific metadata
            metadata: dict[str, Any] = {}
            if previous_path:
                metadata["previous_path"] = previous_path

            entry = ChangesetEntry(
                operation=operation,
                id=blob_sha,
                type=_ENTRY_TYPE_FILE,
                path=path,
                content_ref=content_ref,
                content_type=content_type,
                metadata=metadata,
            )
            changeset_entries.append(entry)

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
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        blob_data: dict[str, Any] = response.json()

        encoding: str = blob_data.get("encoding", "base64")
        if encoding != "base64":
            raise ValueError(
                f"Unsupported blob encoding {encoding!r} for blob {blob_sha!r}. "
                "Only 'base64' is supported."
            )

        # GitHub may include newlines in the base64 content; strip before decoding
        raw_b64: str = blob_data["content"].replace("\n", "")
        return base64.b64decode(raw_b64)
