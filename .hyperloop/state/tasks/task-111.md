---
id: task-111
title: "Secure Enclave Redaction — integration tests against real SpiceDB"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration tests for secure enclave redaction via real SpiceDB"
pr_description: |
  ## What & Why

  The **Graph Query Tool** requirement in `specs/query/mcp-server.spec.md` defines
  secure enclave redaction scenarios:

  > "GIVEN nodes in the result that the caller does not have `view` permission on
  > WHEN the query result is filtered THEN those nodes are returned with only their
  > `id` field AND all other properties are omitted AND the graph topology is
  > preserved"

  > "GIVEN edges in the result that the caller does not have `view` permission on
  > WHEN the query result is filtered THEN those edges are returned with only their
  > `id`, `start_id`, and `end_id` fields AND all other properties are omitted"

  The implementation is complete: `MCPQuerySecureEnclave` in
  `query/application/mcp_secure_enclave.py` calls SpiceDB `check_permission` for
  each node/edge and redacts unauthorized entities to ID-only stubs. Unit tests in
  `tests/unit/query/test_mcp_secure_enclave.py` confirm the redaction logic with a
  `FakeAuthorizationProvider`.

  What is missing is end-to-end integration coverage. The existing
  `tests/integration/test_query_mcp.py` exercises query execution against real
  PostgreSQL+AGE but uses no SpiceDB permission checks — the integration test stack
  does not exercise the secure enclave at all. A regression in the SpiceDB
  `check_permission` call wiring, the fail-safe redact-on-error path, or the
  property-stripping logic would be invisible until production.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md`:
  - **Requirement: Graph Query Tool** — Scenario: *Unauthorized nodes redacted*
  - **Requirement: Graph Query Tool** — Scenario: *Unauthorized edges redacted*
  - **Requirement: Graph Query Tool** — Scenario: *Fail-safe: SpiceDB error causes redaction*

  ## What This Change Does

  Add integration tests that exercise `query_graph` through the full stack — real
  PostgreSQL+AGE + real SpiceDB — so that the `MCPQuerySecureEnclave` permission
  checks are executed against real infrastructure.

  ### Test: `test_unauthorized_nodes_are_redacted_to_id_only`

  Setup:
  1. Create two nodes in the test AGE graph for the test tenant:
     - `Node-A` in `knowledge_graph_id = "kg-authorized"` (has properties: `name`, `type`)
     - `Node-B` in `knowledge_graph_id = "kg-unauthorized"` (has properties: `name`, `type`)
  2. Grant SpiceDB `view` permission on `kg-authorized` for the test subject.
  3. Do NOT grant `view` on `kg-unauthorized`.
  4. Obtain an API key for the test subject.

  Execution:
  - Call `query_graph` with a Cypher that returns both nodes.

  Assertions:
  - `Node-A`'s full properties (`name`, `type`) appear in the result.
  - `Node-B` appears with only `{"id": <node_id>}` — all other properties stripped.
  - The total node count in the result is 2 (topology preserved, redaction is not
    removal).

  ### Test: `test_unauthorized_edges_are_redacted_to_id_start_end_only`

  Setup:
  1. Create two nodes and one edge between them in the test AGE graph:
     - Both nodes belong to `knowledge_graph_id = "kg-authorized"` (caller has `view`).
     - The edge belongs to `knowledge_graph_id = "kg-edge-unauthorized"` (no `view`).
     - Edge has properties: `weight`, `label`.
  2. Grant SpiceDB `view` on `kg-authorized`; do NOT grant `view` on
     `kg-edge-unauthorized`.
  3. Obtain an API key for the test subject.

  Execution:
  - Call `query_graph` with a Cypher returning the edge.

  Assertions:
  - Edge appears with only `{"id": ..., "start_id": ..., "end_id": ...}`.
  - Properties `weight` and `label` are absent from the edge result.

  ### Test: `test_spicedb_error_causes_fail_safe_redaction`

  Setup:
  1. Create a node with `knowledge_graph_id = "kg-any"` in the test AGE graph.
  2. Configure the integration stack so that the SpiceDB `check_permission` call for
     this test returns a service error (e.g., by temporarily providing an invalid
     SpiceDB address or using a fixture that injects a broken authorization client
     for this test only).
  3. Obtain an API key for the test subject.

  Execution:
  - Call `query_graph` with a Cypher returning the node.

  Assertions:
  - Response is successful (not a 5xx error — fail-safe means redact, not crash).
  - The node is redacted to `{"id": ...}` only (fail-safe: deny on error).
  - No raw SpiceDB error details are exposed in the MCP response.

  ## Files / Areas Affected

  - `src/api/tests/integration/query/test_secure_enclave.py` (new) — the three
    integration test cases described above, OR extend `test_query_mcp.py`
  - `src/api/tests/integration/conftest.py` or a shared fixtures module — fixtures
    for writing SpiceDB relationships, seeding AGE graph nodes with `knowledge_graph_id`
    properties, and obtaining scoped API keys
  - No production code changes expected; if a test reveals a real bug, fix it and
    note it in the PR description

  ## Tests

  The integration tests ARE the deliverable. Mark them with `@pytest.mark.integration`
  and ensure they run with `make test-integration` against the isolated dev instance.

  Infrastructure requirements (provided by `make instance-up`):
  - PostgreSQL with Apache AGE extension (for graph nodes/edges)
  - SpiceDB (for `check_permission` calls exercised by `MCPQuerySecureEnclave`)
  - Kartograph API (for MCP HTTP endpoint)

  ## How to Verify

  1. `make instance-up` — start isolated test instance
  2. `source .instances/$(basename $(pwd))/.env.instance`
  3. `cd src/api && uv run pytest tests/integration/ -v -m integration -k "secure_enclave"`
  4. Confirm all three tests pass green

  ## Caveats

  - Nodes must have a `knowledge_graph_id` property set to a valid ULID/string so
    the secure enclave can determine which KG they belong to; verify the property
    key name against the actual implementation in `mcp_secure_enclave.py`.
  - SpiceDB relationship writes in fixtures must be torn down after each test to
    avoid cross-test pollution.
  - The fail-safe test (test 3) is hardest to write cleanly; an alternative approach
    is to inject a failing `IAuthorizationProvider` into the DI graph for that test
    only, rather than corrupting the real SpiceDB connection, if the integration test
    harness supports override fixtures.
  - `MCPQuerySecureEnclave` caches permissions per `knowledge_graph_id` within a
    single `apply_redaction()` call; ensure test nodes use distinct `knowledge_graph_id`
    values to avoid cache aliasing between authorized and unauthorized entities.
---
