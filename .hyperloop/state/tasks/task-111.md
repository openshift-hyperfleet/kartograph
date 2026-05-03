---
id: task-111
title: 'fetch_documentation_source: return error response for invalid URL instead
  of propagating exception'
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: complete
phase: null
deps: []
round: 1
branch: hyperloop/task-111
pr: https://github.com/openshift-hyperfleet/kartograph/pull/581
pr_title: 'fix(query): return RemoteFileRepositoryResponse(success=False) for invalid
  URL in fetch_documentation_source'
pr_description: "## What & Why\n\nThe `fetch_documentation_source` MCP tool has the\
  \ following return type contract:\n\n```python\ndef fetch_documentation_source(url:\
  \ str) -> RemoteFileRepositoryResponse:\n```\n\n`RemoteFileRepositoryResponse` has\
  \ a `success=False` / `error=...` path for\nsignalling failures to callers. However,\
  \ when the URL does not match any\nsupported git provider (GitHub blob URL or GitLab\
  \ `/-/blob/` URL), the current\nimplementation propagates a `ValueError` raised\
  \ by `get_git_repository` /\n`GitRepositoryFactory.create_from_url`. FastMCP catches\
  \ unhandled exceptions and\nconverts them to MCP JSON-RPC errors — a different shape\
  \ from the tool's\ndeclared return type.\n\n### Spec Requirement\n\n`specs/query/mcp-server.spec.md`\
  \ — **Requirement: Documentation Fetch Tool**:\n\n> **Scenario: Invalid URL format**\n\
  > GIVEN a URL that does not match GitHub or GitLab blob patterns\n> WHEN the tool\
  \ is called\n> THEN an error response is returned\n\n\"An error response\" in this\
  \ context means `RemoteFileRepositoryResponse(success=False,\nerror=\"...\")` —\
  \ consistent with the tool's own return type and with how HTTP failures\nare already\
  \ handled (the repository raises `RemoteFileFetchFailed` which is also not\ncaught\
  \ at the tool layer). The spec says *an* error response, not a JSON-RPC fault.\n\
  Returning a typed `RemoteFileRepositoryResponse(success=False)` is the correct\n\
  interpretation because:\n- The tool's return type is `RemoteFileRepositoryResponse`\
  \ — callers expect this shape.\n- MCP clients that pattern-match on `response.success`\
  \ would receive an unexpected\n  JSON-RPC error object instead of a `RemoteFileRepositoryResponse`.\n\
  - The repository layer already has `InvalidRemoteFileURL` as a typed exception for\n\
  \  this exact case (`query/ports/exceptions.py`).\n\n### Test Gap\n\n`tests/unit/query/infrastructure/test_git_repository.py`\
  \ and\n`TestGitRepositoryFactory.test_rejects_invalid_url_format` cover the factory\
  \ level.\n`tests/unit/query/test_mcp_tools.py` covers PAT header extraction but\
  \ has no test\nthat calls `fetch_documentation_source.fn(invalid_url)` and asserts\
  \ a typed\n`RemoteFileRepositoryResponse(success=False)` is returned. This is the\
  \ missing layer.\n\n## Spec Requirements Satisfied\n\n`specs/query/mcp-server.spec.md`:\n\
  - **Requirement: Documentation Fetch Tool** — Scenario: *Invalid URL format*\n\n\
  ## What This Change Does\n\n### 1. `src/api/query/presentation/mcp.py`\n\nWrap the\
  \ `get_git_repository` call (and optionally `repository.get_file`) in a\n`try/except`\
  \ block that catches `InvalidRemoteFileURL` (and `RemoteFileFetchFailed`\nif not\
  \ already caught by the repository's template method) and returns:\n\n```python\n\
  from query.ports.exceptions import InvalidRemoteFileURL, RemoteFileFetchFailed\n\
  \n@mcp.tool\ndef fetch_documentation_source(url: str) -> RemoteFileRepositoryResponse:\n\
  \    headers = get_http_headers()\n    github_token = headers.get(\"x-github-pat\"\
  )\n    gitlab_token = headers.get(\"x-gitlab-pat\")\n\n    try:\n        repository\
  \ = get_git_repository(\n            url=url,\n            github_token=github_token,\n\
  \            gitlab_token=gitlab_token,\n        )\n        return repository.get_file(url=url)\n\
  \    except InvalidRemoteFileURL:\n        return RemoteFileRepositoryResponse(\n\
  \            success=False,\n            error=\"Invalid URL format: must be a GitHub\
  \ or GitLab blob URL\",\n        )\n    except RemoteFileFetchFailed as e:\n   \
  \     return RemoteFileRepositoryResponse(\n            success=False,\n       \
  \     error=str(e) or \"Failed to fetch file from remote repository\",\n       \
  \ )\n```\n\n### 2. `src/api/tests/unit/query/test_mcp_tools.py`\n\nAdd a new test\
  \ class `TestFetchDocumentationSourceErrorHandling` with tests that\ncall `fetch_documentation_source.fn(url)`\
  \ and assert typed error responses:\n\n**Write these tests BEFORE touching the implementation\
  \ (TDD)**:\n\n1. **`test_invalid_url_returns_error_response`** — call `.fn(\"https://example.com/not-a-git-url\"\
  )`;\n   assert `result.success is False` and `result.error` is not None.\n\n2. **`test_invalid_url_does_not_raise`**\
  \ — assert the tool does NOT raise an\n   exception (it must return, not raise,\
  \ for any URL pattern).\n\n3. **`test_github_url_missing_blob_segment_returns_error`**\
  \ — URL like\n   `\"https://github.com/owner/repo\"` (no `/blob/`) returns `success=False`.\n\
  \n4. **`test_remote_fetch_failure_returns_error_response`** — mock\n   `get_git_repository`\
  \ to return a repository whose `.get_file()` raises\n   `RemoteFileFetchFailed(\"\
  HTTP 404\")` and assert `result.success is False`\n   and `result.error` contains\
  \ \"404\".\n\n## Files / Areas Affected\n\n- `src/api/query/presentation/mcp.py`\
  \ — add try/except in `fetch_documentation_source`\n- `src/api/tests/unit/query/test_mcp_tools.py`\
  \ — add `TestFetchDocumentationSourceErrorHandling`\n- No domain or port changes\
  \ required; `InvalidRemoteFileURL` and `RemoteFileFetchFailed`\n  already exist\
  \ in `query/ports/exceptions.py`\n\n## How to Verify\n\n1. TDD cycle: write failing\
  \ tests in `test_mcp_tools.py` first\n2. Add try/except to `fetch_documentation_source`\
  \ in `mcp.py`\n3. `cd src/api && uv run pytest tests/unit/query/test_mcp_tools.py\
  \ -v -k \"ErrorHandling\"`\n   — all 4 new tests pass\n4. `uv run pytest tests/unit/query/\
  \ -v` — no regressions in existing tests\n\n## Caveats\n\n- `RemoteFileFetchFailed`\
  \ is already caught inside the repository's `get_file`\n  template method and re-raised;\
  \ verify whether catching it at the tool layer is\n  redundant or necessary (it\
  \ should be necessary since the template method raises, not\n  swallows).\n- The\
  \ tool's docstring documents `RemoteFileRepositoryResponse` as the return type —\n\
  \  add a note in the Args section that invalid URLs return `success=False`.\n- Do\
  \ not suppress all exceptions: only `InvalidRemoteFileURL` and\n  `RemoteFileFetchFailed`\
  \ should be caught. Other unexpected errors should still\n  propagate so FastMCP\
  \ surfaces them as internal errors (not silent failures)."
---
