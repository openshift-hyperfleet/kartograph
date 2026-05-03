---
id: task-092
title: MCP server — Agent Instructions Resource spec alignment
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "feat(query): verify instructions://agent MCP resource against spec"
pr_description: |
  ## What & Why

  The **Requirement: Agent Instructions Resource** in `specs/query/mcp-server.spec.md`
  has never had a hyperloop task created for it. Both scenarios in this requirement
  are currently implemented in:

  - `src/api/query/presentation/mcp.py` — `get_agent_instructions()` resource,
    module-level fail-fast `get_prompt_repository()` call
  - `src/api/query/infrastructure/prompt_repository.py` — `PromptRepository`
    (reads and caches the agent instructions file at startup)

  This task creates traceability between the spec requirement and the existing
  implementation, and confirms every scenario is covered line-by-line.

  ## Spec Scenarios

  ### Scenario: Read instructions
  > GIVEN the agent instructions file exists at startup
  > WHEN an MCP client reads the `instructions://agent` resource
  > THEN the cached instructions content is returned

  Implementation: The `@mcp.resource(uri="instructions://agent")` decorator
  registers `get_agent_instructions()` as an MCP resource. At startup,
  `_prompt_repository = get_prompt_repository()` loads and caches the agent
  instructions from disk. `get_agent_instructions()` returns
  `_prompt_repository.get_agent_instructions()` — the cached content.

  Key implementation detail: the `PromptRepository` caches the content in-memory
  at startup, so each MCP client read returns the cached string without re-reading
  the file.

  ### Scenario: Missing instructions at startup
  > GIVEN the agent instructions file does not exist
  > WHEN the application starts
  > THEN startup fails immediately (fail-fast)

  Implementation: In `src/api/query/presentation/mcp.py` at module level:

  ```python
  # Eagerly validate prompts at startup (fail-fast if missing)
  _prompt_repository = get_prompt_repository()
  ```

  Because this executes at import time (module level), if the instructions file
  is missing, `get_prompt_repository()` raises immediately, preventing the MCP
  server from starting. FastAPI/uvicorn catches the import error and fails to
  start the application — satisfying the fail-fast requirement.

  ## Files Affected

  No new implementation expected — this task verifies existing code:

  - `src/api/query/presentation/mcp.py` — `get_agent_instructions()` resource
    and module-level `get_prompt_repository()` call
  - `src/api/query/infrastructure/prompt_repository.py` — `PromptRepository`
    implementation
  - `src/api/query/dependencies.py` — `get_prompt_repository()` factory

  ## How to Verify

  1. Confirm `test_mcp_auth_wiring.py` or equivalent covers the `instructions://agent`
     resource registration.
  2. Run unit tests: `cd src/api && uv run pytest tests/unit/query/ -v`
  3. For the fail-fast scenario: verify that `get_prompt_repository()` is called
     at module level (not inside the resource function), confirming startup-time
     validation.
  4. If a test for the fail-fast behavior is missing, add one that patches the
     instructions file path to a non-existent location and confirms import fails.

  ## Design Context

  - The `instructions://agent` resource URI uses the scheme `instructions://` which
    is a custom URI scheme for this resource (similar to `knowledge-graphs://`).
  - The instructions are loaded once at startup and cached — this is by design
    because the instructions are static configuration that doesn't change at runtime.
  - The fail-fast pattern ensures operators discover a misconfigured instructions
    file at deployment time, not at the first MCP request.
  - The `mime_type="text/markdown"` annotation on the resource signals to MCP
    clients that the content is Markdown-formatted.

  ## Gap Analysis

  This task was created by a PM intake run that identified the Agent Instructions
  Resource requirement in `mcp-server.spec.md` had no hyperloop task despite being
  fully implemented. All previous tasks for this spec (task-011, task-085, task-086,
  task-089) covered other requirements. This task provides spec traceability and
  prompts the orchestrator to verify the fail-fast startup behavior is adequately
  tested.
---
