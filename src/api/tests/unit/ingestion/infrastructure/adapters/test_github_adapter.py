"""Unit tests for GitHubAdapter.

Tests cover the extraction scenarios from the spec:
- Full refresh: fetches all files from the repository tree (no checkpoint).
- Incremental sync: fetches only files changed since the checkpoint SHA.
- Credential handling: uses the token from decrypted credentials.
- Checkpoint update: returns a new checkpoint containing the current commit SHA.
- Content fetching: fetches raw file content via the GitHub Blobs API.

Uses httpx.MockTransport to simulate GitHub API responses without real
network calls. Mocking HTTP clients is explicitly allowed per the testing
guidelines ("Mocking is acceptable ONLY for: HTTP clients, gRPC channels,
filesystem I/O").

Spec scenarios covered:
- Repository tree extraction
- Content fetching
- Incremental sync via checkpoint
- Full refresh
- Credential handling
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from ingestion.infrastructure.adapters.github import GitHubAdapter
from ingestion.ports.adapters import IDatasourceAdapter
from shared_kernel.job_package.value_objects import (
    AdapterCheckpoint,
    ChangeOperation,
    SyncMode,
)

# ---------------------------------------------------------------------------
# Fake GitHub API response builders
# ---------------------------------------------------------------------------

BASE_SHA = "deadbeef1234567890abcdef1234567890abcdef"
HEAD_SHA = "cafebabe1234567890abcdef1234567890abcdef"
BLOB_SHA_README = "aaa111aaa111aaa111aaa111aaa111aaa111aaa1"
BLOB_SHA_MAIN = "bbb222bbb222bbb222bbb222bbb222bbb222bbb2"
BLOB_SHA_UTILS = "ccc333ccc333ccc333ccc333ccc333ccc333ccc3"

README_CONTENT = b"# My Repository\n\nThis is the README."
MAIN_PY_CONTENT = b"def main():\n    print('hello')\n"
UTILS_PY_CONTENT = b"def helper():\n    return 42\n"


def _branch_response(sha: str = HEAD_SHA) -> dict:
    return {"commit": {"sha": sha}}


def _tree_response(
    files: list[dict] | None = None,
) -> dict:
    """Simulate GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1."""
    if files is None:
        files = [
            {
                "path": "README.md",
                "type": "blob",
                "sha": BLOB_SHA_README,
                "size": len(README_CONTENT),
                "mode": "100644",
            },
            {
                "path": "src/main.py",
                "type": "blob",
                "sha": BLOB_SHA_MAIN,
                "size": len(MAIN_PY_CONTENT),
                "mode": "100644",
            },
        ]
    return {"sha": HEAD_SHA, "tree": files, "truncated": False}


def _compare_response(
    changed_files: list[dict] | None = None,
) -> dict:
    """Simulate GET /repos/{owner}/{repo}/compare/{base}...{head}."""
    if changed_files is None:
        changed_files = [
            {
                "filename": "src/utils.py",
                "sha": BLOB_SHA_UTILS,
                "status": "added",
                "previous_filename": None,
            }
        ]
    return {"files": changed_files}


def _blob_response(content: bytes) -> dict:
    """Simulate GET /repos/{owner}/{repo}/git/blobs/{sha}."""
    encoded = base64.b64encode(content).decode("ascii")
    return {
        "content": encoded + "\n",
        "encoding": "base64",
        "sha": "ignored",
        "size": len(content),
    }


# ---------------------------------------------------------------------------
# Fake transport
# ---------------------------------------------------------------------------


class FakeGitHubTransport(httpx.AsyncBaseTransport):
    """Fake async httpx transport that simulates GitHub REST API responses.

    Routes requests to pre-configured response handlers based on URL patterns.
    Inherits from httpx.AsyncBaseTransport (the correct base for async clients).
    """

    def __init__(self, responses: dict[str, dict]) -> None:
        """
        Args:
            responses: Mapping of URL path suffix → JSON response dict.
                       Paths are matched as suffixes of the request URL.
        """
        self._responses = responses

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        for path_suffix, response_data in self._responses.items():
            if url_path.endswith(path_suffix) or path_suffix in url_path:
                return httpx.Response(
                    status_code=200,
                    content=json.dumps(response_data).encode(),
                    headers={"content-type": "application/json"},
                )
        raise RuntimeError(
            f"FakeGitHubTransport: no response configured for {url_path}.\n"
            f"Configured paths: {list(self._responses.keys())}"
        )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def connection_config() -> dict[str, str]:
    return {"owner": "myorg", "repo": "myrepo", "branch": "main"}


@pytest.fixture
def credentials() -> dict[str, str]:
    return {"token": "ghp_test_token_abc123"}


@pytest.fixture
def full_refresh_transport() -> FakeGitHubTransport:
    """Transport configured for a full refresh extraction."""
    return FakeGitHubTransport(
        {
            # Branch tip
            "/branches/main": _branch_response(HEAD_SHA),
            # Full tree
            f"/git/trees/{HEAD_SHA}": _tree_response(),
            # Blobs
            f"/git/blobs/{BLOB_SHA_README}": _blob_response(README_CONTENT),
            f"/git/blobs/{BLOB_SHA_MAIN}": _blob_response(MAIN_PY_CONTENT),
        }
    )


@pytest.fixture
def incremental_transport() -> FakeGitHubTransport:
    """Transport configured for an incremental extraction (one new file)."""
    return FakeGitHubTransport(
        {
            # Branch tip
            "/branches/main": _branch_response(HEAD_SHA),
            # Compare endpoint
            f"/compare/{BASE_SHA}...{HEAD_SHA}": _compare_response(
                [
                    {
                        "filename": "src/utils.py",
                        "sha": BLOB_SHA_UTILS,
                        "status": "added",
                        "previous_filename": None,
                    }
                ]
            ),
            # Blob for the new file
            f"/git/blobs/{BLOB_SHA_UTILS}": _blob_response(UTILS_PY_CONTENT),
        }
    )


# ---------------------------------------------------------------------------
# Spec scenario: Full refresh
# ---------------------------------------------------------------------------


class TestFullRefresh:
    """Scenario: Full refresh — no checkpoint, extract all content.

    - GIVEN no previous checkpoint state (or a full_refresh sync mode)
    - WHEN the adapter runs
    - THEN it extracts all content from the repository
    """

    @pytest.mark.asyncio
    async def test_full_refresh_with_no_checkpoint_returns_all_files(
        self, connection_config, credentials, full_refresh_transport
    ):
        """With no checkpoint, all tree blobs are returned as ADD entries."""
        client = httpx.AsyncClient(transport=full_refresh_transport)
        adapter = GitHubAdapter(http_client=client)

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        paths = {e.path for e in result.changeset_entries}
        assert "README.md" in paths
        assert "src/main.py" in paths
        assert len(result.changeset_entries) == 2

    @pytest.mark.asyncio
    async def test_full_refresh_entries_are_add_operations(
        self, connection_config, credentials, full_refresh_transport
    ):
        """All entries in a full refresh have ChangeOperation.ADD."""
        client = httpx.AsyncClient(transport=full_refresh_transport)
        adapter = GitHubAdapter(http_client=client)

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        for entry in result.changeset_entries:
            assert entry.operation == ChangeOperation.ADD

    @pytest.mark.asyncio
    async def test_full_refresh_fetches_content_for_each_file(
        self, connection_config, credentials, full_refresh_transport
    ):
        """Content blobs are fetched for every file in the tree."""
        client = httpx.AsyncClient(transport=full_refresh_transport)
        adapter = GitHubAdapter(http_client=client)

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        # Each entry's content_ref must resolve to a blob in content_blobs
        for entry in result.changeset_entries:
            assert entry.content_ref.hex_digest in result.content_blobs

        # The actual bytes must match the expected content
        readme_hex = next(
            e.content_ref.hex_digest
            for e in result.changeset_entries
            if e.path == "README.md"
        )
        assert result.content_blobs[readme_hex] == README_CONTENT

    @pytest.mark.asyncio
    async def test_full_refresh_skips_tree_entries_that_are_not_blobs(
        self, connection_config, credentials
    ):
        """Directory (tree-type) entries in the tree are skipped."""
        transport = FakeGitHubTransport(
            {
                "/branches/main": _branch_response(HEAD_SHA),
                f"/git/trees/{HEAD_SHA}": _tree_response(
                    [
                        {
                            "path": "src",
                            "type": "tree",  # directory — must be skipped
                            "sha": "dir-sha",
                            "size": 0,
                            "mode": "040000",
                        },
                        {
                            "path": "src/main.py",
                            "type": "blob",
                            "sha": BLOB_SHA_MAIN,
                            "size": len(MAIN_PY_CONTENT),
                            "mode": "100644",
                        },
                    ]
                ),
                f"/git/blobs/{BLOB_SHA_MAIN}": _blob_response(MAIN_PY_CONTENT),
            }
        )
        client = httpx.AsyncClient(transport=transport)
        adapter = GitHubAdapter(http_client=client)

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        assert len(result.changeset_entries) == 1
        assert result.changeset_entries[0].path == "src/main.py"

    @pytest.mark.asyncio
    async def test_full_refresh_with_full_refresh_mode_and_existing_checkpoint(
        self, connection_config, credentials, full_refresh_transport
    ):
        """SyncMode.FULL_REFRESH overrides checkpoint — extracts everything."""
        client = httpx.AsyncClient(transport=full_refresh_transport)
        adapter = GitHubAdapter(http_client=client)

        existing_checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=existing_checkpoint,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        # Full refresh ignores checkpoint, fetches all files
        assert len(result.changeset_entries) == 2


# ---------------------------------------------------------------------------
# Spec scenario: Incremental sync via checkpoint
# ---------------------------------------------------------------------------


class TestIncrementalSync:
    """Scenario: Incremental sync via checkpoint.

    - GIVEN a previous checkpoint state (e.g., a commit SHA)
    - WHEN the adapter runs
    - THEN it extracts only changes since the checkpoint
    - AND updates the checkpoint with the current position
    """

    @pytest.mark.asyncio
    async def test_incremental_returns_only_changed_files(
        self, connection_config, credentials, incremental_transport
    ):
        """Only files changed since the checkpoint are returned."""
        client = httpx.AsyncClient(transport=incremental_transport)
        adapter = GitHubAdapter(http_client=client)

        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        assert len(result.changeset_entries) == 1
        assert result.changeset_entries[0].path == "src/utils.py"

    @pytest.mark.asyncio
    async def test_incremental_maps_added_status_to_add_operation(
        self, connection_config, credentials, incremental_transport
    ):
        """GitHub 'added' status maps to ChangeOperation.ADD."""
        client = httpx.AsyncClient(transport=incremental_transport)
        adapter = GitHubAdapter(http_client=client)

        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        entry = result.changeset_entries[0]
        assert entry.operation == ChangeOperation.ADD

    @pytest.mark.asyncio
    async def test_incremental_maps_modified_status_to_modify_operation(
        self, connection_config, credentials
    ):
        """GitHub 'modified' status maps to ChangeOperation.MODIFY."""
        transport = FakeGitHubTransport(
            {
                "/branches/main": _branch_response(HEAD_SHA),
                f"/compare/{BASE_SHA}...{HEAD_SHA}": _compare_response(
                    [
                        {
                            "filename": "README.md",
                            "sha": BLOB_SHA_README,
                            "status": "modified",
                            "previous_filename": None,
                        }
                    ]
                ),
                f"/git/blobs/{BLOB_SHA_README}": _blob_response(README_CONTENT),
            }
        )
        client = httpx.AsyncClient(transport=transport)
        adapter = GitHubAdapter(http_client=client)

        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        assert result.changeset_entries[0].operation == ChangeOperation.MODIFY

    @pytest.mark.asyncio
    async def test_incremental_maps_renamed_status_to_modify_operation(
        self, connection_config, credentials
    ):
        """GitHub 'renamed' status maps to ChangeOperation.MODIFY with previous_path metadata."""
        transport = FakeGitHubTransport(
            {
                "/branches/main": _branch_response(HEAD_SHA),
                f"/compare/{BASE_SHA}...{HEAD_SHA}": _compare_response(
                    [
                        {
                            "filename": "src/new_name.py",
                            "sha": BLOB_SHA_MAIN,
                            "status": "renamed",
                            "previous_filename": "src/old_name.py",
                        }
                    ]
                ),
                f"/git/blobs/{BLOB_SHA_MAIN}": _blob_response(MAIN_PY_CONTENT),
            }
        )
        client = httpx.AsyncClient(transport=transport)
        adapter = GitHubAdapter(http_client=client)

        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        entry = result.changeset_entries[0]
        assert entry.operation == ChangeOperation.MODIFY
        assert entry.path == "src/new_name.py"
        assert entry.metadata.get("previous_path") == "src/old_name.py"

    @pytest.mark.asyncio
    async def test_incremental_ignores_removed_files(
        self, connection_config, credentials
    ):
        """Removed files are excluded from the result (no DELETE operation in spec)."""
        transport = FakeGitHubTransport(
            {
                "/branches/main": _branch_response(HEAD_SHA),
                f"/compare/{BASE_SHA}...{HEAD_SHA}": _compare_response(
                    [
                        {
                            "filename": "deleted_file.py",
                            "sha": "remove-sha",
                            "status": "removed",
                            "previous_filename": None,
                        }
                    ]
                ),
            }
        )
        client = httpx.AsyncClient(transport=transport)
        adapter = GitHubAdapter(http_client=client)

        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        assert result.changeset_entries == []

    @pytest.mark.asyncio
    async def test_incremental_no_changes_returns_empty_result(
        self, connection_config, credentials
    ):
        """When there are no changes since the checkpoint, result is empty."""
        transport = FakeGitHubTransport(
            {
                "/branches/main": _branch_response(HEAD_SHA),
                f"/compare/{BASE_SHA}...{HEAD_SHA}": _compare_response([]),
            }
        )
        client = httpx.AsyncClient(transport=transport)
        adapter = GitHubAdapter(http_client=client)

        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        assert result.changeset_entries == []
        assert result.content_blobs == {}

    @pytest.mark.asyncio
    async def test_checkpoint_updated_with_current_head_sha(
        self, connection_config, credentials, incremental_transport
    ):
        """The returned checkpoint contains the current HEAD commit SHA."""
        client = httpx.AsyncClient(transport=incremental_transport)
        adapter = GitHubAdapter(http_client=client)

        old_checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=old_checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        assert result.new_checkpoint.data["commit_sha"] == HEAD_SHA
        assert result.new_checkpoint.schema_version == "1.0.0"

    @pytest.mark.asyncio
    async def test_full_refresh_checkpoint_updated_with_head_sha(
        self, connection_config, credentials, full_refresh_transport
    ):
        """Full refresh also updates the checkpoint with current HEAD SHA."""
        client = httpx.AsyncClient(transport=full_refresh_transport)
        adapter = GitHubAdapter(http_client=client)

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        assert result.new_checkpoint.data["commit_sha"] == HEAD_SHA


# ---------------------------------------------------------------------------
# Spec scenario: Credential handling
# ---------------------------------------------------------------------------


class TestCredentialHandling:
    """Scenario: Credential handling.

    - GIVEN encrypted credentials stored by the Management context
    - WHEN the adapter runs
    - THEN the adapter receives decrypted credentials at runtime
    - AND the adapter uses them for data source API authentication
    """

    @pytest.mark.asyncio
    async def test_authorization_header_sent_with_token(
        self, connection_config, credentials
    ):
        """The token from credentials is sent as a Bearer token in the Authorization header."""
        # Delegate transport that records auth headers before forwarding
        inner_transport = FakeGitHubTransport(
            {
                "/branches/main": _branch_response(HEAD_SHA),
                f"/git/trees/{HEAD_SHA}": _tree_response([]),
            }
        )
        calls: list[str] = []

        class HeaderCapturingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(
                self, request: httpx.Request
            ) -> httpx.Response:
                calls.append(request.headers.get("authorization", ""))
                return await inner_transport.handle_async_request(request)

        client = httpx.AsyncClient(transport=HeaderCapturingTransport())
        adapter = GitHubAdapter(http_client=client)

        await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        # All requests must include Bearer token
        assert calls, "No requests were captured"
        assert all("Bearer ghp_test_token_abc123" in h for h in calls), (
            f"Expected Bearer token in all requests, got: {calls}"
        )

    @pytest.mark.asyncio
    async def test_adapter_uses_token_from_credentials(self, connection_config):
        """Different tokens are used for different credentials (not hardcoded)."""
        seen_tokens: list[str] = []

        class TokenCapture(httpx.AsyncBaseTransport):
            async def handle_async_request(
                self, request: httpx.Request
            ) -> httpx.Response:
                seen_tokens.append(request.headers.get("authorization", ""))
                url_path = request.url.path
                if url_path.endswith("/branches/main"):
                    data: dict = _branch_response(HEAD_SHA)
                elif "git/trees" in url_path:
                    data = _tree_response([])
                else:
                    raise RuntimeError(f"Unexpected: {url_path}")
                return httpx.Response(
                    200,
                    content=json.dumps(data).encode(),
                    headers={"content-type": "application/json"},
                )

        creds_a = {"token": "token-AAA"}

        adapter = GitHubAdapter(http_client=httpx.AsyncClient(transport=TokenCapture()))

        seen_tokens.clear()
        await adapter.extract(
            connection_config=connection_config,
            credentials=creds_a,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )
        assert any("token-AAA" in t for t in seen_tokens)


# ---------------------------------------------------------------------------
# Spec scenario: IDatasourceAdapter protocol compliance
# ---------------------------------------------------------------------------


class TestGitHubAdapterProtocolCompliance:
    """GitHubAdapter implements the IDatasourceAdapter port.

    Spec scenario: Extract contract
    - GIVEN an adapter for a specific data source type (GitHub)
    - THEN it implements the IDatasourceAdapter port
    """

    def test_github_adapter_satisfies_idatasource_adapter_protocol(self):
        """GitHubAdapter is structurally compatible with IDatasourceAdapter."""
        adapter = GitHubAdapter()
        assert isinstance(adapter, IDatasourceAdapter)

    def test_github_adapter_extract_returns_extraction_result(self):
        """extract() returns an ExtractionResult instance (type annotation check)."""
        import inspect

        sig = inspect.signature(GitHubAdapter.extract)
        # The return annotation should reference ExtractionResult
        return_annotation = str(sig.return_annotation)
        assert "ExtractionResult" in return_annotation


# ---------------------------------------------------------------------------
# Spec scenario: Content fetching (only changed files)
# ---------------------------------------------------------------------------


class TestContentFetching:
    """Scenario: Content fetching.

    - GIVEN files identified as changed
    - WHEN content is fetched
    - THEN the adapter retrieves raw file content via the GitHub API
    - AND only changed files are fetched (not the entire repository)
    """

    @pytest.mark.asyncio
    async def test_incremental_only_fetches_content_for_changed_files(
        self, connection_config, credentials
    ):
        """Incremental sync fetches content only for files returned by compare."""
        fetched_blobs: list[str] = []

        class BlobTrackingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(
                self, request: httpx.Request
            ) -> httpx.Response:
                url_path = request.url.path
                if url_path.endswith("/branches/main"):
                    data: dict = _branch_response(HEAD_SHA)
                elif f"/compare/{BASE_SHA}...{HEAD_SHA}" in url_path:
                    data = _compare_response(
                        [
                            {
                                "filename": "src/utils.py",
                                "sha": BLOB_SHA_UTILS,
                                "status": "added",
                                "previous_filename": None,
                            }
                        ]
                    )
                elif "git/blobs" in url_path:
                    blob_sha = url_path.split("/")[-1]
                    fetched_blobs.append(blob_sha)
                    data = _blob_response(UTILS_PY_CONTENT)
                else:
                    raise RuntimeError(f"Unexpected URL: {url_path}")
                return httpx.Response(
                    200,
                    content=json.dumps(data).encode(),
                    headers={"content-type": "application/json"},
                )

        client = httpx.AsyncClient(transport=BlobTrackingTransport())
        adapter = GitHubAdapter(http_client=client)

        checkpoint = AdapterCheckpoint(
            schema_version="1.0.0", data={"commit_sha": BASE_SHA}
        )

        await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=checkpoint,
            sync_mode=SyncMode.INCREMENTAL,
        )

        # Only the changed file's blob should have been fetched
        assert fetched_blobs == [BLOB_SHA_UTILS], (
            f"Expected only {BLOB_SHA_UTILS} to be fetched, got: {fetched_blobs}"
        )

    @pytest.mark.asyncio
    async def test_content_blobs_keyed_by_sha256_hex_digest(
        self, connection_config, credentials, full_refresh_transport
    ):
        """Content blobs are keyed by SHA-256 hex digest, not GitHub blob SHA."""
        import hashlib

        client = httpx.AsyncClient(transport=full_refresh_transport)
        adapter = GitHubAdapter(http_client=client)

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        for entry in result.changeset_entries:
            digest = entry.content_ref.hex_digest
            assert digest in result.content_blobs
            expected_digest = hashlib.sha256(result.content_blobs[digest]).hexdigest()
            assert digest == expected_digest, (
                f"Content blob key {digest!r} does not match SHA-256 of content"
            )

    @pytest.mark.asyncio
    async def test_changeset_entry_type_is_file(
        self, connection_config, credentials, full_refresh_transport
    ):
        """Each changeset entry has the file type identifier."""
        client = httpx.AsyncClient(transport=full_refresh_transport)
        adapter = GitHubAdapter(http_client=client)

        result = await adapter.extract(
            connection_config=connection_config,
            credentials=credentials,
            checkpoint=None,
            sync_mode=SyncMode.FULL_REFRESH,
        )

        for entry in result.changeset_entries:
            assert entry.type == "io.kartograph.change.file"
