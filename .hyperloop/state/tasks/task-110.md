---
id: task-110
title: "MCP Knowledge Graphs Resource — integration tests for knowledge-graphs://accessible"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration tests for knowledge-graphs://accessible MCP resource"
pr_description: |
  ## What & Why

  The **Knowledge Graphs Resource** requirement in `specs/query/mcp-server.spec.md`
  defines two scenarios:

  > "GIVEN an authenticated MCP client WHEN the client reads the
  > `knowledge_graphs://accessible` resource THEN the response contains all knowledge
  > graphs the caller has `view` permission on within their tenant AND each entry
  > includes the knowledge graph `id`, `name`, and `description` AND knowledge graphs
  > the caller cannot access are omitted entirely"

  > "GIVEN an authenticated MCP client with no accessible knowledge graphs WHEN the
  > client reads the `knowledge_graphs://accessible` resource THEN an empty list is
  > returned"

  The implementation is complete: `get_accessible_knowledge_graphs()` in
  `query/presentation/mcp.py` calls `MCPKnowledgeGraphsService.get_accessible()`,
  which queries SpiceDB for `view`-permissioned KG IDs, then fetches metadata from
  the Management DB. Unit tests in `tests/unit/query/test_mcp_knowledge_graphs_resource.py`
  confirm the service logic with fakes.

  What is missing is end-to-end integration coverage. The existing
  `tests/integration/test_query_mcp.py` exercises the `query_graph` Cypher tool
  only. No integration test reads the `knowledge-graphs://accessible` resource against
  real SpiceDB + Management DB. A regression in the SpiceDB `lookup_resources` call,
  the Management DB query, or the MCP resource wiring would be invisible until
  production.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md`:
  - **Requirement: Knowledge Graphs Resource** — Scenario: *List accessible knowledge graphs*
  - **Requirement: Knowledge Graphs Resource** — Scenario: *No accessible knowledge graphs*

  ## What This Change Does

  Add integration tests that exercise the `knowledge-graphs://accessible` MCP resource
  against real SpiceDB and Management DB:

  ### Test: `test_accessible_knowledge_graphs_lists_permitted_kgs`

  Setup:
  1. Create two KG records in the Management DB for the test tenant.
  2. Grant SpiceDB `view` permission on KG-1 for the test subject (API key holder).
  3. Do NOT grant `view` on KG-2.
  4. Obtain an API key for the test subject.

  Execution:
  - Read the `knowledge-graphs://accessible` MCP resource via the MCP HTTP protocol.

  Assertions:
  - Response is successful.
  - Response body contains exactly one KG entry (KG-1).
  - Entry contains `id`, `name`, and `description` fields.
  - KG-2 is absent from the list.

  ### Test: `test_accessible_knowledge_graphs_returns_empty_list_when_no_access`

  Setup:
  1. Create one KG record in Management DB for the test tenant.
  2. Grant NO SpiceDB permissions to the test subject for any KG.
  3. Obtain an API key for the test subject.

  Execution:
  - Read the `knowledge-graphs://accessible` resource.

  Assertions:
  - Response is successful (not an error).
  - Response body is an empty JSON array `[]`.

  ## Files / Areas Affected

  - `src/api/tests/integration/query/test_kg_resource.py` (new) — the two integration
    test cases described above, OR extend `test_query_mcp.py`
  - `src/api/tests/integration/conftest.py` or a shared fixtures module — fixtures
    for seeding KG records in Management DB, writing SpiceDB relationships, and
    obtaining scoped API keys for test subjects
  - No production code changes expected; if a test reveals a real bug, fix it and
    note it in the PR description

  ## Tests

  The integration tests ARE the deliverable. Mark them with `@pytest.mark.integration`
  and ensure they run with `make test-integration` against the isolated dev instance.

  Infrastructure requirements (provided by `make instance-up`):
  - PostgreSQL (Management DB — for KG metadata)
  - SpiceDB (for `lookup_resources` permission checks)
  - Kartograph API (for MCP HTTP endpoint)

  ## How to Verify

  1. `make instance-up` — start isolated test instance
  2. `source .instances/$(basename $(pwd))/.env.instance`
  3. `cd src/api && uv run pytest tests/integration/ -v -m integration -k "kg_resource"`
  4. Confirm both tests pass green

  ## Caveats

  - The resource URI registered in `mcp.py` is `knowledge-graphs://accessible`
    (hyphen, RFC 3986 compliant) — not `knowledge_graphs://accessible` (underscore).
    Ensure the integration test client requests the exact registered URI.
  - SpiceDB relationship writes in fixtures must be torn down after each test to avoid
    cross-test pollution in the SpiceDB store.
  - `MCPKnowledgeGraphsService` short-circuits to an empty list if SpiceDB returns no
    accessible KG IDs; the "no access" test implicitly validates this code path against
    real SpiceDB infrastructure rather than just unit mocks.
  - If the integration test environment uses the fake OIDC provider, ensure the API key
    auth middleware correctly extracts `tenant_id` and `subject` from the issued JWT,
    as these are used to scope the SpiceDB `lookup_resources` call.
---
