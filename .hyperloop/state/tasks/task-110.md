---
id: task-110
title: MCP Knowledge Graphs Resource — integration tests for knowledge-graphs://accessible
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: complete
phase: null
deps: []
round: 0
branch: hyperloop/task-110
pr: https://github.com/openshift-hyperfleet/kartograph/pull/577
pr_title: 'test(query): add integration tests for knowledge-graphs://accessible MCP
  resource'
pr_description: "## What & Why\n\nThe **Knowledge Graphs Resource** requirement in\
  \ `specs/query/mcp-server.spec.md`\ndefines two scenarios:\n\n> \"GIVEN an authenticated\
  \ MCP client WHEN it reads the `knowledge-graphs://accessible`\n> resource THEN\
  \ it receives a JSON list of knowledge graphs the caller has `view`\n> permission\
  \ on, each entry containing at minimum `id`, `name`, and `description`\"\n\n> \"\
  GIVEN an authenticated MCP client with no accessible knowledge graphs WHEN it\n\
  > reads the `knowledge-graphs://accessible` resource THEN it receives an empty list\n\
  > (not an error)\"\n\nThe implementation is complete: `get_accessible_knowledge_graphs()`\
  \ in\n`query/presentation/mcp.py` calls `MCPKnowledgeGraphsService.get_accessible()`,\n\
  which queries SpiceDB for `view`-permissioned KG IDs, then fetches metadata from\n\
  the Management DB. Unit tests in `tests/unit/query/test_mcp_knowledge_graphs_resource.py`\n\
  confirm the service logic with fakes.\n\nWhat is missing is end-to-end integration\
  \ coverage. The existing\n`tests/integration/test_query_mcp.py` exercises the `query_graph`\
  \ Cypher tool\nonly. No integration test reads the `knowledge-graphs://accessible`\
  \ resource against\nreal SpiceDB + Management DB. A regression in the SpiceDB `lookup_resources`\
  \ call,\nthe Management DB query, or the MCP resource wiring would be invisible\
  \ until\nproduction.\n\n## Spec Requirements Satisfied\n\n`specs/query/mcp-server.spec.md`:\n\
  - **Requirement: Knowledge Graphs Resource** — Scenario: *List accessible knowledge\
  \ graphs*\n- **Requirement: Knowledge Graphs Resource** — Scenario: *Empty list\
  \ when no access*\n\n## What This Change Does\n\nAdd integration tests in `src/api/tests/integration/query/`\
  \ that exercise the\n`knowledge-graphs://accessible` MCP resource against real SpiceDB\
  \ and Management DB:\n\n### Test: `test_accessible_knowledge_graphs_lists_permitted_kgs`\n\
  \nSetup:\n1. Create two KG records in the Management DB for the test tenant.\n2.\
  \ Grant SpiceDB `view` permission on KG-1 for the test subject (API key holder).\n\
  3. Do NOT grant `view` on KG-2.\n4. Obtain an API key for the test subject.\n\n\
  Execution:\n- Read the `knowledge-graphs://accessible` MCP resource via HTTP\n \
  \ (`GET /mcp/resources/read` with `uri: \"knowledge-graphs://accessible\"`, or use\n\
  \  the MCP client protocol as appropriate for the framework version in use).\n\n\
  Assertions:\n- Response is 200.\n- Response body contains exactly one KG entry (KG-1).\n\
  - Entry contains `id`, `name`, and `description` fields.\n- KG-2 is absent from\
  \ the list.\n\n### Test: `test_accessible_knowledge_graphs_returns_empty_list_when_no_access`\n\
  \nSetup:\n1. Create one KG record in Management DB.\n2. Grant NO SpiceDB permissions\
  \ to the test subject.\n3. Obtain an API key for the test subject.\n\nExecution:\n\
  - Read the `knowledge-graphs://accessible` resource.\n\nAssertions:\n- Response\
  \ is 200 (not an error).\n- Response body is an empty JSON array `[]`.\n\n## Files\
  \ / Areas Affected\n\n- `src/api/tests/integration/query/test_kg_resource.py` (new)\
  \ — the two integration\n  test cases described above\n- `src/api/tests/integration/conftest.py`\
  \ or a shared fixtures module — fixtures\n  for seeding KG records in Management\
  \ DB, writing SpiceDB relationships, and\n  obtaining scoped API keys for test subjects\n\
  - No production code changes expected; if a test reveals a real bug, fix it and\n\
  \  note it in the PR description\n\n## Tests\n\nThe two integration tests ARE the\
  \ deliverable. Mark them with `@pytest.mark.integration`\nand ensure they run with\
  \ `make test-integration` against the isolated dev instance.\n\nInfrastructure requirements\
  \ (provided by `make instance-up`):\n- PostgreSQL (Management DB — for KG metadata)\n\
  - SpiceDB (for `lookup_resources` permission checks)\n- Kartograph API (for MCP\
  \ HTTP endpoint)\n\n## How to Verify\n\n1. `make instance-up` — start isolated test\
  \ instance\n2. `source .instances/$(basename $(pwd))/.env.instance`\n3. `cd src/api\
  \ && uv run pytest tests/integration/query/test_kg_resource.py -v -m integration`\n\
  4. Confirm both tests pass green\n\n## Caveats\n\n- The resource URI is `knowledge-graphs://accessible`\
  \ (hyphen, per RFC 3986) — not\n  `knowledge_graphs://accessible`. Ensure the integration\
  \ test client uses the exact\n  URI registered in `mcp.py`.\n- SpiceDB relationship\
  \ writes in fixtures must be torn down after each test to avoid\n  cross-test pollution\
  \ in the SpiceDB store.\n- `MCPKnowledgeGraphsService` short-circuits to an empty\
  \ list if SpiceDB returns no\n  IDs; the \"no access\" test implicitly validates\
  \ this short-circuit path in production\n  infrastructure (not just unit mocks).\n\
  - If the integration test environment uses the fake OIDC provider, ensure the API\
  \ key\n  auth middleware correctly extracts `tenant_id` and `subject` from the issued\
  \ JWT,\n  as these are used to scope the SpiceDB lookup."
---
