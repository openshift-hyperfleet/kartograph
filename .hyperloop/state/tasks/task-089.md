---
id: task-089
title: Route MCP queries to per-tenant AGE graph
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: in_progress
phase: spec-review
deps: []
round: 0
branch: hyperloop/task-089
pr: https://github.com/openshift-hyperfleet/kartograph/pull/553
pr_title: 'feat(query): route MCP queries to tenant-specific AGE graph'
pr_description: "## What and Why\n\nThe query-execution spec (Requirement: Per-Tenant\
  \ Graph Routing) mandates that\nevery Cypher query executes against the AGE graph\
  \ named `tenant_{tenant_id}`\nfor the authenticated caller's tenant, never the default\
  \ graph.\n\nCurrently `get_mcp_query_service()` in `src/api/query/dependencies.py`\
  \ creates\nan `AgeGraphClient` without a tenant-specific `graph_name` argument,\
  \ meaning\nall MCP queries run against `settings.graph_name` (the default single-tenant\n\
  graph). This violates the per-tenant isolation requirement and will silently\nreturn\
  \ wrong data as soon as more than one tenant's data is present.\n\nThe `MCPAuthContext`\
  \ (set by the auth middleware for every MCP request) already\ncarries `tenant_id`,\
  \ so the routing information is available — it just isn't\nbeing used.\n\n## Spec\
  \ Requirements Satisfied\n\n- **Scenario: Query routed to tenant graph** — queries\
  \ execute against\n  `tenant_{tenant_id}` and never cross tenant boundaries.\n-\
  \ **Scenario: Tenant graph not found** — if the AGE graph for the tenant has\n \
  \ not been provisioned, the request is rejected with an execution error before\n\
  \  reaching the database.\n\n## Key Design Decisions\n\n### Tenant graph routing\n\
  `get_mcp_query_service()` (or its inner `mcp_graph_client_context()`) must:\n1.\
  \ Call `get_mcp_auth_context()` to obtain `tenant_id`.\n2. Construct `graph_name\
  \ = f\"tenant_{tenant_id}\"`.\n3. Pass `graph_name` to `AgeGraphClient.__init__`\
  \ (the constructor already\n   accepts this parameter for per-tenant isolation).\n\
  \n`mcp_graph_client_context` should be refactored to accept an optional\n`graph_name`\
  \ parameter so the test surface remains clean.\n\n### Tenant graph existence check\n\
  `AgeGraphClient.connect()` currently auto-creates the graph if it does not\nexist\
  \ — correct for provisioning contexts, wrong for the Query context. Two\noptions:\n\
  a) Add an `existence_only=True` mode to `AgeGraphClient` that raises\n   `QueryExecutionError`\
  \ instead of auto-creating.\nb) **Preferred**: Add a lightweight existence check\
  \ inside\n   `QueryGraphRepository.execute_cypher` (or a new `ensure_graph_exists`\n\
  \   helper) that queries `ag_catalog.ag_graph` before running the user query\n \
  \  and raises `QueryExecutionError(\"Tenant graph not provisioned\")` when the\n\
  \   graph is absent.\n\nOption (b) keeps the Graph infrastructure unchanged and\
  \ is simpler to test in\nisolation.\n\n### Error propagation\nThe `QueryExecutionError`\
  \ raised for \"graph not found\" surfaces to the caller\nas `error_type = \"execution_error\"\
  ` through the existing error categorisation in\n`MCPQueryService`, which is the\
  \ spec's expected behaviour.\n\n## Files / Areas Affected\n\n- `src/api/query/dependencies.py`\
  \ — `mcp_graph_client_context()` and\n  `get_mcp_query_service()`: read `MCPAuthContext.tenant_id`,\
  \ derive\n  `graph_name`, pass to `AgeGraphClient`\n- `src/api/query/infrastructure/query_repository.py`\
  \ — add a pre-execution\n  check that the `tenant_{tenant_id}` AGE graph exists;\
  \ raise\n  `QueryExecutionError` if not\n- `src/api/tests/unit/query/test_query_repository.py`\
  \ — add tests for\n  \"tenant graph not found\" scenario (mock `ag_catalog.ag_graph`\
  \ returning\n  no rows)\n- `src/api/tests/unit/query/test_mcp_auth_wiring.py` or\
  \ new\n  `test_mcp_tenant_routing.py` — unit tests verifying the correct graph name\n\
  \  is passed to `AgeGraphClient` based on `MCPAuthContext.tenant_id`\n- `src/api/tests/integration/test_query_mcp.py`\
  \ — ensure existing integration\n  tests still pass with the tenant-scoped graph\
  \ name (`tenant_{tenant_id}`)\n\n## How to Verify\n\n1. `make test-unit` — new unit\
  \ tests must pass.\n2. `make instance-up` — the instance manager provisions a tenant\
  \ graph during\n   setup; the `test-integration` suite should pass unchanged.\n\
  3. Manually create a second tenant (no AGE graph provisioned) and attempt an\n \
  \  MCP query with that tenant's API key — expect `error_type: \"execution_error\"\
  `\n   in the response.\n4. Confirm that queries from tenant A never return nodes/edges\
  \ belonging to\n   tenant B by checking the `knowledge_graph_id` properties in results.\n\
  \n## Caveats\n\n- The integration test suite uses a single test tenant whose graph\
  \ is\n  provisioned by the instance setup script. All existing tests should continue\n\
  \  to pass without modification; only the graph-name parameter changes.\n- If `MCPAuthContext`\
  \ is not set when `get_mcp_query_service()` is called\n  (e.g., in a test that bypasses\
  \ the auth middleware), the call to\n  `get_mcp_auth_context()` will raise `LookupError`.\
  \ Unit tests for the\n  dependency function must mock the context var.\n- The \"\
  tenant graph not found\" check adds one extra SQL query per MCP query\n  execution.\
  \ This is acceptable for correctness; it can be cached per-request\n  if profiling\
  \ shows it is a bottleneck."
---
