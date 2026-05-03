---
id: task-092
title: MCP server — Agent Instructions Resource spec alignment
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: mark-ready
deps: []
round: 1
branch: hyperloop/task-092
pr: https://github.com/openshift-hyperfleet/kartograph/pull/558
pr_title: 'feat(query): verify instructions://agent MCP resource against spec'
pr_description: "## What & Why\n\nThe **Requirement: Agent Instructions Resource**\
  \ in `specs/query/mcp-server.spec.md`\nhas never had a hyperloop task created for\
  \ it. Both scenarios in this requirement\nare currently implemented in:\n\n- `src/api/query/presentation/mcp.py`\
  \ — `get_agent_instructions()` resource,\n  module-level fail-fast `get_prompt_repository()`\
  \ call\n- `src/api/query/infrastructure/prompt_repository.py` — `PromptRepository`\n\
  \  (reads and caches the agent instructions file at startup)\n\nThis task creates\
  \ traceability between the spec requirement and the existing\nimplementation, and\
  \ confirms every scenario is covered line-by-line.\n\n## Spec Scenarios\n\n### Scenario:\
  \ Read instructions\n> GIVEN the agent instructions file exists at startup\n> WHEN\
  \ an MCP client reads the `instructions://agent` resource\n> THEN the cached instructions\
  \ content is returned\n\nImplementation: The `@mcp.resource(uri=\"instructions://agent\"\
  )` decorator\nregisters `get_agent_instructions()` as an MCP resource. At startup,\n\
  `_prompt_repository = get_prompt_repository()` loads and caches the agent\ninstructions\
  \ from disk. `get_agent_instructions()` returns\n`_prompt_repository.get_agent_instructions()`\
  \ — the cached content.\n\nKey implementation detail: the `PromptRepository` caches\
  \ the content in-memory\nat startup, so each MCP client read returns the cached\
  \ string without re-reading\nthe file.\n\n### Scenario: Missing instructions at\
  \ startup\n> GIVEN the agent instructions file does not exist\n> WHEN the application\
  \ starts\n> THEN startup fails immediately (fail-fast)\n\nImplementation: In `src/api/query/presentation/mcp.py`\
  \ at module level:\n\n```python\n# Eagerly validate prompts at startup (fail-fast\
  \ if missing)\n_prompt_repository = get_prompt_repository()\n```\n\nBecause this\
  \ executes at import time (module level), if the instructions file\nis missing,\
  \ `get_prompt_repository()` raises immediately, preventing the MCP\nserver from\
  \ starting. FastAPI/uvicorn catches the import error and fails to\nstart the application\
  \ — satisfying the fail-fast requirement.\n\n## Files Affected\n\nNo new implementation\
  \ expected — this task verifies existing code:\n\n- `src/api/query/presentation/mcp.py`\
  \ — `get_agent_instructions()` resource\n  and module-level `get_prompt_repository()`\
  \ call\n- `src/api/query/infrastructure/prompt_repository.py` — `PromptRepository`\n\
  \  implementation\n- `src/api/query/dependencies.py` — `get_prompt_repository()`\
  \ factory\n\n## How to Verify\n\n1. Confirm `test_mcp_auth_wiring.py` or equivalent\
  \ covers the `instructions://agent`\n   resource registration.\n2. Run unit tests:\
  \ `cd src/api && uv run pytest tests/unit/query/ -v`\n3. For the fail-fast scenario:\
  \ verify that `get_prompt_repository()` is called\n   at module level (not inside\
  \ the resource function), confirming startup-time\n   validation.\n4. If a test\
  \ for the fail-fast behavior is missing, add one that patches the\n   instructions\
  \ file path to a non-existent location and confirms import fails.\n\n## Design Context\n\
  \n- The `instructions://agent` resource URI uses the scheme `instructions://` which\n\
  \  is a custom URI scheme for this resource (similar to `knowledge-graphs://`).\n\
  - The instructions are loaded once at startup and cached — this is by design\n \
  \ because the instructions are static configuration that doesn't change at runtime.\n\
  - The fail-fast pattern ensures operators discover a misconfigured instructions\n\
  \  file at deployment time, not at the first MCP request.\n- The `mime_type=\"text/markdown\"\
  ` annotation on the resource signals to MCP\n  clients that the content is Markdown-formatted.\n\
  \n## Gap Analysis\n\nThis task was created by a PM intake run that identified the\
  \ Agent Instructions\nResource requirement in `mcp-server.spec.md` had no hyperloop\
  \ task despite being\nfully implemented. All previous tasks for this spec (task-011,\
  \ task-085, task-086,\ntask-089) covered other requirements. This task provides\
  \ spec traceability and\nprompts the orchestrator to verify the fail-fast startup\
  \ behavior is adequately\ntested."
---
