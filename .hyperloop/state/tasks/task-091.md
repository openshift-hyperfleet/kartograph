---
id: task-091
title: MCP server — Documentation Fetch Tool spec alignment
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(query): verify fetch_documentation_source MCP tool against spec"
pr_description: |
  ## What & Why

  The **Requirement: Documentation Fetch Tool** in `specs/query/mcp-server.spec.md`
  has never had a hyperloop task created for it. All five scenarios in this
  requirement are currently implemented in:

  - `src/api/query/infrastructure/git_repository.py` — `GithubRepository`,
    `GitLabRepository`, `GitRepositoryFactory`, `_strip_asciidoc_metadata`
  - `src/api/query/presentation/mcp.py` — `fetch_documentation_source` tool
  - `src/api/tests/unit/query/infrastructure/test_git_repository.py`
  - `src/api/tests/unit/query/test_mcp_tools.py` — `TestFetchDocumentationSourceHeaders`

  This task creates traceability between the spec requirement and the existing
  implementation, and confirms every scenario is covered line-by-line.

  ## Spec Scenarios

  ### Scenario: Fetch from GitHub
  > GIVEN a GitHub blob URL (e.g., `https://github.com/owner/repo/blob/main/file.adoc`)
  > WHEN the tool is called
  > THEN the file content is fetched via the GitHub API
  > AND AsciiDoc metadata and comments are stripped

  Implementation: `GithubRepository.get_file()` + `_strip_asciidoc_metadata()`.
  The GitHub Contents API is called with `Accept: application/vnd.github.v3.raw`.
  AsciiDoc metadata is stripped by `_strip_asciidoc_metadata()` before returning.

  Tests: `TestGetFile.test_fetches_file_successfully`,
  `TestAsciiDocStripping.test_strips_attribute_metadata_before_title`,
  `TestAsciiDocStripping.test_strips_single_line_comments_before_title`.

  ### Scenario: Fetch from GitLab
  > GIVEN a GitLab blob URL (e.g., `https://gitlab.com/owner/repo/-/blob/main/file.adoc`)
  > WHEN the tool is called
  > THEN the file content is fetched via the GitLab API

  Implementation: `GitLabRepository.get_file()` uses the GitLab Repository Files
  API (`/api/v4/projects/{project}/repository/files/{path}/raw?ref={ref}`).

  Tests: `TestGitLabRepository.test_fetches_gitlab_file_successfully`.

  ### Scenario: Private repository with token
  > GIVEN a private repository URL and an access token (via `x-github-pat` or
  >   `x-gitlab-pat` header)
  > WHEN the tool is called
  > THEN the token is used for authentication against the provider API

  Implementation: `fetch_documentation_source` reads `x-github-pat` and
  `x-gitlab-pat` from MCP HTTP request headers via `get_http_headers()` and
  passes them to `GitRepositoryFactory.create_from_url()`.

  Tests: `TestFetchDocumentationSourceHeaders` — four test cases covering
  GitHub token, GitLab token, both tokens simultaneously, and no tokens.

  ### Scenario: Self-hosted instance
  > GIVEN a URL pointing to a GitHub Enterprise or self-hosted GitLab instance
  > WHEN the tool is called
  > THEN the correct API endpoint is derived from the hostname

  Implementation:
  - `GithubRepository._build_api_url()`: `github.com` → `api.github.com`;
    any other hostname → `https://{hostname}/api/v3` (GitHub Enterprise).
  - `GitLabRepository._build_api_url()`: always uses `https://{hostname}/api/v4/`.
  - `GitRepositoryFactory.create_from_url()`: detects provider by URL pattern
    (`/-/blob/` = GitLab, `/blob/` = GitHub), selects the appropriate token.

  Tests: `TestBuildApiUrl.test_builds_enterprise_api_url`,
  `TestGitLabRepository.test_builds_api_url_for_self_hosted`,
  `TestGitRepositoryFactory.test_creates_gitlab_repository_for_self_hosted`,
  `TestGitRepositoryFactory.test_creates_github_repository_for_github_enterprise`.

  ### Scenario: Invalid URL format
  > GIVEN a URL that does not match GitHub or GitLab blob patterns
  > WHEN the tool is called
  > THEN an error response is returned

  Implementation: `GitRepositoryFactory.create_from_url()` raises `ValueError`
  for unsupported providers. `AbstractGitRemoteFileRepository.get_file()` catches
  `ValueError` from `_parse_url()` and raises `InvalidRemoteFileURL`, which
  propagates as an error response to the MCP client.

  Tests: `TestGitRepositoryFactory.test_raises_for_unsupported_provider`,
  `TestGitRepositoryFactory.test_rejects_invalid_url_format`,
  `TestGetFile.test_raises_on_invalid_url`.

  ## Files Affected

  No new implementation expected — this task verifies existing code:

  - `src/api/query/infrastructure/git_repository.py` — primary implementation
  - `src/api/query/presentation/mcp.py` — `fetch_documentation_source` tool
  - `src/api/query/ports/file_repository_models.py` — response model
  - `src/api/query/ports/exceptions.py` — `InvalidRemoteFileURL`, `RemoteFileFetchFailed`
  - `src/api/tests/unit/query/infrastructure/test_git_repository.py`
  - `src/api/tests/unit/query/test_mcp_tools.py`

  ## How to Verify

  1. Run unit tests: `cd src/api && uv run pytest tests/unit/query/infrastructure/test_git_repository.py tests/unit/query/test_mcp_tools.py -v`
  2. All tests should pass with no changes required.
  3. If any test is missing or fails, add the test (TDD: write test first, then
     fix/extend implementation to pass).

  ## Design Context

  - The `fetch_documentation_source` tool is named after the `DocumentationModule`
    domain concept — the `documentationmodule_view_uri` parameter accepts any
    GitHub or GitLab blob URL, not just documentation-specific ones.
  - The tool strips AsciiDoc metadata to clean up content for MCP agents, which
    don't need AsciiDoc attribute headers.
  - The `GitRepositoryFactory` detects the provider by URL pattern to avoid
    requiring the caller to specify the provider explicitly.

  ## Gap Analysis

  This task was created by a PM intake run that identified the Documentation
  Fetch Tool requirement in `mcp-server.spec.md` had no hyperloop task despite
  being fully implemented. All previous tasks for this spec (task-011, task-085,
  task-086, task-089) covered other requirements (KG filter, secure enclave,
  KG resource, result truncation). This task provides spec traceability.
---
