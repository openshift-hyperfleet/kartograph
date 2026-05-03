---
id: task-111
title: "fetch_documentation_source: return error response for invalid URL instead of propagating exception"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "fix(query): return RemoteFileRepositoryResponse(success=False) for invalid URL in fetch_documentation_source"
pr_description: |
  ## What & Why

  The `fetch_documentation_source` MCP tool has the following return type contract:

  ```python
  def fetch_documentation_source(url: str) -> RemoteFileRepositoryResponse:
  ```

  `RemoteFileRepositoryResponse` has a `success=False` / `error=...` path for
  signalling failures to callers. However, when the URL does not match any
  supported git provider (GitHub blob URL or GitLab `/-/blob/` URL), the current
  implementation propagates a `ValueError` raised by `get_git_repository` /
  `GitRepositoryFactory.create_from_url`. FastMCP catches unhandled exceptions and
  converts them to MCP JSON-RPC errors — a different shape from the tool's
  declared return type.

  ### Spec Requirement

  `specs/query/mcp-server.spec.md` — **Requirement: Documentation Fetch Tool**:

  > **Scenario: Invalid URL format**
  > GIVEN a URL that does not match GitHub or GitLab blob patterns
  > WHEN the tool is called
  > THEN an error response is returned

  "An error response" in this context means `RemoteFileRepositoryResponse(success=False,
  error="...")` — consistent with the tool's own return type and with how HTTP failures
  are already handled (the repository raises `RemoteFileFetchFailed` which is also not
  caught at the tool layer). The spec says *an* error response, not a JSON-RPC fault.
  Returning a typed `RemoteFileRepositoryResponse(success=False)` is the correct
  interpretation because:
  - The tool's return type is `RemoteFileRepositoryResponse` — callers expect this shape.
  - MCP clients that pattern-match on `response.success` would receive an unexpected
    JSON-RPC error object instead of a `RemoteFileRepositoryResponse`.
  - The repository layer already has `InvalidRemoteFileURL` as a typed exception for
    this exact case (`query/ports/exceptions.py`).

  ### Test Gap

  `tests/unit/query/infrastructure/test_git_repository.py` and
  `TestGitRepositoryFactory.test_rejects_invalid_url_format` cover the factory level.
  `tests/unit/query/test_mcp_tools.py` covers PAT header extraction but has no test
  that calls `fetch_documentation_source.fn(invalid_url)` and asserts a typed
  `RemoteFileRepositoryResponse(success=False)` is returned. This is the missing layer.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md`:
  - **Requirement: Documentation Fetch Tool** — Scenario: *Invalid URL format*

  ## What This Change Does

  ### 1. `src/api/query/presentation/mcp.py`

  Wrap the `get_git_repository` call (and optionally `repository.get_file`) in a
  `try/except` block that catches `InvalidRemoteFileURL` (and `RemoteFileFetchFailed`
  if not already caught by the repository's template method) and returns:

  ```python
  from query.ports.exceptions import InvalidRemoteFileURL, RemoteFileFetchFailed

  @mcp.tool
  def fetch_documentation_source(url: str) -> RemoteFileRepositoryResponse:
      headers = get_http_headers()
      github_token = headers.get("x-github-pat")
      gitlab_token = headers.get("x-gitlab-pat")

      try:
          repository = get_git_repository(
              url=url,
              github_token=github_token,
              gitlab_token=gitlab_token,
          )
          return repository.get_file(url=url)
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
  ```

  ### 2. `src/api/tests/unit/query/test_mcp_tools.py`

  Add a new test class `TestFetchDocumentationSourceErrorHandling` with tests that
  call `fetch_documentation_source.fn(url)` and assert typed error responses:

  **Write these tests BEFORE touching the implementation (TDD)**:

  1. **`test_invalid_url_returns_error_response`** — call `.fn("https://example.com/not-a-git-url")`;
     assert `result.success is False` and `result.error` is not None.

  2. **`test_invalid_url_does_not_raise`** — assert the tool does NOT raise an
     exception (it must return, not raise, for any URL pattern).

  3. **`test_github_url_missing_blob_segment_returns_error`** — URL like
     `"https://github.com/owner/repo"` (no `/blob/`) returns `success=False`.

  4. **`test_remote_fetch_failure_returns_error_response`** — mock
     `get_git_repository` to return a repository whose `.get_file()` raises
     `RemoteFileFetchFailed("HTTP 404")` and assert `result.success is False`
     and `result.error` contains "404".

  ## Files / Areas Affected

  - `src/api/query/presentation/mcp.py` — add try/except in `fetch_documentation_source`
  - `src/api/tests/unit/query/test_mcp_tools.py` — add `TestFetchDocumentationSourceErrorHandling`
  - No domain or port changes required; `InvalidRemoteFileURL` and `RemoteFileFetchFailed`
    already exist in `query/ports/exceptions.py`

  ## How to Verify

  1. TDD cycle: write failing tests in `test_mcp_tools.py` first
  2. Add try/except to `fetch_documentation_source` in `mcp.py`
  3. `cd src/api && uv run pytest tests/unit/query/test_mcp_tools.py -v -k "ErrorHandling"`
     — all 4 new tests pass
  4. `uv run pytest tests/unit/query/ -v` — no regressions in existing tests

  ## Caveats

  - `RemoteFileFetchFailed` is already caught inside the repository's `get_file`
    template method and re-raised; verify whether catching it at the tool layer is
    redundant or necessary (it should be necessary since the template method raises, not
    swallows).
  - The tool's docstring documents `RemoteFileRepositoryResponse` as the return type —
    add a note in the Args section that invalid URLs return `success=False`.
  - Do not suppress all exceptions: only `InvalidRemoteFileURL` and
    `RemoteFileFetchFailed` should be caught. Other unexpected errors should still
    propagate so FastMCP surfaces them as internal errors (not silent failures).
---
