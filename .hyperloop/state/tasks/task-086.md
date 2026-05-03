---
id: task-086
title: Route MCP queries to tenant-scoped AGE graph
spec_ref: specs/query/query-execution.spec.md@dbcf0d7c2fa9c2456896ee20adbfdc8cc33090c2
status: in_progress
phase: implement
deps: []
round: 0
branch: hyperloop/task-086
pr: null
pr_title: 'feat(query): route MCP queries to per-tenant AGE graph'
pr_description: "## What & Why\n\n`query-execution.spec.md` was updated with a new\
  \ requirement:\n\n> **Requirement: Per-Tenant Graph Routing**\n> The system SHALL\
  \ route all queries to the caller's tenant-specific AGE graph.\n\nwith two scenarios:\n\
  \n**Scenario: Query routed to tenant graph**\n> GIVEN an authenticated query request\n\
  > WHEN the query is executed\n> THEN it executes against the AGE graph named `tenant_{tenant_id}`\
  \ for the resolved tenant\n> AND queries never cross tenant boundaries regardless\
  \ of query content\n\n**Scenario: Tenant graph not found**\n> GIVEN a tenant whose\
  \ AGE graph has not been provisioned\n> WHEN a query is submitted\n> THEN the request\
  \ is rejected with an execution error before reaching the database\n\nCurrently\
  \ `get_mcp_query_service()` in `src/api/query/dependencies.py` creates an\n`AgeGraphClient`\
  \ without a `graph_name` override, so all MCP queries execute against\nthe default\
  \ graph name from settings — a single shared graph for all tenants. This\nviolates\
  \ tenant isolation.\n\n`AgeGraphClient` already accepts a `graph_name` constructor\
  \ parameter (defaulting to\n`settings.graph_name`) and `auto_create=False` prevents\
  \ accidental graph provisioning.\n`get_mcp_auth_context()` already exposes `tenant_id`.\
  \ The wiring is simply missing.\n\n## What This PR Does\n\n### 1. Tenant-scoped\
  \ client in `query/dependencies.py`\n\nModify `mcp_graph_client_context()` to read\
  \ the MCP auth context and pass the\ntenant-specific graph name to `AgeGraphClient`:\n\
  \n```python\n@contextmanager\ndef mcp_graph_client_context() -> Generator[\"AgeGraphClient\"\
  , None, None]:\n    from graph.infrastructure.age_client import AgeGraphClient\n\
  \    from shared_kernel.middleware.mcp_auth import get_mcp_auth_context\n\n    auth_context\
  \ = get_mcp_auth_context()\n    graph_name = f\"tenant_{auth_context.tenant_id}\"\
  \n\n    pool = get_age_connection_pool()\n    settings = get_database_settings()\n\
  \    factory = ConnectionFactory(settings, pool=pool)\n    client = AgeGraphClient(settings,\
  \ connection_factory=factory, graph_name=graph_name)\n    client.connect()\n   \
  \ try:\n        yield client\n    finally:\n        client.disconnect()\n```\n\n\
  ### 2. Graph existence check in `QueryGraphRepository`\n\nAdd a `_verify_graph_exists(tx)`\
  \ helper that runs before any Cypher query:\n\n```python\ndef _verify_graph_exists(self,\
  \ tx) -> None:\n    \"\"\"Check that the tenant's AGE graph is provisioned.\n\n\
  \    Raises:\n        QueryExecutionError: If the graph does not exist in ag_catalog.ag_graph.\n\
  \    \"\"\"\n    result = tx.execute_sql(\n        \"SELECT 1 FROM ag_catalog.ag_graph\
  \ WHERE name = %s\",\n        (self._client.graph_name,),\n    )\n    if not result:\n\
  \        raise QueryExecutionError(\n            f\"Tenant graph '{self._client.graph_name}'\
  \ has not been provisioned.\",\n        )\n```\n\nCall `_verify_graph_exists(tx)`\
  \ as the first step inside the transaction block in\n`execute_cypher()`, before\
  \ the Cypher query is issued. This satisfies the spec's\n\"rejected with an execution\
  \ error **before reaching the database**\" intent — the check\nqueries the catalog\
  \ (metadata), not the tenant graph itself, so the Cypher query\nnever fires against\
  \ the missing graph.\n\nNote: If `tx.execute_sql` doesn't return rows natively,\
  \ use the raw psycopg2\ncursor pattern consistent with how `_ensure_graph_exists()`\
  \ works in `AgeGraphClient`.\nInspect the `GraphTransactionProtocol` to find the\
  \ right API surface; adapt as needed\nand keep the unit test mockable.\n\n### 3.\
  \ Unit tests\n\nAdd a new test class (or extend `TestExecuteCypher`) in\n`src/api/tests/unit/query/test_query_repository.py`:\n\
  \n- **`test_execute_cypher_uses_client_graph_name`** — create `QueryGraphRepository`\n\
  \  with a mock client whose `graph_name` is `\"tenant_abc123\"`; assert the graph\
  \ name\n  stored on the client is used, not a hardcoded default.\n- **`test_tenant_isolation_different_tenant_ids_produce_different_graph_names`**\
  \ —\n  two repositories built with clients named `\"tenant_aaa\"` and `\"tenant_bbb\"\
  ` must\n  have distinct `_client.graph_name` values.\n- **`test_raises_execution_error_when_tenant_graph_not_found`**\
  \ — mock the\n  graph-existence SQL check to return an empty result; assert `QueryExecutionError`\n\
  \  is raised before `execute_cypher` is called on the transaction.\n- **`test_execution_error_before_cypher_when_graph_missing`**\
  \ — same setup; confirm\n  that `mock_transaction.execute_cypher` is **never** called.\n\
  \nAlso add a test in `src/api/tests/unit/query/test_dependencies.py` (or a new\n\
  `test_mcp_graph_routing.py`):\n\n- **`test_mcp_graph_client_uses_tenant_graph_name`**\
  \ — mock `get_mcp_auth_context()`\n  to return a context with `tenant_id=\"t1\"\
  `, then assert that `AgeGraphClient` is\n  constructed with `graph_name=\"tenant_t1\"\
  `.\n\n## Files Affected\n\n- `src/api/query/dependencies.py` — read `auth_context.tenant_id`\
  \ in\n  `mcp_graph_client_context()` and pass `graph_name` to `AgeGraphClient`\n\
  - `src/api/query/infrastructure/query_repository.py` — add graph-existence check\n\
  \  inside `execute_cypher()` before query dispatch\n- `src/api/tests/unit/query/test_query_repository.py`\
  \ — new test cases for\n  tenant routing and missing-graph rejection\n- `src/api/tests/unit/query/test_dependencies.py`\
  \ — new test for graph name wiring\n\n## How to Verify\n\n1. Unit tests pass: `make\
  \ test-unit`\n2. With a running instance: authenticate as a tenant whose AGE graph\
  \ exists, execute\n   a `query_graph` call, confirm results come back. Then attempt\
  \ a call with a\n   fabricated tenant whose graph does not exist and confirm a `QueryExecutionError`\n\
  \   is returned (not a raw psycopg2 error).\n3. Confirm that two tenants cannot\
  \ read each other's data even if both graphs exist\n   (tenant isolation is structural\
  \ — each query is wired to its own graph name).\n\n## Design Decisions\n\n- **Where\
  \ to read the tenant ID** — `mcp_graph_client_context()` is the correct\n  call\
  \ site because it owns the `AgeGraphClient` lifecycle. Reading it there ensures\n\
  \  the graph name is fixed for the entire request; the repository never needs to\
  \ be\n  aware of the auth context.\n- **Graph existence check location** — inside\
  \ the transaction in\n  `QueryGraphRepository.execute_cypher()`. This keeps the\
  \ repository self-contained\n  and mockable, and runs the check in the same transaction\
  \ context as the query.\n- **No `auto_create` for query path** — the query path\
  \ must never provision graphs\n  (that is the responsibility of the provisioning/admin\
  \ path). `auto_create` stays\n  `False` (the default).\n- **Error type** — `QueryExecutionError`\
  \ is the correct type per the spec's\n  \"execution error\" language. It maps to\
  \ `\"execution_error\"` in the `MCPQueryService`\n  error categorization.\n\n##\
  \ Caveats\n\nThe `GraphTransactionProtocol` may not expose a raw SQL execution method\
  \ that\nreturns rows. If that is the case, either extend the protocol or execute\
  \ the\nexistence check using the client's raw connection before starting the transaction.\n\
  The key invariant is: the Cypher query must never be dispatched if the graph is\n\
  absent."
---
