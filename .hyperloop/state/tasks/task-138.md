---
id: task-138
title: "Unit tests for git repository infrastructure — Documentation Fetch Tool"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add unit tests for git repository infrastructure (GitHub, GitLab, self-hosted)"
pr_description: |
  ## What and Why

  The `fetch_documentation_source` MCP tool is backed by `query/infrastructure/git_repository.py`,
  which contains three production classes and one utility function:

  - `_strip_asciidoc_metadata()` — strips AsciiDoc header/comment lines before the first `= Title`
  - `GithubRepository` — parses GitHub blob URLs, builds GitHub Contents API URLs (including GitHub Enterprise)
  - `GitLabRepository` — parses GitLab blob URLs, builds GitLab Repository Files API URLs (including self-hosted)
  - `GitRepositoryFactory` — detects provider from URL structure and returns the correct repository instance

  **These classes have zero unit tests.** The only test coverage comes from `test_mcp_tools.py`,
  which tests the MCP tool wrapper (header forwarding, error response shape) by mocking
  `get_git_repository()`. This leaves the URL parsing, API URL construction, AsciiDoc
  stripping, and provider detection logic completely unverified.

  The four affected spec scenarios (all from `specs/query/mcp-server.spec.md`) are:

  - **Fetch from GitHub** — GitHub blob URL parsed, raw content fetched via GitHub API
  - **Fetch from GitLab** — GitLab blob URL parsed, raw content fetched via GitLab API
  - **Self-hosted instance** — GitHub Enterprise (`/api/v3/`) and self-hosted GitLab derived from hostname
  - **Invalid URL format** — URL not matching GitHub/GitLab patterns raises `InvalidRemoteFileURL`

  Without these tests, a bug in URL parsing, API URL construction, or provider detection
  would go undetected until an integration test or a real user hit it.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:

  - **Requirement: Documentation Fetch Tool — Scenario: Fetch from GitHub**
    "THEN the file content is fetched via the GitHub API AND AsciiDoc metadata and comments are stripped"

  - **Requirement: Documentation Fetch Tool — Scenario: Fetch from GitLab**
    "THEN the file content is fetched via the GitLab API"

  - **Requirement: Documentation Fetch Tool — Scenario: Self-hosted instance**
    "THEN the correct API endpoint is derived from the hostname"

  - **Requirement: Documentation Fetch Tool — Scenario: Invalid URL format**
    "GIVEN a URL that does not match GitHub or GitLab blob patterns
     WHEN the tool is called
     THEN an error response is returned"

  The tool-wrapper-level scenarios (Private repository with token, header forwarding) are
  already covered by `test_mcp_tools.py` and are NOT duplicated here.

  ## Key Design Decisions

  This task creates a new test file `src/api/tests/unit/query/test_git_repository.py`
  following the same TDD approach as the other query unit tests.

  The tests exercise the **pure parsing and URL-building logic** without making real HTTP
  calls (no `httpx` mocking needed for the URL-construction tests). HTTP behaviour is tested
  only via the `AbstractGitRemoteFileRepository.get_file()` template method, which does
  require `httpx` mocking.

  ## What Files Are Affected

  - **New**: `src/api/tests/unit/query/test_git_repository.py`
  - **Read-only**: `src/api/query/infrastructure/git_repository.py` (inspect only)

  No production code changes are expected. If a test reveals a bug in the existing
  implementation, fix the production code rather than the test.

  ## Test Coverage Plan

  ### `_strip_asciidoc_metadata`

  - Given content starting with `= Title`, returns content from that line onwards
  - Given content with attribute lines and comments before `= Title`, strips them all
  - Given content with no document title (no `= ` line), returns original content unchanged
  - Does NOT treat `== Section` as a document title
  - Non-AsciiDoc content passes through unchanged (no `= Title` line found)

  ### `GithubRepository._parse_url`

  - Parses public GitHub blob URL: `https://github.com/owner/repo/blob/main/path/file.adoc`
    → `ParsedGitUrl(hostname="github.com", owner="owner", repo="repo", ref="main", path="path/file.adoc")`
  - Parses GitHub Enterprise blob URL: `https://github.example.com/owner/repo/blob/sha/file.txt`
    → hostname is `github.example.com`, NOT `github.com`
  - Normalises hostname to lowercase
  - Raises `ValueError` for non-blob URLs (e.g., missing `/blob/`)
  - Strips query strings and fragments before pattern matching

  ### `GithubRepository._build_api_url`

  - Public GitHub (`github.com`) → `https://api.github.com/repos/owner/repo/contents/path?ref=main`
  - GitHub Enterprise (`github.example.com`) → `https://github.example.com/api/v3/repos/owner/repo/contents/path?ref=main`
  - Ref is URL-encoded (handles `+`, `#`, `&` in branch names)

  ### `GitLabRepository._parse_url`

  - Parses public GitLab blob URL: `https://gitlab.com/owner/repo/-/blob/main/path/file.adoc`
    → `ParsedGitUrl(hostname="gitlab.com", owner="owner", repo="repo", ref="main", path="path/file.adoc")`
  - Parses self-hosted GitLab URL: `https://gitlab.company.com/org/repo/-/blob/sha/file.md`
    → hostname is `gitlab.company.com`
  - Normalises hostname to lowercase
  - Raises `ValueError` for non-`/-/blob/` URLs

  ### `GitLabRepository._build_api_url`

  - Builds `/api/v4/projects/{encoded_project}/repository/files/{encoded_path}/raw?ref={encoded_ref}`
  - `owner/repo` project path is URL-encoded (handles slashes)
  - File path is URL-encoded
  - Ref is URL-encoded
  - Self-hosted: uses `parsed.hostname` instead of `gitlab.com`

  ### `GitRepositoryFactory.create_from_url`

  - URL containing `/-/blob/` → returns `GitLabRepository` (with `gitlab_token`)
  - URL containing `/blob/` (without `/-/`) → returns `GithubRepository` (with `github_token`)
  - URL with neither pattern → raises `InvalidRemoteFileURL`
  - URL with no hostname → raises `InvalidRemoteFileURL`
  - GitHub token is NOT forwarded to GitLab instance (and vice versa)

  ### `AbstractGitRemoteFileRepository.get_file` (via a concrete subclass)

  - Successful HTTP 200 → returns `RemoteFileRepositoryResponse(success=True, content=...)`
  - HTTP non-200 → raises `RemoteFileFetchFailed`
  - Network error → raises `RemoteFileFetchFailed`
  - Invalid URL → raises `InvalidRemoteFileURL` (from `_parse_url`)
  - AsciiDoc stripping is applied to response content

  ## How to Verify

  ```bash
  cd src/api && uv run pytest tests/unit/query/test_git_repository.py -v
  ```

  All tests must pass. No integration infrastructure required (pure unit tests with mocks).

  ## Implementation Notes

  - Follow TDD: write failing tests first, then verify existing code passes them.
    (If a test fails, it reveals a real gap — fix the production code.)
  - Use `unittest.mock.patch` or `httpx_mock` for HTTP calls in `get_file` tests.
  - Do not import from `query.presentation.mcp` — test the infrastructure layer directly.
  - Use `pytest.raises(ValueError)` for URL parse errors (raised by `_parse_url`),
    and `pytest.raises(InvalidRemoteFileURL)` for factory-level rejections.
  - `ParsedGitUrl` is a `dataclass(frozen=True, slots=True)` — compare fields directly.

  ## Caveats

  - Branch names containing forward slashes (e.g., `feature/my-branch`) are NOT supported
    by the current regex — the tests should document this known limitation, not try to fix it.
  - The `get_file` integration path (HTTP mocking) is lower priority than the pure URL parsing
    and URL construction tests; focus on those first.
---
