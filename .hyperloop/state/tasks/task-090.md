---
id: task-090
title: Unit tests for fetch_documentation_source tool (git repository classes)
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: complete
phase: null
deps: []
round: 0
branch: hyperloop/task-090
pr: https://github.com/openshift-hyperfleet/kartograph/pull/556
pr_title: 'test(query): add unit tests for fetch_documentation_source tool and git
  repository classes'
pr_description: "## What & Why\n\nThe MCP server spec defines five scenarios for the\
  \ `fetch_documentation_source` tool:\n\n1. **Fetch from GitHub** — GitHub blob URL\
  \ → GitHub Contents API, AsciiDoc stripped\n2. **Fetch from GitLab** — GitLab blob\
  \ URL → GitLab Repository Files API\n3. **Private repository with token** — `x-github-pat`\
  \ / `x-gitlab-pat` header passed\n4. **Self-hosted instance** — GitHub Enterprise\
  \ and self-hosted GitLab hostnames resolved\n5. **Invalid URL format** — non-GitHub/GitLab\
  \ URL returns an error response\n\nAll five scenarios have production implementations\
  \ in:\n- `src/api/query/infrastructure/git_repository.py` — `GithubRepository`,\n\
  \  `GitLabRepository`, `AbstractGitRemoteFileRepository`, `GitRepositoryFactory`\n\
  - `src/api/query/infrastructure/observability/remote_file_repository_probe.py`\n\
  \nHowever, **zero unit tests exist** for any of these classes. The scenarios listed\n\
  above are entirely unverified by automated tests. This PR adds a dedicated unit\
  \ test\nfile that covers all five spec scenarios via HTTP-mocked tests (no real\
  \ network calls).\n\n## What This PR Does\n\n### New file: `src/api/tests/unit/query/test_git_repository.py`\n\
  \nAll tests use `unittest.mock.patch` (or `respx` / `httpx.MockTransport`) to intercept\n\
  HTTP calls made by `httpx.get()` inside `AbstractGitRemoteFileRepository.get_file()`.\n\
  \n#### Scenario 1: Fetch from GitHub\n\n```python\nclass TestGithubRepository:\n\
  \    def test_fetch_github_blob_url_calls_contents_api(self):\n        \"\"\"GIVEN\
  \ a GitHub blob URL WHEN get_file() is called\n        THEN the GitHub Contents\
  \ API is called and content is returned.\"\"\"\n        url = \"https://github.com/owner/repo/blob/main/docs/file.adoc\"\
  \n        content = \"= My Title\\n\\nBody text.\"\n        with httpx_mock.mock(url=\"\
  https://api.github.com/repos/owner/repo/contents/docs/file.adoc?ref=main\",\n  \
  \                           response_text=content):\n            repo = GithubRepository()\n\
  \            response = repo.get_file(url)\n        assert response.success is True\n\
  \        assert response.content == content\n        assert response.source_url\
  \ == url\n\n    def test_asciidoc_metadata_stripped_before_title(self):\n      \
  \  \"\"\"GIVEN AsciiDoc content with metadata header\n        WHEN get_file() returns\
  \ it\n        THEN metadata before the document title is stripped.\"\"\"\n     \
  \   raw = \":doctype: article\\n:toc: auto\\n// comment\\n= Real Title\\n\\nBody.\"\
  \n        with mock_github_response(raw):\n            response = GithubRepository().get_file(\"\
  https://github.com/o/r/blob/main/f.adoc\")\n        assert response.content.startswith(\"\
  = Real Title\")\n        assert \":doctype:\" not in response.content\n```\n\n####\
  \ Scenario 2: Fetch from GitLab\n\n```python\nclass TestGitLabRepository:\n    def\
  \ test_fetch_gitlab_blob_url_calls_files_api(self):\n        \"\"\"GIVEN a GitLab\
  \ blob URL WHEN get_file() is called\n        THEN the GitLab Repository Files API\
  \ is called.\"\"\"\n        url = \"https://gitlab.com/owner/repo/-/blob/main/docs/file.adoc\"\
  \n        # Expected API URL: /api/v4/projects/owner%2Frepo/repository/files/docs%2Ffile.adoc/raw?ref=main\n\
  \        with mock_gitlab_response(\"= Title\\n\\nBody\"):\n            response\
  \ = GitLabRepository().get_file(url)\n        assert response.success is True\n\
  ```\n\n#### Scenario 3: Private repository with token\n\n```python\nclass TestPrivateRepositoryToken:\n\
  \    def test_github_access_token_in_authorization_header(self):\n        \"\"\"\
  GIVEN a GitHub access token\n        THEN Authorization: Bearer <token> header is\
  \ sent.\"\"\"\n        token = \"ghp_test_token\"\n        with capture_github_request()\
  \ as captured:\n            GithubRepository(access_token=token).get_file(GITHUB_URL)\n\
  \        assert captured.headers[\"Authorization\"] == f\"Bearer {token}\"\n\n \
  \   def test_gitlab_access_token_in_private_token_header(self):\n        \"\"\"\
  GIVEN a GitLab access token\n        THEN PRIVATE-TOKEN header is sent.\"\"\"\n\
  \        token = \"glpat-test\"\n        with capture_gitlab_request() as captured:\n\
  \            GitLabRepository(access_token=token).get_file(GITLAB_URL)\n       \
  \ assert captured.headers[\"PRIVATE-TOKEN\"] == token\n```\n\n#### Scenario 4: Self-hosted\
  \ instance\n\n```python\nclass TestSelfHostedInstances:\n    def test_github_enterprise_uses_api_v3_path(self):\n\
  \        \"\"\"GIVEN a GitHub Enterprise hostname\n        THEN api_base is https://github.enterprise.com/api/v3\
  \ (not api.github.com).\"\"\"\n        url = \"https://github.enterprise.com/owner/repo/blob/main/file.adoc\"\
  \n        with capture_github_request() as captured:\n            GithubRepository().get_file(url)\n\
  \        assert \"github.enterprise.com/api/v3\" in captured.url\n\n    def test_gitlab_self_hosted_uses_correct_hostname(self):\n\
  \        \"\"\"GIVEN a self-hosted GitLab URL\n        THEN the API call uses the\
  \ self-hosted hostname.\"\"\"\n        url = \"https://gitlab.company.com/owner/repo/-/blob/main/file.adoc\"\
  \n        with capture_gitlab_request() as captured:\n            GitLabRepository().get_file(url)\n\
  \        assert \"gitlab.company.com\" in captured.url\n```\n\n#### Scenario 5:\
  \ Invalid URL format\n\n```python\nclass TestInvalidURLFormat:\n    def test_non_github_non_gitlab_url_raises_invalid_remote_file_url(self):\n\
  \        \"\"\"GIVEN a URL that is not a GitHub or GitLab blob pattern\n       \
  \ WHEN get_file() is called\n        THEN InvalidRemoteFileURL is raised.\"\"\"\n\
  \        with pytest.raises(InvalidRemoteFileURL):\n            GithubRepository().get_file(\"\
  https://bitbucket.org/owner/repo/src/main/file.txt\")\n\n    def test_factory_unsupported_url_raises_value_error(self):\n\
  \        \"\"\"GIVEN a URL that is neither GitHub nor GitLab\n        WHEN GitRepositoryFactory.create_from_url()\
  \ is called\n        THEN ValueError is raised.\"\"\"\n        with pytest.raises(ValueError,\
  \ match=\"Unsupported git provider\"):\n            GitRepositoryFactory.create_from_url(\"\
  https://bitbucket.org/o/r/src/main/f.txt\")\n```\n\n#### Additional tests for `GitRepositoryFactory`:\n\
  \n```python\nclass TestGitRepositoryFactory:\n    def test_github_url_returns_github_repository(self):\n\
  \        repo = GitRepositoryFactory.create_from_url(\"https://github.com/o/r/blob/main/f.adoc\"\
  )\n        assert isinstance(repo, GithubRepository)\n\n    def test_gitlab_url_returns_gitlab_repository(self):\n\
  \        repo = GitRepositoryFactory.create_from_url(\"https://gitlab.com/o/r/-/blob/main/f.adoc\"\
  )\n        assert isinstance(repo, GitLabRepository)\n\n    def test_github_token_passed_to_github_repository(self):\n\
  \        repo = GitRepositoryFactory.create_from_url(\n            \"https://github.com/o/r/blob/main/f.adoc\"\
  , github_token=\"ghp_token\"\n        )\n        assert repo._access_token == \"\
  ghp_token\"\n\n    def test_gitlab_token_passed_to_gitlab_repository(self):\n  \
  \      repo = GitRepositoryFactory.create_from_url(\n            \"https://gitlab.com/o/r/-/blob/main/f.adoc\"\
  , gitlab_token=\"glpat-token\"\n        )\n        assert repo._access_token ==\
  \ \"glpat-token\"\n```\n\n#### Tests for `_strip_asciidoc_metadata()` (helper function):\n\
  \n```python\nclass TestStripAsciiDocMetadata:\n    def test_strips_attribute_lines_before_title(self):\n\
  \        content = \":doctype: article\\n= Title\\n\\nBody.\"\n        assert _strip_asciidoc_metadata(content)\
  \ == \"= Title\\n\\nBody.\"\n\n    def test_strips_comment_lines_before_title(self):\n\
  \        content = \"// This is a comment\\n= Title\\n\\nBody.\"\n        assert\
  \ _strip_asciidoc_metadata(content).startswith(\"= Title\")\n\n    def test_returns_content_unchanged_if_no_document_title(self):\n\
  \        content = \"No document title here\\nJust regular text.\"\n        assert\
  \ _strip_asciidoc_metadata(content) == content\n\n    def test_does_not_strip_section_headings(self):\n\
  \        content = \"== Section\\n\\nBody.\"\n        assert _strip_asciidoc_metadata(content)\
  \ == content  # no change\n\n    def test_non_asciidoc_content_passes_through(self):\n\
  \        content = \"# Markdown Title\\n\\nBody.\"\n        assert _strip_asciidoc_metadata(content)\
  \ == content\n```\n\n### HTTP mocking approach\n\nUse `unittest.mock.patch(\"httpx.get\"\
  )` with `MagicMock` configured to return a fake\nresponse object with `status_code=200`\
  \ and `text=\"...\"`. This avoids adding any new\ntest dependencies. Alternatively,\
  \ use `pytest-httpx` if it is already in the dev\ndependencies.\n\nCheck `src/api/pyproject.toml`\
  \ for the available test dependencies before choosing\nthe mocking strategy.\n\n\
  ## Files Affected\n\n- `src/api/tests/unit/query/test_git_repository.py` — new file\
  \ (all tests)\n\n## How to Verify\n\n```bash\ncd src/api && uv run pytest tests/unit/query/test_git_repository.py\
  \ -v\ncd src/api && uv run pytest tests/unit/query/ -v  # no regressions\n```\n\n\
  ## Design Decisions\n\n- **No real network calls**: All tests mock `httpx.get` to\
  \ avoid flakiness and\n  network dependencies. These are pure unit tests.\n- **Test\
  \ the URL construction logic**: The most valuable behaviour to test is that\n  the\
  \ correct API endpoint URL is derived from the input blob URL. Tests verify this\n\
  \  by inspecting the URL passed to the mocked HTTP client.\n- **AsciiDoc stripping**:\
  \ `_strip_asciidoc_metadata` is a pure function and can be\n  tested without HTTP\
  \ mocking at all. Separate test class for clarity.\n- **Factory delegation**: `GitRepositoryFactory.create_from_url()`\
  \ is tested via\n  `isinstance()` checks on the returned object type and `_access_token`\
  \ attribute\n  inspection, without triggering HTTP calls.\n\n## Spec Reference\n\
  \n`specs/query/mcp-server.spec.md` — Requirement: Documentation Fetch Tool (all\
  \ 5 scenarios)"
---
