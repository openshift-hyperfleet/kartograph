---
id: task-090
title: Unit tests for fetch_documentation_source tool (git repository classes)
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add unit tests for fetch_documentation_source tool and git repository classes"
pr_description: |
  ## What & Why

  The MCP server spec defines five scenarios for the `fetch_documentation_source` tool:

  1. **Fetch from GitHub** — GitHub blob URL → GitHub Contents API, AsciiDoc stripped
  2. **Fetch from GitLab** — GitLab blob URL → GitLab Repository Files API
  3. **Private repository with token** — `x-github-pat` / `x-gitlab-pat` header passed
  4. **Self-hosted instance** — GitHub Enterprise and self-hosted GitLab hostnames resolved
  5. **Invalid URL format** — non-GitHub/GitLab URL returns an error response

  All five scenarios have production implementations in:
  - `src/api/query/infrastructure/git_repository.py` — `GithubRepository`,
    `GitLabRepository`, `AbstractGitRemoteFileRepository`, `GitRepositoryFactory`
  - `src/api/query/infrastructure/observability/remote_file_repository_probe.py`

  However, **zero unit tests exist** for any of these classes. The scenarios listed
  above are entirely unverified by automated tests. This PR adds a dedicated unit test
  file that covers all five spec scenarios via HTTP-mocked tests (no real network calls).

  ## What This PR Does

  ### New file: `src/api/tests/unit/query/test_git_repository.py`

  All tests use `unittest.mock.patch` (or `respx` / `httpx.MockTransport`) to intercept
  HTTP calls made by `httpx.get()` inside `AbstractGitRemoteFileRepository.get_file()`.

  #### Scenario 1: Fetch from GitHub

  ```python
  class TestGithubRepository:
      def test_fetch_github_blob_url_calls_contents_api(self):
          """GIVEN a GitHub blob URL WHEN get_file() is called
          THEN the GitHub Contents API is called and content is returned."""
          url = "https://github.com/owner/repo/blob/main/docs/file.adoc"
          content = "= My Title\n\nBody text."
          with httpx_mock.mock(url="https://api.github.com/repos/owner/repo/contents/docs/file.adoc?ref=main",
                               response_text=content):
              repo = GithubRepository()
              response = repo.get_file(url)
          assert response.success is True
          assert response.content == content
          assert response.source_url == url

      def test_asciidoc_metadata_stripped_before_title(self):
          """GIVEN AsciiDoc content with metadata header
          WHEN get_file() returns it
          THEN metadata before the document title is stripped."""
          raw = ":doctype: article\n:toc: auto\n// comment\n= Real Title\n\nBody."
          with mock_github_response(raw):
              response = GithubRepository().get_file("https://github.com/o/r/blob/main/f.adoc")
          assert response.content.startswith("= Real Title")
          assert ":doctype:" not in response.content
  ```

  #### Scenario 2: Fetch from GitLab

  ```python
  class TestGitLabRepository:
      def test_fetch_gitlab_blob_url_calls_files_api(self):
          """GIVEN a GitLab blob URL WHEN get_file() is called
          THEN the GitLab Repository Files API is called."""
          url = "https://gitlab.com/owner/repo/-/blob/main/docs/file.adoc"
          # Expected API URL: /api/v4/projects/owner%2Frepo/repository/files/docs%2Ffile.adoc/raw?ref=main
          with mock_gitlab_response("= Title\n\nBody"):
              response = GitLabRepository().get_file(url)
          assert response.success is True
  ```

  #### Scenario 3: Private repository with token

  ```python
  class TestPrivateRepositoryToken:
      def test_github_access_token_in_authorization_header(self):
          """GIVEN a GitHub access token
          THEN Authorization: Bearer <token> header is sent."""
          token = "ghp_test_token"
          with capture_github_request() as captured:
              GithubRepository(access_token=token).get_file(GITHUB_URL)
          assert captured.headers["Authorization"] == f"Bearer {token}"

      def test_gitlab_access_token_in_private_token_header(self):
          """GIVEN a GitLab access token
          THEN PRIVATE-TOKEN header is sent."""
          token = "glpat-test"
          with capture_gitlab_request() as captured:
              GitLabRepository(access_token=token).get_file(GITLAB_URL)
          assert captured.headers["PRIVATE-TOKEN"] == token
  ```

  #### Scenario 4: Self-hosted instance

  ```python
  class TestSelfHostedInstances:
      def test_github_enterprise_uses_api_v3_path(self):
          """GIVEN a GitHub Enterprise hostname
          THEN api_base is https://github.enterprise.com/api/v3 (not api.github.com)."""
          url = "https://github.enterprise.com/owner/repo/blob/main/file.adoc"
          with capture_github_request() as captured:
              GithubRepository().get_file(url)
          assert "github.enterprise.com/api/v3" in captured.url

      def test_gitlab_self_hosted_uses_correct_hostname(self):
          """GIVEN a self-hosted GitLab URL
          THEN the API call uses the self-hosted hostname."""
          url = "https://gitlab.company.com/owner/repo/-/blob/main/file.adoc"
          with capture_gitlab_request() as captured:
              GitLabRepository().get_file(url)
          assert "gitlab.company.com" in captured.url
  ```

  #### Scenario 5: Invalid URL format

  ```python
  class TestInvalidURLFormat:
      def test_non_github_non_gitlab_url_raises_invalid_remote_file_url(self):
          """GIVEN a URL that is not a GitHub or GitLab blob pattern
          WHEN get_file() is called
          THEN InvalidRemoteFileURL is raised."""
          with pytest.raises(InvalidRemoteFileURL):
              GithubRepository().get_file("https://bitbucket.org/owner/repo/src/main/file.txt")

      def test_factory_unsupported_url_raises_value_error(self):
          """GIVEN a URL that is neither GitHub nor GitLab
          WHEN GitRepositoryFactory.create_from_url() is called
          THEN ValueError is raised."""
          with pytest.raises(ValueError, match="Unsupported git provider"):
              GitRepositoryFactory.create_from_url("https://bitbucket.org/o/r/src/main/f.txt")
  ```

  #### Additional tests for `GitRepositoryFactory`:

  ```python
  class TestGitRepositoryFactory:
      def test_github_url_returns_github_repository(self):
          repo = GitRepositoryFactory.create_from_url("https://github.com/o/r/blob/main/f.adoc")
          assert isinstance(repo, GithubRepository)

      def test_gitlab_url_returns_gitlab_repository(self):
          repo = GitRepositoryFactory.create_from_url("https://gitlab.com/o/r/-/blob/main/f.adoc")
          assert isinstance(repo, GitLabRepository)

      def test_github_token_passed_to_github_repository(self):
          repo = GitRepositoryFactory.create_from_url(
              "https://github.com/o/r/blob/main/f.adoc", github_token="ghp_token"
          )
          assert repo._access_token == "ghp_token"

      def test_gitlab_token_passed_to_gitlab_repository(self):
          repo = GitRepositoryFactory.create_from_url(
              "https://gitlab.com/o/r/-/blob/main/f.adoc", gitlab_token="glpat-token"
          )
          assert repo._access_token == "glpat-token"
  ```

  #### Tests for `_strip_asciidoc_metadata()` (helper function):

  ```python
  class TestStripAsciiDocMetadata:
      def test_strips_attribute_lines_before_title(self):
          content = ":doctype: article\n= Title\n\nBody."
          assert _strip_asciidoc_metadata(content) == "= Title\n\nBody."

      def test_strips_comment_lines_before_title(self):
          content = "// This is a comment\n= Title\n\nBody."
          assert _strip_asciidoc_metadata(content).startswith("= Title")

      def test_returns_content_unchanged_if_no_document_title(self):
          content = "No document title here\nJust regular text."
          assert _strip_asciidoc_metadata(content) == content

      def test_does_not_strip_section_headings(self):
          content = "== Section\n\nBody."
          assert _strip_asciidoc_metadata(content) == content  # no change

      def test_non_asciidoc_content_passes_through(self):
          content = "# Markdown Title\n\nBody."
          assert _strip_asciidoc_metadata(content) == content
  ```

  ### HTTP mocking approach

  Use `unittest.mock.patch("httpx.get")` with `MagicMock` configured to return a fake
  response object with `status_code=200` and `text="..."`. This avoids adding any new
  test dependencies. Alternatively, use `pytest-httpx` if it is already in the dev
  dependencies.

  Check `src/api/pyproject.toml` for the available test dependencies before choosing
  the mocking strategy.

  ## Files Affected

  - `src/api/tests/unit/query/test_git_repository.py` — new file (all tests)

  ## How to Verify

  ```bash
  cd src/api && uv run pytest tests/unit/query/test_git_repository.py -v
  cd src/api && uv run pytest tests/unit/query/ -v  # no regressions
  ```

  ## Design Decisions

  - **No real network calls**: All tests mock `httpx.get` to avoid flakiness and
    network dependencies. These are pure unit tests.
  - **Test the URL construction logic**: The most valuable behaviour to test is that
    the correct API endpoint URL is derived from the input blob URL. Tests verify this
    by inspecting the URL passed to the mocked HTTP client.
  - **AsciiDoc stripping**: `_strip_asciidoc_metadata` is a pure function and can be
    tested without HTTP mocking at all. Separate test class for clarity.
  - **Factory delegation**: `GitRepositoryFactory.create_from_url()` is tested via
    `isinstance()` checks on the returned object type and `_access_token` attribute
    inspection, without triggering HTTP calls.

  ## Spec Reference

  `specs/query/mcp-server.spec.md` — Requirement: Documentation Fetch Tool (all 5 scenarios)
---

## Spec Coverage

**Requirement: Documentation Fetch Tool** from `specs/query/mcp-server.spec.md`:

All five scenarios are unverified by unit tests:

| Scenario | Code exists? | Unit test exists? |
|---|---|---|
| Fetch from GitHub | ✅ `GithubRepository` | ❌ None |
| Fetch from GitLab | ✅ `GitLabRepository` | ❌ None |
| Private repository with token | ✅ Both classes support `access_token` | ❌ None |
| Self-hosted instance | ✅ Enterprise URL logic in both classes | ❌ None |
| Invalid URL format | ✅ `InvalidRemoteFileURL` raised | ❌ None |

Additionally, the private `_strip_asciidoc_metadata()` helper function has no tests.

## Gap Analysis

The gap is entirely in the test layer. The implementation in
`src/api/query/infrastructure/git_repository.py` appears correct for all five
scenarios, but none of the logic has been exercised by automated tests.

## Verification Commands

```bash
cd src/api && uv run pytest tests/unit/query/test_git_repository.py -v
cd src/api && uv run pytest tests/unit/query/ -v
```
