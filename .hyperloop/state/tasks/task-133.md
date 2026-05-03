---
id: task-133
title: "MCP secure enclave — integration test for entity redaction at HTTP transport layer"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add integration test for secure enclave entity redaction via MCP HTTP"
pr_description: |
  ## What and Why

  The MCP server spec's Secure Enclave Redaction scenario is a security-critical
  requirement: unauthorized callers must not receive entity properties, only the
  structural identifiers needed to preserve graph topology. This requirement is
  the "secure enclave" pattern that makes Kartograph's multi-tenant graph safe
  for cross-KG querying.

  ### Existing coverage

  The redaction logic is well-tested at the unit level:

  - `test_mcp_secure_enclave.py` (TestNodeRedaction, TestEdgeRedaction,
    TestGraphTopologyPreservation, TestPermissionCaching, TestAuthorizationFailSafe)
    — `MCPQuerySecureEnclave.apply_redaction()` is exhaustively unit-tested with
    a fake `AuthorizationProvider`.
  - `test_mcp_query_tool_wiring.py` / `test_mcp_query_tool.py`
    — verify that `query_graph` calls `secure_enclave.apply_redaction()` in the
    correct order (after KG filter, before internal property filter).

  ### The gap

  There is no **integration test** that exercises the full chain through a live
  SpiceDB instance:

  1. Create a KnowledgeGraph in SpiceDB and grant VIEW permission to User A
     but **not** to User B.
  2. Insert nodes/edges stamped with that KG's `knowledge_graph_id`.
  3. Authenticate as User B (no VIEW permission) and call `query_graph` via the
     MCP HTTP transport.
  4. Assert that node results are `{"id": "..."}` only (properties stripped).
  5. Assert that edge results are `{"id": "...", "start_id": "...", "end_id": "..."}` only.
  6. Assert that the rows still appear (topology preserved — entities are not
     removed, just redacted).

  Without this test, a regression in the SpiceDB permission check (e.g., a
  schema change that silently grants VIEW to everyone, or a broken `check_permission`
  call that defaults to `True`) would not be caught by any automated test.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:

  - **Requirement: Graph Query Tool — Scenario: Secure enclave redaction**:
    "GIVEN query results containing entities the caller is not authorized to view
    WHEN the results are returned
    THEN unauthorized nodes are redacted to ID-only (all other properties stripped)
    AND unauthorized edges are redacted to their ID, start_id, and end_id only
      (all other properties stripped)
    AND the graph topology (which entities exist and are connected) is preserved"

  ## What This Change Does

  Adds a new integration test file (or a new class inside an existing integration
  test file) with the following test methods:

  ### `TestSecureEnclaveRedactionIntegration`

  **`test_unauthorized_nodes_redacted_to_id_only`**

  1. Provision a tenant AGE graph and insert two `Person` nodes stamped with
     `knowledge_graph_id = "kg-restricted"`.
  2. Register `knowledge_graph:kg-restricted` in SpiceDB granting `view` to
     `user:alice` but **not** to `user:bob`.
  3. Authenticate as `user:bob` (API key or Bearer token tied to bob's identity).
  4. Call `query_graph` with `MATCH (n:Person) RETURN n LIMIT 10` via the
     MCP HTTP transport.
  5. Assert the response `success == True`.
  6. For each row in `rows`:
     - The `node` dict contains only the `"id"` key (no `"label"`, no `"properties"`).

  **`test_unauthorized_edges_redacted_to_structural_fields_only`**

  1. Insert two nodes and a `KNOWS` edge stamped with `knowledge_graph_id = "kg-restricted"`.
  2. Deny VIEW to bob for `kg-restricted`.
  3. Call `query_graph` with `MATCH (a)-[r:KNOWS]->(b) RETURN r LIMIT 10`.
  4. For each row: `edge` dict contains only `"id"`, `"start_id"`, `"end_id"`.

  **`test_graph_topology_preserved_for_unauthorized_caller`**

  1. Insert 3 nodes in `kg-restricted`; deny VIEW to bob.
  2. Call `query_graph` with `MATCH (n) RETURN n`.
  3. Assert `len(rows) == 3` — all three rows are present, just redacted.

  **`test_authorized_caller_receives_full_properties`** (positive control)

  1. Same graph state.
  2. Authenticate as `user:alice` (who has VIEW on `kg-restricted`).
  3. Call `query_graph` and assert nodes include `label` and `properties`.

  ## Files / Areas Affected

  - `src/api/tests/integration/test_secure_enclave_mcp.py` — new test file
    (or extend `test_query_mcp_http.py` with a new class)
  - Fixture helpers in `src/api/tests/integration/conftest.py` may need
    extension to support per-test SpiceDB relationship setup/teardown.

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/test_secure_enclave_mcp.py \
      -v -m integration
  ```

  All four test methods must pass.

  ## Implementation Notes for the Agent

  - The integration test instance includes a real SpiceDB (see `make instance-up`
    output). Use the `IAuthorizationProvider` (via `get_authz_client()` or the
    test conftest helpers) to write SpiceDB relationships at test setup time.
  - Use `teardown` (or pytest fixture with `yield`) to delete the test
    relationships after each test to avoid cross-test pollution.
  - For authentication, use the fake OIDC provider's pre-configured test users
    (`alice` / `password` and `bob` / `password`) or create API keys tied to
    specific user IDs. Check `tests/fakes/oidc_provider.py` for how the fake
    OIDC issues JWTs with `sub` claims.
  - The `MCPApiKeyAuthMiddleware` resolves user identity from the API key's
    `created_by_user_id`. Create separate API keys for alice and bob to simplify
    the setup.
  - Insert AGE nodes using `GraphMutationService` or directly via the AGE
    client (`tx.execute_cypher`). Each node must have `knowledge_graph_id`
    stamped in its properties (this is what `MCPQuerySecureEnclave` uses to
    look up permissions).
  - Write tests FIRST (TDD). The production code should need no changes — the
    secure enclave is already implemented.

  ## Caveats

  - Requires a running SpiceDB instance (`make instance-up`). These tests are
    `@pytest.mark.integration` and will not run in the pre-push unit test suite.
  - SpiceDB schema must include the `knowledge_graph` resource type with a
    `view` permission. Confirm this is already in the deployed schema before
    writing the tests.
  - If the fake OIDC provider's JWT `sub` claim format differs from what
    SpiceDB expects for the `user:` subject prefix, adapt the subject format
    in the `write_relationship` call accordingly.
---
