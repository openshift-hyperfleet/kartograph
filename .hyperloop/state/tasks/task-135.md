---
id: task-135
title: "Knowledge Graphs Resource — HTTP MCP transport integration test"
spec_ref: "specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e"
status: not-started
phase: null
deps: []
round: 0
branch: null
pr: null
pr_title: "test(query): add HTTP MCP transport integration test for knowledge-graphs://accessible resource"
pr_description: |
  ## What and Why

  The Knowledge Graphs Resource requirement specifies:

  > The system SHALL expose the caller's accessible knowledge graphs as an MCP
  > resource.

  with two scenarios:

  > **Scenario: List accessible knowledge graphs**
  > - GIVEN an authenticated MCP client
  > - WHEN the client reads the `knowledge_graphs://accessible` resource
  > - THEN the response contains all knowledge graphs the caller has `view`
  >   permission on within their tenant
  > - AND each entry includes the knowledge graph `id`, `name`, and `description`
  > - AND knowledge graphs the caller cannot access are omitted entirely

  > **Scenario: No accessible knowledge graphs**
  > - GIVEN an authenticated MCP client with no accessible knowledge graphs
  > - WHEN the client reads the `knowledge_graphs://accessible` resource
  > - THEN an empty list is returned

  ### Current coverage

  The resource is tested at two layers:

  - **Unit tests** (`test_mcp_knowledge_graphs_resource.py`): `MCPKnowledgeGraphsService`
    is tested directly with fake providers. Covers both scenarios in isolation.
  - **Service-level integration tests** (`tests/integration/query/test_kg_resource.py`,
    task-110): Tests `MCPKnowledgeGraphsService` against real SpiceDB and PostgreSQL.
    Covers list-with-permissions and empty-list scenarios through the service object.

  ### The gap

  There is no **HTTP-transport-level integration test** that exercises the full
  MCP JSON-over-HTTP protocol path:

  1. An authenticated caller sends an MCP `resources/read` request to
     `knowledge-graphs://accessible` via the HTTP transport.
  2. The response is a properly serialised MCP resource with the correct JSON
     content.

  A regression in:
  - The FastMCP resource registration (e.g., the URI changes, content-type breaks)
  - The response serialisation (e.g., the list is wrapped incorrectly)
  - The middleware wiring (e.g., auth context not propagated to the resource handler)

  would be invisible to the existing unit and service-level tests.

  This mirrors the existing pattern: `test_query_mcp.py` tests the service
  directly; `test_query_mcp_http.py` tests the HTTP transport layer.

  ## Spec Requirements Satisfied

  `specs/query/mcp-server.spec.md@2ac8d03afbf2153e3b569f1289e10b5ad5d21d6e`:

  - **Requirement: Knowledge Graphs Resource — Scenario: List accessible knowledge
    graphs**: "each entry includes the knowledge graph `id`, `name`, and
    `description`"
  - **Requirement: Knowledge Graphs Resource — Scenario: No accessible knowledge
    graphs**: "an empty list is returned"
  - **Requirement: MCP Authentication — Scenario: API key authentication**: The
    resource is protected by API key auth (same middleware as `query_graph`).

  ## What This Change Does

  Creates a new integration test file
  `src/api/tests/integration/query/test_kg_resource_http.py` containing:

  ### `TestKnowledgeGraphsResourceHTTP`

  **`test_authenticated_caller_can_read_resource`**

  1. Start the application with `LifespanManager`.
  2. Create an API key via the IAM API (JWT auth).
  3. Using a `fastmcp.Client` over `StreamableHttpTransport` (same pattern as
     `test_query_mcp_http.py`), read the `knowledge-graphs://accessible` resource
     with the API key in the `X-API-Key` header.
  4. Assert the response is a list (possibly empty — the default tenant has no KGs
     unless we create them).
  5. Assert `response.status_code` is not 401/403.

  **`test_resource_returns_empty_list_when_no_accessible_kgs`**

  1. Same setup as above.
  2. The default tenant's default user has no KGs with `view` permission.
  3. Read `knowledge-graphs://accessible`.
  4. Assert the result is an empty list `[]`.

  **`test_resource_returns_kg_after_creation_and_permission_grant`**

  1. Create a knowledge graph via the Management API (POST
     `/management/workspaces/{ws_id}/knowledge-graphs`).
  2. Write a SpiceDB `view` relationship: `knowledge_graph:{kg_id}#view@user:{user_id}`.
  3. Read `knowledge-graphs://accessible`.
  4. Assert the returned list contains exactly one entry.
  5. Assert the entry has `id`, `name`, and `description` keys.
  6. Assert `id` matches the created KG's ULID and `name` matches the given name.

  **`test_resource_omits_kgs_without_view_permission`**

  1. Create two knowledge graphs: KG-A (grant `view`) and KG-B (no `view`).
  2. Read `knowledge-graphs://accessible`.
  3. Assert only KG-A appears in the list; KG-B is absent.

  ## Files / Areas Affected

  - `src/api/tests/integration/query/test_kg_resource_http.py` — new test file

  ## How to Verify

  ```bash
  make instance-up
  source .instances/$(basename $(pwd))/.env.instance
  cd src/api && uv run pytest tests/integration/query/test_kg_resource_http.py \
      -v -m integration
  ```

  All four tests must pass. Regression check: comment out the `get_accessible_knowledge_graphs`
  resource registration in `mcp.py` and confirm all four tests fail.

  ## Implementation Notes for the Agent

  - Use the same ASGI-transport `httpx_client_factory` pattern from
    `test_query_mcp_http.py` so no network is required.
  - The FastMCP `Client` resource read API: `await client.read_resource("knowledge-graphs://accessible")`.
    The returned content is a list of `TextContent` items; parse the first item's
    `text` field as JSON to get the KG list.
  - For SpiceDB relationship writes in the permission-grant tests, use the
    `get_spicedb_client()` dependency or adapt the relationship-write helper used
    in `tests/integration/query/test_kg_resource.py`.
  - Use `yield`-based pytest fixtures to delete created KGs and SpiceDB
    relationships after each test to prevent cross-test pollution.
  - Use the pre-configured fake OIDC test users (`alice` / `password`) or
    the `default_tenant_id` / `tenant_auth_headers` fixtures from conftest.
  - Write tests FIRST (TDD). No production code changes are expected.

  ## Caveats

  - `knowledge-graphs://accessible` uses a hyphen, not an underscore, because
    RFC 3986 does not allow underscores in URI schemes. The MCP client must use
    the hyphenated URI exactly.
  - The resource is marked `idempotentHint: False` because it reflects real-time
    SpiceDB permissions — avoid caching in test assertions.
  - The workspace fixture must exist before creating KGs; derive it from
    `tenant_auth_headers` or use the workspace API.
---
