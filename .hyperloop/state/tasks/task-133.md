---
id: task-133
title: MCP secure enclave — integration test for entity redaction at HTTP transport
  layer
spec_ref: specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e
status: in_progress
phase: implement
deps: []
round: 1
branch: hyperloop/task-133
pr: https://github.com/openshift-hyperfleet/kartograph/pull/605
pr_title: 'test(query): add integration test for secure enclave entity redaction via
  MCP HTTP'
pr_description: "## What and Why\n\nThe MCP server spec's Secure Enclave Redaction\
  \ scenario is a security-critical\nrequirement: unauthorized callers must not receive\
  \ entity properties, only the\nstructural identifiers needed to preserve graph topology.\
  \ This requirement is\nthe \"secure enclave\" pattern that makes Kartograph's multi-tenant\
  \ graph safe\nfor cross-KG querying.\n\n### Existing coverage\n\nThe redaction logic\
  \ is well-tested at the unit level:\n\n- `test_mcp_secure_enclave.py` (TestNodeRedaction,\
  \ TestEdgeRedaction,\n  TestGraphTopologyPreservation, TestPermissionCaching, TestAuthorizationFailSafe)\n\
  \  — `MCPQuerySecureEnclave.apply_redaction()` is exhaustively unit-tested with\n\
  \  a fake `AuthorizationProvider`.\n- `test_mcp_query_tool_wiring.py` / `test_mcp_query_tool.py`\n\
  \  — verify that `query_graph` calls `secure_enclave.apply_redaction()` in the\n\
  \  correct order (after KG filter, before internal property filter).\n\n### The\
  \ gap\n\nThere is no **integration test** that exercises the full chain through\
  \ a live\nSpiceDB instance:\n\n1. Create a KnowledgeGraph in SpiceDB and grant VIEW\
  \ permission to User A\n   but **not** to User B.\n2. Insert nodes/edges stamped\
  \ with that KG's `knowledge_graph_id`.\n3. Authenticate as User B (no VIEW permission)\
  \ and call `query_graph` via the\n   MCP HTTP transport.\n4. Assert that node results\
  \ are `{\"id\": \"...\"}` only (properties stripped).\n5. Assert that edge results\
  \ are `{\"id\": \"...\", \"start_id\": \"...\", \"end_id\": \"...\"}` only.\n6.\
  \ Assert that the rows still appear (topology preserved — entities are not\n   removed,\
  \ just redacted).\n\nWithout this test, a regression in the SpiceDB permission check\
  \ (e.g., a\nschema change that silently grants VIEW to everyone, or a broken `check_permission`\n\
  call that defaults to `True`) would not be caught by any automated test.\n\n## Spec\
  \ Requirements Satisfied\n\n`specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:\n\
  \n- **Requirement: Graph Query Tool — Scenario: Secure enclave redaction**:\n  \"\
  GIVEN query results containing entities the caller is not authorized to view\n \
  \ WHEN the results are returned\n  THEN unauthorized nodes are redacted to ID-only\
  \ (all other properties stripped)\n  AND unauthorized edges are redacted to their\
  \ ID, start_id, and end_id only\n    (all other properties stripped)\n  AND the\
  \ graph topology (which entities exist and are connected) is preserved\"\n\n## What\
  \ This Change Does\n\nAdds a new integration test file (or a new class inside an\
  \ existing integration\ntest file) with the following test methods:\n\n### `TestSecureEnclaveRedactionIntegration`\n\
  \n**`test_unauthorized_nodes_redacted_to_id_only`**\n\n1. Provision a tenant AGE\
  \ graph and insert two `Person` nodes stamped with\n   `knowledge_graph_id = \"\
  kg-restricted\"`.\n2. Register `knowledge_graph:kg-restricted` in SpiceDB granting\
  \ `view` to\n   `user:alice` but **not** to `user:bob`.\n3. Authenticate as `user:bob`\
  \ (API key or Bearer token tied to bob's identity).\n4. Call `query_graph` with\
  \ `MATCH (n:Person) RETURN n LIMIT 10` via the\n   MCP HTTP transport.\n5. Assert\
  \ the response `success == True`.\n6. For each row in `rows`:\n   - The `node` dict\
  \ contains only the `\"id\"` key (no `\"label\"`, no `\"properties\"`).\n\n**`test_unauthorized_edges_redacted_to_structural_fields_only`**\n\
  \n1. Insert two nodes and a `KNOWS` edge stamped with `knowledge_graph_id = \"kg-restricted\"\
  `.\n2. Deny VIEW to bob for `kg-restricted`.\n3. Call `query_graph` with `MATCH\
  \ (a)-[r:KNOWS]->(b) RETURN r LIMIT 10`.\n4. For each row: `edge` dict contains\
  \ only `\"id\"`, `\"start_id\"`, `\"end_id\"`.\n\n**`test_graph_topology_preserved_for_unauthorized_caller`**\n\
  \n1. Insert 3 nodes in `kg-restricted`; deny VIEW to bob.\n2. Call `query_graph`\
  \ with `MATCH (n) RETURN n`.\n3. Assert `len(rows) == 3` — all three rows are present,\
  \ just redacted.\n\n**`test_authorized_caller_receives_full_properties`** (positive\
  \ control)\n\n1. Same graph state.\n2. Authenticate as `user:alice` (who has VIEW\
  \ on `kg-restricted`).\n3. Call `query_graph` and assert nodes include `label` and\
  \ `properties`.\n\n## Files / Areas Affected\n\n- `src/api/tests/integration/test_secure_enclave_mcp.py`\
  \ — new test file\n  (or extend `test_query_mcp_http.py` with a new class)\n- Fixture\
  \ helpers in `src/api/tests/integration/conftest.py` may need\n  extension to support\
  \ per-test SpiceDB relationship setup/teardown.\n\n## How to Verify\n\n```bash\n\
  make instance-up\nsource .instances/$(basename $(pwd))/.env.instance\ncd src/api\
  \ && uv run pytest tests/integration/test_secure_enclave_mcp.py \\\n    -v -m integration\n\
  ```\n\nAll four test methods must pass.\n\n## Implementation Notes for the Agent\n\
  \n- The integration test instance includes a real SpiceDB (see `make instance-up`\n\
  \  output). Use the `IAuthorizationProvider` (via `get_authz_client()` or the\n\
  \  test conftest helpers) to write SpiceDB relationships at test setup time.\n-\
  \ Use `teardown` (or pytest fixture with `yield`) to delete the test\n  relationships\
  \ after each test to avoid cross-test pollution.\n- For authentication, use the\
  \ fake OIDC provider's pre-configured test users\n  (`alice` / `password` and `bob`\
  \ / `password`) or create API keys tied to\n  specific user IDs. Check `tests/fakes/oidc_provider.py`\
  \ for how the fake\n  OIDC issues JWTs with `sub` claims.\n- The `MCPApiKeyAuthMiddleware`\
  \ resolves user identity from the API key's\n  `created_by_user_id`. Create separate\
  \ API keys for alice and bob to simplify\n  the setup.\n- Insert AGE nodes using\
  \ `GraphMutationService` or directly via the AGE\n  client (`tx.execute_cypher`).\
  \ Each node must have `knowledge_graph_id`\n  stamped in its properties (this is\
  \ what `MCPQuerySecureEnclave` uses to\n  look up permissions).\n- Write tests FIRST\
  \ (TDD). The production code should need no changes — the\n  secure enclave is already\
  \ implemented.\n\n## Caveats\n\n- Requires a running SpiceDB instance (`make instance-up`).\
  \ These tests are\n  `@pytest.mark.integration` and will not run in the pre-push\
  \ unit test suite.\n- SpiceDB schema must include the `knowledge_graph` resource\
  \ type with a\n  `view` permission. Confirm this is already in the deployed schema\
  \ before\n  writing the tests.\n- If the fake OIDC provider's JWT `sub` claim format\
  \ differs from what\n  SpiceDB expects for the `user:` subject prefix, adapt the\
  \ subject format\n  in the `write_relationship` call accordingly."
---
